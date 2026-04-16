import { colorForPercent } from "../lib/theme.js";

export function renderWeeklyCard(el, data) {
  const rl = data.rateLimits ?? {};
  el.replaceChildren();

  const title = document.createElement("div");
  title.className = "card-title";
  title.textContent = "Weekly Limits";
  el.appendChild(title);

  appendWeeklyRow(el, "All models", rl.weeklyAll?.percentUsed ?? 0, rl.weeklyAll?.resetsLabel);
  appendWeeklyRow(el, "Sonnet", rl.weeklySonnet?.percentUsed ?? 0, rl.weeklySonnet?.resetsLabel);
}

function appendWeeklyRow(parent, label, pct, resetLabel) {
  const color = colorForPercent(pct);

  const row = document.createElement("div");
  row.className = "weekly-row";
  const nameSpan = document.createElement("span");
  nameSpan.className = "weekly-label";
  nameSpan.textContent = label;
  const pctSpan = document.createElement("span");
  pctSpan.className = "weekly-pct";
  pctSpan.style.color = color;
  pctSpan.textContent = Math.round(pct) + "%";
  row.append(nameSpan, pctSpan);
  parent.appendChild(row);

  const track = document.createElement("div");
  track.className = "bar-track";
  const fill = document.createElement("div");
  fill.className = "bar-fill";
  fill.style.width = Math.min(100, pct) + "%";
  fill.style.background = color;
  track.appendChild(fill);
  parent.appendChild(track);

  if (resetLabel) {
    const reset = document.createElement("div");
    reset.className = "weekly-reset";
    reset.textContent = "Resets " + resetLabel;
    parent.appendChild(reset);
  }
}
