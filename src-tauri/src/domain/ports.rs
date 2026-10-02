use super::{journal::*, models::*, Reachability};
use serde_json::Value;
use std::future::Future;
use thiserror::Error;

#[derive(Debug, Error)]
#[error("{0}")]
pub struct PortError(pub String);

pub trait ExchangePort: Send + Sync {
    fn deposit(&self, item: ExchangeItem<'_>) -> Result<String, PortError>;
    fn list(
        &self,
        since: Option<&str>,
        attachments: &[Attachment],
    ) -> Result<ExchangeBatch, PortError>;
    fn listen(&self) -> Result<tokio::sync::watch::Receiver<u64>, PortError>;
}

pub trait ProviderPort: Send + Sync {
    fn id(&self) -> &'static str;
    fn present(&self) -> ProviderStatus;
    fn equip(&self) -> Result<ProviderStatus, PortError>;
    fn deliver(&self, session: &str, message: &str) -> Result<Reachability, PortError>;
    fn deliver_verdict(&self, session: &str, verdict: &str) -> Result<Reachability, PortError>;
    fn receive(&self) -> bool;
}

pub trait RepositoryPort: Send + Sync {
    fn schema_version(&self) -> impl Future<Output = Result<u8, PortError>> + Send;
    fn save(
        &self,
        mutation: &Mutation,
        journey: &str,
    ) -> impl Future<Output = Result<bool, PortError>> + Send;
    fn mutations(
        &self,
        kind: Option<&str>,
        journey: Option<&str>,
    ) -> impl Future<Output = Result<Vec<StoredMutation>, PortError>> + Send;
    /// A row that becomes published or integrated gets its local position once.
    fn set_journey(
        &self,
        kind: &str,
        id: &str,
        journey: &str,
    ) -> impl Future<Output = Result<(), PortError>> + Send;
    /// Rows with a position above `position`, in position order: the integration cursor.
    fn after(
        &self,
        position: u64,
        limit: usize,
    ) -> impl Future<Output = Result<Vec<(u64, StoredMutation)>, PortError>> + Send;
    fn setting(&self, key: &str) -> impl Future<Output = Result<Option<Value>, PortError>> + Send;
    fn set_setting(
        &self,
        key: &str,
        value: Value,
    ) -> impl Future<Output = Result<(), PortError>> + Send;
    fn save_blob(
        &self,
        reference: &Attachment,
        bytes: Vec<u8>,
    ) -> impl Future<Output = Result<(), PortError>> + Send;
    fn blob(
        &self,
        fingerprint: &str,
    ) -> impl Future<Output = Result<Option<Vec<u8>>, PortError>> + Send;
}
