use super::*;

impl<R: RepositoryPort, E: ExchangePort> MailboxService<R, E> {
    pub async fn events(&self) -> Result<Vec<Event>, MailboxError> {
        let mut events = self
            .rows("event")
            .await?
            .into_iter()
            .filter_map(|v| match v {
                Mutation::Event(e) => Some(e),
                _ => None,
            })
            .collect::<Vec<_>>();
        events.sort_by(|a, b| a.emitted_at.cmp(&b.emitted_at).then(a.id.cmp(&b.id)));
        Ok(events)
    }
    pub async fn event(&self, change: Change) -> Result<String, MailboxError> {
        self.publish(Mutation::Event(Event {
            id: new_id(),
            emitted_at: now(),
            installation: self.installation.clone(),
            change,
        }))
        .await
    }
    pub async fn accounts(&self) -> Result<Vec<AgentAccount>, MailboxError> {
        let mut accounts = BTreeMap::new();
        for row in self.rows("legacy_account").await? {
            if let Mutation::LegacyAccount(v) = row {
                if v["humain"].as_bool() == Some(true) || v["nom"] == "owner" {
                    continue;
                }
                let address = v["nom"].as_str().unwrap_or_default().to_owned();
                if address.is_empty() {
                    continue;
                }
                let string = |key: &str| v[key].as_str().unwrap_or_default().to_owned();
                accounts.insert(
                    address.clone(),
                    AgentAccount {
                        address,
                        display: string("affichage"),
                        host: string("hote"),
                        machine: string("machine"),
                        role: string("role"),
                        active: v["actif"].as_bool().unwrap_or(true),
                        created_at: string("cree"),
                        installation: String::new(),
                        project: v["projet"].as_str().map(str::to_owned),
                        merged_into: v["fusionne_dans"].as_str().map(str::to_owned),
                    },
                );
            }
        }
        let events = self.events().await?;
        for event in &events {
            if let Change::Account { account } = &event.change {
                if Account::enroll(&account.address, &account.role).is_err() {
                    self.incident(Incident{id:format!("compte:{}",event.id),kind:"compte_invalide".into(),message:"Un compte reçu ne respecte pas les règles des agents et a été écarté du répertoire. Les comptes existants restent disponibles.".into(),message_id:None});
                    continue;
                }
                accounts.insert(account.address.clone(), account.clone());
            }
        }
        for event in events {
            match event.change {
                Change::Merge { source, target } => {
                    let mut effective = target.clone();
                    let mut seen = BTreeSet::new();
                    while let Some(next) =
                        accounts.get(&effective).and_then(|a| a.merged_into.clone())
                    {
                        if !seen.insert(effective.clone()) {
                            break;
                        }
                        effective = next;
                    }
                    if effective == source || !accounts.get(&effective).is_some_and(|a| a.active) {
                        self.incident(Incident{id:format!("fusion:{}",event.id),kind:"fusion_en_conflit".into(),message:"Deux fusions concurrentes sont incompatibles. La fusion qui formerait une boucle a été écartée ; les comptes et le courrier restent conservés.".into(),message_id:None});
                    } else if let Some(a) = accounts.get_mut(&source) {
                        a.active = false;
                        a.merged_into = Some(target);
                    }
                }
                Change::File { account, project } => {
                    if let Some(a) = accounts.get_mut(&account) {
                        a.project = project;
                    }
                }
                _ => {}
            }
        }
        Ok(accounts.into_values().collect())
    }
    pub(crate) async fn require_account(
        &self,
        address: &str,
    ) -> Result<AgentAccount, MailboxError> {
        Account::enroll(address, "agent")?;
        let resolved = self.resolve_account(address).await?;
        let account = self
            .accounts()
            .await?
            .into_iter()
            .find(|a| a.address == resolved)
            .ok_or_else(|| {
                refusal(
                    "compte_inconnu",
                    "Ce compte n’existe pas dans cette boîte. Enrôle-toi ou reprends ton compte.",
                )
            })?;
        if !account.active {
            return Err(refusal(
                "compte_inactif",
                "Ce compte a été désactivé. Reprends un compte actif avant d’écrire.",
            ));
        }
        Ok(account)
    }

    pub(crate) async fn resolve_account(&self, address: &str) -> Result<String, MailboxError> {
        resolve_address(&self.accounts().await?, address)
    }

    pub async fn identity(
        &self,
        provider: &str,
        session: &str,
    ) -> Result<Option<SessionIdentity>, MailboxError> {
        self.setting(&format!("session:{provider}:{session}"))
            .await?
            .map(serde_json::from_value)
            .transpose()
            .map_err(|_| {
                refusal(
                    "identite_invalide",
                    "L’identité de cette session est illisible.",
                )
            })
    }
    pub async fn enroll(
        &self,
        provider: &str,
        session: &str,
        display: &str,
        role: &str,
        project: Option<String>,
    ) -> Result<Value, MailboxError> {
        let _guard = self.changes.lock().await;
        if session.is_empty()
            || !single_line(display)
            || !single_line(role)
            || matches!(role.trim().to_lowercase().as_str(), "human" | "humain")
        {
            return Err(DomainError::InvalidAccount.into());
        }
        if let Some(identity) = self.identity(provider, session).await? {
            return Ok(json!({"identity":identity,"already_enrolled":true}));
        }
        if project.as_ref().is_some_and(|p| !valid_name(p)) {
            return Err(refusal(
                "projet_invalide",
                "Le nom du projet doit être une adresse simple, sans espace ni chemin.",
            ));
        }
        let prefix = display
            .chars()
            .filter(|c| c.is_ascii_alphanumeric() || *c == '-' || *c == '_')
            .collect::<String>()
            .to_lowercase();
        if prefix.is_empty() || prefix == "owner" {
            return Err(DomainError::InvalidAccount.into());
        }
        let existing = self.accounts().await?;
        let mut suffix = 0;
        let address = loop {
            let local = if suffix == 0 {
                prefix.clone()
            } else {
                format!("{prefix}-{suffix}")
            };
            let candidate = match &project {
                Some(p) => format!("{local}@{p}"),
                None => local,
            };
            if !existing.iter().any(|a| a.address == candidate) {
                break candidate;
            }
            suffix += 1;
        };
        let account = AgentAccount {
            address: address.clone(),
            display: display.into(),
            host: provider.into(),
            machine: self.machine.clone(),
            role: role.into(),
            active: true,
            created_at: now(),
            installation: self.installation.clone(),
            project: project.clone(),
            merged_into: None,
        };
        let identity = SessionIdentity {
            session: session.into(),
            provider: provider.into(),
            account: address.clone(),
            installation: self.installation.clone(),
            project,
        };
        // A recovery key stays on the local installation; it never enters the shared journal.
        let recovery_key = new_id() + &new_id();
        self.set_setting(
            &format!("recovery:{address}"),
            json!(hash(recovery_key.as_bytes())),
        )
        .await?;
        self.event(Change::Account {
            account: account.clone(),
        })
        .await?;
        self.set_setting(&format!("session:{provider}:{session}"), json!(identity))
            .await?;
        Ok(json!({"identity":identity,"account":account,"recovery_key":recovery_key}))
    }
    pub async fn recognize(
        &self,
        provider: &str,
        session: &str,
        address: &str,
        recovery_key: &str,
    ) -> Result<SessionIdentity, MailboxError> {
        let _guard = self.changes.lock().await;
        if let Some(identity) = self.identity(provider, session).await? {
            if identity.account != address {
                return Err(refusal(
                    "session_deja_liee",
                    "Cette session appartient déjà à un autre compte.",
                ));
            }
            return Ok(identity);
        }
        let account = self.require_account(address).await?;
        let expected = self.setting(&format!("recovery:{address}")).await?;
        if expected.as_ref().and_then(Value::as_str) != Some(hash(recovery_key.as_bytes()).as_str())
        {
            return Err(refusal(
                "reprise_refusee",
                "La clé de reprise ne correspond pas à ce compte sur cette installation.",
            ));
        }
        let mut account = account;
        account.installation = self.installation.clone();
        account.host = provider.into();
        account.machine = self.machine.clone();
        self.event(Change::Account {
            account: account.clone(),
        })
        .await?;
        let identity = SessionIdentity {
            session: session.into(),
            provider: provider.into(),
            account: account.address,
            installation: self.installation.clone(),
            project: account.project,
        };
        self.set_setting(&format!("session:{provider}:{session}"), json!(identity))
            .await?;
        Ok(identity)
    }
    pub async fn merge_accounts(&self, source: &str, target: &str) -> Result<String, MailboxError> {
        let _guard = self.changes.lock().await;
        if !self
            .accounts()
            .await?
            .iter()
            .any(|a| a.address == source && a.active)
        {
            return Err(refusal(
                "compte_ferme",
                "Le compte source de cette fusion est déjà fermé.",
            ));
        }
        self.require_account(source).await?;
        self.require_account(target).await?;
        if source == target || self.resolve_account(target).await? == source {
            return Err(refusal(
                "fusion_invalide",
                "Choisis deux comptes distincts et actifs.",
            ));
        }
        self.event(Change::Merge {
            source: source.into(),
            target: target.into(),
        })
        .await
    }
    pub async fn file_account(
        &self,
        address: &str,
        project: Option<String>,
    ) -> Result<String, MailboxError> {
        let _guard = self.changes.lock().await;
        let account = self.require_account(address).await?;
        if address.contains('@') {
            return Err(refusal(
                "projet_fixe",
                "Le projet de ce compte appartient à son adresse.",
            ));
        }
        if project.as_ref().is_some_and(|p| !valid_name(p)) {
            return Err(refusal("projet_invalide", "Le nom du projet est invalide."));
        }
        self.event(Change::File {
            account: account.address,
            project,
        })
        .await
    }
    pub async fn contacts(&self, address: &str) -> Result<Vec<Contact>, MailboxError> {
        self.require_account(address).await?;
        Ok(self
            .contact_books()
            .await?
            .remove(address)
            .unwrap_or_default())
    }
    pub(crate) async fn contact_books(
        &self,
    ) -> Result<BTreeMap<String, Vec<Contact>>, MailboxError> {
        let mut books = BTreeMap::new();
        for mutation in self.rows("legacy_account").await? {
            if let Mutation::LegacyAccount(v) = mutation {
                if let Some(address) = v["nom"].as_str() {
                    let contacts = v["contacts"]
                        .as_array()
                        .into_iter()
                        .flatten()
                        .filter_map(|c| {
                            Some(Contact {
                                alias: c["alias"].as_str()?.into(),
                                addresses: c["adresses"]
                                    .as_array()?
                                    .iter()
                                    .filter_map(|a| a.as_str().map(str::to_owned))
                                    .collect(),
                                note: c["note"].as_str().unwrap_or_default().into(),
                            })
                        })
                        .collect();
                    books.insert(address.to_owned(), contacts);
                }
            }
        }
        for event in self.events().await? {
            if let Change::Contacts { account, contacts } = event.change {
                books.insert(account, contacts);
            }
        }
        Ok(books)
    }
    pub async fn set_contacts(
        &self,
        address: &str,
        contacts: Vec<Contact>,
    ) -> Result<String, MailboxError> {
        let _guard = self.changes.lock().await;
        self.require_account(address).await?;
        let mut aliases = BTreeSet::new();
        for contact in &contacts {
            if !single_line(&contact.alias)
                || !aliases.insert(contact.alias.clone())
                || contact.addresses.is_empty()
            {
                return Err(refusal(
                    "contact_invalide",
                    "Chaque contact doit avoir un alias unique et au moins une adresse.",
                ));
            }
            for target in &contact.addresses {
                self.require_account(target).await?;
            }
        }
        self.event(Change::Contacts {
            account: address.into(),
            contacts,
        })
        .await
    }
    pub async fn is_recipient(
        &self,
        message: &MailMessage,
        address: &str,
    ) -> Result<bool, MailboxError> {
        let effective = self.resolve_account(address).await?;
        for recipient in &message.to {
            if self.resolve_account(recipient).await? == effective {
                return Ok(true);
            }
        }
        Ok(false)
    }
    pub async fn is_copy(
        &self,
        message: &MailMessage,
        address: &str,
    ) -> Result<bool, MailboxError> {
        let effective = self.resolve_account(address).await?;
        for copy in &message.copies {
            if self.resolve_account(copy).await? == effective {
                return Ok(true);
            }
        }
        Ok(false)
    }
    pub async fn is_participant(
        &self,
        message: &MailMessage,
        address: &str,
    ) -> Result<bool, MailboxError> {
        Ok(
            self.resolve_account(&message.from).await? == self.resolve_account(address).await?
                || self.is_recipient(message, address).await?
                || self.is_copy(message, address).await?,
        )
    }
}

pub(crate) fn valid_name(name: &str) -> bool {
    !name.is_empty()
        && name.len() <= 120
        && name
            .chars()
            .all(|c| c.is_ascii_alphanumeric() || matches!(c, '-' | '_' | '.'))
        && name != "."
        && name != ".."
}

pub(crate) fn resolve_address(
    accounts: &[AgentAccount],
    address: &str,
) -> Result<String, MailboxError> {
    let mut address = address.to_owned();
    let mut seen = BTreeSet::new();
    while let Some(next) = accounts
        .iter()
        .find(|a| a.address == address)
        .and_then(|a| a.merged_into.clone())
    {
        if !seen.insert(address) {
            return Err(refusal(
                "fusion_cyclique",
                "La fusion des comptes forme une boucle.",
            ));
        }
        address = next;
    }
    Ok(address)
}
