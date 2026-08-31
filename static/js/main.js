/* ===========================================================
   AlmacenSys — main.js
   Utilidades compartidas por todas las páginas.
   No depende de ningún framework: JS puro.
   Adoptado del design system nuevo (design/main.js) — Fase 3.
   =========================================================== */

document.addEventListener("DOMContentLoaded", function () {
  initUserMenu();
  initToolbarSearch();
});

/* ---------- Menú de usuario (topbar) ---------- */
function initUserMenu() {
  const trigger = document.querySelector("[data-user-trigger]");
  const dropdown = document.querySelector("[data-user-dropdown]");
  if (!trigger || !dropdown) return;

  trigger.addEventListener("click", function (e) {
    e.stopPropagation();
    dropdown.classList.toggle("open");
  });

  document.addEventListener("click", function (e) {
    if (!dropdown.contains(e.target) && !trigger.contains(e.target)) {
      dropdown.classList.remove("open");
    }
  });
}

/* ---------- Filtro genérico de tablas / grids por texto ----------
   Uso: <input data-search-target="#miTabla tbody tr" data-search-fields=".nombre,.codigo">
------------------------------------------------------------------ */
function initToolbarSearch() {
  document.querySelectorAll("[data-search-target]").forEach(function (input) {
    input.addEventListener("input", function () {
      const term = input.value.trim().toLowerCase();
      const targets = document.querySelectorAll(input.getAttribute("data-search-target"));
      targets.forEach(function (row) {
        const text = row.innerText.toLowerCase();
        row.style.display = text.includes(term) ? "" : "none";
      });
      updateEmptyState(input);
    });
  });
}

function updateEmptyState(input) {
  const emptyEl = document.querySelector(input.getAttribute("data-empty-target") || "");
  if (!emptyEl) return;
  const targets = document.querySelectorAll(input.getAttribute("data-search-target"));
  const visible = Array.from(targets).some((el) => el.style.display !== "none");
  emptyEl.style.display = visible ? "none" : "block";
}

/* ---------- Toolbar: filtro por select (categoría, estado, etc.) ----------
   Uso: <select data-filter-target="#miTabla tbody tr" data-filter-attr="data-categoria">
 ------------------------------------------------------------------------- */
document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll("[data-filter-target]").forEach(function (select) {
    select.addEventListener("change", function () {
      const value = select.value;
      const attr = select.getAttribute("data-filter-attr");
      const targets = document.querySelectorAll(select.getAttribute("data-filter-target"));
      targets.forEach(function (row) {
        if (!value || value === "all") {
          row.style.display = "";
        } else {
          row.style.display = row.getAttribute(attr) === value ? "" : "none";
        }
      });
    });
  });
});

/* ---------- Acordeón (historial agrupado por proyecto) ---------- */
function toggleGroup(headerEl) {
  const card = headerEl.closest(".group-card");
  if (!card) return;
  const body = card.querySelector(".group-body");
  const isOpen = card.classList.contains("open");

  if (isOpen) {
    card.classList.remove("open");
    body.style.maxHeight = null;
  } else {
    card.classList.add("open");
    body.style.maxHeight = body.scrollHeight + "px";
  }
}

/* Abre el primer grupo por defecto al cargar */
document.addEventListener("DOMContentLoaded", function () {
  const first = document.querySelector(".group-card");
  if (first) toggleGroup(first.querySelector(".group-header"));
});
