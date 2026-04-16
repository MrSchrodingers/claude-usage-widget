import { dumbLevelColor } from "../lib/theme.js";

export function renderDumbnessCard(el, data) {
  const d = data.dumbness ?? {};
  const score = d.score ?? 0;
  const level = d.level ?? "genius";
  const reasons = d.reasons ?? [];
  const color = dumbLevelColor(level);
  const labels = {
    genius: "Genius", smart: "Smart", slow: "Degraded",
    dumb: "Dumb", braindead: "Braindead",
  };

  el.replaceChildren();

  const title = document.createElement("div");
  title.className = "card-title";
  title.textContent = "Intelligence Score";
  el.appendChild(title);

  const header = document.createElement("div");
  header.className = "dumb-header";
  const scoreWrap = document.createElement("div");
  const scoreSpan = document.createElement("span");
  scoreSpan.className = "dumb-score";
  scoreSpan.style.color = color;
  scoreSpan.textContent = String(score);
  const maxSpan = document.createElement("span");
  maxSpan.className = "text-dim";
  maxSpan.textContent = "/100";
  scoreWrap.append(scoreSpan, maxSpan);
  const levelSpan = document.createElement("div");
  levelSpan.className = "dumb-level";
  levelSpan.style.color = color;
  levelSpan.textContent = labels[level] ?? level;
  header.append(scoreWrap, levelSpan);
  el.appendChild(header);

  const reasonsDiv = document.createElement("div");
  reasonsDiv.className = "dumb-reasons";
  reasonsDiv.textContent = reasons.length > 0 ? reasons.join(" \u00B7 ") : "No issues detected";
  el.appendChild(reasonsDiv);
}
