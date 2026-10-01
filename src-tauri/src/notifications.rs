use crate::AppMailbox;
use serde_json::json;
use std::{collections::BTreeSet, sync::Arc};
use tauri::{AppHandle, Emitter, Manager};

/// Something new for the owner: a message, or a request an agent addressed to them.
pub(crate) enum Arrival {
    Message { id: String, from: String, subject: String },
    Request { id: String, opened_by: String, gesture: String, intervention: bool },
}
#[derive(Debug, PartialEq)]
pub(crate) struct Toast {
    pub summary: String,
    pub body: String,
    pub label: &'static str,
    /// The event the window receives on click, with the item it opens.
    pub open: Option<(&'static str, String)>,
}
/// More than three arrivals at once become a single notification.
pub(crate) fn toasts(arrivals: Vec<Arrival>) -> Vec<Toast> {
    if arrivals.len() > 3 {
        let messages = arrivals.iter().filter(|a| matches!(a, Arrival::Message { .. })).count();
        let requests = arrivals.len() - messages;
        let parts = [(messages, "message(s)"), (requests, "demande(s) pour toi")]
            .iter()
            .filter(|(n, _)| *n > 0)
            .map(|(n, what)| format!("{n} {what}"))
            .collect::<Vec<_>>();
        return vec![Toast {
            summary: "arkalabs Messenger".into(),
            body: format!("{} nouveautés : {}.", arrivals.len(), parts.join(", ")),
            label: "Ouvrir Messenger",
            open: None,
        }];
    }
    arrivals
        .into_iter()
        .map(|arrival| match arrival {
            Arrival::Message { id, from, subject } => Toast {
                summary: "arkalabs Messenger".into(),
                body: format!("{from} — {subject}"),
                label: "Voir le message",
                open: Some(("open-message", id)),
            },
            Arrival::Request { id, opened_by, gesture, intervention } => Toast {
                summary: if intervention {
                    format!("{opened_by} demande ton intervention")
                } else {
                    format!("{opened_by} demande ta validation")
                },
                body: gesture,
                label: "Voir la demande",
                open: Some(("open-request", id)),
            },
        })
        .collect()
}
/// The ids seen at the previous pass; the first pass records what exists without announcing it.
async fn previous(mailbox: &AppMailbox, key: &str, current: &BTreeSet<String>) -> Option<BTreeSet<String>> {
    match mailbox.setting(key).await.ok().flatten() {
        Some(saved) => Some(serde_json::from_value::<BTreeSet<String>>(saved).unwrap_or_default()),
        None => {
            let _ = mailbox.set_setting(key, json!(current)).await;
            None
        }
    }
}
pub async fn notify(mailbox: &Arc<AppMailbox>, app: &AppHandle) {
    let Ok(views) = mailbox.message_views().await else {
        return;
    };
    let Ok(requests) = mailbox.approvals(None).await else {
        return;
    };
    let messages = views
        .into_iter()
        .filter(|v| matches!(v.journey.as_str(), "published" | "integrated"))
        .map(|v| v.message)
        .filter(|m| m.origin.host != "prototype")
        .collect::<Vec<_>>();
    let current = messages.iter().map(|m| m.id.clone()).collect::<BTreeSet<_>>();
    let asked = requests.iter().map(|r| r.request.id.clone()).collect::<BTreeSet<_>>();
    let seen_messages = previous(mailbox, "notified_messages", &current).await;
    let seen_requests = previous(mailbox, "notified_requests", &asked).await;
    let mut arrivals = Vec::new();
    if let Some(seen) = &seen_messages {
        for message in messages.into_iter().filter(|m| !seen.contains(&m.id)) {
            arrivals.push(Arrival::Message { id: message.id, from: message.from, subject: message.subject });
        }
    }
    if let Some(seen) = &seen_requests {
        for view in requests.into_iter().filter(|r| !seen.contains(&r.request.id)) {
            // Only requests still waiting for the owner: no decision, closure or take-over yet.
            if view.verdict.is_none() && view.reorientation.is_none() && view.closure.is_none() && !view.taken {
                let intervention = view.effective_nature == crate::domain::models::RequestNature::Intervention;
                let request = view.request;
                arrivals.push(Arrival::Request { id: request.id, opened_by: request.opened_by, gesture: request.gesture, intervention });
            }
        }
    }
    let preferences = mailbox.setting("preferences").await.ok().flatten();
    if preferences.as_ref().is_none_or(|p| p["notif"] != "off") {
        for toast in toasts(arrivals) {
            show(app, toast);
        }
    }
    for (key, seen, now) in [("notified_messages", seen_messages, current), ("notified_requests", seen_requests, asked)] {
        if seen.is_some_and(|seen| seen != now) {
            let _ = mailbox.set_setting(key, json!(now)).await;
        }
    }
}
fn show(app: &AppHandle, toast: Toast) {
    let app = app.clone();
    // ponytail: one native notification waiter per toast; bursts are grouped above three arrivals.
    std::thread::spawn(move || {
        let mut notification = notify_rust::Notification::new();
        notification
            .summary(&toast.summary)
            .body(&toast.body)
            .action("default", toast.label);
        #[cfg(target_os = "windows")]
        notification.app_id("app.arkalabs.messenger");
        if let Ok(handle) = notification.show() {
            handle.wait_for_action(|action| {
                if action != "__closed" {
                    if let Some(window) = app.get_webview_window("main") {
                        let _ = window.show();
                        let _ = window.set_focus();
                    }
                    if let Some((event, id)) = toast.open {
                        let _ = app.emit(event, id);
                    }
                }
            });
        }
    });
}

#[cfg(test)]
mod tests {
    use super::*;
    fn request(id: &str) -> Arrival {
        Arrival::Request { id: id.into(), opened_by: "cd-agent-a-win".into(), gesture: "Publier".into(), intervention: false }
    }
    #[test]
    fn owner_requests_are_announced_and_bursts_are_grouped() {
        let single = toasts(vec![request("r1")]);
        assert_eq!(single[0].summary, "cd-agent-a-win demande ta validation");
        assert_eq!(single[0].open, Some(("open-request", "r1".into())));
        let message = Arrival::Message { id: "m".into(), from: "a".into(), subject: "Objet".into() };
        assert_eq!(toasts(vec![message, request("r1"), request("r2")]).len(), 3);
        let burst = (0..4).map(|i| request(&format!("r{i}"))).collect();
        let grouped = toasts(burst);
        assert_eq!(grouped.len(), 1);
        assert_eq!(grouped[0].body, "4 nouveautés : 4 demande(s) pour toi.");
        assert_eq!(grouped[0].open, None);
    }
}
