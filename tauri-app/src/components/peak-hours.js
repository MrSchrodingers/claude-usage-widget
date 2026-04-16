export function renderPeakHours(el, data) {
  const peakData = data.lifetime?.peakHours ?? {};

  if (Object.keys(peakData).length === 0) {
    el.style.display = "none";
    return;
  }
  el.style.display = "";
  el.replaceChildren();

  const title = document.createElement("div");
  title.className = "card-title";
  title.textContent = "Peak hours";
  el.appendChild(title);

  const wrap = document.createElement("div");
  wrap.className = "chart-canvas-wrap";

  const canvas = document.createElement("canvas");
  canvas.width = 370;
  canvas.height = 40;
  canvas.style.height = "40px";
  wrap.appendChild(canvas);
  el.appendChild(wrap);

  drawPeakChart(canvas, peakData);
}

function drawPeakChart(canvas, data) {
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  const vals = [];
  let maxV = 1;
  for (let i = 0; i < 24; i++) {
    const v = data[i.toString()] || 0;
    vals.push(v);
    if (v > maxV) maxV = v;
  }

  const bw = (w - 4) / 24;
  const ch = h - 12;

  const textColor = getComputedStyle(document.documentElement).getPropertyValue("--text").trim() || "#e0e0e0";

  for (let i = 0; i < 24; i++) {
    const x = 2 + i * bw + 1;
    const barH = Math.max(1, (vals[i] / maxV) * ch);
    const y = ch - barH;
    const bWidth = bw - 2;

    const alpha = vals[i] > 0 ? 0.3 + (vals[i] / maxV) * 0.5 : 0.08;

    // Amber for work hours (9-18), blue for night (match QML)
    if (i >= 9 && i <= 18) {
      ctx.fillStyle = "rgba(217,119,6," + alpha + ")";
    } else {
      ctx.fillStyle = "rgba(59,130,246," + alpha + ")";
    }
    ctx.fillRect(x, y, bWidth, barH);

    // Hour labels every 6h
    if (i % 6 === 0) {
      ctx.fillStyle = textColor;
      ctx.globalAlpha = 0.3;
      ctx.font = "7px sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(i + "h", x + bWidth / 2, h - 1);
      ctx.globalAlpha = 1.0;
    }
  }
}
