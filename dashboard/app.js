/**
 * Brandywine Price Tracker dashboard.
 * Reads directly from Supabase using the public anon key (read-only,
 * enforced by Row Level Security policies in supabase/schema.sql).
 * No backend of its own — pure static HTML/JS, deployable to GitHub Pages.
 */

const SUPABASE_URL = "https://yxvtmgylbxknqrucriyl.supabase.co";
const SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl4dnRtZ3lsYnhrbnFydWNyaXlsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODMxODY2MTcsImV4cCI6MjA5ODc2MjYxN30.1LMBbu1q3hKMC5DblmlaVIyCZA3smyCx4eGmVcj5tZ4";

const supabase = window.supabase?.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

let allChemicals = [];      // [{ name, category, price, unit, date, source, change, status }]
let activeCategory = "all";
let searchTerm = "";
let sortBy = "name";
let chartInstance = null;

function showError(message) {
  const el = document.getElementById("error-state");
  el.textContent = message;
  el.hidden = false;
}

function clearError() {
  const el = document.getElementById("error-state");
  el.textContent = "";
  el.hidden = true;
}

async function init() {
  clearError();
  if (!window.supabase) {
    showError("Dashboard failed to load: Supabase client library did not load.");
    return;
  }
  await Promise.all([loadChemicals(), loadAlertHistory()]);
  document.getElementById("last-updated-label").textContent =
    `Updated ${new Date().toLocaleString()}`;
}

async function loadChemicals() {
  const { data: configRows, error: configErr } = await supabase
    .from("chemicals_config")
    .select("*")
    .eq("is_active", true);

  if (configErr) {
    console.error("Failed to load chemicals_config", configErr);
    showError(`Could not load chemical list: ${configErr.message}`);
    return;
  }

  if (!configRows || configRows.length === 0) {
    showError("No chemicals configured yet. Run supabase/schema.sql in your Supabase project.");
    return;
  }

  const results = [];
  for (const cfg of configRows) {
    const { data: priceRows } = await supabase
      .from("chemical_prices")
      .select("*")
      .eq("chemical_name", cfg.chemical_name)
      .order("date_recorded", { ascending: false })
      .limit(8); // latest + enough history for a rough 7-day comparison

    if (!priceRows || priceRows.length === 0) continue;

    const latest = priceRows[0];
    const weekAgo = priceRows[priceRows.length - 1];
    const pctChange = weekAgo.price
      ? ((latest.price - weekAgo.price) / weekAgo.price) * 100
      : 0;

    const { data: recentAlerts } = await supabase
      .from("price_alerts")
      .select("*")
      .eq("chemical_name", cfg.chemical_name)
      .gte("triggered_at", new Date(Date.now() - 24 * 3600 * 1000).toISOString())
      .limit(1);

    let status = "stable";
    if (recentAlerts && recentAlerts.length > 0) status = "alert";
    else if (Math.abs(pctChange) >= 2) status = "moving";

    results.push({
      name: cfg.chemical_name,
      category: cfg.category || "uncategorized",
      price: latest.price,
      unit: latest.unit,
      date: latest.date_recorded,
      source: latest.source,
      pctChange,
      status,
    });
  }

  allChemicals = results;
  renderCategoryChips();
  renderCards();

  if (results.length === 0) {
    showError(
      `${configRows.length} chemicals configured but no price data yet. ` +
      "Trigger the Chemical Price Scraper workflow in GitHub Actions."
    );
  }
}

async function loadAlertHistory() {
  const { data, error } = await supabase
    .from("price_alerts")
    .select("*")
    .order("triggered_at", { ascending: false })
    .limit(20);

  const tbody = document.getElementById("alert-table-body");
  if (error || !data || data.length === 0) {
    tbody.innerHTML = `<tr><td colspan="4" class="muted">No alerts yet.</td></tr>`;
    return;
  }

  tbody.innerHTML = data.map(a => `
    <tr>
      <td>${escapeHtml(a.chemical_name)}</td>
      <td class="${a.direction === 'up' ? 'chem-change-pos' : 'chem-change-neg'}">
        ${a.percent_change > 0 ? '+' : ''}${a.percent_change.toFixed(1)}%
      </td>
      <td>${a.direction === 'up' ? '▲ Up' : '▼ Down'}</td>
      <td>${new Date(a.triggered_at).toLocaleDateString()}</td>
    </tr>
  `).join("");
}

function renderCategoryChips() {
  const categories = ["all", ...new Set(allChemicals.map(c => c.category))];
  const container = document.getElementById("category-filters");
  container.innerHTML = categories.map(cat => `
    <button class="chip ${cat === activeCategory ? 'chip-active' : ''}" data-category="${cat}">
      ${cat === "all" ? "All" : capitalize(cat)}
    </button>
  `).join("");

  container.querySelectorAll(".chip").forEach(btn => {
    btn.addEventListener("click", () => {
      activeCategory = btn.dataset.category;
      renderCategoryChips();
      renderCards();
    });
  });
}

function renderCards() {
  let filtered = allChemicals.filter(c =>
    (activeCategory === "all" || c.category === activeCategory) &&
    c.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  filtered = sortChemicals(filtered, sortBy);

  const grid = document.getElementById("card-grid");
  const emptyState = document.getElementById("empty-state");

  grid.querySelectorAll(".chem-card").forEach(el => el.remove());

  if (filtered.length === 0) {
    emptyState.hidden = false;
    return;
  }
  emptyState.hidden = true;

  filtered.forEach(chem => {
    const card = document.createElement("div");
    card.className = "chem-card";
    card.tabIndex = 0;
    card.setAttribute("role", "button");
    card.setAttribute("aria-label", `View ${chem.name} price history`);

    const statusLabel = { stable: "Stable", moving: "Moving", alert: "Alert" }[chem.status];
    const changeClass = chem.pctChange >= 0 ? "chem-change-pos" : "chem-change-neg";

    card.innerHTML = `
      <div class="chem-card-top">
        <div>
          <div class="chem-name">${escapeHtml(chem.name)}</div>
          <div class="chem-category">${escapeHtml(chem.category)}</div>
        </div>
        <span class="status-badge status-${chem.status}">${statusLabel}</span>
      </div>
      <div class="chem-price">$${chem.price.toFixed(2)}</div>
      <div class="chem-price-unit">${escapeHtml(chem.unit)}</div>
      <div class="chem-meta-row">
        <span class="${changeClass}">${chem.pctChange >= 0 ? '+' : ''}${chem.pctChange.toFixed(1)}% (7d)</span>
        <span>${chem.date}</span>
      </div>
    `;
    card.addEventListener("click", () => openModal(chem));
    card.addEventListener("keypress", (e) => { if (e.key === "Enter") openModal(chem); });
    grid.appendChild(card);
  });
}

function sortChemicals(list, by) {
  const copy = [...list];
  if (by === "name") copy.sort((a, b) => a.name.localeCompare(b.name));
  if (by === "change") copy.sort((a, b) => Math.abs(b.pctChange) - Math.abs(a.pctChange));
  if (by === "price") copy.sort((a, b) => b.price - a.price);
  return copy;
}

async function openModal(chem) {
  document.getElementById("modal-title").textContent = chem.name;
  document.getElementById("modal-meta").textContent =
    `Current: $${chem.price.toFixed(2)} ${chem.unit} · Source: ${chem.source}`;
  document.getElementById("modal-backdrop").hidden = false;

  const { data } = await supabase
    .from("chemical_prices")
    .select("*")
    .eq("chemical_name", chem.name)
    .order("date_recorded", { ascending: true })
    .gte("date_recorded", new Date(Date.now() - 30 * 24 * 3600 * 1000).toISOString().slice(0, 10));

  const ctx = document.getElementById("modal-chart").getContext("2d");
  if (chartInstance) chartInstance.destroy();
  chartInstance = new Chart(ctx, {
    type: "line",
    data: {
      labels: (data || []).map(r => r.date_recorded),
      datasets: [{
        label: chem.name,
        data: (data || []).map(r => r.price),
        borderColor: "#2A7B8C",
        backgroundColor: "rgba(42,123,140,0.08)",
        fill: true,
        tension: 0.25,
        pointRadius: 2,
      }],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: false } },
    },
  });
}

function closeModal() {
  document.getElementById("modal-backdrop").hidden = true;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}
function capitalize(s) { return s.charAt(0).toUpperCase() + s.slice(1); }

document.getElementById("modal-close").addEventListener("click", closeModal);
document.getElementById("modal-backdrop").addEventListener("click", (e) => {
  if (e.target.id === "modal-backdrop") closeModal();
});
document.getElementById("search-input").addEventListener("input", (e) => {
  searchTerm = e.target.value;
  renderCards();
});
document.getElementById("sort-select").addEventListener("change", (e) => {
  sortBy = e.target.value;
  renderCards();
});

init();
