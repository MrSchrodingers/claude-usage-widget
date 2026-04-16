// Match QML limitColor thresholds exactly
export function limitColor(pct) {
  if (pct > 80) return "var(--red)";
  if (pct > 50) return "var(--amber-light)";
  return "var(--text)";
}

// Match QML barFill: >80 red, >50 amber-light, else base color
export function barFill(pct, base) {
  if (pct > 80) return "var(--red)";
  if (pct > 50) return "var(--amber-light)";
  return base;
}

// Legacy alias — some components still use this
export function colorForPercent(pct) {
  return limitColor(pct);
}

export function statusColor(indicator) {
  if (indicator === "none") return "var(--green)";
  if (indicator === "minor") return "var(--amber-light)";
  if (indicator === "major") return "#F97316";
  if (indicator === "critical") return "var(--red)";
  return "var(--text-dim)";
}

export function statusColorRGB(indicator) {
  if (indicator === "none") return [16, 185, 129];
  if (indicator === "minor") return [245, 158, 11];
  if (indicator === "major") return [249, 115, 22];
  if (indicator === "critical") return [239, 68, 68];
  return [128, 128, 128];
}

export function componentStatusColor(status) {
  if (status === "operational") return "var(--green)";
  if (status === "degraded_performance") return "var(--amber-light)";
  if (status === "partial_outage") return "#F97316";
  if (status === "major_outage") return "var(--red)";
  return "var(--text-dim)";
}

export function dumbLevelColor(level) {
  const map = {
    genius: "#FFD700",
    smart: "var(--green)",
    slow: "var(--amber-light)",
    dumb: "#F97316",
    braindead: "var(--red)",
  };
  return map[level] || "var(--text)";
}

export function dumbLevelLabel(level) {
  const map = {
    genius: "Genius",
    smart: "Smart",
    slow: "Slow",
    dumb: "Dumb",
    braindead: "Braindead",
  };
  return map[level] || level;
}

export function dumbLevelEmoji(level) {
  const map = {
    genius: "\u2728 Genius",
    smart: "\uD83E\uDD14 Hmm",
    slow: "\uD83C\uDF27 Slow",
    dumb: "\uD83D\uDD25 This is Fine",
    braindead: "\uD83D\uDC80 Braindead",
  };
  return map[level] || level;
}

export function formatTokens(n) {
  if (!n) return "0";
  if (n >= 1e9) return (n / 1e9).toFixed(1) + "B";
  if (n >= 1e6) return (n / 1e6).toFixed(1) + "M";
  if (n >= 1e3) return (n / 1e3).toFixed(0) + "K";
  return n.toString();
}
