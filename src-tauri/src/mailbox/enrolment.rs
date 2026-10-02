use super::directory::{agent_identity, raw_identity, resolve_address, system, valid_name};
use super::*;

impl<R: RepositoryPort, E: ExchangePort> MailboxService<R, E> {
    /// Enrols an agent under the box naming rule, as the first mailbox did: the address
    /// `cl-agent-<tâche>-win` and the display `CL_Agent-<Tâche>_WIN` come from the attested
    /// provider, the agent's task and this computer's system, so every account names its post.
    pub async fn enroll_agent(
        &self,
        provider: &str,
        session: &str,
        task: &str,
        role: &str,
        project: Option<String>,
    ) -> Result<Value, MailboxError> {
        let (prefix, display) = agent_identity(provider, task, system())
            .ok_or(MailboxError::from(DomainError::InvalidAccount))?;
        // An account composed before the task was cleaned up (CL_Agent-Agent-X_WIN_WIN) stays the
        // account of the agent that returns with the same task.
        if let Some((legacy, _)) = raw_identity(provider, task, system()).filter(|(l, _)| *l != prefix) {
            let address = match &project {
                Some(p) => format!("{legacy}@{p}"),
                None => legacy.clone(),
            };
            let returning = self.accounts().await?.iter().any(|a| {
                a.address == address && a.active && a.installation == self.installation && a.host == provider
            });
            if returning {
                return self.enroll_as(provider, session, &legacy, &display, role, project).await;
            }
        }
        self.enroll_as(provider, session, &prefix, &display, role, project)
            .await
    }
    #[cfg(test)]
    pub async fn enroll(
        &self,
        provider: &str,
        session: &str,
        display: &str,
        role: &str,
        project: Option<String>,
    ) -> Result<Value, MailboxError> {
        let prefix = display
            .chars()
            .filter(|c| c.is_ascii_alphanumeric() || *c == '-' || *c == '_')
            .collect::<String>()
            .to_lowercase();
        self.enroll_as(provider, session, &prefix, display, role, project)
            .await
    }
    /// The address is always composed first, so a session is never trapped in the account it was
    /// bound to: the same task returns its account, another task gets its own, and the session follows.
    async fn enroll_as(
        &self,
        provider: &str,
        session: &str,
        prefix: &str,
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
        if project.as_ref().is_some_and(|p| !valid_name(p)) {
            return Err(refusal(
                "projet_invalide",
                "Le nom du projet doit être une adresse simple, sans espace ni chemin.",
            ));
        }
        if prefix.is_empty() || prefix == "owner" {
            return Err(DomainError::InvalidAccount.into());
        }
        let current = self.identity(provider, session).await?;
        let existing = self.accounts().await?;
        let mut suffix = 0;
        let address = loop {
            let local = if suffix == 0 {
                prefix.to_owned()
            } else {
                format!("{prefix}-{suffix}")
            };
            let candidate = match &project {
                Some(p) => format!("{local}@{p}"),
                None => local,
            };
            match existing.iter().find(|a| a.address == candidate) {
                None => break candidate,
                // The same agent returning: same task, provider and installation. Its key stays valid.
                Some(a) if a.active && a.installation == self.installation && a.host == provider => {
                    let bound = current.as_ref().is_some_and(|c| {
                        resolve_address(&existing, &c.account).is_ok_and(|e| e == a.address)
                    });
                    let identity = match current {
                        Some(identity) if bound => identity,
                        _ => self.bind_session(provider, session, a).await?,
                    };
                    return Ok(json!({"identity":identity,"account":a,"already_enrolled":true}));
                }
                // This agent's account was merged by the owner: it follows its mail to the target.
                Some(a) if a.merged_into.is_some() && a.installation == self.installation && a.host == provider => {
                    let target = resolve_address(&existing, &a.address)?;
                    let found = existing.iter().find(|t| {
                        t.address == target && t.active && t.installation == self.installation && t.host == provider
                    });
                    let Some(target) = found else {
                        return Err(refusal(
                            "compte_fusionne",
                            &format!("Ton compte {} a été fusionné dans {target} : reprends-le avec me_reconnaitre ou demande son invite à ton humain.", a.address),
                        ));
                    };
                    let identity = self.bind_session(provider, session, target).await?;
                    return Ok(json!({"identity":identity,"account":target,"already_enrolled":true,"fusionne_dans":target.address}));
                }
                Some(_) => suffix += 1,
            }
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
    /// A valid key always wins: a session bound to another account is rebound to this one.
    pub async fn recognize(
        &self,
        provider: &str,
        session: &str,
        address: &str,
        recovery_key: &str,
    ) -> Result<SessionIdentity, MailboxError> {
        let _guard = self.changes.lock().await;
        if let Some(identity) = self.identity(provider, session).await? {
            if identity.account == address {
                return Ok(identity);
            }
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
        // An imported account the agents' rule rejects would be discarded everywhere once
        // re-published: the owner repairs it first, then the agent resumes it.
        if Account::enroll(&account.address, &account.role).is_err() {
            return Err(if account.role.trim().is_empty() {
                refusal("compte_sans_role", "Ce compte importé n’a pas de rôle : demande à ton humain de le renseigner dans Messenger, puis reprends-le.")
            } else {
                refusal("compte_invalide", "Ce compte importé ne respecte pas la règle des comptes : demande à ton humain de le fusionner dans un compte valide.")
            });
        }
        let mut account = account;
        // Resuming from the same installation, host and machine changes nothing to publish.
        let moved = account.installation != self.installation
            || account.host != provider
            || account.machine != self.machine;
        account.installation = self.installation.clone();
        account.host = provider.into();
        account.machine = self.machine.clone();
        if moved {
            self.event(Change::Account {
                account: account.clone(),
            })
            .await?;
        }
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
}
