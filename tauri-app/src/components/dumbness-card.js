import { dumbLevelEmoji } from "../lib/theme.js";

export function renderDumbnessCard(el, data) {
  const d = data.dumbness ?? {};
  const score = d.score ?? 0;
  const level = d.level ?? "genius";
  const reasons = d.reasons ?? [];
  const adaptiveOn = data.adaptiveThinking?.adaptive_thinking ?? true;

  // Only show when score > 0 (match QML: visible: root.dumbScore > 0)
  if (score <= 0) {
    el.style.display = "none";
    return;
  }
  el.style.display = "";

  // Card background color based on score (match QML)
  if (score >= 75) {
    el.style.background = "rgba(239,68,68,0.12)";
  } else if (score >= 50) {
    el.style.background = "rgba(249,115,22,0.10)";
  } else if (score >= 25) {
    el.style.background = "rgba(245,158,11,0.10)";
  } else {
    el.style.background = "var(--bg-card)";
  }

  el.replaceChildren();

  // Header: emoji label + score pill badge
  const header = document.createElement("div");
  header.className = "dumb-header";

  const emojiLabel = document.createElement("span");
  emojiLabel.className = "dumb-emoji-label";
  emojiLabel.textContent = dumbLevelEmoji(level);
  header.appendChild(emojiLabel);

  // Score pill badge
  const badge = document.createElement("span");
  badge.className = "dumb-score-badge";
  let badgeBg, badgeColor;
  if (score >= 75) {
    badgeBg = "rgba(239,68,68,0.25)";
    badgeColor = "var(--red)";
  } else if (score >= 50) {
    badgeBg = "rgba(249,115,22,0.25)";
    badgeColor = "#F97316";
  } else {
    badgeBg = "rgba(245,158,11,0.25)";
    badgeColor = "var(--amber-light)";
  }
  badge.style.background = badgeBg;
  badge.style.color = badgeColor;
  badge.textContent = score + "/100";
  header.appendChild(badge);

  el.appendChild(header);

  // Reasons as bullet list
  if (reasons.length > 0) {
    const reasonsDiv = document.createElement("div");
    reasonsDiv.className = "dumb-reasons";
    for (const r of reasons) {
      const item = document.createElement("div");
      item.className = "dumb-reason";
      item.textContent = "  \u2022 " + r;
      reasonsDiv.appendChild(item);
    }
    el.appendChild(reasonsDiv);
  }

  // Adaptive thinking tip
  if (!adaptiveOn) {
    const tip = document.createElement("div");
    tip.className = "dumb-tip";
    tip.textContent = "Tip: Adaptive Thinking is OFF in settings.json";
    el.appendChild(tip);
  }
}
