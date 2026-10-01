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
    pub async fn declare_project(&self, name: &str) -> Result<String, MailboxError> {
        let name = project_name(name);
        if !valid_name(&name) {
            return Err(refusal(
                "projet_invalide",
                "Choisis un nom simple : lettres sans accent, chiffres, point, tiret ou soulignement.",
            ));
        }
        if name == COMMON_PROJECT {
            return Err(refusal(
                "projet_reserve",
                "« commun » désigne déjà les comptes sans projet : choisis un autre nom.",
            ));
        }
        let _guard = self.changes.lock().await;
        // Pending, published and received declarations all count; random ids never collide between machines.
        if self
            .events()
            .await?
            .iter()
            .any(|e| matches!(&e.change, Change::Project { name: declared } if *declared == name))
        {
            return Ok(name);
        }
        self.event(Change::Project { name: name.clone() }).await?;
        Ok(name)
    }
    #[cfg(test)]
    pub async fn projects(&self) -> Result<Vec<String>, MailboxError> {
        Ok(shared_projects(&self.events().await?, &self.accounts().await?))
    }
    /// Shares once the projects that earlier versions kept only in the local setting.
    pub async fn share_legacy_projects(&self) -> Result<usize, MailboxError> {
        if self.setting("projects_shared").await?.is_some() {
            return Ok(0);
        }
        let legacy = self
            .setting("projects")
            .await?
            .and_then(|v| v.as_array().cloned())
            .unwrap_or_default();
        let mut shared = 0;
        for name in legacy
            .iter()
            .filter_map(|v| v.get("name").and_then(Value::as_str))
        {
            match self.declare_project(name).await {
                Ok(_) => shared += 1,
                Err(MailboxError::Refusal { .. }) => {}
                Err(error) => return Err(error),
            }
        }
        self.set_setting("projects_shared", json!(true)).await?;
        Ok(shared)
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

// The interface already names the accounts without a project "commun".
pub(crate) const COMMON_PROJECT: &str = "commun";

pub(crate) fn project_name(name: &str) -> String {
    name.trim()
        .to_lowercase()
        .split_whitespace()
        .collect::<Vec<_>>()
        .join("-")
}

/// This computer's system in account names: `win`, `mac` or `lnx`.
pub(crate) fn system() -> &'static str {
    if cfg!(windows) {
        "win"
    } else if cfg!(target_os = "macos") {
        "mac"
    } else {
        "lnx"
    }
}

/// `(address prefix, display)` for an agent: `cl-agent-messengerai-win` and
/// `CL_Agent-MessengerAI_WIN`. The prefix stays within 32 characters.
pub(crate) fn agent_identity(provider: &str, task: &str, system: &str) -> Option<(String, String)> {
    compose_identity(provider, task, system, true)
}

/// The identity composed from the task exactly as given, before `bare_task`: accounts enrolled
/// that way keep serving the agent that returns with the same task.
pub(crate) fn raw_identity(provider: &str, task: &str, system: &str) -> Option<(String, String)> {
    compose_identity(provider, task, system, false)
}

/// A task already written as an account name (`CL_Agent-Cortex-5_WIN`, `Agent-Cortex-5_WIN`)
/// keeps only the task, so the composed name is never doubled.
pub(crate) fn bare_task(task: &str) -> &str {
    let mut rest = task.trim();
    let head = rest.get(..9).unwrap_or("");
    let named = head.len() == 9
        && head.as_bytes()[..2].iter().all(u8::is_ascii_alphabetic)
        && (head[2..].eq_ignore_ascii_case("_agent-") || head[2..].eq_ignore_ascii_case("-agent-"));
    if named {
        rest = &rest[9..];
    } else if rest.get(..6).is_some_and(|h| h.eq_ignore_ascii_case("agent-") || h.eq_ignore_ascii_case("agent_")) {
        rest = &rest[6..];
    }
    loop {
        let cut = ["_win", "_mac", "_lnx", "-win", "-mac", "-lnx"].into_iter().find(|suffix| {
            rest.len() > suffix.len()
                && rest.get(rest.len() - suffix.len()..).is_some_and(|end| end.eq_ignore_ascii_case(suffix))
        });
        match cut {
            Some(suffix) => rest = rest[..rest.len() - suffix.len()].trim_end(),
            None => break,
        }
    }
    let rest = rest.trim();
    if rest.is_empty() { task.trim() } else { rest }
}

fn compose_identity(provider: &str, task: &str, system: &str, bare: bool) -> Option<(String, String)> {
    if task.contains(['\n', '\r']) {
        return None;
    }
    let task = task.split_whitespace().collect::<Vec<_>>().join(" ");
    let task = if bare { bare_task(&task).to_owned() } else { task };
    if task.is_empty() {
        return None;
    }
    let initials = match provider {
        "claude-code" => "cl".to_owned(),
        "codex" => "cd".to_owned(),
        "kimi" | "kimi-code" => "km".to_owned(),
        "hermes" => "he".to_owned(),
        other => {
            let letters = slug(other, 2);
            if letters.is_empty() { "ag".to_owned() } else { letters }
        }
    };
    let room = 32usize.saturating_sub(format!("{initials}-agent--{system}").len()).max(4);
    let task_slug = Some(slug(&task, room)).filter(|s| !s.is_empty()).unwrap_or_else(|| "agent".into());
    Some((
        format!("{initials}-agent-{task_slug}-{system}"),
        format!("{}_Agent-{task}_{}", initials.to_uppercase(), system.to_uppercase()),
    ))
}

/// Lowercase ASCII, accents folded, other characters reduced to single `-`, at most `max` long.
fn slug(text: &str, max: usize) -> String {
    let folded = text.to_lowercase().chars().map(|c| match c {
        'à' | 'â' | 'ä' | 'á' => 'a',
        'é' | 'è' | 'ê' | 'ë' => 'e',
        'î' | 'ï' | 'í' => 'i',
        'ô' | 'ö' | 'ó' => 'o',
        'ù' | 'û' | 'ü' | 'ú' => 'u',
        'ç' => 'c',
        c if c.is_ascii_alphanumeric() => c,
        _ => '-',
    }).collect::<String>();
    let joined = folded.split('-').filter(|p| !p.is_empty()).collect::<Vec<_>>().join("-");
    joined.chars().take(max).collect::<String>().trim_matches('-').to_owned()
}

/// A name another machine may have published: valid, normalized and not the common group.
fn shared_name(name: &str) -> bool {
    valid_name(name) && name != COMMON_PROJECT && project_name(name) == name
}

/// Declared names, deduplicated across machines, plus the projects carried by active accounts.
/// A malformed name from another machine is ignored, never fatal.
pub(crate) fn shared_projects(events: &[Event], accounts: &[AgentAccount]) -> Vec<String> {
    events
        .iter()
        .filter_map(|e| match &e.change {
            Change::Project { name } => Some(name.clone()),
            _ => None,
        })
        .chain(accounts.iter().filter(|a| a.active).filter_map(|a| {
            a.address
                .split_once('@')
                .map(|(_, project)| project.to_owned())
                .or_else(|| a.project.clone())
        }))
        .filter(|name| shared_name(name))
        .collect::<BTreeSet<_>>()
        .into_iter()
        .collect()
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
