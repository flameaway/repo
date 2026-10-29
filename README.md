# Flame's Repo

A Sileo / Zebra / Cydia repo for my jailbreak tweaks, hosted for free on GitHub Pages.

**Repo URL:** `https://flameaway.github.io/repo/`

Open **[flameaway.github.io/repo](https://flameaway.github.io/repo/)** on your jailbroken device and tap **Add to Sileo** or **Add to Zebra**, or add the URL above under Sources in your package manager.

| Package | Description |
| --- | --- |
| [Peel](https://github.com/flameaway/peel) (`com.flame.stickers`) | iOS 17-style stickers on iOS 16 |

## Publishing an update

Tweaks listed under `sources` in `repo.json` publish themselves: create a GitHub release in the tweak's repo with the `.deb` attached (Peel's `make release` does this). Every hour, and on every push here, GitHub Actions (`.github/workflows/pages.yml`) runs `scripts/sync.py`, which downloads the `.deb` from each release, then rebuilds the indexes and deploys the site. Sileo and Zebra pick up the new version the next time they refresh sources.

Sileo and Zebra download these packages straight from the GitHub release (the `Filename` in `Packages` is the release download URL), so each release's download count is the number of installs. To see them:

```sh
gh api repos/flameaway/peel/releases --jq '.[] | "\(.tag_name): \(.assets[] | select(.name | endswith(".deb")) | .download_count)"'
```

The sync keeps the `.deb`s it has already fetched in `.asset-cache/` (cached between workflow runs), so it adds at most one download per release. This needs a package manager that accepts full URLs in `Filename`, which Sileo and Zebra do; plain `apt` on the command line doesn't.

To publish right away instead of waiting for the hourly run, start the workflow from the Actions tab, or send a `tweak-released` [repository dispatch](https://docs.github.com/en/rest/repos/repos#create-a-repository-dispatch-event) from the tweak's own release workflow (that needs an access token with access to this repo).

### Adding a tweak

1. Add its GitHub repo (`owner/name`) to `sources` in `repo.json`.
2. In the tweak's repo, add a `listing/` folder: `info.json` (see below) and a square `icon.png`.
3. Publish a release with the `.deb` attached.

The store listing is read from `listing/` at the tweak's latest release tag, so it always matches the published version.

### Packages not on GitHub

Drop the `.deb` into `debs/` and, optionally, its listing into `meta/<package>/` (`info.json` plus `icon.png`, `header.png` and screenshot images next to it), then commit and push.

## Layout

| Path | What it is |
| --- | --- |
| `debs/` | Packages added by hand. Every `.deb` here is published. |
| `meta/<package>/` | Listings for packages added by hand: `info.json` (display name, tagline, long description, compatibility, source link, screenshots, changelog) plus `icon.png`, `header.png` and screenshot images. |
| `repo.json` | Repo name, description, public URL, tint color, and `sources`: the GitHub repos of tweaks that publish through releases. |
| `site/` | The website: landing page with the add buttons, and the web depiction page. |
| `scripts/sync.py` | Downloads the `.deb` and listing of every tweak in `sources` into `_sources/`, and their release URLs into `_sources/urls.json`. |
| `scripts/build.py` | Builds everything into `_site/`. |

The build runs `dpkg-scanpackages`, adds `Depiction`, `SileoDepiction` and `Icon` fields to each package, writes `Packages` (plain, `.gz`, `.bz2`, `.xz`, `.zst`) and `Release`, generates a Sileo native depiction per package in `depictions/`, and writes `packages.json` for the website.

### `info.json`

```json
{
  "name": "Peel",
  "tagline": "iOS 17-style stickers on iOS 16",
  "description": "Markdown shown in the depiction.",
  "compatibility": "iOS 15 – 16 (rootless)",
  "source": "https://github.com/flameaway/peel",
  "header": "docs/images/hero.png",
  "screenshots": [{"file": "listing/screenshots/1-keyboard.jpg", "alt": "..."}],
  "changelog": {"1.0.0": "- What changed"}
}
```

In a tweak's `listing/info.json`, `header` and screenshot `file`s are paths in the tweak's repo, and `changelog` is optional (release notes aren't used, so there's no Changelog tab unless you write one). In `meta/<package>/info.json` they're file names next to it, the header is always `header.png`, and there's no `header` field.

Give each screen its own screenshot (a plain PNG or JPEG of the whole screen, not several phones in one image) so people can tap it to see it full screen in Sileo, Zebra and on the website. The depiction sizes the thumbnails from the first screenshot's shape.

## Building locally

Needs Python 3 and `dpkg-scanpackages` (`brew install dpkg` on macOS).

```sh
python3 scripts/sync.py   # optional: pull the tweaks' releases
python3 scripts/build.py
python3 -m http.server -d _site 8000
```
