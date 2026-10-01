use crate::{
    domain::{journal::{ExchangeBatch, ExchangeItem}, models::Attachment, ports::{ExchangePort, PortError}},
    exchange::DirectoryExchange,
    remote_exchange::RemoteExchange,
    retention::{self, RetentionPreview},
};

#[derive(Clone)]
pub enum AppExchange {
    Directory(DirectoryExchange),
    Remote(RemoteExchange),
}

impl AppExchange {
    pub fn location(&self) -> String {
        match self {
            Self::Directory(exchange) => exchange.root().to_string_lossy().into_owned(),
            Self::Remote(exchange) => exchange.url().into(),
        }
    }
    pub fn kind(&self) -> &'static str {
        match self { Self::Remote(_) => "url", Self::Directory(_) => "folder" }
    }
    pub fn listening(&self) -> bool {
        match self { Self::Directory(exchange) => exchange.listening(), Self::Remote(_) => false }
    }
    pub fn retention_preview(&self) -> Result<RetentionPreview, PortError> {
        match self { Self::Directory(exchange) => retention::preview(exchange), Self::Remote(exchange) => exchange.retention_preview() }
    }
    pub fn retention_apply(&self, fingerprint: &str, installation: &str) -> Result<RetentionPreview, PortError> {
        match self { Self::Directory(exchange) => retention::apply(exchange, fingerprint, installation), Self::Remote(exchange) => exchange.retention_apply(fingerprint, installation) }
    }
}

impl ExchangePort for AppExchange {
    fn deposit(&self, item: ExchangeItem<'_>) -> Result<String, PortError> {
        match self { Self::Directory(exchange) => exchange.deposit(item), Self::Remote(exchange) => exchange.deposit(item) }
    }
    fn list(&self, since: Option<&str>, attachments: &[Attachment]) -> Result<ExchangeBatch, PortError> {
        match self { Self::Directory(exchange) => exchange.list(since, attachments), Self::Remote(exchange) => exchange.list(since, attachments) }
    }
    fn listen(&self) -> Result<tokio::sync::watch::Receiver<u64>, PortError> {
        match self { Self::Directory(exchange) => exchange.listen(), Self::Remote(exchange) => exchange.listen() }
    }
}
