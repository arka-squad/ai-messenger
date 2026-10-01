use super::HttpState;
use crate::{
    domain::ports::{ExchangePort, RepositoryPort},
    mailbox::{MailboxError, MailboxService},
};
use axum::{
    body::Bytes,
    extract::State,
    http::{HeaderMap, StatusCode},
    response::{IntoResponse, Response},
    Json,
};
use serde_json::{json, Value};

/// Hooks run on this computer only: never a browser Origin, always the exact local Host.
pub(super) fn hook_headers(headers: &HeaderMap, port: u16) -> bool {
    headers.get("origin").is_none()
        && super::local_headers(headers)
        && headers
            .get("host")
            .and_then(|v| v.to_str().ok())
            .is_some_and(|host| host == format!("127.0.0.1:{port}"))
}

pub(super) async fn hook<R: RepositoryPort, E: ExchangePort>(
    State(state): State<HttpState<R, E>>,
    headers: HeaderMap,
    body: Bytes,
) -> Response {
    if !hook_headers(&headers, state.port) {
        return StatusCode::FORBIDDEN.into_response();
    }
    let Ok(request) = serde_json::from_slice::<Value>(&body) else {
        return StatusCode::BAD_REQUEST.into_response();
    };
    // A hook must never block its host: an unreadable mailbox simply says nothing.
    let notice = notice(&state.mailbox, &request).await.unwrap_or(None);
    Json(json!({ "notice": notice })).into_response()
}

/// The one line a host hook injects at session start, on each prompt or at end of turn. No secret.
pub(crate) async fn notice<R: RepositoryPort, E: ExchangePort>(
    mailbox: &MailboxService<R, E>,
    request: &Value,
) -> Result<Option<String>, MailboxError> {
    let Some(provider) = request["provider"]
        .as_str()
        .filter(|p| matches!(*p, "claude-code" | "codex" | "kimi"))
    else {
        return Ok(None);
    };
    let start = request["event"] == "SessionStart";
    let cwd = request["cwd"]
        .as_str()
        .unwrap_or_default()
        .chars()
        .filter(|c| !c.is_control())
        .collect::<String>();
    let shown = if cwd.trim().is_empty() { "<chemin absolu de ton dossier de travail>" } else { cwd.as_str() };
    let shared = mailbox.shared(provider, &cwd).await?;
    if shared.len() > 1 {
        let names = shared.iter().map(|a| a.address.as_str()).collect::<Vec<_>>().join(", ");
        if start {
            return Ok(Some(format!("Messenger : plusieurs comptes sont retenus pour ce dossier ({names}) : qui_suis_je (dossier={shown}), puis reprends le tien avec me_reconnaitre ou m_enroler (même tâche).")));
        }
        let mut counts = Vec::new();
        for account in &shared {
            let waiting = mailbox.inbox_entries(&account.address).await?.iter().filter(|(_, nouveau, _)| *nouveau).count();
            if waiting > 0 {
                counts.push(format!("{} ({waiting})", account.address));
            }
        }
        return Ok((!counts.is_empty()).then(|| format!("MAIL — nouveau courrier : {} ; relève depuis ton propre compte.", counts.join(", "))));
    }
    let Some(account) = mailbox.remembered(provider, &cwd).await? else {
        if !start {
            return Ok(None);
        }
        // A parent folder's account is only a hint: this session may be another agent.
        if let Some((parent, account)) = mailbox.remembered_parent(provider, &cwd).await? {
            let address = account.address;
            return Ok(Some(format!("Messenger : aucun compte pour ce dossier ; le dossier parent {parent} est retenu pour {address}. Si c’est ton compte : qui_suis_je (dossier={shown}), puis m_enroler avec la même tâche ou me_reconnaitre. Sinon, si tu dois échanger du courrier entre agents : m_enroler (tache, role, project, dossier).")));
        }
        return Ok(Some(no_account(shown)));
    };
    let waiting = mailbox
        .inbox_entries(&account.address)
        .await?
        .iter()
        .filter(|(_, nouveau, _)| *nouveau)
        .count();
    let address = account.address;
    if waiting > 0 {
        return Ok(Some(format!("MAIL — {waiting} nouveau(x) courrier(s) pour {address} : appelle relever (outils arkalabs-messenger-app).")));
    }
    Ok(start.then(|| format!("Messenger : tu es {address} ; aucun nouveau courrier.")))
}

/// Conditional: most sessions on this computer never exchange mail and must not enrol for nothing.
pub(crate) fn no_account(cwd: &str) -> String {
    format!("Messenger : aucun compte pour ce dossier. Si tu dois échanger du courrier entre agents : qui_suis_je (dossier={cwd}), puis m_enroler (tache, role, project, dossier).")
}
