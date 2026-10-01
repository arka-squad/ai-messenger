use crate::domain::{
    journal::*,
    models::*,
    ports::{ExchangePort, PortError, RepositoryPort},
    Account, DomainError, Message,
};
use chrono::Utc;
use serde_json::{json, Value};
use std::{
    collections::{BTreeMap, BTreeSet},
    sync::{Arc, Mutex},
};
use tokio::sync::{Mutex as AsyncMutex, Notify};

pub(crate) mod directory;
mod receive;
mod requests;
mod views;
pub use requests::ApprovalView;

#[derive(Debug, thiserror::Error)]
pub enum MailboxError {
    #[error("{0}")]
    Infrastructure(#[from] PortError),
    #[error("{0}")]
    Domain(#[from] DomainError),
    #[error("{message}")]
    Refusal { reason: String, message: String },
}

pub struct MailboxService<R, E> {
    pub(crate) store: R,
    pub(crate) exchange: E,
    pub(crate) installation: String,
    pub(crate) machine: String,
    pub(crate) changes: AsyncMutex<()>,
    sync: AsyncMutex<()>,
    incidents: Mutex<BTreeMap<String, Incident>>,
    pub(crate) arrived: Arc<Notify>,
}

impl<R: RepositoryPort, E: ExchangePort> MailboxService<R, E> {
    #[cfg(test)]
    pub fn new(store: R, exchange: E) -> Self {
        Self::with_installation(store, exchange, "test-installation".into(), "Test".into())
    }
    pub fn with_installation(store: R, exchange: E, installation: String, machine: String) -> Self {
        Self {
            store,
            exchange,
            installation,
            machine,
            changes: AsyncMutex::new(()),
            sync: AsyncMutex::new(()),
            incidents: Mutex::new(BTreeMap::new()),
            arrived: Arc::new(Notify::new()),
        }
    }
    pub async fn schema_version(&self) -> Result<u8, MailboxError> {
        Ok(self.store.schema_version().await?)
    }
    pub(crate) async fn rows(&self, kind: &str) -> Result<Vec<Mutation>, MailboxError> {
        Ok(self
            .store
            .mutations(Some(kind), None)
            .await?
            .into_iter()
            .filter(|row| row.journey != "conflict")
            .map(|row| row.mutation)
            .collect())
    }
    pub(crate) async fn find(
        &self,
        kind: &str,
        id: &str,
    ) -> Result<Option<Mutation>, MailboxError> {
        Ok(self
            .rows(kind)
            .await?
            .into_iter()
            .find(|value| value.id() == id))
    }
    pub async fn setting(&self, key: &str) -> Result<Option<Value>, MailboxError> {
        Ok(self.store.setting(key).await?)
    }
    pub async fn set_setting(&self, key: &str, value: Value) -> Result<(), MailboxError> {
        Ok(self.store.set_setting(key, value).await?)
    }
    pub(crate) async fn publish(&self, mutation: Mutation) -> Result<String, MailboxError> {
        self.store.save(&mutation, "pending").await?;
        match self.exchange.deposit(ExchangeItem::Mutation(&mutation)) {
            Ok(proof) => {
                self.store
                    .set_journey(mutation.kind(), mutation.id(), "published")
                    .await?;
                self.clear_incident(&format!(
                    "publication:{}:{}",
                    mutation.kind(),
                    mutation.id()
                ));
                self.arrived.notify_waiters();
                Ok(proof)
            }
            Err(error) if error.0 == "mutation_en_conflit" => {
                self.store
                    .set_journey(mutation.kind(), mutation.id(), "conflict")
                    .await?;
                Err(refusal(
                    "mutation_en_conflit",
                    "Cette écriture porte un identifiant déjà utilisé. Rien n’a été remplacé.",
                ))
            }
            Err(error) => {
                self.incident(Incident {id:format!("publication:{}:{}",mutation.kind(),mutation.id()),kind:error.0.clone(),
                    message:if error.0=="emplacement_injoignable" {"La boîte partagée n’est pas joignable. Les écritures restent en attente et seront reprises dès son retour."}
                    else {"La boîte n’a pas confirmé cette écriture. Elle reste en attente ; Messenger réessaiera."}.into(),
                    message_id:Some(mutation.id().into())});
                Ok("pending".into())
            }
        }
    }
    pub async fn send(&self, mut message: MailMessage) -> Result<String, MailboxError> {
        let _guard = self.changes.lock().await;
        validate_message(&message)?;
        self.require_account(&message.from).await?;
        if self.find("legacy_message", &message.id).await?.is_some() {
            return Err(refusal("message_immuable","Cet identifiant appartient à un message repris du prototype. Publie une correction avec un nouvel identifiant."));
        }
        if let Some(parent) = &message.reply_to {
            if parent == &message.id {
                return Err(refusal(
                    "reponse_invalide",
                    "Un message ne peut pas répondre à lui-même.",
                ));
            }
            let previous = self.read(parent, &message.from).await?;
            if !self.is_recipient(&previous, &message.from).await?
                && self.resolve_account(&previous.from).await?
                    != self.resolve_account(&message.from).await?
            {
                return Err(refusal(
                    "en_copie",
                    "Un agent en copie voit le message, sans répondre ni accuser réception.",
                ));
            }
        }
        for address in message.to.iter().chain(&message.copies) {
            self.require_account(address).await?;
        }
        message.projects = message
            .to
            .iter()
            .chain(&message.copies)
            .chain(std::iter::once(&message.from))
            .filter_map(|address| {
                address
                    .split_once('@')
                    .map(|(_, project)| project.to_owned())
            })
            .collect::<BTreeSet<_>>()
            .into_iter()
            .collect();
        if let Some(reference) = &message.attachment {
            let bytes = self
                .store
                .blob(&reference.fingerprint)
                .await?
                .ok_or_else(|| {
                    refusal(
                        "piece_jointe_absente",
                        "La pièce jointe doit être fournie avant l’envoi.",
                    )
                })?;
            if hash(&bytes) != reference.fingerprint || bytes.len() as u64 != reference.size {
                return Err(refusal("piece_jointe_invalide","La pièce jointe locale ne correspond plus à son empreinte. Fournis-la de nouveau avant l’envoi."));
            }
            let mut outbox = self
                .setting("attachment_outbox")
                .await?
                .unwrap_or_else(|| json!({}));
            outbox[&reference.fingerprint] = json!(reference);
            self.set_setting("attachment_outbox", outbox.clone())
                .await?;
            if self
                .exchange
                .deposit(ExchangeItem::Attachment {
                    reference,
                    bytes: &bytes,
                })
                .is_ok()
            {
                outbox
                    .as_object_mut()
                    .expect("attachment outbox object")
                    .remove(&reference.fingerprint);
                self.set_setting("attachment_outbox", outbox).await?;
            }
        }
        self.publish(Mutation::Message(message)).await
    }
    pub async fn mark(&self, marking: Marking) -> Result<String, MailboxError> {
        let _guard = self.changes.lock().await;
        if !safe_id(&marking.id) || chrono::DateTime::parse_from_rfc3339(&marking.posed_at).is_err()
        {
            return Err(refusal(
                "marquage_invalide",
                "Le marquage doit avoir un identifiant et une date valides.",
            ));
        }
        self.require_account(&marking.by).await?;
        if self.find("marking", &marking.id).await? == Some(Mutation::Marking(marking.clone())) {
            return self.publish(Mutation::Marking(marking)).await;
        }
        let message = self
            .message(&marking.message_id)
            .await?
            .ok_or(DomainError::UnknownMessage)?;
        if !self.is_recipient(&message, &marking.by).await? {
            return Err(DomainError::NotRecipient.into());
        }
        let statuses = self.statuses().await?;
        let accounts = self.accounts().await?;
        let author = directory::resolve_address(&accounts, &marking.by)?;
        let current = message
            .to
            .iter()
            .filter(|address| {
                directory::resolve_address(&accounts, address).is_ok_and(|a| a == author)
            })
            .map(|address| {
                status_rank(
                    statuses
                        .get(&message.id)
                        .and_then(|s| s.get(address))
                        .map(String::as_str)
                        .unwrap_or("nouveau"),
                )
            })
            .min()
            .unwrap_or(0);
        if current
            > status_rank(match marking.status {
                MailStatus::Read => "lu",
                MailStatus::Done => "traité",
            })
        {
            return Err(DomainError::StatusBackwards.into());
        }
        self.publish(Mutation::Marking(marking)).await
    }
    pub async fn read(&self, id: &str, account: &str) -> Result<MailMessage, MailboxError> {
        self.require_account(account).await?;
        let message = self.message(id).await?.ok_or(DomainError::UnknownMessage)?;
        if !self.is_participant(&message, account).await? {
            return Err(DomainError::NotParticipant.into());
        }
        Ok(message)
    }
    pub async fn reply(
        &self,
        mut message: MailMessage,
        reply_to: &str,
    ) -> Result<String, MailboxError> {
        let parent = self.read(reply_to, &message.from).await?;
        if !self.is_recipient(&parent, &message.from).await?
            && self.resolve_account(&parent.from).await?
                != self.resolve_account(&message.from).await?
        {
            return Err(refusal(
                "en_copie",
                "Un agent en copie voit le message, sans répondre ni accuser réception.",
            ));
        }
        message.reply_to = Some(reply_to.into());
        self.send(message).await
    }
    pub async fn inbox(&self, account: &str) -> Result<Vec<MailMessage>, MailboxError> {
        self.require_account(account).await?;
        let effective = self.resolve_account(account).await?;
        let statuses = self.statuses().await?;
        let mut result = Vec::new();
        for message in self.messages().await? {
            let addressed = self.is_recipient(&message, &effective).await?;
            let copy = self.is_copy(&message, &effective).await?;
            let mut done = true;
            for recipient in &message.to {
                if self.resolve_account(recipient).await? == effective
                    && statuses
                        .get(&message.id)
                        .and_then(|s| s.get(recipient))
                        .is_none_or(|s| s != "traité")
                {
                    done = false;
                }
            }
            if (addressed && !done) || copy {
                result.push(message);
            }
        }
        Ok(result)
    }
    pub async fn put_attachment(
        &self,
        name: String,
        bytes: Vec<u8>,
    ) -> Result<Attachment, MailboxError> {
        if !Attachment::safe_name(&name) {
            return Err(refusal(
                "piece_jointe_invalide",
                "Le nom de la pièce jointe est invalide.",
            ));
        }
        let reference = Attachment {
            name,
            fingerprint: hash(&bytes),
            size: bytes.len() as u64,
        };
        self.store.save_blob(&reference, bytes).await?;
        Ok(reference)
    }
    pub async fn attachment(&self, id: &str) -> Result<Option<Vec<u8>>, MailboxError> {
        let message = self.message(id).await?.ok_or(DomainError::UnknownMessage)?;
        match message.attachment {
            Some(reference) => {
                Ok(self.store.blob(&reference.fingerprint).await?.filter(|b| {
                    hash(b) == reference.fingerprint && b.len() as u64 == reference.size
                }))
            }
            None => Ok(None),
        }
    }
    pub(crate) fn incident(&self, incident: Incident) {
        self.incidents
            .lock()
            .expect("incident lock")
            .insert(incident.id.clone(), incident);
    }
    pub(crate) fn clear_incident(&self, id: &str) {
        self.incidents.lock().expect("incident lock").remove(id);
    }
    pub fn incidents(&self) -> Vec<Incident> {
        self.incidents
            .lock()
            .expect("incident lock")
            .values()
            .cloned()
            .collect()
    }
}

pub(crate) fn now() -> String {
    Utc::now().to_rfc3339()
}
pub(crate) fn new_id() -> String {
    uuid::Uuid::new_v4().to_string()
}
pub(crate) fn hash(bytes: &[u8]) -> String {
    use sha2::{Digest, Sha256};
    format!("{:x}", Sha256::digest(bytes))
}
pub(crate) fn refusal(reason: &str, message: &str) -> MailboxError {
    MailboxError::Refusal {
        reason: reason.into(),
        message: message.into(),
    }
}
pub(crate) fn status_rank(status: &str) -> u8 {
    match status {
        "traité" => 2,
        "lu" => 1,
        _ => 0,
    }
}
pub(crate) fn single_line(value: &str) -> bool {
    !value.trim().is_empty() && !value.contains(['\r', '\n'])
}
pub(crate) fn validate_message(message: &MailMessage) -> Result<(), MailboxError> {
    if !safe_id(&message.id) {
        return Err(refusal(
            "identifiant_invalide",
            "L’identifiant du message est invalide.",
        ));
    }
    if !single_line(&message.subject) {
        return Err(refusal(
            "objet_invalide",
            "L’objet doit tenir sur une ligne non vide.",
        ));
    }
    if chrono::DateTime::parse_from_rfc3339(&message.emitted_at).is_err() {
        return Err(refusal(
            "date_invalide",
            "La date d’émission doit préciser son fuseau horaire.",
        ));
    }
    let sender = Account::enroll(&message.from, "agent")?;
    let recipients = message
        .to
        .iter()
        .map(|v| Account::enroll(v, "agent").map(|a| a.address().clone()))
        .collect::<Result<Vec<_>, _>>()?;
    let copies = message
        .copies
        .iter()
        .map(|v| Account::enroll(v, "agent").map(|a| a.address().clone()))
        .collect::<Result<Vec<_>, _>>()?;
    Message::compose(
        &message.id,
        &sender,
        recipients,
        copies,
        message.body.clone(),
    )?;
    if message.attachment.as_ref().is_some_and(|a| {
        !Attachment::safe_name(&a.name)
            || a.fingerprint.len() != 64
            || !a
                .fingerprint
                .bytes()
                .all(|c| c.is_ascii_digit() || matches!(c, b'a'..=b'f'))
    }) {
        return Err(refusal(
            "piece_jointe_invalide",
            "La référence de pièce jointe est invalide.",
        ));
    }
    Ok(())
}

#[cfg(test)]
#[path = "mailbox_tests.rs"]
mod tests;
#[cfg(test)]
#[path = "projects_tests.rs"]
mod projects_tests;
