use serde::{Deserialize, Serialize};

use super::Status;
pub fn safe_id(id: &str) -> bool {
    !id.is_empty()
        && id.len() <= 200
        && id != "."
        && id != ".."
        && !id.contains(['/', '\\', ':', '*', '?', '"', '<', '>', '|'])
        && !id.chars().any(char::is_control)
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct Attachment {
    pub name: String,
    pub fingerprint: String,
    pub size: u64,
}
impl Attachment {
    pub fn safe_name(name: &str) -> bool {
        let stem = name
            .split('.')
            .next()
            .unwrap_or_default()
            .to_ascii_uppercase();
        !name.trim().is_empty()
            && name.len() <= 240
            && !name.ends_with(['.', ' '])
            && !name.contains(['/', '\\', ':', '*', '?', '"', '<', '>', '|'])
            && !name.chars().any(char::is_control)
            && !matches!(
                stem.as_str(),
                "CON"
                    | "PRN"
                    | "AUX"
                    | "NUL"
                    | "COM1"
                    | "COM2"
                    | "COM3"
                    | "COM4"
                    | "COM5"
                    | "COM6"
                    | "COM7"
                    | "COM8"
                    | "COM9"
                    | "LPT1"
                    | "LPT2"
                    | "LPT3"
                    | "LPT4"
                    | "LPT5"
                    | "LPT6"
                    | "LPT7"
                    | "LPT8"
                    | "LPT9"
            )
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct Origin {
    pub host: String,
    pub session: String,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct MailMessage {
    pub id: String,
    pub emitted_at: String,
    pub from: String,
    pub to: Vec<String>,
    pub copies: Vec<String>,
    pub subject: String,
    pub body: Vec<String>,
    pub attachment: Option<Attachment>,
    pub reply_to: Option<String>,
    pub projects: Vec<String>,
    pub origin: Origin,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct Marking {
    pub id: String,
    pub message_id: String,
    pub by: String,
    pub status: MailStatus,
    pub posed_at: String,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, Ord, PartialEq, PartialOrd, Serialize)]
pub enum MailStatus {
    #[serde(rename = "lu")]
    Read,
    #[serde(rename = "traité")]
    Done,
}

impl MailStatus {
    pub fn domain(self) -> Status {
        match self {
            Self::Read => Status::Read,
            Self::Done => Status::Done,
        }
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct ApprovalRequest {
    pub id: String,
    pub opened_by: String,
    pub gesture: String,
    pub scope: String,
    pub reversible: String,
    pub if_refused: String,
    pub why_now: String,
    pub opened_at: String,
    #[serde(default, skip_serializing_if = "RequestNature::is_validation")]
    pub nature: RequestNature,
}

#[derive(Clone, Copy, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum RequestNature {
    #[default]
    Validation,
    Intervention,
}

impl RequestNature {
    pub fn is_validation(&self) -> bool {
        *self == Self::Validation
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct Verdict {
    pub request_id: String,
    pub response: VerdictResponse,
    pub rendered_at: String,
    pub rendered_from: String,
    pub note: Option<String>,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub enum VerdictResponse {
    #[serde(rename = "valider")]
    Approve,
    #[serde(rename = "refuser")]
    Refuse,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct RequestClosure {
    pub id: String,
    pub request_id: String,
    pub by: String,
    pub result: String,
    pub closed_at: String,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct Reorientation {
    pub request_id: String,
    pub to: String,
    pub redirected_at: String,
    pub note: Option<String>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct DeliveryRoute {
    pub request_id: String,
    pub provider: String,
    pub session: String,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct ProviderStatus {
    pub id: String,
    pub name: String,
    pub version: Option<String>,
    pub state: String,
    pub detail: String,
    pub available: bool,
    pub equipped: bool,
    pub can_equip: bool,
}
