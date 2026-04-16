import { dumbLevelColor, dumbLevelLabel, statusColorRGB } from "../lib/theme.js";

const SPRITE_MAP = {
  genius: { prefix: "halo", frames: 6, interval: 250 },
  smart:  { prefix: "smart", frames: 6, interval: 300 },
  slow:   { prefix: "rain", frames: 6, interval: 100 },
  dumb:   { prefix: "fire", frames: 6, interval: 120 },
  braindead: { prefix: "skull", frames: 6, interval: 200 },
};

let spriteFrame = 0;
let spriteTimer = null;
let currentLevel = null;

// Easter egg state
let tapCount = 0;
let tapTimer = null;
let eggStates = ["genius", "smart", "slow", "dumb", "braindead", "live"];
let eggIndex = 0;
let eggActive = false;
let eggTimeout = null;
let eggHideTimer = null;

// Preload all sprite images
for (const [, cfg] of Object.entries(SPRITE_MAP)) {
  for (let i = 0; i < cfg.frames; i++) {
    const img = new Image();
    img.src = "/sprites/" + cfg.prefix + "-" + i + ".png";
  }
}

export function renderHeader(el, data) {
  const level = eggActive ? currentLevel : (data.dumbness?.level ?? "genius");
  const source = data.rateLimits?.source === "api" ? "Live" : "Offline";
  const plan = data.rateLimits?.plan ?? "Max (20x)";
  const indicator = data.serviceStatus?.indicator ?? "none";
  const prefix = SPRITE_MAP[level]?.prefix ?? "halo";

  if (!el.querySelector("#clawd-img")) {
    const mascotDiv = document.createElement("div");
    mascotDiv.className = "mascot-container";
    mascotDiv.addEventListener("click", () => handleEasterEgg(data));

    // Base Clawd character (hidden when braindead, like QML)
    const clawd = document.createElement("img");
    clawd.id = "clawd-img";
    clawd.src = "/sprites/clawd.svg";
    clawd.alt = "Clawd mascot";
    clawd.style.cssText = "position:absolute;top:50%;left:50%;transform:translate(-50%,-45%);width:70%;height:70%;";
    mascotDiv.appendChild(clawd);

    // Sprite overlay on top of Clawd
    const sprite = document.createElement("img");
    sprite.id = "mascot-img";
    sprite.src = "/sprites/" + prefix + "-0.png";
    sprite.alt = "";
    mascotDiv.appendChild(sprite);

    const eggLbl = document.createElement("div");
    eggLbl.id = "egg-label";
    eggLbl.className = "egg-label";
    eggLbl.style.display = "none";
    mascotDiv.appendChild(eggLbl);

    const infoDiv = document.createElement("div");
    infoDiv.className = "header-info";
    infoDiv.id = "header-info";
    el.replaceChildren(mascotDiv, infoDiv);
  }

  // Toggle Clawd visibility (hidden when braindead — skull replaces him)
  const clawdImg = el.querySelector("#clawd-img");
  if (clawdImg) clawdImg.style.display = level === "braindead" ? "none" : "";

  const infoDiv = el.querySelector("#header-info");
  infoDiv.replaceChildren();

  // Title row: "Claude" + pill badge
  const titleRow = document.createElement("div");
  titleRow.className = "header-title-row";

  const title = document.createElement("span");
  title.className = "header-title";
  title.textContent = "Claude";
  titleRow.appendChild(title);

  // Level pill badge (like QML)
  const pill = document.createElement("span");
  pill.className = "pill-badge";
  const levelText = dumbLevelLabel(level);
  const levelClr = dumbLevelColor(level);
  const rgb = statusColorRGB(indicator);
  pill.style.background = "rgba(" + rgb[0] + "," + rgb[1] + "," + rgb[2] + ",0.18)";
  pill.style.color = levelClr;
  pill.textContent = levelText;
  titleRow.appendChild(pill);

  infoDiv.appendChild(titleRow);

  // Sub line: Claude logo + plan · source
  const subLine = document.createElement("div");
  subLine.className = "header-sub";

  const logo = document.createElement("img");
  logo.className = "header-sub-logo";
  logo.src = "/sprites/claude-logo.svg";
  logo.alt = "";
  subLine.appendChild(logo);

  const planSpan = document.createElement("span");
  planSpan.className = "header-sub-plan";
  planSpan.textContent = plan;
  subLine.appendChild(planSpan);

  const dot = document.createElement("span");
  dot.className = "header-sub-dot";
  subLine.appendChild(dot);

  const srcSpan = document.createElement("span");
  srcSpan.className = "header-sub-source";
  srcSpan.style.color = source === "Live" ? "var(--green)" : "var(--text)";
  srcSpan.textContent = source;
  subLine.appendChild(srcSpan);

  infoDiv.appendChild(subLine);

  startSpriteAnimation(level);
}

function handleEasterEgg(data) {
  tapCount++;
  if (tapTimer) clearTimeout(tapTimer);
  tapTimer = setTimeout(() => { tapCount = 0; }, 1500);

  if (tapCount >= 5) {
    tapCount = 0;
    eggIndex = (eggIndex + 1) % eggStates.length;
    const state = eggStates[eggIndex];
    const eggLbl = document.getElementById("egg-label");

    if (state === "live") {
      eggActive = false;
      if (eggLbl) { eggLbl.textContent = "\uD83D\uDD34 Live"; eggLbl.style.display = ""; }
    } else {
      eggActive = true;
      currentLevel = state;
      if (eggLbl) {
        eggLbl.textContent = "\uD83E\uDD5A " + state.charAt(0).toUpperCase() + state.slice(1);
        eggLbl.style.display = "";
      }
      startSpriteAnimation(state);
    }

    if (eggHideTimer) clearTimeout(eggHideTimer);
    eggHideTimer = setTimeout(() => {
      if (eggLbl) eggLbl.style.display = "none";
    }, 1500);

    if (eggTimeout) clearTimeout(eggTimeout);
    eggTimeout = setTimeout(() => {
      eggActive = false;
      eggIndex = 0;
      if (eggLbl) eggLbl.style.display = "none";
    }, 30000);
  }
}

function startSpriteAnimation(level) {
  if (level === currentLevel && spriteTimer) return;
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
