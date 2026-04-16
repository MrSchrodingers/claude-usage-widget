let targetTime = null;
let tickTimer = null;
let onTick = null;

export function startCountdown(resetsInMinutes, callback) {
  onTick = callback;
  targetTime = Date.now() + resetsInMinutes * 60 * 1000;
  if (tickTimer) clearInterval(tickTimer);
  tickTimer = setInterval(tick, 1000);
  tick();
}

export function stopCountdown() {
  if (tickTimer) clearInterval(tickTimer);
  tickTimer = null;
}

function tick() {
  const remaining = Math.max(0, targetTime - Date.now());
  const totalSec = Math.floor(remaining / 1000);
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  const label = h > 0
    ? h + "h " + String(m).padStart(2, "0") + "m " + String(s).padStart(2, "0") + "s"
    : m + "m " + String(s).padStart(2, "0") + "s";
  if (onTick) onTick({ h, m, s, totalSec, label });
}
