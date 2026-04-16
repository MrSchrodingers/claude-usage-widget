import { startCountdown } from "../lib/countdown.js";
import { colorForPercent } from "../lib/theme.js";

const RADIUS = 34;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

export function renderSessionCard(el, data) {
  const session = data.rateLimits?.session ?? {};
  const pct = session.percentUsed ?? 0;
  const resetMin = session.resetsInMinutes ?? 0;
  const color = colorForPercent(pct);
  const offset = CIRCUMFERENCE * (1 - pct / 100);

  el.replaceChildren();

  const title = document.createElement("div");
  title.className = "card-title";
  title.textContent = "Session (5h window)";
  el.appendChild(title);

  const wrap = document.createElement("div");
  wrap.className = "session-ring-wrap";

  // SVG ring
  const ringContainer = document.createElement("div");
  ringContainer.className = "ring-container";

  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 80 80");

  const bgCircle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
  bgCircle.setAttribute("class", "ring-bg");
  bgCircle.setAttribute("cx", "40");
  bgCircle.setAttribute("cy", "40");
  bgCircle.setAttribute("r", String(RADIUS));

  const fgCircle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
  fgCircle.setAttribute("class", "ring-fg");
  fgCircle.setAttribute("cx", "40");
  fgCircle.setAttribute("cy", "40");
  fgCircle.setAttribute("r", String(RADIUS));
  fgCircle.setAttribute("stroke", color);
  fgCircle.setAttribute("stroke-dasharray", String(CIRCUMFERENCE));
  fgCircle.setAttribute("stroke-dashoffset", String(offset));

  svg.append(bgCircle, fgCircle);
  ringContainer.appendChild(svg);

  const ringLabel = document.createElement("div");
  ringLabel.className = "ring-label";
  ringLabel.style.color = color;
  ringLabel.textContent = Math.round(pct) + "%";
  ringContainer.appendChild(ringLabel);

  // Details
  const details = document.createElement("div");
  details.className = "session-details";

  const pctLine = document.createElement("div");
  pctLine.className = "session-pct";
  const pctBold = document.createElement("span");
  pctBold.className = "fw-bold";
  pctBold.style.color = color;
  pctBold.textContent = pct.toFixed(1) + "%";
  pctLine.append(pctBold, document.createTextNode(" used"));

  const countdownVal = document.createElement("div");
  countdownVal.className = "session-countdown";
  countdownVal.id = "countdown-value";
  countdownVal.textContent = "--:--";

  const countdownLabel = document.createElement("div");
  countdownLabel.className = "session-countdown-label";
  countdownLabel.textContent = "until reset";

  details.append(pctLine, countdownVal, countdownLabel);
  wrap.append(ringContainer, details);
  el.appendChild(wrap);

  startCountdown(resetMin, ({ label }) => {
    const cdEl = document.getElementById("countdown-value");
    if (cdEl) cdEl.textContent = label;
  });
}
