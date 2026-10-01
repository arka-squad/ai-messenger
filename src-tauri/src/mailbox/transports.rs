use super::*;

/// MCP transports kept across app restarts, in one local index: id -> provider, session, seen_at.
const INDEX: &str = "mcp_transports";
/// Hosts reconnect often: only the most recently seen transports are kept, as the first mailbox
/// kept at most 300 entries in its memory.
pub(crate) const KEPT_TRANSPORTS: usize = 300;

fn valid(id: &str) -> bool {
    !id.is_empty() && id.len() <= 96 && id.bytes().all(|b| b.is_ascii_alphanumeric() || b == b'-')
}

impl<R: RepositoryPort, E: ExchangePort> MailboxService<R, E> {
    async fn transport_index(&self) -> Result<serde_json::Map<String, Value>, MailboxError> {
        Ok(self
            .setting(INDEX)
            .await?
            .and_then(|v| v.as_object().cloned())
            .unwrap_or_default())
    }
    /// The transport a restarted app no longer holds in memory; finding it refreshes its seen_at.
    /// A row written by the previous version (`mcp_transport:<id>`) is moved into the index.
    pub(crate) async fn transport(&self, id: &str) -> Result<Option<(String, String)>, MailboxError> {
        if !valid(id) {
            return Ok(None);
        }
        let _guard = self.transports.lock().await;
        let mut index = self.transport_index().await?;
        let legacy = format!("mcp_transport:{id}");
        let entry = match index.get(id) {
            Some(entry) => Some(entry.clone()),
            None => self.setting(&legacy).await?.filter(|v| !v.is_null()),
        };
        let Some(entry) = entry else {
            return Ok(None);
        };
        let (Some(provider), Some(session)) = (entry["provider"].as_str(), entry["session"].as_str()) else {
            return Ok(None);
        };
        let found = (provider.to_owned(), session.to_owned());
        if !index.contains_key(id) {
            self.set_setting(&legacy, Value::Null).await?;
        }
        index.insert(id.into(), json!({"provider":found.0,"session":found.1,"seen_at":now()}));
        self.save_index(index).await?;
        Ok(Some(found))
    }
    /// Records a new transport, or forgets a closed one (`None`).
    pub(crate) async fn save_transport(
        &self,
        id: &str,
        value: Option<(&str, &str)>,
    ) -> Result<(), MailboxError> {
        if !valid(id) {
            return Ok(());
        }
        let _guard = self.transports.lock().await;
        let mut index = self.transport_index().await?;
        match value {
            Some((provider, session)) => {
                index.insert(id.into(), json!({"provider":provider,"session":session,"seen_at":now()}));
            }
            None => {
                let legacy = format!("mcp_transport:{id}");
                if self.setting(&legacy).await?.is_some_and(|v| !v.is_null()) {
                    self.set_setting(&legacy, Value::Null).await?;
                }
                if index.remove(id).is_none() {
                    return Ok(());
                }
            }
        }
        self.save_index(index).await
    }
    async fn save_index(&self, index: serde_json::Map<String, Value>) -> Result<(), MailboxError> {
        let mut entries = index.into_iter().collect::<Vec<_>>();
        if entries.len() > KEPT_TRANSPORTS {
            entries.sort_by_key(|(_, v)| std::cmp::Reverse(views::parse_date(v["seen_at"].as_str().unwrap_or(""))));
            entries.truncate(KEPT_TRANSPORTS);
        }
        self.set_setting(INDEX, Value::Object(entries.into_iter().collect())).await
    }
}
