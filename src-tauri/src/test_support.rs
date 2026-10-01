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
