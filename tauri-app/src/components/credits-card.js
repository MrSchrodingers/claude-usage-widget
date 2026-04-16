export function renderCreditsCard(el, data) {
  const credits = data.rateLimits?.credits;
  const extra = data.rateLimits?.extraUsage;

  // Only show when credits data exists
  if (!credits) {
    el.style.display = "none";
    return;
  }
  el.style.display = "";
  el.replaceChildren();

  // Header: wallet icon + "Credits" + amount
  const header = document.createElement("div");
  header.className = "credits-header";

  const icon = document.createElement("span");
  icon.className = "credits-icon";
  icon.textContent = "\uD83D\uDCB3";
  header.appendChild(icon);

  const title = document.createElement("span");
  title.className = "credits-title";
  title.textContent = "Credits";
  header.appendChild(title);

  const spacer = document.createElement("span");
  spacer.className = "spacer";
  header.appendChild(spacer);

  const amount = document.createElement("span");
  amount.className = "credits-amount";
  const currency = credits.currency ?? "USD";
  const prefix = currency === "BRL" ? "R$ " : "$ ";
  amount.textContent = prefix + formatMoney(credits.amount ?? 0);
  header.appendChild(amount);

  el.appendChild(header);

  // Auto-reload row
  const reloadRow = document.createElement("div");
  reloadRow.className = "credits-row";

  const rlIcon = document.createElement("span");
  rlIcon.textContent = "\u21BB";
  rlIcon.style.cssText = "font-size:0.85em;opacity:0.4;width:14px;text-align:center;";
  const rlLabel = document.createElement("span");
  rlLabel.className = "credits-row-label";
  rlLabel.textContent = "Auto-reload";
  const rlSpacer = document.createElement("span");
  rlSpacer.className = "spacer";
  const rlValue = document.createElement("span");
  rlValue.className = "credits-row-value";
  const autoReload = credits.autoReload ?? false;
  rlValue.textContent = autoReload ? "ON" : "OFF";
  rlValue.style.color = autoReload ? "var(--green)" : "var(--amber-light)";
  reloadRow.append(rlIcon, rlLabel, rlSpacer, rlValue);
  el.appendChild(reloadRow);

  // Extra usage section
  if (extra) {
    const divider = document.createElement("div");
    divider.className = "credits-divider";
    el.appendChild(divider);

    // Extra usage header
    const extraRow = document.createElement("div");
    extraRow.className = "credits-row";
    const exIcon = document.createElement("span");
    exIcon.textContent = "+";
    exIcon.style.cssText = "font-size:1em;opacity:0.5;width:14px;text-align:center;font-weight:bold;";
    const exLabel = document.createElement("span");
    exLabel.style.cssText = "font-size:0.9em;font-weight:600;opacity:0.55;";
    exLabel.textContent = "Extra Usage";
    const exSpacer = document.createElement("span");
    exSpacer.className = "spacer";

    // Enabled/Disabled pill
    const exPill = document.createElement("span");
    exPill.className = "pill-badge";
    const enabled = extra.enabled ?? false;
    const rgb = enabled ? [16, 185, 129] : [239, 68, 68];
    exPill.style.background = "rgba(" + rgb[0] + "," + rgb[1] + "," + rgb[2] + ",0.18)";
    exPill.style.color = enabled ? "var(--green)" : "var(--red)";
    exPill.style.fontSize = "0.82em";
    exPill.textContent = enabled ? "Active" : "Disabled";
    extraRow.append(exIcon, exLabel, exSpacer, exPill);
    el.appendChild(extraRow);

    // Monthly limit
    const limitRow = document.createElement("div");
    limitRow.className = "credits-row";
    const limLabel = document.createElement("span");
    limLabel.className = "credits-row-label";
    limLabel.textContent = "Monthly limit";
    const limSpacer = document.createElement("span");
    limSpacer.className = "spacer";
    const limValue = document.createElement("span");
    limValue.style.cssText = "font-size:0.85em;font-weight:600;";
    const exCurrency = extra.currency ?? "USD";
    const exPrefix = exCurrency === "BRL" ? "R$ " : "$ ";
    limValue.textContent = exPrefix + formatMoney(extra.monthlyLimit ?? 0);
    limitRow.append(limLabel, limSpacer, limValue);
    el.appendChild(limitRow);

    // Used / remaining
    const usedRow = document.createElement("div");
    usedRow.className = "credits-row";
    const usedLabel = document.createElement("span");
    usedLabel.className = "credits-row-label";
    usedLabel.textContent = "Used";
    const usedSpacer = document.createElement("span");
    usedSpacer.className = "spacer";
    const usedValue = document.createElement("span");
    usedValue.style.cssText = "font-size:0.82em;opacity:0.6;";
    const used = extra.usedCredits ?? 0;
    const limit = extra.monthlyLimit ?? 1;
    usedValue.textContent = exPrefix + formatMoney(used) + " / " + exPrefix + formatMoney(limit);
    usedRow.append(usedLabel, usedSpacer, usedValue);
    el.appendChild(usedRow);

    // Usage bar
    const track = document.createElement("div");
    track.className = "bar-track";
    const fill = document.createElement("div");
    fill.className = "bar-fill";
    const pct = limit > 0 ? Math.min(100, (used / limit) * 100) : 0;
    fill.style.width = pct + "%";
    fill.style.background = (used / Math.max(1, limit)) > 0.8 ? "var(--red)" : "var(--amber)";
    track.appendChild(fill);
    el.appendChild(track);
  }
}

function formatMoney(n) {
  return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
