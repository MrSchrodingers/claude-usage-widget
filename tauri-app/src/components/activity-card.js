import { formatTokens } from "../lib/theme.js";

export function renderActivityCard(el, data) {
  el.replaceChildren();

  const title = document.createElement("div");
  title.className = "card-title";
  title.textContent = "Activity";
  el.appendChild(title);

  // Burn rate
  const burnRate = data.burnRate?.output_per_hour ?? 0;
  let burnText;
  if (burnRate >= 1e6) burnText = (burnRate / 1e6).toFixed(1) + "M/h";
  else if (burnRate >= 1e3) burnText = (burnRate / 1e3).toFixed(0) + "K/h";
  else burnText = burnRate + "/h";
  appendRow(el, "\u26A1", "Burn rate", burnText,
    burnRate > 500000 ? "var(--amber-light)" : "var(--text)");

  // Error rate
  const errs = data.errorRate?.total ?? 0;
  const errText = errs > 0 ? errs + " errors" : "None";
  const errColor = errs > 5 ? "var(--red)" : errs > 0 ? "var(--amber-light)" : "var(--green)";
  appendRow(el, "\u26A0", "Errors (2h)", errText, errColor);

  // Adaptive thinking
  const adaptiveOn = data.adaptiveThinking?.adaptive_thinking ?? true;
  appendRow(el, "\u2699", "Adaptive Thinking",
    adaptiveOn ? "ON" : "OFF",
    adaptiveOn ? "var(--green)" : "var(--red)");

  // Avg response quality
  const avg = data.responseQuality?.avgTokensPerResponse ?? 0;
  if (avg > 0) {
    const avgColor = avg > 500 ? "var(--green)" : avg > 200 ? "var(--amber-light)" : "var(--red)";
    appendRow(el, "\u270F", "Avg response", formatTokens(avg) + " tok", avgColor);
  }

  // Latency
  const lat = data.latency?.avgSeconds ?? 0;
  if (lat > 0) {
    const latColor = lat < 10 ? "var(--green)" : lat < 30 ? "var(--amber-light)" : "var(--red)";
    appendRow(el, "\u23F1", "Avg latency", lat.toFixed(1) + "s", latColor);
  }

  // Cache hit rate — green above 60%, neutral in the 15–60 band, amber below
  const hit = data.today?.cacheHitRate ?? 0;
  if (hit > 0) {
    const hitColor = hit >= 60 ? "var(--green)" : hit >= 15 ? "var(--text)" : "var(--amber-light)";
    appendRow(el, "\uD83D\uDCBE", "Cache hit", Math.round(hit) + "%", hitColor);
  }

  // Today's cost + runway (runway only shown when credits narrow the horizon)
  const usd = data.today?.costUSD ?? 0;
  const runwayDays = data.costProjection?.runwayDays ?? null;
  if (usd > 0 || runwayDays !== null) {
    let text = "$" + usd.toFixed(2);
    if (runwayDays !== null && runwayDays < 14) text += " · " + runwayDays.toFixed(1) + "d left";
    const color = (runwayDays !== null && runwayDays < 2) ? "var(--red)"
                : (runwayDays !== null && runwayDays < 7) ? "var(--amber-light)"
                : "var(--text)";
    appendRow(el, "\uD83D\uDCCA", "Cost today", text, color);
  }

  // Compaction events (only when ≥1)
  const compCount = data.compaction?.count ?? 0;
  if (compCount > 0) {
    const color = compCount >= 3 ? "var(--amber-light)" : "var(--text)";
    appendRow(el, "\uD83D\uDDC3", "Compactions (7d)", String(compCount), color);
  }

  // Top tools (compact top-3)
  const byTool = data.toolUse?.byTool ?? {};
  const toolTotal = data.toolUse?.total ?? 0;
  if (toolTotal > 0) {
    const top3 = Object.entries(byTool).sort((a, b) => b[1] - a[1]).slice(0, 3).map(([k]) => k).join(" · ");
    appendRow(el, "\uD83D\uDEE0", "Top tools (7d)", top3, "var(--text)");
  }

  // Model distribution stacked bar
  const models = data.modelBreakdown ?? [];
  if (models.length > 0) {
    const splitTitle = document.createElement("div");
    splitTitle.className = "model-split-title";
    splitTitle.textContent = "Model split";
    el.appendChild(splitTitle);

    // Stacked bar
    const bar = document.createElement("div");
    bar.className = "model-split-bar";
    for (const m of models) {
      const seg = document.createElement("div");
      seg.className = "model-split-segment";
      seg.style.width = (m.percentage ?? 0) + "%";
      seg.style.background = m.color ?? "#9CA3AF";
      bar.appendChild(seg);
    }
    el.appendChild(bar);

    // Legend
    const legend = document.createElement("div");
    legend.className = "model-split-legend";
    for (const m of models) {
      if ((m.percentage ?? 0) <= 0.5) continue;
      const item = document.createElement("span");
      item.className = "model-split-item";
      const dot = document.createElement("span");
      dot.className = "model-split-dot";
      dot.style.background = m.color ?? "#9CA3AF";
      const name = document.createElement("span");
      name.className = "model-split-name";
      name.textContent = (m.model ?? "") + " " + Math.round(m.percentage ?? 0) + "%";
      item.append(dot, name);
      legend.appendChild(item);
    }
    el.appendChild(legend);
  }
}

function appendRow(parent, icon, label, value, valueColor) {
  const row = document.createElement("div");
  row.className = "activity-row";

  const iconEl = document.createElement("span");
  iconEl.className = "activity-icon";
  iconEl.textContent = icon;
  row.appendChild(iconEl);

  const labelEl = document.createElement("span");
  labelEl.className = "activity-label";
  labelEl.textContent = label;
  row.appendChild(labelEl);

  const spacer = document.createElement("span");
  spacer.className = "activity-spacer";
  row.appendChild(spacer);

  const valueEl = document.createElement("span");
  valueEl.className = "activity-value";
  valueEl.style.color = valueColor;
  valueEl.textContent = value;
  row.appendChild(valueEl);

  parent.appendChild(row);
}
