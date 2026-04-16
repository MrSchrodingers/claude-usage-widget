mod tray;

use std::path::PathBuf;
use tauri::{Emitter, Manager};

fn data_file_path() -> PathBuf {
    dirs::home_dir()
        .expect("could not resolve home directory")
        .join(".claude")
        .join("widget-data.json")
}

const MAX_DATA_SIZE: u64 = 1_048_576; // 1 MB

fn emit_data(app: &tauri::AppHandle) {
    let path = data_file_path();
    // Security: check file size before reading to prevent memory exhaustion
    if let Ok(meta) = std::fs::metadata(&path) {
        if meta.len() > MAX_DATA_SIZE {
            eprintln!("[watcher] widget-data.json too large ({}B), skipping", meta.len());
            return;
        }
    }
    if let Ok(contents) = std::fs::read_to_string(&path) {
        // Security: validate JSON before emitting to WebView
        if serde_json::from_str::<serde_json::Value>(&contents).is_ok() {
            let _ = app.emit("widget-data", contents);
        } else {
            eprintln!("[watcher] widget-data.json is not valid JSON, skipping");
        }
    }
}

fn start_file_watcher(app: tauri::AppHandle) {
    let path = data_file_path();

    std::thread::spawn(move || {
        use notify::{Event, EventKind, RecursiveMode, Watcher};

        // Emit initial data
        emit_data(&app);

        let app_clone = app.clone();
        let mut watcher = notify::recommended_watcher(move |res: Result<Event, _>| {
            if let Ok(event) = res {
                if matches!(event.kind, EventKind::Modify(_) | EventKind::Create(_)) {
                    std::thread::sleep(std::time::Duration::from_millis(50));
                    emit_data(&app_clone);
                }
            }
        })
        .expect("failed to create file watcher");

        if let Some(parent) = path.parent() {
            let _ = watcher.watch(parent, RecursiveMode::NonRecursive);
        }

        loop {
            std::thread::sleep(std::time::Duration::from_secs(3600));
        }
    });
}

/// Register Super+Shift+C as a global shortcut to toggle the popup window.
/// This is a Linux/GNOME workaround: tray icon click events are not emitted
/// due to D-Bus/SNI limitations, so this shortcut provides an alternative.
fn register_global_shortcut(app: &tauri::AppHandle) {
    use tauri_plugin_global_shortcut::GlobalShortcutExt;

    let app_clone = app.clone();
    let result = app.global_shortcut()
        .on_shortcut("super+shift+c", move |_app, _shortcut, _event| {
            eprintln!("[shortcut] Super+Shift+C triggered!");
            if let Some(window) = app_clone.get_webview_window("popup") {
                let visible = window.is_visible().unwrap_or(false);
                eprintln!("[shortcut] popup visible={}, toggling...", visible);
                if visible {
                    let _ = window.hide();
                } else {
                    let _ = window.center();
                    let _ = window.show();
                    let _ = window.set_focus();
                }
            } else {
                eprintln!("[shortcut] ERROR: popup window not found!");
            }
        });

    match result {
        Ok(_) => eprintln!("[init] Global shortcut super+shift+c registered OK"),
        Err(e) => eprintln!("[init] Global shortcut FAILED: {}", e),
    }
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_clipboard_manager::init())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            eprintln!("[init] Setting up tray...");
            match tray::create_tray(app.handle()) {
                Ok(_) => eprintln!("[init] Tray created OK"),
                Err(e) => eprintln!("[init] Tray FAILED: {}", e),
            }
            eprintln!("[init] Starting file watcher...");
            start_file_watcher(app.handle().clone());
            eprintln!("[init] Registering global shortcut...");
            register_global_shortcut(app.handle());
            eprintln!("[init] Setup complete!");
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
