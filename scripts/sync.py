#!/usr/bin/env python3
"""Pull packages and store listings from the tweak repos in repo.json's "sources".

For each source (a GitHub repo such as "flameaway/peel") this downloads the .deb
attached to its published releases into _sources/debs/, and builds
_sources/meta/<package>/ from the repo's listing/ folder at its latest release:
listing/info.json, listing/icon.png, and the header and screenshot files
info.json points to (paths in that repo).
Only packages in the latest release are published; older releases add older
versions of those, so a renamed package's old ID drops out.

Each .deb's release download URL goes in _sources/urls.json, so build.py points
the Packages file straight at GitHub and the releases' download counts track
installs. The .debs themselves are kept in .asset-cache/ by asset ID (the
workflow caches it between runs), so the hourly sync doesn't add downloads.

build.py then publishes these alongside anything in debs/ and meta/.

Set GITHUB_TOKEN to avoid the API's rate limit for anonymous requests.

Usage: python3 scripts/sync.py
"""
import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "_sources"
CACHE = ROOT / ".asset-cache"


def fetch(url, accept=None):
    headers = {"User-Agent": "flame-repo-sync"}
    if accept:
        headers["Accept"] = accept
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith("https://api.github.com/"):
        headers["Authorization"] = f"Bearer {token}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as response:
        return response.read()


def fetch_optional(url):
    try:
        return fetch(url)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise


def deb_field(path, field):
    return subprocess.run(["dpkg-deb", "-f", str(path), field], check=True, capture_output=True, text=True).stdout.strip()


def release_asset(item):
    """The asset's bytes, downloaded only the first time this asset ID is seen."""
    cached = CACHE / f"{item['id']}.deb"
    if not cached.exists():
        cached.write_bytes(fetch(item["browser_download_url"]))
    return cached


def sync_source(source, urls, used):
    releases = json.loads(fetch(f"https://api.github.com/repos/{source}/releases?per_page=100"))
    releases = [r for r in releases if not r["draft"] and not r["prerelease"]]
    if not releases:
        print(f"{source}: no releases")
        return

    latest_package = None
    current = None  # the packages in the latest release with any
    for release in releases:  # newest first
        found = set()
        for item in release["assets"]:
            if not item["name"].endswith(".deb"):
                continue
            path = OUT / "debs" / item["name"]
            cached = release_asset(item)
            used.add(cached)
            shutil.copyfile(cached, path)
            package = deb_field(path, "Package")
            if current is not None and package not in current:
                path.unlink()
                print(f"{source}: skipping {item['name']}, not in the latest release")
                continue
            found.add(package)
            urls[item["name"]] = item["browser_download_url"]
            latest_package = latest_package or package
            print(f"{source}: {item['name']}")
        if found and current is None:
            current = found

    if not latest_package:
        print(f"{source}: no .deb in any release")
        return

    tag = releases[0]["tag_name"]
    raw = f"https://raw.githubusercontent.com/{source}/{tag}/"
    info_bytes = fetch_optional(raw + "listing/info.json")
    meta = OUT / "meta" / latest_package
    meta.mkdir(parents=True, exist_ok=True)
    info = json.loads(info_bytes) if info_bytes else {}
    info.setdefault("source", f"https://github.com/{source}")

    icon = fetch_optional(raw + "listing/icon.png")
    if icon:
        (meta / "icon.png").write_bytes(icon)
    header = info.pop("header", None)
    if header:
        (meta / "header.png").write_bytes(fetch(raw + header))
    screenshots = []
    for i, shot in enumerate(info.get("screenshots", []), 1):
        name = f"screenshot-{i}{Path(shot['file']).suffix}"
        (meta / name).write_bytes(fetch(raw + shot["file"]))
        screenshots.append({**shot, "file": name})
    info["screenshots"] = screenshots
    (meta / "info.json").write_text(json.dumps(info, indent=2, ensure_ascii=False))
    print(f"{source}: listing for {latest_package} from {tag}")


def main():
    repo = json.loads((ROOT / "repo.json").read_text())
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "debs").mkdir(parents=True)
    (OUT / "meta").mkdir()
    CACHE.mkdir(exist_ok=True)
    urls, used = {}, set()
    for source in repo.get("sources", []):
        sync_source(source, urls, used)
    (OUT / "urls.json").write_text(json.dumps(urls, indent=2))
    for stale in set(CACHE.glob("*.deb")) - used:
        stale.unlink()


if __name__ == "__main__":
    main()
