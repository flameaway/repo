#!/usr/bin/env python3
"""Build the APT repo into _site/.

Scans debs/ (plus _sources/debs/ from sync.py) with dpkg-scanpackages, adds
depiction and icon fields, writes Packages (plain and compressed), Release,
Sileo native depictions and packages.json for the website, then copies the
site, debs and artwork. Listings come from meta/ and _sources/meta/.

Usage: python3 scripts/build.py [--url https://example.com/repo/]
"""
import argparse
import bz2
import functools
import gzip
import hashlib
import json
import lzma
import os
import re
import shutil
import subprocess
from email.utils import formatdate
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "_site"
# Packages added by hand, then the ones sync.py pulled from tweak releases.
DEB_DIRS = [ROOT / "debs", ROOT / "_sources" / "debs"]
META_DIRS = [ROOT / "meta", ROOT / "_sources" / "meta"]


def parse_stanzas(text):
    stanzas = []
    for block in text.strip().split("\n\n"):
        fields, key = {}, None
        for line in block.splitlines():
            if line[:1] in (" ", "\t") and key:
                fields[key] += "\n" + line
            elif ":" in line:
                key, value = line.split(":", 1)
                fields[key] = value.strip()
        if fields:
            stanzas.append(fields)
    return stanzas


def format_stanza(fields):
    return "".join(f"{k}: {v}\n" for k, v in fields.items())


# Debian version ordering (deb-version(7)), so the newest version is listed first.
def _order(c):
    if c == "~":
        return -1
    if c.isalpha():
        return ord(c)
    return ord(c) + 256 if c else 0


def _cmp_part(a, b):
    while a or b:
        na = re.match(r"[^\d]*", a).group()
        nb = re.match(r"[^\d]*", b).group()
        for i in range(max(len(na), len(nb))):
            ca = _order(na[i] if i < len(na) else "")
            cb = _order(nb[i] if i < len(nb) else "")
            if ca != cb:
                return ca - cb
        a, b = a[len(na):], b[len(nb):]
        da = re.match(r"\d*", a).group()
        db = re.match(r"\d*", b).group()
        if int(da or 0) != int(db or 0):
            return int(da or 0) - int(db or 0)
        a, b = a[len(da):], b[len(db):]
    return 0


def _split_version(v):
    epoch, _, rest = v.partition(":") if ":" in v else ("0", "", v)
    upstream, _, revision = rest.rpartition("-") if "-" in rest else (rest, "", "0")
    return int(epoch or 0), upstream, revision


def compare_versions(a, b):
    ea, ua, ra = _split_version(a)
    eb, ub, rb = _split_version(b)
    return (ea - eb) or _cmp_part(ua, ub) or _cmp_part(ra, rb)


version_key = functools.cmp_to_key(compare_versions)


def meta_file(package, name):
    return next((d / package / name for d in META_DIRS if (d / package / name).exists()), None)


def load_meta(package):
    path = meta_file(package, "info.json")
    return json.loads(path.read_text()) if path else {}


def asset(base, package, name):
    return f"{base}meta/{package}/{name}" if meta_file(package, name) else None


def sileo_depiction(base, repo, pkg, versions, meta):
    package = pkg["Package"]
    details = [{"class": "DepictionMarkdownView", "markdown": meta.get("description") or pkg.get("Description", ""), "useSpacing": True}]
    shots = [s for s in meta.get("screenshots", []) if asset(base, package, s["file"])]
    if shots:
        details.append({
            "class": "DepictionScreenshotsView",
            "itemCornerRadius": 10,
            "itemSize": "{300, 173}",
            "screenshots": [{"url": asset(base, package, s["file"]), "accessibilityText": s.get("alt", "")} for s in shots],
        })
    details.append({"class": "DepictionSeparatorView"})
    rows = [("Version", pkg["Version"])]
    if meta.get("compatibility"):
        rows.append(("Compatibility", meta["compatibility"]))
    rows += [("Author", re.sub(r"\s*<.*>", "", pkg.get("Author", pkg.get("Maintainer", "")))),
             ("Section", pkg.get("Section", "")),
             ("Size", f"{int(pkg['Size']) / 1024:.0f} KB")]
    details += [{"class": "DepictionTableTextView", "title": t, "text": v} for t, v in rows if v]
    if meta.get("source"):
        details.append({"class": "DepictionTableButtonView", "title": "Source code", "action": meta["source"], "openExternal": True})

    tabs = [{"tabname": "Details", "class": "DepictionStackView", "views": details}]
    changelog = meta.get("changelog") or {}
    if changelog:
        views = []
        for v in sorted(changelog, key=version_key, reverse=True):
            views += [{"class": "DepictionSubheaderView", "title": v, "useBoldText": True},
                      {"class": "DepictionMarkdownView", "markdown": changelog[v]}]
        tabs.append({"tabname": "Changelog", "class": "DepictionStackView", "views": views})

    dep = {"minVersion": "0.4", "class": "DepictionTabView", "tintColor": meta.get("tintColor", repo.get("tintColor", "#007AFF")), "tabs": tabs}
    if asset(base, package, "header.png"):
        dep["headerImage"] = asset(base, package, "header.png")
    return dep


def file_hashes(path):
    data = path.read_bytes()
    return len(data), hashlib.md5(data).hexdigest(), hashlib.sha256(data).hexdigest()


def main():
    repo = json.loads((ROOT / "repo.json").read_text())
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=repo["url"], help="public base URL of the repo")
    base = ap.parse_args().url.rstrip("/") + "/"

    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(ROOT / "site", OUT)
    (OUT / "debs").mkdir()
    for d in DEB_DIRS:
        for deb in sorted(d.glob("*.deb")) if d.exists() else []:
            shutil.copy2(deb, OUT / "debs")
    for d in META_DIRS:
        if d.exists():
            shutil.copytree(d, OUT / "meta", ignore=shutil.ignore_patterns("info.json"), dirs_exist_ok=True)
    (OUT / ".nojekyll").touch()
    (OUT / "depictions").mkdir()

    scanned = subprocess.run(["dpkg-scanpackages", "-m", "debs", "/dev/null"], cwd=OUT,
                             check=True, capture_output=True, text=True).stdout
    stanzas = parse_stanzas(scanned)
    stanzas.sort(key=lambda s: (s["Package"], version_key(s["Version"])))

    by_package = {}
    for s in stanzas:
        package = s["Package"]
        s["Depiction"] = f"{base}depiction.html?p={package}"
        s["SileoDepiction"] = f"{base}depictions/{package}.json"
        if asset(base, package, "icon.png"):
            s["Icon"] = asset(base, package, "icon.png")
        by_package.setdefault(package, []).append(s)

    packages_text = "\n".join(format_stanza(s) for s in stanzas)
    (OUT / "Packages").write_text(packages_text)
    raw = packages_text.encode()
    (OUT / "Packages.gz").write_bytes(gzip.compress(raw, 9, mtime=0))
    (OUT / "Packages.bz2").write_bytes(bz2.compress(raw, 9))
    (OUT / "Packages.xz").write_bytes(lzma.compress(raw))
    if shutil.which("zstd"):
        subprocess.run(["zstd", "-q", "-19", "-f", str(OUT / "Packages"), "-o", str(OUT / "Packages.zst")], check=True)

    index_files = [p for p in sorted(OUT.glob("Packages*"))]
    hashes = [(p.name, *file_hashes(p)) for p in index_files]
    release = {
        "Origin": repo["name"],
        "Label": repo["name"],
        "Suite": "stable",
        "Version": "1.0",
        "Codename": "ios",
        "Architectures": "iphoneos-arm iphoneos-arm64 iphoneos-arm64e",
        "Components": "main",
        "Description": repo["description"],
        "Date": formatdate(usegmt=True),
    }
    lines = format_stanza(release)
    lines += "MD5Sum:\n" + "".join(f" {md5} {size} {name}\n" for name, size, md5, _ in hashes)
    lines += "SHA256:\n" + "".join(f" {sha} {size} {name}\n" for name, size, _, sha in hashes)
    (OUT / "Release").write_text(lines)

    site_packages = []
    for package, versions in by_package.items():
        latest = versions[-1]
        meta = load_meta(package)
        dep = sileo_depiction(base, repo, latest, versions, meta)
        (OUT / "depictions" / f"{package}.json").write_text(json.dumps(dep, indent=2, ensure_ascii=False))
        site_packages.append({
            "package": package,
            "name": meta.get("name") or latest.get("Name", package),
            "tagline": meta.get("tagline", ""),
            "description": meta.get("description") or latest.get("Description", ""),
            "version": latest["Version"],
            "architecture": latest["Architecture"],
            "section": latest.get("Section", ""),
            "author": re.sub(r"\s*<.*>", "", latest.get("Author", latest.get("Maintainer", ""))),
            "depends": latest.get("Depends", ""),
            "size": int(latest["Size"]),
            "filename": latest["Filename"],
            "compatibility": meta.get("compatibility", ""),
            "source": meta.get("source", ""),
            "icon": f"meta/{package}/icon.png" if asset(base, package, "icon.png") else None,
            "header": f"meta/{package}/header.png" if asset(base, package, "header.png") else None,
            "screenshots": [{"url": f"meta/{package}/{s['file']}", "alt": s.get("alt", "")}
                            for s in meta.get("screenshots", []) if asset(base, package, s["file"])],
            "changelog": [{"version": v, "notes": meta["changelog"][v]}
                          for v in sorted(meta.get("changelog") or {}, key=version_key, reverse=True)],
            "versions": [s["Version"] for s in reversed(versions)],
        })
    site_packages.sort(key=lambda p: p["name"].lower())
    (OUT / "packages.json").write_text(json.dumps({"repo": {**repo, "url": base}, "packages": site_packages},
                                                  indent=2, ensure_ascii=False))

    print(f"Built {len(stanzas)} deb(s) in {len(by_package)} package(s) -> {os.path.relpath(OUT)}")


if __name__ == "__main__":
    main()
