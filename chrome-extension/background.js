const BRIDGE_URL = 'http://127.0.0.1:47600/cookies';
const ALARM_NAME = 'syncCookies';
const PERIOD_MIN = 10;

async function syncCookies() {
  try {
    const cookies = await chrome.cookies.getAll({ domain: 'claude.ai' });
    if (!cookies || cookies.length === 0) return;
    const hasSession = cookies.some(c => c.name === 'sessionKey');
    if (!hasSession) return;
    const cookieStr = cookies.map(c => `${c.name}=${c.value}`).join('; ');
    await fetch(BRIDGE_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cookies: cookieStr }),
    });
  } catch (_) {
    // widget not running or bridge unreachable — ignore
  }
}

function ensureAlarm() {
  chrome.alarms.create(ALARM_NAME, { periodInMinutes: PERIOD_MIN });
}

chrome.runtime.onInstalled.addListener(() => { ensureAlarm(); syncCookies(); });
chrome.runtime.onStartup.addListener(() => { ensureAlarm(); syncCookies(); });
chrome.alarms.onAlarm.addListener(a => { if (a.name === ALARM_NAME) syncCookies(); });

// Push immediately whenever a claude.ai cookie changes (picks up cf_clearance refresh).
chrome.cookies.onChanged.addListener(info => {
  const d = info.cookie.domain || '';
  if (d === 'claude.ai' || d === '.claude.ai') syncCookies();
});
