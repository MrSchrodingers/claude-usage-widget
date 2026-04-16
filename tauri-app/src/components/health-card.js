import { statusColor, statusColorRGB, componentStatusColor } from "../lib/theme.js";

export function renderHealthCard(el, data) {
  const status = data.serviceStatus ?? {};
  const indicator = status.indicator ?? "none";
  const components = status.components ?? [];
  const incidents = status.active_incidents ?? [];

  // Card background color based on status (match QML)
  if (indicator === "none") {
    el.style.background = "var(--bg-card)";
    el.style.borderColor = "var(--border)";
  } else if (indicator === "minor") {
    el.style.background = "rgba(251,158,22,0.10)";
    el.style.borderColor = "rgba(251,158,22,0.40)";
  } else {
    el.style.background = "rgba(239,68,68,0.10)";
    el.style.borderColor = "rgba(239,68,68,0.40)";
  }

  el.replaceChildren();

  // Header row: pulsing dot + title + status pill
  const header = document.createElement("div");
  header.className = "health-header";

  const dot = document.createElement("span");
  dot.className = "health-dot" + (indicator !== "none" ? " pulsing" : "");
  dot.style.background = statusColor(indicator);
  header.appendChild(dot);

  const title = document.createElement("span");
  title.className = "health-title";
  title.textContent = "Service Health";
  header.appendChild(title);

  const spacer = document.createElement("span");
  spacer.className = "spacer";
  header.appendChild(spacer);

  // Status pill badge
  const rgb = statusColorRGB(indicator);
  const pill = document.createElement("span");
  pill.className = "pill-badge";
  pill.style.background = "rgba(" + rgb[0] + "," + rgb[1] + "," + rgb[2] + ",0.20)";
  pill.style.border = "1px solid rgba(" + rgb[0] + "," + rgb[1] + "," + rgb[2] + ",0.55)";
  pill.style.color = statusColor(indicator);
  pill.style.fontSize = "0.88em";
  pill.style.padding = "4px 9px";
  pill.textContent = statusLabel(indicator);
  header.appendChild(pill);

  el.appendChild(header);

  // Component dots row
  if (components.length > 0) {
    const comps = document.createElement("div");
    comps.className = "health-components";
    for (const c of components) {
      const item = document.createElement("span");
      item.className = "health-comp";
      const cDot = document.createElement("span");
      cDot.className = "health-comp-dot";
      cDot.style.background = componentStatusColor(c.status);
      const cName = document.createElement("span");
      cName.className = "health-comp-name";
      cName.textContent = c.name;
      item.append(cDot, cName);
      comps.appendChild(item);
    }
    el.appendChild(comps);
  }

  // DownDetector link
  const dd = document.createElement("div");
  dd.className = "health-downdetector";
  const ddIcon = document.createElement("span");
  ddIcon.textContent = "\uD83C\uDF10";
  ddIcon.style.fontSize = "0.7em";
  ddIcon.style.opacity = "0.35";
  const ddLabel = document.createElement("span");
  ddLabel.className = "health-dd-label";
  ddLabel.textContent = "User reports:";
  const ddSpacer = document.createElement("span");
  ddSpacer.className = "spacer";
  const ddLink = document.createElement("button");
  ddLink.className = "health-dd-link";
  ddLink.textContent = "DownDetector \u2197";
  ddLink.addEventListener("click", () => {
    import("@tauri-apps/plugin-shell").then(m => m.open("https://downdetector.com/status/claude-ai/")).catch(() => {});
  });
  dd.append(ddIcon, ddLabel, ddSpacer, ddLink);
  el.appendChild(dd);

  // Active incidents (show first only, like QML)
  const visibleIncidents = incidents.length > 0 ? [incidents[0]] : [];
  for (const inc of visibleIncidents) {
    const box = document.createElement("div");
    box.className = "incident-box";
    const incName = document.createElement("div");
    incName.className = "incident-name";
    incName.textContent = inc.name;
    box.appendChild(incName);
    if (inc.latest_update) {
      const incUpdate = document.createElement("div");
      incUpdate.className = "incident-update";
      incUpdate.textContent = inc.latest_update;
      box.appendChild(incUpdate);
    }
    el.appendChild(box);
  }
}

function statusLabel(indicator) {
  if (indicator === "none") return "Healthy";
  if (indicator === "minor") return "Degraded";
  if (indicator === "major") return "Major Outage";
  if (indicator === "critical") return "Critical Outage";
  return "Unknown";
}
