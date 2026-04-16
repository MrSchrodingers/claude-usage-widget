export function renderHealthCard(el, data) {
  const status = data.serviceStatus ?? {};
  const components = status.components ?? [];
  const incidents = status.active_incidents ?? [];

  el.replaceChildren();

  const title = document.createElement("div");
  title.className = "card-title";
  title.textContent = "Service Health";
  el.appendChild(title);

  const desc = document.createElement("div");
  desc.style.cssText = "font-size:0.88em;margin-bottom:8px;";
  desc.style.color = status.indicator === "none" ? "var(--green)" : "var(--amber)";
  desc.textContent = status.description ?? "Unknown";
  el.appendChild(desc);

  const grid = document.createElement("div");
  grid.className = "health-grid";
  for (const c of components) {
    const item = document.createElement("div");
    item.className = "health-item";
    const dot = document.createElement("span");
    dot.className = "status-dot " + c.status.replace(/ /g, "_");
    const name = document.createTextNode(c.name);
    item.append(dot, name);
    grid.appendChild(item);
  }
  el.appendChild(grid);

  for (const inc of incidents) {
    const box = document.createElement("div");
    box.className = "mt-4";
    box.style.cssText = "font-size:0.82em;padding:8px;background:rgba(239,68,68,0.1);border-radius:6px;";
    const incName = document.createElement("div");
    incName.className = "fw-bold";
    incName.style.color = "var(--red)";
    incName.textContent = inc.name;
    box.appendChild(incName);
    if (inc.latest_update) {
      const incUpdate = document.createElement("div");
      incUpdate.className = "text-muted mt-4";
      incUpdate.textContent = inc.latest_update;
      box.appendChild(incUpdate);
    }
    el.appendChild(box);
  }
}
