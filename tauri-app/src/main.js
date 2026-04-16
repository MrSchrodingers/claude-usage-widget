import { listen } from "@tauri-apps/api/event";
import { getCurrentWindow } from "@tauri-apps/api/window";

let data = {};

listen("widget-data", (event) => {
  try {
    data = JSON.parse(event.payload);
    render(data);
  } catch (e) {
    console.error("Failed to parse widget data:", e);
  }
});

// Close popup when it loses focus
getCurrentWindow().onFocusChanged(({ payload: focused }) => {
  if (!focused) {
    getCurrentWindow().hide();
  }
});

function render(d) {
  const app = document.getElementById("app");
  const preview = JSON.stringify(d, null, 2).slice(0, 500);
  app.textContent = preview + "...";
  app.style.cssText = "color:#ccc;padding:16px;font-size:12px;white-space:pre;font-family:monospace;";
}
