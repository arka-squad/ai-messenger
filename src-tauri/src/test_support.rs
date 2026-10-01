use crate::{
    domain::{models::*, ports::*},
    exchange::DirectoryExchange,
    mailbox::MailboxService,
    storage::LocalStore,
};
use std::{fs, path::PathBuf};
pub struct Temporary(pub PathBuf);
impl Temporary {
    pub fn new() -> Self {
        let p = std::env::temp_dir().join(format!("messenger-test-{}", uuid::Uuid::new_v4()));
        fs::create_dir_all(&p).unwrap();
        Self(p)
    }
    pub async fn mailbox(&self, name: &str) -> MailboxService<LocalStore, DirectoryExchange> {
        let shared = self.0.join("shared");
        fs::create_dir_all(&shared).unwrap();
        let store = LocalStore::open(self.0.join(name)).await.unwrap();
        MailboxService::with_installation(
            store,
            DirectoryExchange::new(shared),
            name.into(),
            format!("machine-{name}"),
        )
    }
}
impl Drop for Temporary {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}
pub async fn account<R: RepositoryPort, E: ExchangePort>(
    box_: &MailboxService<R, E>,
    name: &str,
) -> String {
    box_.enroll("test", name, name, "développeur", Some("project".into()))
        .await
        .unwrap()["identity"]["account"]
        .as_str()
        .unwrap()
        .into()
}
/// Calls an MCP tool as `provider`/`session` and returns the whole tool result (isError included).
pub async fn tool<R: RepositoryPort, E: ExchangePort>(
    mailbox: &MailboxService<R, E>,
    provider: &str,
    session: &str,
    name: &str,
    arguments: serde_json::Value,
) -> serde_json::Value {
    let request = serde_json::json!({"method":"tools/call","params":{"name":name,"arguments":arguments}});
    let route = crate::mcp::RouteContext { provider, session, live_session: false };
    crate::mcp::dispatch(mailbox, &request, serde_json::json!(1), Some(route)).await["result"].clone()
}
/// Serves the local MCP and hook endpoints on a free port, as the app does on 47652.
pub async fn serve_mcp(
    mailbox: std::sync::Arc<MailboxService<LocalStore, DirectoryExchange>>,
) -> (u16, tokio::task::JoinHandle<()>) {
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let port = listener.local_addr().unwrap().port();
    let router = crate::mcp::router(mailbox, port);
    (port, tokio::spawn(async move { axum::serve(listener, router).await.unwrap() }))
}
/// A raw local POST: (status, response head, JSON body or null).
pub async fn post(
    port: u16,
    path: &str,
    headers: &[(&str, &str)],
    body: serde_json::Value,
) -> (u16, String, serde_json::Value) {
    let head = headers.iter().map(|(k, v)| format!("{k}: {v}\r\n")).collect::<String>();
    let path = path.to_owned();
    tokio::task::spawn_blocking(move || {
        use std::io::{Read, Write};
        let body = body.to_string();
        let mut connection = std::net::TcpStream::connect(("127.0.0.1", port)).unwrap();
        connection.set_read_timeout(Some(std::time::Duration::from_secs(15))).unwrap();
        write!(connection, "POST {path} HTTP/1.1\r\nContent-Type: application/json\r\nConnection: close\r\n{head}Content-Length: {}\r\n\r\n{body}", body.len()).unwrap();
        let mut response = String::new();
        connection.read_to_string(&mut response).unwrap();
        let (head, body) = response.split_once("\r\n\r\n").unwrap_or((&response, ""));
        let status = head.split_whitespace().nth(1).and_then(|s| s.parse().ok()).unwrap_or(0);
        (status, head.to_owned(), serde_json::from_str(body).unwrap_or(serde_json::Value::Null))
    })
    .await
    .unwrap()
}
pub fn message(id: &str, from: &str, to: &str) -> MailMessage {
    MailMessage {
        id: id.into(),
        emitted_at: crate::mailbox::now(),
        from: from.into(),
        to: vec![to.into()],
        copies: vec![],
        subject: "Travail à relire".into(),
        body: vec!["Information uniquement.".into()],
        attachment: None,
        reply_to: None,
        projects: vec![],
        origin: Origin {
            host: "test".into(),
            session: "test-session".into(),
        },
    }
}
pub fn request(id: &str, by: &str) -> ApprovalRequest {
    ApprovalRequest {
        id: id.into(),
        opened_by: by.into(),
        gesture: "Publier le résultat".into(),
        scope: "Projet".into(),
        reversible: "Oui".into(),
        if_refused: "Conserver localement".into(),
        why_now: "Résultat relu".into(),
        opened_at: crate::mailbox::now(),
        nature: RequestNature::Validation,
    }
}
pub fn marking(id: &str, message: &str, by: &str, status: MailStatus) -> Marking {
    Marking {
        id: id.into(),
        message_id: message.into(),
        by: by.into(),
        status,
        posed_at: crate::mailbox::now(),
    }
}
