const SPRITE_MAP = {
  genius: { prefix: "halo", frames: 6, interval: 120 },
  smart:  { prefix: "smart", frames: 6, interval: 150 },
  slow:   { prefix: "rain", frames: 6, interval: 150 },
  dumb:   { prefix: "fire", frames: 6, interval: 120 },
  braindead: { prefix: "skull", frames: 6, interval: 200 },
};

let spriteFrame = 0;
let spriteTimer = null;
let currentLevel = null;

// Preload all sprite images
for (const [, cfg] of Object.entries(SPRITE_MAP)) {
  for (let i = 0; i < cfg.frames; i++) {
    const img = new Image();
    img.src = "/sprites/" + cfg.prefix + "-" + i + ".png";
  }
}

export function renderHeader(el, data) {
  const level = data.dumbness?.level ?? "genius";
  const score = data.dumbness?.score ?? 0;
  const source = data.rateLimits?.source === "api" ? "Live" : "Local";
  const sourceClass = source === "Live" ? "text-green" : "text-dim";
  const plan = data.rateLimits?.plan ?? "";
  const labels = {
    genius: "Genius", smart: "Smart", slow: "Slow",
    dumb: "Dumb", braindead: "Braindead",
  };
  const prefix = SPRITE_MAP[level]?.prefix ?? "halo";

  if (!el.querySelector("#mascot-img")) {
    const mascotDiv = document.createElement("div");
    mascotDiv.className = "mascot-container";
    const img = document.createElement("img");
    img.id = "mascot-img";
    img.src = "/sprites/" + prefix + "-0.png";
    img.alt = "Clawd mascot";
    mascotDiv.appendChild(img);

    const infoDiv = document.createElement("div");
    infoDiv.className = "header-info";
    infoDiv.id = "header-info";
    el.replaceChildren(mascotDiv, infoDiv);
  }

  const infoDiv = el.querySelector("#header-info");
  infoDiv.replaceChildren();

  const title = document.createElement("div");
  title.className = "header-title";
  title.textContent = "Claude Usage";
  infoDiv.appendChild(title);

  const statusLine = document.createElement("div");
  statusLine.className = "header-status";
  const levelSpan = document.createElement("span");
  levelSpan.style.color = dumbColor(level);
  levelSpan.textContent = labels[level] ?? level;
  const scoreSpan = document.createElement("span");
  scoreSpan.className = "text-dim";
  scoreSpan.textContent = " \u00B7 " + score;
  statusLine.append(levelSpan, scoreSpan);
  infoDiv.appendChild(statusLine);

  const subLine = document.createElement("div");
  subLine.className = "header-sub";
  const srcSpan = document.createElement("span");
  srcSpan.className = sourceClass;
  srcSpan.textContent = source;
  subLine.appendChild(srcSpan);
  if (plan) {
    subLine.appendChild(document.createTextNode(" \u00B7 " + plan));
  }
  infoDiv.appendChild(subLine);

  startSpriteAnimation(level);
}

function startSpriteAnimation(level) {
  if (level === currentLevel) return;
  currentLevel = level;
  if (spriteTimer) clearInterval(spriteTimer);
  spriteFrame = 0;
  const cfg = SPRITE_MAP[level];
  if (!cfg) return;
  const img = document.getElementById("mascot-img");
  if (!img) return;
  img.src = "/sprites/" + cfg.prefix + "-0.png";
  spriteTimer = setInterval(() => {
    spriteFrame = (spriteFrame + 1) % cfg.frames;
    img.src = "/sprites/" + cfg.prefix + "-" + spriteFrame + ".png";
  }, cfg.interval);
}

function dumbColor(level) {
  const map = {
    genius: "var(--green)", smart: "var(--blue)", slow: "var(--amber)",
    dumb: "var(--amber-light)", braindead: "var(--red)",
  };
  return map[level] || "var(--text)";
}
