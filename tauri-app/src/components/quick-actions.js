export function renderQuickActions(el, data) {
  el.replaceChildren();

  const btns = [
    { label: "claude.ai", icon: "\uD83C\uDF10", url: "https://claude.ai" },
    { label: "Status", icon: "\uD83D\uDD17", url: "https://status.claude.com" },
    { label: "Copy Stats", icon: "\uD83D\uDCCB", action: () => copyStats(data) },
  ];

  for (const b of btns) {
    const btn = document.createElement("button");
    btn.className = "quick-btn";
    const iconSpan = document.createElement("span");
    iconSpan.textContent = b.icon;
    const labelSpan = document.createElement("span");
    labelSpan.textContent = b.label;
    btn.append(iconSpan, labelSpan);

    if (b.url) {
      btn.addEventListener("click", () => {
        import("@tauri-apps/plugin-shell").then(m => m.open(b.url)).catch(() => {});
      });
    } else if (b.action) {
      btn.addEventListener("click", b.action);
    }
    el.appendChild(btn);
  }
}

async function copyStats(data) {
  const s = data;
  const stats = "Claude " + new Date().toLocaleDateString()
    + " | Session: " + Math.round(s.rateLimits?.session?.percentUsed ?? 0) + "%"
    + " | Weekly: " + Math.round(s.rateLimits?.weeklyAll?.percentUsed ?? 0) + "%"
    + " | $" + (s.today?.costUSD ?? 0).toFixed(2)
    + " | " + formatTokens(s.today?.totalTokens ?? 0) + " tokens";

  try {
    const { writeText } = await import("@tauri-apps/plugin-clipboard-manager");
    await writeText(stats);
  } catch {
    // Fallback: navigator clipboard
    try { await navigator.clipboard.writeText(stats); } catch {}
  }
}

function formatTokens(n) {
  if (!n) return "0";
  if (n >= 1e9) return (n / 1e9).toFixed(1) + "B";
  if (n >= 1e6) return (n / 1e6).toFixed(1) + "M";
  if (n >= 1e3) return (n / 1e3).toFixed(0) + "K";
  return n.toString();
}
