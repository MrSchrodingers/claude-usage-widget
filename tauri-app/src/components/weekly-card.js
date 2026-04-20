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
  // Collector only emits these blocks when the API populated them, so the
  // presence check distinguishes "metric unavailable" from a genuine zero.
  if (rl.weeklyOpus) {
    appendWeeklyRow(el, "Opus only", rl.weeklyOpus.percentUsed ?? 0, rl.weeklyOpus.resetsLabel, "#A855F7");
  }
  if (rl.weeklyDesign) {
    appendWeeklyRow(el, "Claude Design", rl.weeklyDesign.percentUsed ?? 0, rl.weeklyDesign.resetsLabel, "#EC4899");
  }
  if (rl.weeklyOauthApps) {
    appendWeeklyRow(el, "OAuth apps", rl.weeklyOauthApps.percentUsed ?? 0, rl.weeklyOauthApps.resetsLabel, "#06B6D4");
  }
  if (rl.weeklyCowork) {
    appendWeeklyRow(el, "Cowork", rl.weeklyCowork.percentUsed ?? 0, rl.weeklyCowork.resetsLabel, "#F59E0B");
  }
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
