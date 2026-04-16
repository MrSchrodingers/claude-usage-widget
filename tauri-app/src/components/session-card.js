import { startCountdown } from "../lib/countdown.js";
import { limitColor, barFill } from "../lib/theme.js";

const RADIUS = 38;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

export function renderSessionCard(el, data) {
  const session = data.rateLimits?.session ?? {};
  const pct = session.percentUsed ?? 0;
  const resetMin = session.resetsInMinutes ?? 0;
  const color = limitColor(pct);
  const strokeColor = barFill(pct, "var(--amber)");
  const offset = CIRCUMFERENCE * (1 - pct / 100);

  // Border color based on usage (match QML)
  if (pct > 80) {
    el.style.borderColor = "rgba(239,68,68,0.6)";
  } else if (pct > 50) {
    el.style.borderColor = "rgba(245,158,11,0.5)";
  } else {
    el.style.borderColor = "rgba(217,119,6,0.35)";
  }

  el.replaceChildren();

  // Header row: "Current session" + reset label
  const header = document.createElement("div");
  header.className = "session-header";

  const title = document.createElement("span");
  title.className = "session-title";
  title.textContent = "Current session";
  header.appendChild(title);

  const resetLabel = document.createElement("span");
  resetLabel.className = "session-reset";
  resetLabel.id = "session-reset-label";
  resetLabel.textContent = formatResetLabel(resetMin, 0);
  header.appendChild(resetLabel);

  el.appendChild(header);

  // Centered ring
  const wrap = document.createElement("div");
  wrap.className = "session-ring-wrap";

  const ringContainer = document.createElement("div");
  ringContainer.className = "ring-container";

  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 96 96");

  const bgCircle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
  bgCircle.setAttribute("class", "ring-bg");
  bgCircle.setAttribute("cx", "48");
  bgCircle.setAttribute("cy", "48");
  bgCircle.setAttribute("r", String(RADIUS));

  const fgCircle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
  fgCircle.setAttribute("class", "ring-fg");
  fgCircle.setAttribute("cx", "48");
  fgCircle.setAttribute("cy", "48");
  fgCircle.setAttribute("r", String(RADIUS));
  fgCircle.setAttribute("stroke", strokeColor);
  fgCircle.setAttribute("stroke-dasharray", String(CIRCUMFERENCE));
  fgCircle.setAttribute("stroke-dashoffset", String(offset));

  svg.append(bgCircle, fgCircle);
  ringContainer.appendChild(svg);

  const ringLabel = document.createElement("div");
  ringLabel.className = "ring-label";
  ringLabel.style.color = color;
  ringLabel.textContent = Math.round(pct) + "%";
  ringContainer.appendChild(ringLabel);

  wrap.appendChild(ringContainer);
  el.appendChild(wrap);

  // Predictive limit alert
  const eta = data.limitEta;
  if (eta && eta.minutesToLimit != null && eta.minutesToLimit < 120 && eta.minutesToLimit > 0) {
    const alert = document.createElement("div");
    alert.className = "session-alert";
    alert.textContent = "At current rate, limit in " + (eta.label ?? "?");
    el.appendChild(alert);
  }

  // Start countdown and update reset label
  startCountdown(resetMin, ({ h, m, s }) => {
    const lbl = document.getElementById("session-reset-label");
    if (lbl) lbl.textContent = formatResetLabel(h * 60 + m, s);
  });
}

function formatResetLabel(totalMin, sec) {
  if (totalMin > 60) return "Resets in " + Math.floor(totalMin / 60) + "h " + (totalMin % 60) + "m";
  if (totalMin > 0) return "Resets in " + totalMin + "m " + sec + "s";
  if (sec > 0) return "Resets in " + sec + "s";
  return "Rolling 5h";
}
