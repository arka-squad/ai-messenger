use super::*;

// Role and activation changes re-publish the whole account: accounts() keeps the last writer.
impl<R: RepositoryPort, E: ExchangePort> MailboxService<R, E> {
    pub async fn set_role(&self, address: &str, role: &str) -> Result<AgentAccount, MailboxError> {
        let _guard = self.changes.lock().await;
        let role = role.trim();
        if !single_line(role) || matches!(role.to_lowercase().as_str(), "human" | "humain") {
            return Err(refusal(
                "role_invalide",
                "Le rôle tient sur une ligne et désigne un agent, jamais un humain.",
            ));
        }
        let mut account = self.known_account(address).await?;
        if account.role != role {
            account.role = role.into();
            publishable(&account, "modifié")?;
            self.event(Change::Account { account: account.clone() }).await?;
        }
        Ok(account)
    }
    /// Deactivating keeps the account, its mail and its history; it only stops new mail and actions.
    pub async fn set_active(&self, address: &str, active: bool) -> Result<AgentAccount, MailboxError> {
        let _guard = self.changes.lock().await;
        let accounts = self.accounts().await?;
        let mut account = accounts
            .iter()
            .find(|a| a.address == address)
            .cloned()
            .ok_or_else(|| refusal("compte_inconnu", "Ce compte n’existe pas dans cette boîte."))?;
        if account.merged_into.is_some() {
            return Err(refusal(
                "compte_fusionne",
                "Ce compte a été fusionné dans un autre ; son courrier y est déjà redirigé.",
            ));
        }
        if account.active == active {
            return Ok(account);
        }
        // Every installation drops a merge whose target is inactive: the merged accounts would
        // come back and their mail would stop following the target.
        let merged = accounts
            .iter()
            .filter(|a| a.merged_into.as_deref() == Some(address))
            .map(|a| a.address.as_str())
            .collect::<Vec<_>>();
        if !active && !merged.is_empty() {
            return Err(refusal(
                "compte_cible_de_fusion",
                &format!("Ce compte a reçu la fusion de {} : le désactiver annulerait cette fusion et leur courrier ne le suivrait plus. Garde-le actif.", merged.join(", ")),
            ));
        }
        account.active = active;
        publishable(&account, if active { "réactivé" } else { "désactivé" })?;
        self.event(Change::Account { account: account.clone() }).await?;
        Ok(account)
    }
    async fn known_account(&self, address: &str) -> Result<AgentAccount, MailboxError> {
        self.accounts()
            .await?
            .into_iter()
            .find(|a| a.address == address)
            .ok_or_else(|| refusal("compte_inconnu", "Ce compte n’existe pas dans cette boîte."))
    }
}

/// An account every installation would discard (accounts() applies `Account::enroll`) is refused
/// before it is published, so that the owner is never told a change happened when it did not.
fn publishable(account: &AgentAccount, change: &str) -> Result<(), MailboxError> {
    if Account::enroll(&account.address, &account.role).is_ok() {
        return Ok(());
    }
    Err(if account.role.trim().is_empty() {
        refusal(
            "compte_sans_role",
            &format!("Ce compte importé n’a pas de rôle : renseigne-le avant qu’il soit {change}."),
        )
    } else {
        refusal(
            "compte_invalide",
            &format!("L’adresse « {} » ne respecte pas les règles des agents : ce compte importé ne peut pas être {change}. Fusionne-le plutôt dans un compte valide.", account.address),
        )
    })
}

/// Deactivated accounts the owner can reactivate; merged ones stay with their successor.
pub(crate) fn inactive_directory(accounts: &[AgentAccount]) -> Vec<Value> {
    accounts
        .iter()
        .filter(|a| !a.active && a.merged_into.is_none())
        .map(|a| json!({"address":a.address,"display":a.display,"role":a.role,"host":a.host,"machine":a.machine,"project":a.project}))
        .collect()
}
