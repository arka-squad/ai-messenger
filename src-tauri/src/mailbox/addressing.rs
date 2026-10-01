use super::*;

/// Recipients as the agent wrote them, resolved against the directory and its own address book.
pub(crate) struct Recipients {
    pub to: Vec<String>,
    pub copies: Vec<String>,
    /// What was written -> what it became, only for names that changed.
    pub resolved: BTreeMap<String, Vec<String>>,
}

impl<R: RepositoryPort, E: ExchangePort> MailboxService<R, E> {
    /// A recipient refusal names the faulty address and points to the directory, never to the sender's enrolment.
    pub(crate) async fn require_recipient(&self, address: &str) -> Result<(), MailboxError> {
        match self.require_account(address).await {
            Err(MailboxError::Refusal { reason, .. }) if reason == "compte_inconnu" => Err(refusal(
                "destinataire_inconnu",
                &format!("Le destinataire « {address} » n’existe pas dans cette boîte. Consulte l’outil agents pour son adresse exacte."),
            )),
            Err(MailboxError::Refusal { reason, .. }) if reason == "compte_inactif" => Err(refusal(
                "destinataire_inactif",
                &format!("Le destinataire « {address} » est désactivé. Consulte l’outil agents pour choisir un compte actif."),
            )),
            result => result.map(|_| ()),
        }
    }
    /// An exact address stays; an alias of the sender's book expands; a name without `@` becomes the
    /// unique active account with that local part, preferring the sender's project. Anything else is
    /// left as written so that sending refuses it by name.
    pub(crate) async fn resolve_recipients(
        &self,
        sender: &str,
        to: &[String],
        copies: &[String],
    ) -> Result<Recipients, MailboxError> {
        let accounts = self.accounts().await?;
        let book = self.contact_books().await?.remove(sender).unwrap_or_default();
        let project = sender
            .split_once('@')
            .map(|(_, p)| p.to_owned())
            .or_else(|| accounts.iter().find(|a| a.address == sender).and_then(|a| a.project.clone()));
        let mut resolved = BTreeMap::new();
        let mut expand = |names: &[String]| -> Result<Vec<String>, MailboxError> {
            let mut result = Vec::new();
            for written in names {
                let name = written.trim();
                let found = if accounts.iter().any(|a| a.address == name) {
                    vec![name.to_owned()]
                } else if let Some(contact) = book.iter().find(|c| c.alias == name) {
                    contact.addresses.clone()
                } else if !name.contains('@') {
                    short_name(&accounts, name, project.as_deref())?
                } else {
                    vec![name.to_owned()]
                };
                if found != [written.clone()] {
                    resolved.insert(written.clone(), found.clone());
                }
                for address in found {
                    if !result.contains(&address) {
                        result.push(address);
                    }
                }
            }
            Ok(result)
        };
        let to = expand(to)?;
        let copies = expand(copies)?
            .into_iter()
            .filter(|address| !to.contains(address))
            .collect();
        Ok(Recipients { to, copies, resolved })
    }
}

fn short_name(
    accounts: &[AgentAccount],
    name: &str,
    project: Option<&str>,
) -> Result<Vec<String>, MailboxError> {
    let matches = accounts
        .iter()
        .filter(|a| a.active && a.address.split('@').next() == Some(name))
        .map(|a| a.address.clone())
        .collect::<Vec<_>>();
    let mine = matches
        .iter()
        .filter(|a| project.is_some() && a.split_once('@').map(|(_, p)| p) == project)
        .cloned()
        .collect::<Vec<_>>();
    match (matches.len(), mine.len()) {
        (0, _) => Ok(vec![name.to_owned()]),
        (1, _) => Ok(matches),
        (_, 1) => Ok(mine),
        _ => Err(refusal(
            "destinataire_ambigu",
            &format!("« {name} » désigne plusieurs comptes : {}. Écris l’adresse complète.", matches.join(", ")),
        )),
    }
}
