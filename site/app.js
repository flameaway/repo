"use strict";

const SCHEMES = {
  sileo: (url) => `sileo://source/${url}`,
  zebra: (url) => `zbra://sources/add/${url}`,
  cydia: (url) => `cydia://url/https://cydia.saurik.com/api/share#?source=${url}`,
  installer: (url) => `installer://add/repo=${url}`,
};

function loadRepo() {
  return fetch("packages.json", { cache: "no-cache" }).then((r) => {
    if (!r.ok) throw new Error(`packages.json: HTTP ${r.status}`);
    return r.json();
  });
}

function escapeHTML(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// Enough Markdown for depictions: paragraphs, "- " lists, **bold**, *italic*, `code`, [links](url).
function markdown(src) {
  const inline = (s) =>
    escapeHTML(s)
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/\*([^*]+)\*/g, "<em>$1</em>")
      .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2">$1</a>');
  return src
    .trim()
    .split(/\n{2,}/)
    .map((block) => {
      const lines = block.split("\n");
      if (lines.every((l) => /^\s*[-*] /.test(l))) {
        return "<ul>" + lines.map((l) => `<li>${inline(l.replace(/^\s*[-*] /, ""))}</li>`).join("") + "</ul>";
      }
      return `<p>${inline(lines.join(" "))}</p>`;
    })
    .join("");
}

function formatSize(bytes) {
  return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.round(bytes / 1024)} KB`;
}

function iconHTML(pkg, cls) {
  return pkg.icon
    ? `<img class="${cls}" src="${escapeHTML(pkg.icon)}" alt="" loading="lazy">`
    : `<div class="${cls} icon-fallback">${escapeHTML(pkg.name.charAt(0))}</div>`;
}

function renderIndex() {
  loadRepo()
    .then(({ repo, packages }) => {
      const url = repo.url;
      document.title = repo.name;
      document.getElementById("repo-name").textContent = repo.name;
      document.getElementById("repo-description").textContent = repo.description;
      document.getElementById("repo-url").textContent = url;
      if (repo.github) document.getElementById("github").href = repo.github;
      document.querySelectorAll("[data-scheme]").forEach((a) => (a.href = SCHEMES[a.dataset.scheme](url)));

      const copy = document.getElementById("copy");
      copy.addEventListener("click", () => {
        navigator.clipboard.writeText(url).then(() => {
          copy.textContent = "Copied";
          setTimeout(() => (copy.textContent = "Copy"), 1500);
        });
      });

      document.getElementById("packages").innerHTML = packages.length
        ? packages
            .map(
              (p) => `
          <li>
            <a class="package" href="depiction.html?p=${encodeURIComponent(p.package)}">
              ${iconHTML(p, "pkg-icon")}
              <div class="pkg-text">
                <div class="pkg-name">${escapeHTML(p.name)}</div>
                <div class="pkg-tagline muted">${escapeHTML(p.tagline || p.description.split("\n")[0])}</div>
              </div>
              <span class="pkg-version">${escapeHTML(p.version)}</span>
            </a>
          </li>`
            )
            .join("")
        : '<li class="muted">No packages yet.</li>';
    })
    .catch((e) => {
      document.getElementById("packages").innerHTML = `<li class="muted">Couldn't load packages (${escapeHTML(e.message)}).</li>`;
    });
}

function renderDepiction(id) {
  const el = document.getElementById("depiction");
  loadRepo()
    .then(({ repo, packages }) => {
      const p = packages.find((x) => x.package === id);
      if (!p) {
        el.innerHTML = '<p class="muted">Package not found.</p>';
        return;
      }
      document.title = `${p.name} · ${repo.name}`;
      const rows = [
        ["Version", p.version],
        ["Compatibility", p.compatibility],
        ["Author", p.author],
        ["Section", p.section],
        ["Size", formatSize(p.size)],
        ["Package", p.package],
      ].filter(([, v]) => v);

      el.innerHTML = `
        ${p.header ? `<img class="header-image" src="${escapeHTML(p.header)}" alt="">` : ""}
        <div class="dep-title">
          ${iconHTML(p, "dep-icon")}
          <div>
            <h1>${escapeHTML(p.name)}</h1>
            ${p.tagline ? `<p class="muted">${escapeHTML(p.tagline)}</p>` : ""}
          </div>
        </div>
        <div class="dep-actions">
          <a class="btn btn-primary" href="${SCHEMES.sileo(repo.url)}">Add repo to Sileo</a>
          <a class="btn btn-zebra" href="${SCHEMES.zebra(repo.url)}">Add repo to Zebra</a>
        </div>
        <div class="card prose">${markdown(p.description)}</div>
        ${
          p.screenshots.length
            ? `<div class="screenshots">${p.screenshots
                .map((s) => `<img src="${escapeHTML(s.url)}" alt="${escapeHTML(s.alt)}" loading="lazy">`)
                .join("")}</div>`
            : ""
        }
        <dl class="card info">${rows.map(([k, v]) => `<div><dt>${k}</dt><dd>${escapeHTML(v)}</dd></div>`).join("")}</dl>
        ${p.source ? `<p><a class="link-row card" href="${escapeHTML(p.source)}">Source code <span>›</span></a></p>` : ""}
        ${
          p.changelog.length
            ? `<h2>Changelog</h2><div class="card prose">${p.changelog
                .map((c) => `<h3>${escapeHTML(c.version)}</h3>${markdown(c.notes)}`)
                .join("")}</div>`
            : ""
        }`;
    })
    .catch((e) => {
      el.innerHTML = `<p class="muted">Couldn't load package (${escapeHTML(e.message)}).</p>`;
    });
}
