use crate::AppMailbox;
use serde_json::json;
use std::{collections::BTreeSet, sync::Arc};
use tauri::{AppHandle, Emitter, Manager};
pub async fn notify(mailbox: &Arc<AppMailbox>, app: &AppHandle) {
    let Ok(views) = mailbox.message_views().await else {
        return;
    };
    let messages = views
        .into_iter()
        .filter(|v| matches!(v.journey.as_str(), "published" | "integrated"))
        .map(|v| v.message)
        .collect::<Vec<_>>();
    let current = messages
        .iter()
        .filter(|m| m.origin.host != "prototype")
        .map(|m| m.id.clone())
        .collect::<BTreeSet<_>>();
    let saved = mailbox.setting("notified_messages").await.ok().flatten();
    let Some(saved) = saved else {
        let _ = mailbox
            .set_setting("notified_messages", json!(current))
            .await;
        return;
    };
    let previous = serde_json::from_value::<BTreeSet<String>>(saved).unwrap_or_default();
    let preferences = mailbox.setting("preferences").await.ok().flatten();
    let enabled = preferences.as_ref().is_none_or(|p| p["notif"] != "off");
    if enabled {
        for message in messages
            .into_iter()
            .filter(|m| current.contains(&m.id) && !previous.contains(&m.id))
        {
            let app = app.clone();
            let id = message.id;
            // ponytail: one native notification waiter per message; replace with a shared event loop if traffic exceeds the measured ~30 messages/day.
            std::thread::spawn(move || {
                let mut notification = notify_rust::Notification::new();
                notification
                    .summary("arkalabs Messenger")
                    .body(&format!("{} — {}", message.from, message.subject))
                    .action("default", "Voir le message");
                #[cfg(target_os = "windows")]
                notification.app_id("app.arkalabs.messenger");
                if let Ok(handle) = notification.show() {
                    handle.wait_for_action(|action| {
                        if action != "__closed" {
                            if let Some(window) = app.get_webview_window("main") {
                                let _ = window.show();
                                let _ = window.set_focus();
                            }
                            let _ = app.emit("open-message", id);
                        }
                    });
                }
            });
        }
    }
    if previous != current {
        let _ = mailbox
            .set_setting("notified_messages", json!(current))
            .await;
    }
}
