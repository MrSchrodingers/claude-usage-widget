export function colorForPercent(pct) {
  if (pct >= 90) return "var(--red)";
  if (pct >= 70) return "var(--amber)";
  return "var(--green)";
}

export function colorForStatus(status) {
  if (status === "operational") return "var(--green)";
  if (status === "degraded_performance" || status === "partial_outage") return "var(--amber)";
  return "var(--red)";
}

export function dumbLevelColor(level) {
  const map = {
    genius: "var(--green)", smart: "var(--blue)", slow: "var(--amber)",
    dumb: "var(--amber-light)", braindead: "var(--red)",
  };
  return map[level] || "var(--text)";
}
