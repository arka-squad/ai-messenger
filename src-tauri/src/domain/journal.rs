use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};
use serde_json::Value;

use super::models::*;

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct AgentAccount {
    pub address: String,
    pub display: String,
    pub host: String,
    pub machine: String,
    pub role: String,
    pub active: bool,
    pub created_at: String,
    pub installation: String,
    #[serde(default)]
    pub project: Option<String>,
    #[serde(default)]
    pub merged_into: Option<String>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct Contact {
    pub alias: String,
    pub addresses: Vec<String>,
    pub note: String,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct Project {
    pub name: String,
    pub directory: String,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct SessionIdentity {
    pub session: String,
    pub provider: String,
    pub account: String,
    pub installation: String,
    pub project: Option<String>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct Event {
    pub id: String,
    pub emitted_at: String,
    pub installation: String,
    pub change: Change,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum Change {
    Account {
        account: AgentAccount,
    },
    Merge {
        source: String,
        target: String,
    },
    File {
        account: String,
        project: Option<String>,
    },
    Contacts {
        account: String,
        contacts: Vec<Contact>,
    },
    Collected {
        account: String,
    },
    Integrated {
        message_id: String,
        installation: String,
    },
    Reached {
        message_id: String,
        account: String,
        reachability: super::Reachability,
    },
    Taken {
        request_id: String,
    },
    AttachmentRequested {
        message_id: String,
        requested_by: String,
    },
    LegacyAttachment {
        message_id: String,
        reference: Attachment,
    },
    Imported {
        source_fingerprint: String,
        box_metadata: Value,
        manifest_metadata: Value,
    },
    Purged {
        removed: Vec<String>,
        dormant: Vec<String>,
    },
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(tag = "kind", content = "payload", rename_all = "snake_case")]
pub enum Mutation {
    Message(MailMessage),
    Marking(Marking),
    Approval(ApprovalRequest),
    Verdict(Verdict),
    Reorientation(Reorientation),
    Closure(RequestClosure),
    Event(Event),
    LegacyMessage(Value),
    LegacyAccount(Value),
}

impl Mutation {
    pub fn kind(&self) -> &'static str {
        match self {
            Self::Message(_) => "message",
            Self::Marking(_) => "marking",
            Self::Approval(_) => "approval",
            Self::Verdict(_) => "verdict",
            Self::Reorientation(_) => "reorientation",
            Self::Closure(_) => "closure",
            Self::Event(_) => "event",
            Self::LegacyMessage(_) => "legacy_message",
            Self::LegacyAccount(_) => "legacy_account",
        }
    }

    pub fn id(&self) -> &str {
        match self {
            Self::Message(v) => &v.id,
            Self::Marking(v) => &v.id,
            Self::Approval(v) => &v.id,
            Self::Verdict(v) => &v.request_id,
            Self::Reorientation(v) => &v.request_id,
            Self::Closure(v) => &v.id,
            Self::Event(v) => &v.id,
            Self::LegacyMessage(v) => v["id"].as_str().unwrap_or(""),
            Self::LegacyAccount(v) => v["nom"].as_str().unwrap_or(""),
        }
    }

    pub fn emitted_at(&self) -> &str {
        match self {
            Self::Message(v) => &v.emitted_at,
            Self::Marking(v) => &v.posed_at,
            Self::Approval(v) => &v.opened_at,
            Self::Verdict(v) => &v.rendered_at,
            Self::Reorientation(v) => &v.redirected_at,
            Self::Closure(v) => &v.closed_at,
            Self::Event(v) => &v.emitted_at,
            Self::LegacyMessage(v) => v["date"].as_str().unwrap_or(""),
            Self::LegacyAccount(v) => v["cree"].as_str().unwrap_or(""),
        }
    }
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct StoredMutation {
    pub mutation: Mutation,
    pub journey: String,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct ReadCheckpoint {
    pub id: String,
    pub machine: String,
    pub seen_at: String,
    pub integrated: BTreeMap<String, String>,
    #[serde(default)]
    pub missed_before: Option<String>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct Incident {
    pub id: String,
    pub kind: String,
    pub message: String,
    pub message_id: Option<String>,
}

#[derive(Clone, Debug, Default, Deserialize, Serialize)]
pub struct ExchangeBatch {
    pub mutations: Vec<Mutation>,
    pub attachments: BTreeMap<String, Vec<u8>>,
    pub checkpoints: Vec<ReadCheckpoint>,
    pub incidents: Vec<Incident>,
}

pub enum ExchangeItem<'a> {
    Mutation(&'a Mutation),
    Attachment {
        reference: &'a Attachment,
        bytes: &'a [u8],
    },
    Checkpoint(&'a ReadCheckpoint),
}

pub fn canonical_bytes<T: Serialize>(value: &T) -> Result<Vec<u8>, serde_json::Error> {
    fn ordered(value: Value) -> Value {
        match value {
            Value::Object(map) => Value::Object(
                map.into_iter()
                    .collect::<BTreeMap<_, _>>()
                    .into_iter()
                    .map(|(key, value)| (key, ordered(value)))
                    .collect(),
            ),
            Value::Array(values) => Value::Array(values.into_iter().map(ordered).collect()),
            value => value,
        }
    }
    serde_json::to_vec(&ordered(serde_json::to_value(value)?))
}
