use std::sync::Mutex;
use tauri::{Manager, RunEvent};
use tauri_plugin_shell::ShellExt;

type BackendChild = Mutex<Option<tauri_plugin_shell::process::CommandChild>>;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let sidecar = app
                .shell()
                .sidecar("circuit-simulator-backend")
                .expect("backend sidecar binary not found — run scripts/build-desktop.sh first");

            let (_rx, child) = sidecar
                .spawn()
                .expect("failed to start Python backend");

            app.manage(Mutex::new(Some(child)));
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error building tauri application");

    app.run(|app_handle, event| {
        if let RunEvent::Exit = event {
            // Kill the Python backend process when the app exits
            if let Some(state) = app_handle.try_state::<BackendChild>() {
                if let Ok(mut guard) = state.lock() {
                    if let Some(child) = guard.take() {
                        let _ = child.kill();
                    }
                }
            }
        }
    });
}
