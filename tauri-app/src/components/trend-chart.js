export function renderTrendChart(el, data) {
  const trend = data.trend7d ?? [];
  el.replaceChildren();

  const title = document.createElement("div");
  title.className = "card-title";
  title.textContent = "7-day activity";
  el.appendChild(title);

  if (trend.length === 0) return;

  const wrap = document.createElement("div");
  wrap.className = "chart-canvas-wrap";

  const canvas = document.createElement("canvas");
  canvas.width = 370;
  canvas.height = 56;
  canvas.style.height = "56px";
  wrap.appendChild(canvas);
  el.appendChild(wrap);

  drawTrendChart(canvas, trend);
}

function drawTrendChart(canvas, data) {
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  let maxT = 1;
  for (const d of data) {
    if ((d.tokens || 0) > maxT) maxT = d.tokens;
  }

  const bw = (w - 12) / data.length;
  const pad = 3;
  const ch = h - 14;

  // Read CSS --text color for labels
  const textColor = getComputedStyle(document.documentElement).getPropertyValue("--text").trim() || "#e0e0e0";

  for (let i = 0; i < data.length; i++) {
    const x = 6 + i * bw + pad / 2;
    const barH = Math.max(2, (data[i].tokens / maxT) * ch);
    const y = ch - barH;
    const bWidth = bw - pad;
    const isLast = i === data.length - 1;

    // Gradient-like alpha: brighter for today (match QML)
    const alpha = isLast ? 0.85 : 0.2 + (i / data.length) * 0.2;
    ctx.fillStyle = "rgba(217,119,6," + alpha + ")"; // amber #D97706

    // Rounded top corners
    const r = Math.min(4, bWidth / 2);
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + bWidth, y, x + bWidth, y + barH, r);
    ctx.lineTo(x + bWidth, ch);
    ctx.lineTo(x, ch);
    ctx.arcTo(x, y, x + r, y, r);
    ctx.closePath();
    ctx.fill();

    // Day label
    ctx.fillStyle = textColor;
    ctx.globalAlpha = isLast ? 0.8 : 0.35;
    ctx.font = (isLast ? "bold " : "") + "8px sans-serif";
    ctx.textAlign = "center";
    ctx.fillText(data[i].label || "", x + bWidth / 2, h - 1);
    ctx.globalAlpha = 1.0;
  }
}
