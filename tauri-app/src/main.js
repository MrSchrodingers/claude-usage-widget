import { listen } from "@tauri-apps/api/event";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { renderHeader } from "./components/header.js";

let data = {};

listen("widget-data", (event) => {
  try {
    data = JSON.parse(event.payload);
    render(data);
  } catch (e) { console.error(e); }
});

getCurrentWindow().onFocusChanged(({ payload: focused }) => {
  if (!focused) getCurrentWindow().hide();
});

function render(d) {
  renderHeader(document.getElementById("header"), d);
  // Placeholder for remaining cards (Tasks 7+8)
  document.getElementById("session-card").textContent = "Session: " + (d.rateLimits?.session?.percentUsed ?? "--") + "%";
  document.getElementById("weekly-card").textContent = "Weekly: " + (d.rateLimits?.weeklyAll?.percentUsed ?? "--") + "%";
  document.getElementById("health-card").textContent = "Health: " + (d.serviceStatus?.description ?? "--");
  document.getElementById("dumbness-card").textContent = "Score: " + (d.dumbness?.score ?? "--");
}
