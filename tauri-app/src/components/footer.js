export function renderFooter(el, data) {
  el.replaceChildren();

  const lifetime = data.lifetime ?? {};
  const sessions = lifetime.totalSessions ?? 0;
  const firstSession = lifetime.firstSession ?? "";
  const streakDays = data.streak?.days ?? 0;
  const version = data.claudeCodeVersion ?? "";

  // Claude logo
  const logo = document.createElement("img");
  logo.className = "footer-logo";
  logo.src = "/sprites/claude-logo.svg";
  logo.alt = "";
  el.appendChild(logo);

  // Sessions count
  const sessionsEl = document.createElement("span");
  sessionsEl.className = "footer-text";
  sessionsEl.textContent = sessions + " sessions";
  el.appendChild(sessionsEl);

  // Dot separator
  el.appendChild(createDot());

  // Since date
  if (firstSession) {
    const sinceEl = document.createElement("span");
    sinceEl.className = "footer-text";
    const d = new Date(firstSession);
    const month = d.toLocaleDateString(undefined, { month: "short" });
    const year = d.getFullYear();
    sinceEl.textContent = "since " + month + " " + year;
    el.appendChild(sinceEl);
  }

  // Streak badge
  if (streakDays > 1) {
    const badge = document.createElement("span");
    badge.className = "footer-streak";
    badge.style.background = "rgba(217,119,6,0.15)";
    badge.style.color = "var(--amber)";
    badge.textContent = streakDays + "d streak";
    el.appendChild(badge);
  }

  // Spacer
  const spacer = document.createElement("span");
  spacer.className = "footer-spacer";
  el.appendChild(spacer);

  // Version
  if (version) {
    const versionEl = document.createElement("span");
    versionEl.className = "footer-version";
    versionEl.textContent = version;
    el.appendChild(versionEl);

    el.appendChild(createDot());
  }

  // Anthropic brand
  const brand = document.createElement("span");
  brand.className = "footer-brand";
  brand.textContent = "Anthropic";
  el.appendChild(brand);
}

function createDot() {
  const dot = document.createElement("span");
  dot.className = "footer-dot";
  return dot;
}
