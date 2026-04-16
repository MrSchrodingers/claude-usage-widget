mod tray;

use std::path::PathBuf;
use tauri::Emitter;

fn data_file_path() -> PathBuf {
    dirs::home_dir()
        .expect("could not resolve home directory")
        .join(".claude")
        .join("widget-data.json")
}

fn emit_data(app: &tauri::AppHandle) {
    let path = data_file_path();
    if let Ok(contents) = std::fs::read_to_string(&path) {
        let _ = app.emit("widget-data", contents);
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

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_clipboard_manager::init())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            tray::create_tray(app.handle())?;
            start_file_watcher(app.handle().clone());
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
