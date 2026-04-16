import { listen } from "@tauri-apps/api/event";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { renderHeader } from "./components/header.js";
import { renderSessionCard } from "./components/session-card.js";
import { renderWeeklyCard } from "./components/weekly-card.js";
import { renderHealthCard } from "./components/health-card.js";
import { renderDumbnessCard } from "./components/dumbness-card.js";

let data = {};

listen("widget-data", (event) => {
  try {
    data = JSON.parse(event.payload);
    render(data);
  } catch (e) {
    console.error("Failed to parse widget data:", e);
  }
});

getCurrentWindow().onFocusChanged(({ payload: focused }) => {
  if (!focused) getCurrentWindow().hide();
});

function render(d) {
  renderHeader(document.getElementById("header"), d);
  renderSessionCard(document.getElementById("session-card"), d);
  renderWeeklyCard(document.getElementById("weekly-card"), d);
  renderHealthCard(document.getElementById("health-card"), d);
  renderDumbnessCard(document.getElementById("dumbness-card"), d);
}
