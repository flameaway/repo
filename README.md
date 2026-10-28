# Flame's Repo

A Sileo / Zebra / Cydia repo for my jailbreak tweaks, hosted for free on GitHub Pages.

**Repo URL:** `https://flameaway.github.io/repo/`

Open **[flameaway.github.io/repo](https://flameaway.github.io/repo/)** on your jailbroken device and tap **Add to Sileo** or **Add to Zebra**, or add the URL above under Sources in your package manager.

| Package | Description |
| --- | --- |
| [Peel](https://github.com/flameaway/peel) (`com.josh.stickers`) | iOS 17-style stickers on iOS 16 |

## Publishing an update

1. Copy the new `.deb` into `debs/` (keep older versions if you want people to be able to downgrade, or delete them).
2. Optionally add a changelog entry to `meta/<package>/info.json`.
3. Commit and push:

   ```sh
   cp ../stickers/packages/com.josh.stickers_1.7.0_iphoneos-arm64.deb debs/
   git add debs meta && git commit -m "Peel 1.7.0" && git push
   ```

GitHub Actions (`.github/workflows/pages.yml`) rebuilds the indexes and deploys the site. Sileo and Zebra pick up the new version the next time they refresh sources.

## Layout

| Path | What it is |
| --- | --- |
| `debs/` | The packages. Every `.deb` here is published. |
| `meta/<package>/` | Optional per-package extras: `info.json` (display name, tagline, long description, compatibility, source link, screenshots, changelog) plus `icon.png`, `header.png` and screenshot images. |
| `repo.json` | Repo name, description, public URL and tint color. |
| `site/` | The website: landing page with the add buttons, and the web depiction page. |
| `scripts/build.py` | Builds everything into `_site/`. |

The build runs `dpkg-scanpackages`, adds `Depiction`, `SileoDepiction` and `Icon` fields to each package, writes `Packages` (plain, `.gz`, `.bz2`, `.xz`, `.zst`) and `Release`, generates a Sileo native depiction per package in `depictions/`, and writes `packages.json` for the website.

### `meta/<package>/info.json`

```json
{
  "name": "Peel",
  "tagline": "iOS 17-style stickers on iOS 16",
  "description": "Markdown shown in the depiction.",
  "compatibility": "iOS 15 – 16 (rootless)",
  "source": "https://github.com/flameaway/peel",
  "screenshots": [{"file": "screenshot-1.png", "alt": "..."}],
  "changelog": {"1.7.0": "- What changed"}
}
```

## Building locally

Needs Python 3 and `dpkg-scanpackages` (`brew install dpkg` on macOS).

```sh
python3 scripts/build.py
python3 -m http.server -d _site 8000
```
