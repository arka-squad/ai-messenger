use super::*;

impl<R: RepositoryPort, E: ExchangePort> MailboxService<R, E> {
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
    /// Replaces the whole book. Only new or changed contacts are checked against the directory, so
    /// a contact whose account was later deactivated never blocks an unrelated edit.
    pub async fn set_contacts(
        &self,
        address: &str,
        contacts: Vec<Contact>,
    ) -> Result<String, MailboxError> {
        let _guard = self.changes.lock().await;
        self.require_account(address).await?;
        let accounts = self.accounts().await?;
        let previous = self.contact_books().await?.remove(address).unwrap_or_default();
        let mut aliases = BTreeSet::new();
        for contact in &contacts {
            if !aliases.insert(contact.alias.clone()) {
                return Err(refusal(
                    "contact_invalide",
                    &format!("L’alias « {} » apparaît deux fois dans le carnet.", contact.alias),
                ));
            }
            if !previous.contains(contact) {
                self.check_contact(&accounts, contact).await?;
            }
        }
        self.event(Change::Contacts {
            account: address.into(),
            contacts,
        })
        .await
    }
    /// Adds (or replaces) one alias and removes another, read and written under the changes lock so
    /// that two sessions of the same account never lose each other's edit. Nothing is published
    /// when the book does not change.
    pub async fn edit_contacts(
        &self,
        address: &str,
        added: Option<Contact>,
        removed: Option<&str>,
    ) -> Result<Option<String>, MailboxError> {
        let _guard = self.changes.lock().await;
        self.require_account(address).await?;
        let mut book = self.contact_books().await?.remove(address).unwrap_or_default();
        let before = book.clone();
        if let Some(alias) = removed {
            book.retain(|c| c.alias != alias);
        }
        if let Some(contact) = added {
            if !before.contains(&contact) {
                self.check_contact(&self.accounts().await?, &contact).await?;
            }
            match book.iter_mut().find(|c| c.alias == contact.alias) {
                Some(existing) => *existing = contact,
                None => book.push(contact),
            }
        }
        if book == before {
            return Ok(None);
        }
        self.event(Change::Contacts {
            account: address.into(),
            contacts: book,
        })
        .await
        .map(Some)
    }
    /// A refusal names the alias concerned.
    async fn check_contact(
        &self,
        accounts: &[AgentAccount],
        contact: &Contact,
    ) -> Result<(), MailboxError> {
        let alias = &contact.alias;
        if !single_line(alias) {
            return Err(refusal(
                "contact_invalide",
                &format!("L’alias « {} » doit tenir sur une ligne non vide.", alias.trim()),
            ));
        }
        // An alias never shadows a real address: sending resolves addresses first.
        if accounts.iter().any(|a| a.address == *alias) {
            return Err(refusal(
                "contact_invalide",
                &format!("L’alias « {alias} » est déjà l’adresse d’un compte : choisis un autre nom."),
            ));
        }
        if contact.addresses.is_empty() {
            return Err(refusal(
                "contact_invalide",
                &format!("L’alias « {alias} » doit viser au moins une adresse."),
            ));
        }
        for target in &contact.addresses {
            match self.require_recipient(target).await {
                Ok(()) => {}
                Err(MailboxError::Refusal { reason, message }) => {
                    return Err(refusal(&reason, &format!("Contact « {alias} » : {message}")));
                }
                Err(MailboxError::Domain(_)) => {
                    return Err(refusal(
                        "contact_invalide",
                        &format!("Contact « {alias} » : l’adresse « {target} » est invalide. Consulte l’outil agents."),
                    ));
                }
                Err(error) => return Err(error),
            }
        }
        Ok(())
    }
}
