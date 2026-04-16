import { limitColor, barFill } from "../lib/theme.js";

export function renderWeeklyCard(el, data) {
  const rl = data.rateLimits ?? {};
  el.replaceChildren();

  const title = document.createElement("div");
  title.className = "card-title";
  title.textContent = "Weekly limits";
  el.appendChild(title);

  appendWeeklyRow(el, "All models", rl.weeklyAll?.percentUsed ?? 0, rl.weeklyAll?.resetsLabel, "var(--blue)");
  appendWeeklyRow(el, "Sonnet only", rl.weeklySonnet?.percentUsed ?? 0, rl.weeklySonnet?.resetsLabel, "var(--green)");
}

function appendWeeklyRow(parent, label, pct, resetLabel, baseColor) {
  const section = document.createElement("div");
  section.className = "weekly-section";

  const row = document.createElement("div");
  row.className = "weekly-row";

  // Colored dot
  const dot = document.createElement("span");
  dot.className = "weekly-dot";
  dot.style.background = baseColor;
  row.appendChild(dot);

  const nameSpan = document.createElement("span");
  nameSpan.className = "weekly-label";
  nameSpan.textContent = label;
  row.appendChild(nameSpan);

  const spacer = document.createElement("span");
  spacer.className = "weekly-spacer";
  row.appendChild(spacer);

  // Reset label
  if (resetLabel) {
    const reset = document.createElement("span");
    reset.className = "weekly-reset";
    reset.textContent = "Resets " + resetLabel;
    row.appendChild(reset);
  }

  const pctSpan = document.createElement("span");
  pctSpan.className = "weekly-pct";
  pctSpan.style.color = limitColor(pct);
  pctSpan.textContent = Math.round(pct) + "%";
  row.appendChild(pctSpan);

  section.appendChild(row);

  // Bar
  const track = document.createElement("div");
  track.className = "bar-track";
  const fill = document.createElement("div");
  fill.className = "bar-fill";
  fill.style.width = Math.min(100, pct) + "%";
  fill.style.background = barFill(pct, baseColor);
  track.appendChild(fill);
  section.appendChild(track);

  parent.appendChild(section);
}
