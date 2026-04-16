import { listen } from "@tauri-apps/api/event";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { renderHeader } from "./components/header.js";
import { renderSessionCard } from "./components/session-card.js";
import { renderWeeklyCard } from "./components/weekly-card.js";
import { renderCreditsCard } from "./components/credits-card.js";
import { renderHealthCard } from "./components/health-card.js";
import { renderDumbnessCard } from "./components/dumbness-card.js";
import { renderActivityCard } from "./components/activity-card.js";
import { renderQuickActions } from "./components/quick-actions.js";
import { renderTrendChart } from "./components/trend-chart.js";
import { renderPeakHours } from "./components/peak-hours.js";
import { renderFooter } from "./components/footer.js";

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
  renderCreditsCard(document.getElementById("credits-card"), d);
  renderHealthCard(document.getElementById("health-card"), d);
  renderDumbnessCard(document.getElementById("dumbness-card"), d);
  renderActivityCard(document.getElementById("activity-card"), d);
  renderQuickActions(document.getElementById("quick-actions"), d);
  renderTrendChart(document.getElementById("trend-chart"), d);
  renderPeakHours(document.getElementById("peak-hours"), d);
  renderFooter(document.getElementById("footer"), d);
}
