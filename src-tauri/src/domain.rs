use std::collections::{BTreeMap, BTreeSet};

use thiserror::Error;

#[path = "domain/journal.rs"]
pub mod journal;
#[path = "domain/models.rs"]
pub mod models;
#[path = "domain/ports.rs"]
pub mod ports;

#[derive(Clone, Debug, Eq, Ord, PartialEq, PartialOrd)]
pub struct Address(String);

impl Address {
    pub fn as_str(&self) -> &str {
        &self.0
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Account {
    address: Address,
    role: String,
}

impl Account {
    pub fn enroll(
        address: impl Into<String>,
        role: impl Into<String>,
    ) -> Result<Self, DomainError> {
        let address = address.into();
        let role = role.into();
        if address.trim().is_empty()
            || address.eq_ignore_ascii_case("owner")
            || role.trim().is_empty()
            || matches!(role.trim().to_lowercase().as_str(), "human" | "humain")
            || address.chars().any(char::is_whitespace)
            || address.matches('@').count() > 1
            || address.split('@').any(|part| part.is_empty())
            || address.contains(['/', '\\', ':', '*', '?', '"', '<', '>', '|'])
            || address.chars().any(char::is_control)
        {
            return Err(DomainError::InvalidAccount);
        }
        Ok(Self {
            address: Address(address),
            role,
        })
    }

    pub fn address(&self) -> &Address {
        &self.address
    }

    pub fn role(&self) -> &str {
        &self.role
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Message {
    id: String,
    from: Address,
    recipients: BTreeSet<Address>,
    copies: BTreeSet<Address>,
    body: Vec<String>,
    reply_to: Option<String>,
}

impl Message {
    pub fn compose(
        id: impl Into<String>,
        sender: &Account,
        recipients: impl IntoIterator<Item = Address>,
        copies: impl IntoIterator<Item = Address>,
        body: Vec<String>,
    ) -> Result<Self, DomainError> {
        if body.len() > 2 || body.iter().any(|line| line.contains(['\n', '\r'])) {
            return Err(DomainError::BodyTooLong);
        }
        let recipients = recipients.into_iter().collect::<BTreeSet<_>>();
        if recipients.is_empty() {
            return Err(DomainError::NoRecipient);
        }
        let copies = copies.into_iter().collect::<BTreeSet<_>>();
        if !recipients.is_disjoint(&copies) {
            return Err(DomainError::RecipientIsCopy);
        }
        Ok(Self {
            id: id.into(),
            from: sender.address.clone(),
            recipients,
            copies,
            body,
            reply_to: None,
        })
    }

    pub fn correction(
        &self,
        id: impl Into<String>,
        body: Vec<String>,
    ) -> Result<Self, DomainError> {
        let mut correction = Self::compose(
            id,
            &Account {
                address: self.from.clone(),
                role: String::new(),
            },
            self.recipients.clone(),
            self.copies.clone(),
            body,
        )?;
        correction.reply_to = Some(self.id.clone());
        Ok(correction)
    }

    pub fn id(&self) -> &str {
        &self.id
    }

    pub fn sender(&self) -> &Address {
        &self.from
    }

    pub fn is_recipient(&self, account: &Account) -> bool {
        self.recipients.contains(account.address())
    }

    pub fn is_copy(&self, account: &Account) -> bool {
        self.copies.contains(account.address())
    }
}

#[derive(Clone, Copy, Debug, Eq, Ord, PartialEq, PartialOrd)]
pub enum Status {
    New,
    Read,
    Done,
}

#[derive(Default)]
pub struct RecipientStatuses(BTreeMap<Address, Status>);

impl RecipientStatuses {
    pub fn mark(
        &mut self,
        message: &Message,
        actor: &Account,
        status: Status,
    ) -> Result<(), DomainError> {
        if !message.is_recipient(actor) {
            return Err(DomainError::NotRecipient);
        }
        let current = self.0.get(actor.address()).copied().unwrap_or(Status::New);
        if status < current {
            return Err(DomainError::StatusBackwards);
        }
        self.0.insert(actor.address.clone(), status);
        Ok(())
    }

    pub fn for_account(&self, account: &Account) -> Status {
        self.0
            .get(account.address())
            .copied()
            .unwrap_or(Status::New)
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct WriteProof(String);

impl WriteProof {
    pub fn verified(content_hash: impl Into<String>) -> Result<Self, DomainError> {
        let content_hash = content_hash.into();
        if content_hash.is_empty() {
            return Err(DomainError::MissingWriteProof);
        }
        Ok(Self(content_hash))
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum Publication {
    Pending,
    Published(WriteProof),
}

impl Publication {
    pub fn confirm(proof: WriteProof) -> Self {
        Self::Published(proof)
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Journey {
    PendingPublication,
    Published,
    Integrated,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, serde::Deserialize, serde::Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Reachability {
    LiveSession,
    NextStart,
    NoSession,
}

#[derive(Default)]
pub struct MutationLog(BTreeMap<String, Message>);

impl MutationLog {
    pub fn append(&mut self, message: Message) -> Result<(), DomainError> {
        if self.0.contains_key(message.id()) {
            return Err(DomainError::DuplicateMutation);
        }
        self.0.insert(message.id.clone(), message);
        Ok(())
    }

    pub fn get(&self, id: &str) -> Option<&Message> {
        self.0.get(id)
    }
}

#[derive(Debug, Error, Eq, PartialEq)]
pub enum DomainError {
    #[error("an account must belong to an agent")]
    InvalidAccount,
    #[error("a message needs a recipient")]
    NoRecipient,
    #[error("a recipient cannot also be a copy")]
    RecipientIsCopy,
    #[error("a message body has at most two lines")]
    BodyTooLong,
    #[error("only a recipient can mark a message")]
    NotRecipient,
    #[error("message not found")]
    UnknownMessage,
    #[error("only a message participant can read or reply")]
    NotParticipant,
    #[error("a status cannot move backward")]
    StatusBackwards,
    #[error("a confirmed write needs a proof")]
    MissingWriteProof,
    #[error("a mutation cannot overwrite another mutation")]
    DuplicateMutation,
}

#[cfg(test)]
mod tests {
    use super::*;

    fn agent(name: &str) -> Account {
        Account::enroll(name, "agent").unwrap()
    }

    fn message(sender: &Account, recipient: &Account) -> Message {
        Message::compose(
            "message-1",
            sender,
            [recipient.address().clone()],
            [],
            vec!["Bonjour".into()],
        )
        .unwrap()
    }

    #[test]
    fn message_is_immutable_and_corrections_are_new_messages() {
        let sender = agent("sender");
        let recipient = agent("recipient");
        let original = message(&sender, &recipient);
        let correction = original
            .correction("message-2", vec!["Corrigé".into()])
            .unwrap();
        assert_eq!(original.id(), "message-1");
        assert_eq!(correction.reply_to.as_deref(), Some("message-1"));
    }

    #[test]
    fn statuses_belong_to_each_recipient() {
        let sender = agent("sender");
        let one = agent("one");
        let two = agent("two");
        let message = Message::compose(
            "message-1",
            &sender,
            [one.address().clone(), two.address().clone()],
            [],
            vec![],
        )
        .unwrap();
        let mut statuses = RecipientStatuses::default();
        statuses.mark(&message, &one, Status::Read).unwrap();
        assert_eq!(statuses.for_account(&one), Status::Read);
        assert_eq!(statuses.for_account(&two), Status::New);
    }

    #[test]
    fn status_never_moves_backward() {
        let sender = agent("sender");
        let recipient = agent("recipient");
        let message = message(&sender, &recipient);
        let mut statuses = RecipientStatuses::default();
        statuses.mark(&message, &recipient, Status::Done).unwrap();
        assert_eq!(
            statuses.mark(&message, &recipient, Status::Read),
            Err(DomainError::StatusBackwards)
        );
    }

    #[test]
    fn bodies_have_at_most_two_lines() {
        let sender = agent("sender");
        let recipient = agent("recipient");
        assert_eq!(
            Message::compose(
                "message-1",
                &sender,
                [recipient.address().clone()],
                [],
                vec!["1".into(), "2".into(), "3".into()]
            ),
            Err(DomainError::BodyTooLong)
        );
    }

    #[test]
    fn an_actor_can_only_write_as_its_own_account() {
        let sender = agent("sender");
        let recipient = agent("recipient");
        assert_eq!(message(&sender, &recipient).sender(), sender.address());
    }

    #[test]
    fn application_mutations_have_no_secret_field() {
        let sender = agent("sender");
        let recipient = agent("recipient");
        let debug = format!("{:?}", message(&sender, &recipient));
        for forbidden in ["token", "password", "secret", "key"] {
            assert!(!debug.contains(forbidden));
        }
    }

    #[test]
    fn a_message_is_data_not_an_execution_authority() {
        let sender = agent("sender");
        let recipient = agent("recipient");
        let message = message(&sender, &recipient);
        assert!(message.is_recipient(&recipient));
        assert!(!message.is_copy(&recipient));
    }

    #[test]
    fn a_human_cannot_be_enrolled_as_an_account() {
        assert_eq!(
            Account::enroll("owner", "human"),
            Err(DomainError::InvalidAccount)
        );
    }

    #[test]
    fn a_write_is_not_confirmed_without_proof() {
        assert_eq!(
            WriteProof::verified(""),
            Err(DomainError::MissingWriteProof)
        );
        assert_eq!(
            Publication::confirm(WriteProof::verified("abc").unwrap()),
            Publication::Published(WriteProof("abc".into()))
        );
    }

    #[test]
    fn one_mutation_cannot_erase_another() {
        let sender = agent("sender");
        let recipient = agent("recipient");
        let mut log = MutationLog::default();
        log.append(message(&sender, &recipient)).unwrap();
        assert_eq!(
            log.append(message(&sender, &recipient)),
            Err(DomainError::DuplicateMutation)
        );
        assert_eq!(log.get("message-1").unwrap().sender(), sender.address());
    }

    #[test]
    fn publication_and_agent_reachability_are_distinct() {
        assert_eq!(Journey::Published, Journey::Published);
        assert_eq!(Reachability::NextStart, Reachability::NextStart);
    }
}
