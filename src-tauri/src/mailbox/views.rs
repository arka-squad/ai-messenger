use super::*;
use serde::Serialize;

#[derive(Clone, Debug, Serialize)]
pub struct MessageView {
    #[serde(flatten)]
    pub message: MailMessage,
    pub journey: String,
    pub reachability: BTreeMap<String, crate::domain::Reachability>,
    pub statuses: BTreeMap<String, String>,
    pub overall: String,
    pub complete: bool,
    pub attachment_notice: Option<String>,
    pub announced_attachment: Option<String>,
    pub history: Vec<Value>,
    pub integrated_by: Vec<String>,
}
impl<R: RepositoryPort, E: ExchangePort> MailboxService<R, E> {
    pub async fn thread(&self, id: &str, account: &str) -> Result<Vec<MessageView>, MailboxError> {
        self.read(id, account).await?;
        let messages = self.message_views().await?;
        let accounts = self.accounts().await?;
        let actor = directory::resolve_address(&accounts, account)?;
        let mut ids = BTreeSet::from([id.to_owned()]);
        loop {
            let before = ids.len();
            for view in &messages {
                let message = &view.message;
                if let Some(parent) = &message.reply_to {
                    if ids.contains(&message.id) || ids.contains(parent) {
                        ids.insert(message.id.clone());
                        ids.insert(parent.clone());
                    }
                }
            }
            if ids.len() == before {
                break;
            }
        }
        let mut visible = Vec::new();
        for view in messages.into_iter().filter(|m| ids.contains(&m.message.id)) {
            let message = &view.message;
            let mut participant = false;
            for address in std::iter::once(&message.from)
                .chain(&message.to)
                .chain(&message.copies)
            {
                if directory::resolve_address(&accounts, address)? == actor {
                    participant = true;
                    break;
                }
            }
            if participant {
                visible.push(view);
            }
        }
        Ok(visible)
    }
    pub async fn inbox_views(&self, account: &str) -> Result<Vec<MessageView>, MailboxError> {
        let ids = self
            .inbox(account)
            .await?
            .into_iter()
            .map(|m| m.id)
            .collect::<BTreeSet<_>>();
        Ok(self
            .message_views()
            .await?
            .into_iter()
            .filter(|v| ids.contains(&v.message.id))
            .collect())
    }
    pub async fn messages(&self) -> Result<Vec<MailMessage>, MailboxError> {
        let mut messages = BTreeMap::new();
        for row in self.rows("legacy_message").await? {
            if let Mutation::LegacyMessage(v) = row {
                if let Some(message) = legacy_message(&v) {
                    messages.insert(message.id.clone(), message);
                }
            }
        }
        for row in self.rows("message").await? {
            if let Mutation::Message(message) = row {
                messages.insert(message.id.clone(), message);
            }
        }
        for event in self.events().await? {
            if let Change::LegacyAttachment {
                message_id,
                reference,
            } = event.change
            {
                if let Some(message) = messages.get_mut(&message_id) {
                    message.attachment = Some(reference);
                }
            }
        }
        let mut messages = messages.into_values().collect::<Vec<_>>();
        messages.sort_by(|a, b| {
            parse_date(&b.emitted_at)
                .cmp(&parse_date(&a.emitted_at))
                .then(b.id.cmp(&a.id))
        });
        Ok(messages)
    }
    pub async fn message(&self, id: &str) -> Result<Option<MailMessage>, MailboxError> {
        Ok(self.messages().await?.into_iter().find(|m| m.id == id))
    }
    pub async fn statuses(
        &self,
    ) -> Result<BTreeMap<String, BTreeMap<String, String>>, MailboxError> {
        let messages = self.messages().await?;
        let mut statuses = messages
            .iter()
            .map(|m| {
                (
                    m.id.clone(),
                    m.to.iter()
                        .map(|a| (a.clone(), "nouveau".into()))
                        .collect::<BTreeMap<String, String>>(),
                )
            })
            .collect::<BTreeMap<_, _>>();
        for mutation in self.rows("legacy_message").await? {
            if let Mutation::LegacyMessage(v) = mutation {
                if let Some(row) = v["id"].as_str().and_then(|id| statuses.get_mut(id)) {
                    for (recipient, status) in row.iter_mut() {
                        let value = v["statuts"][recipient.as_str()]
                            .as_str()
                            .or_else(|| v["statut"].as_str())
                            .unwrap_or("nouveau");
                        *status = value.into();
                    }
                }
            }
        }
        let accounts = self.accounts().await?;
        for mutation in self.rows("marking").await? {
            if let Mutation::Marking(marking) = mutation {
                if let Some(row) = statuses.get_mut(&marking.message_id) {
                    let value = match marking.status {
                        MailStatus::Read => "lu",
                        MailStatus::Done => "traité",
                    };
                    for (address, current) in row.iter_mut() {
                        let effective = directory::resolve_address(&accounts, address)?;
                        let author = directory::resolve_address(&accounts, &marking.by)?;
                        if (address == &marking.by || effective == author)
                            && status_rank(value) > status_rank(current)
                        {
                            *current = value.into();
                        }
                    }
                }
            }
        }
        Ok(statuses)
    }
    pub async fn message_views(&self) -> Result<Vec<MessageView>, MailboxError> {
        let statuses = self.statuses().await?;
        let rows = self.store.mutations(None, None).await?;
        let events = self.events().await?;
        let mut views = Vec::new();
        for message in self.messages().await? {
            let mut journey = rows
                .iter()
                .find(|r| {
                    r.mutation.id() == message.id
                        && matches!(
                            r.mutation,
                            Mutation::Message(_) | Mutation::LegacyMessage(_)
                        )
                })
                .map(|r| r.journey.clone())
                .unwrap_or_else(|| "integrated".into());
            let legacy = rows.iter().find_map(|row| match &row.mutation {
                Mutation::LegacyMessage(value) if value["id"] == message.id => Some(value),
                _ => None,
            });
            let announced_attachment = legacy
                .and_then(|v| v["pj"].as_str())
                .filter(|s| !s.is_empty())
                .map(str::to_owned);
            let history = legacy
                .and_then(|v| v["historique"].as_array())
                .cloned()
                .unwrap_or_default();
            let complete = if let Some(reference) = &message.attachment {
                self.store
                    .blob(&reference.fingerprint)
                    .await?
                    .is_some_and(|bytes| {
                        hash(&bytes) == reference.fingerprint
                            && bytes.len() as u64 == reference.size
                    })
            } else {
                announced_attachment.is_none()
            };
            let status = statuses.get(&message.id).cloned().unwrap_or_default();
            let overall = status
                .values()
                .min_by_key(|s| status_rank(s))
                .cloned()
                .unwrap_or_else(|| "nouveau".into());
            let mut reachability = BTreeMap::new();
            let mut integrated_by = BTreeSet::new();
            for event in &events {
                if let Change::Integrated {
                    message_id,
                    installation,
                } = &event.change
                {
                    if message_id == &message.id {
                        integrated_by.insert(installation.clone());
                    }
                }
                if let Change::Reached {
                    message_id,
                    account,
                    reachability: value,
                } = &event.change
                {
                    if message_id == &message.id {
                        reachability.insert(account.clone(), *value);
                    }
                }
            }
            if !complete {
                reachability.clear();
            }
            if journey == "integrated" && message.origin.host != "prototype" {
                journey = "published".into();
            }
            if matches!(journey.as_str(), "published" | "integrated") && !integrated_by.is_empty() {
                journey = "integrated".into();
            }
            views.push(MessageView {message,journey,reachability,statuses:status,overall,complete,announced_attachment,history,integrated_by:integrated_by.into_iter().collect(),
                attachment_notice:if complete {None} else {Some("Pièce jointe absente ou incomplète. Le message reste lisible ; tu peux demander sa remise.".into())}});
        }
        Ok(views)
    }
    pub async fn request_attachment(&self, id: &str) -> Result<String, MailboxError> {
        let message = self.message(id).await?.ok_or(DomainError::UnknownMessage)?;
        let legacy = self.find("legacy_message", id).await?;
        let announced = matches!(legacy,Some(Mutation::LegacyMessage(v)) if v["pj"].as_str().is_some_and(|s|!s.is_empty()));
        if message.attachment.is_none() && !announced {
            return Err(refusal(
                "sans_piece_jointe",
                "Ce message ne possède pas de pièce jointe.",
            ));
        }
        self.event(Change::AttachmentRequested {
            message_id: id.into(),
            requested_by: self.installation.clone(),
        })
        .await
    }
}
pub(crate) fn parse_date(date: &str) -> i64 {
    chrono::DateTime::parse_from_rfc3339(date)
        .map(|v| v.timestamp_millis())
        .unwrap_or(0)
}
pub(crate) fn legacy_message(value: &Value) -> Option<MailMessage> {
    let list = |key: &str| {
        value[key]
            .as_array()
            .into_iter()
            .flatten()
            .filter_map(|v| v.as_str().map(str::to_owned))
            .collect::<Vec<_>>()
    };
    let body = match &value["corps"] {
        Value::String(v) => v.lines().map(str::to_owned).collect(),
        _ => list("corps"),
    };
    let attachment = value
        .get("_messenger_attachment")
        .cloned()
        .and_then(|v| serde_json::from_value(v).ok());
    Some(MailMessage {
        id: value["id"].as_str()?.into(),
        emitted_at: value["date"].as_str().unwrap_or_default().into(),
        from: value["de"].as_str().unwrap_or_default().into(),
        to: list("a"),
        copies: list("cc"),
        subject: value["objet"].as_str().unwrap_or_default().into(),
        body,
        attachment,
        reply_to: value["re"].as_str().map(str::to_owned),
        projects: list("projets"),
        origin: Origin {
            host: "prototype".into(),
            session: String::new(),
        },
    })
}
