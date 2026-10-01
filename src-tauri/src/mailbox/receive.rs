use super::*;

impl<R: RepositoryPort, E: ExchangePort> MailboxService<R, E> {
    pub async fn receive(&self) -> Result<usize, MailboxError> {
        let _guard = self.sync.lock().await;
        let _changes = self.changes.lock().await;
        let references = self
            .messages()
            .await?
            .into_iter()
            .filter_map(|m| m.attachment)
            .map(|r| (r.fingerprint.clone(), r))
            .collect::<BTreeMap<_, _>>();
        let mut missing = Vec::new();
        for reference in references.values() {
            if self
                .store
                .blob(&reference.fingerprint)
                .await?
                .is_none_or(|bytes| {
                    hash(&bytes) != reference.fingerprint || bytes.len() as u64 != reference.size
                })
            {
                missing.push(reference.clone());
            }
        }
        let since = self
            .store
            .setting("exchange_since")
            .await?
            .and_then(|v| v.as_str().map(str::to_owned));
        let batch = match self.exchange.list(since.as_deref(), &missing) {
            Ok(batch) => batch,
            Err(error) => {
                self.incident(Incident{id:"emplacement".into(),kind:error.0.clone(),
                    message:if error.0=="boite_occupee" {"La boîte est temporairement occupée par une autre écriture. Le courrier local reste consultable ; Messenger réessaiera."} else {"La boîte partagée n’est pas joignable. Le courrier local reste consultable ; Messenger réessaiera."}.into(),message_id:None});
                return Ok(0);
            }
        };
        self.clear_incident("emplacement");
        let mut integrated = 0;
        for mutation in batch.mutations {
            if let Mutation::Event(Event {
                change: Change::Purged { removed, dormant },
                ..
            }) = &mutation
            {
                if dormant.contains(&self.installation) {
                    self.set_setting("missed_before", json!(mutation.emitted_at()))
                        .await?;
                    self.incident(Incident{id:format!("conservation:{}",mutation.id()),kind:"installation_dormante".into(),message:format!("Cette installation est restée silencieuse plus de six mois. {} anciennes écritures ont été retirées pendant son absence. Le courrier déjà conservé localement reste consultable.",removed.len()),message_id:None});
                }
            }
            if let Mutation::Event(Event {
                change: Change::AttachmentRequested { message_id, .. },
                ..
            }) = &mutation
            {
                if let Some(reference) = self.message(message_id).await?.and_then(|m| m.attachment)
                {
                    let mut outbox = self
                        .setting("attachment_outbox")
                        .await?
                        .unwrap_or_else(|| json!({}));
                    outbox[&reference.fingerprint] = json!(reference);
                    self.set_setting("attachment_outbox", outbox).await?;
                }
            }
            if let Mutation::Message(message) = &mutation {
                if let Err(error) = validate_message(message) {
                    self.incident(Incident {
                        id: format!("invalide:{}", mutation.id()),
                        kind: "mutation_invalide".into(),
                        message: error.to_string(),
                        message_id: Some(mutation.id().into()),
                    });
                    continue;
                }
            }
            let saved = match self.store.save(&mutation, "integrated").await {
                Ok(saved) => saved,
                Err(error) if error.0 == "mutation_en_conflit" => {
                    self.store
                        .set_journey(mutation.kind(), mutation.id(), "conflict")
                        .await?;
                    self.incident(Incident {id:format!("conflit:{}:{}",mutation.kind(),mutation.id()),kind:"mutation_en_conflit".into(),message:"Une autre écriture a été publiée pour cet identifiant. La boîte affiche l’écriture confirmée ; le contenu local écarté reste conservé.".into(),message_id:Some(mutation.id().into())});
                    self.store.save(&mutation, "integrated").await?
                }
                Err(error) => return Err(error.into()),
            };
            if saved {
                integrated += 1;
            } else if self
                .store
                .mutations(Some(mutation.kind()), Some("pending"))
                .await?
                .iter()
                .any(|v| v.mutation.id() == mutation.id())
            {
                self.store
                    .set_journey(mutation.kind(), mutation.id(), "published")
                    .await?;
            }
        }
        for reference in &missing {
            if let Some(bytes) = batch.attachments.get(&reference.fingerprint) {
                self.store.save_blob(reference, bytes.clone()).await?;
            }
        }
        // Newly received references are fetched in the same pass, without rereading old mutations.
        let all_references = self
            .messages()
            .await?
            .into_iter()
            .filter_map(|m| m.attachment)
            .map(|r| (r.fingerprint.clone(), r))
            .collect::<BTreeMap<_, _>>();
        let discovered = all_references
            .values()
            .filter(|r| !references.contains_key(&r.fingerprint))
            .cloned()
            .collect::<Vec<_>>();
        if !discovered.is_empty() {
            let attachments = self
                .exchange
                .list(Some(&Utc::now().date_naive().to_string()), &discovered)?
                .attachments;
            for reference in &discovered {
                if let Some(bytes) = attachments.get(&reference.fingerprint) {
                    self.store.save_blob(reference, bytes.clone()).await?;
                }
            }
        }
        // Attachment delivery has its own durable retry path, even after its message is published.
        let mut outbox = self
            .setting("attachment_outbox")
            .await?
            .unwrap_or_else(|| json!({}));
        let queued = outbox
            .as_object()
            .ok_or_else(|| {
                refusal(
                    "file_invalide",
                    "La reprise des pièces jointes est illisible.",
                )
            })?
            .values()
            .cloned()
            .collect::<Vec<_>>();
        for reference in queued {
            let reference: Attachment = serde_json::from_value(reference).map_err(|_| {
                refusal(
                    "file_invalide",
                    "Une référence de pièce jointe en attente est illisible.",
                )
            })?;
            if let Some(bytes) = self.store.blob(&reference.fingerprint).await? {
                if hash(&bytes) == reference.fingerprint && bytes.len() as u64 == reference.size {
                    if self
                        .exchange
                        .deposit(ExchangeItem::Attachment {
                            reference: &reference,
                            bytes: &bytes,
                        })
                        .is_ok()
                    {
                        outbox
                            .as_object_mut()
                            .unwrap()
                            .remove(&reference.fingerprint);
                    }
                }
            }
        }
        self.set_setting("attachment_outbox", outbox).await?;
        {
            let mut incidents = self.incidents.lock().expect("incident lock");
            incidents.retain(|_, v| v.kind != "lecture_incomplete");
            for incident in &batch.incidents {
                incidents.insert(incident.id.clone(), incident.clone());
            }
        }
        if batch.incidents.is_empty() {
            self.store
                .set_setting("exchange_since", json!(Utc::now().date_naive().to_string()))
                .await?;
        }
        for row in self.store.mutations(None, Some("pending")).await? {
            if let Mutation::Message(message) = &row.mutation {
                if let Some(reference) = &message.attachment {
                    if let Some(bytes) = self.store.blob(&reference.fingerprint).await? {
                        if self
                            .exchange
                            .deposit(ExchangeItem::Attachment {
                                reference,
                                bytes: &bytes,
                            })
                            .is_err()
                        {
                            continue;
                        }
                    }
                }
            }
            match self.publish(row.mutation).await {
                Err(MailboxError::Refusal { reason, .. }) if reason == "mutation_en_conflit" => {}
                result => {
                    result?;
                }
            }
        }
        let accounts = self.accounts().await?;
        for view in self.message_views().await? {
            let mut destination_here = false;
            for account in accounts
                .iter()
                .filter(|a| a.active && a.installation == self.installation)
            {
                if self.is_recipient(&view.message, &account.address).await? {
                    destination_here = true;
                    break;
                }
            }
            if view.complete
                && destination_here
                && view.message.origin.host != "prototype"
                && matches!(view.journey.as_str(), "published" | "integrated")
            {
                let key = format!("integration:{}", view.message.id);
                if self.setting(&key).await?.is_none() {
                    let event = Event {
                        id: new_id(),
                        emitted_at: now(),
                        installation: self.installation.clone(),
                        change: Change::Integrated {
                            message_id: view.message.id,
                            installation: self.installation.clone(),
                        },
                    };
                    self.set_setting(&key, json!(event)).await?;
                }
                if let Some(value) = self.setting(&key).await? {
                    let event: Event = serde_json::from_value(value).map_err(|_| {
                        refusal(
                            "integration_invalide",
                            "La preuve d’intégration locale est illisible.",
                        )
                    })?;
                    if self.find("event", &event.id).await?.is_none() {
                        self.publish(Mutation::Event(event)).await?;
                    }
                }
            }
        }
        self.checkpoint().await?;
        if integrated > 0 {
            self.arrived.notify_waiters();
        }
        Ok(integrated)
    }
    pub async fn checkpoint(&self) -> Result<(), MailboxError> {
        let mutations = self.store.mutations(None, None).await?;
        let incomplete = self
            .message_views()
            .await?
            .into_iter()
            .filter(|v| !v.complete)
            .map(|v| v.message.id)
            .collect::<BTreeSet<_>>();
        let integrated=mutations.into_iter().filter(|row|row.journey=="published" || row.journey=="integrated")
            .filter(|row|!matches!(&row.mutation,Mutation::Message(m) if incomplete.contains(&m.id))
                && !matches!(&row.mutation,Mutation::LegacyMessage(v) if v["id"].as_str().is_some_and(|id|incomplete.contains(id))))
            .map(|row|(format!("{}:{}",row.mutation.kind(),row.mutation.id()),hash(&canonical_bytes(&row.mutation).expect("a decoded mutation serializes")))).collect();
        let missed_before = self
            .setting("missed_before")
            .await?
            .and_then(|v| v.as_str().map(str::to_owned));
        let checkpoint = ReadCheckpoint {
            id: self.installation.clone(),
            machine: self.machine.clone(),
            seen_at: now(),
            integrated,
            missed_before,
        };
        self.exchange
            .deposit(ExchangeItem::Checkpoint(&checkpoint))?;
        Ok(())
    }
    pub async fn await_mail(
        &self,
        account: &str,
        timeout: u64,
    ) -> Result<Vec<MailMessage>, MailboxError> {
        self.require_account(account).await?;
        let deadline =
            tokio::time::Instant::now() + std::time::Duration::from_secs(timeout.min(300));
        loop {
            let notified = self.arrived.notified();
            tokio::pin!(notified);
            notified.as_mut().enable();
            self.receive().await?;
            let messages = self.inbox(account).await?;
            if !messages.is_empty() {
                return Ok(messages);
            }
            if tokio::time::timeout_at(deadline, notified).await.is_err() {
                return Ok(Vec::new());
            }
        }
    }
}
