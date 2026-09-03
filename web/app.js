const app = document.getElementById("app");
const searchInput = document.getElementById("search");
const coverModal = document.getElementById("cover-modal");
const coverModalImg = document.getElementById("cover-modal-img");
let entries = [];

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function renderList() {
  const query = searchInput.value.trim().toLocaleLowerCase("sv-SE");
  const visible = entries
    .filter((e) => {
      if (!query) return true;
      const haystack = (e.title + " " + (e.creators || []).join(" ") + " " + (e.publisher || ""))
        .toLocaleLowerCase("sv-SE");
      return haystack.includes(query);
    });

  const countEl = `<div id="count">${visible.length} dokument</div>`;

  if (!visible.length) {
    app.innerHTML = countEl + `<div class="empty">Inga dokument hittades.</div>`;
    return;
  }

  const cards = visible.map((e) => `
    <a class="card" href="/dokument/${e.id}/">
      <div class="cover">${e.cover_image
        ? `<img src="${escapeHtml("/assets/covers/" + e.cover_image)}" alt="" loading="lazy">`
        : escapeHtml(e.title)}</div>
      <div class="title">${escapeHtml(e.title)}</div>
      <div class="meta">${escapeHtml((e.creators || []).join(", "))}</div>
      <div class="meta year">${e.year || "?"}${e.type ? " · " + escapeHtml(e.type) : ""}</div>
    </a>
  `).join("");

  app.innerHTML = countEl + `<div class="grid">${cards}</div>`;
}

function openCoverModal(src) {
  coverModalImg.src = src;
  coverModal.hidden = false;
}

function closeCoverModal() {
  coverModal.hidden = true;
  coverModalImg.src = "";
}

// Shared by the list page (cards never carry data-cover today, but harmless)
// and the pre-rendered /dokument/<id>/ pages, where both the cover and each
// example-page thumbnail open the same zoom modal.
app.addEventListener("click", (e) => {
  const target = e.target.closest("[data-cover]");
  if (target) openCoverModal(target.dataset.cover);
});
app.addEventListener("keydown", (e) => {
  const target = e.target.closest("[data-cover]");
  if ((e.key === "Enter" || e.key === " ") && target) {
    e.preventDefault();
    openCoverModal(target.dataset.cover);
  }
});
coverModal.addEventListener("click", (e) => {
  if (e.target === coverModal || e.target.classList.contains("cover-modal-close")) closeCoverModal();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !coverModal.hidden) closeCoverModal();
});

// Everything below is the list page only -- index.html's #app starts empty;
// a pre-rendered /dokument/<id>/ page's #app is already filled with real
// content, so it skips all of this and just gets the cover-modal wiring above.
if (!app.children.length) {
  searchInput.addEventListener("input", renderList);

  fetch("/data/entries.json")
    .then((r) => r.json())
    .then((data) => {
      entries = data;
      renderList();
    })
    .catch((err) => {
      app.innerHTML = `<div class="empty">Kunde inte läsa data/entries.json. Har du kört <code>python3 cli.py build</code>? (${escapeHtml(String(err))})</div>`;
    });
}
