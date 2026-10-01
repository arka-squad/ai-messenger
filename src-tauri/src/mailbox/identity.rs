use super::*;

/// The key of a working folder: `\` becomes `/`, trailing `/` are dropped, case is folded on Windows.
/// Only absolute paths qualify, so two agents never share a key by accident.
pub(crate) fn folder_key(path: &str) -> Option<String> {
    let mut key = path.trim().replace('\\', "/");
    // Git Bash names C:\ as /c/ on Windows; hooks and channels use the native form.
    let bytes = key.as_bytes();
    if cfg!(windows) && bytes.len() >= 2 && bytes[0] == b'/' && bytes[1].is_ascii_alphabetic() && (bytes.len() == 2 || bytes[2] == b'/') {
        key = format!("{}:{}", &key[1..2], &key[2..]);
    }
    while key.len() > 1 && key.ends_with('/') {
        key.pop();
    }
    let bytes = key.as_bytes();
    let drive = bytes.len() >= 2
        && bytes[0].is_ascii_alphabetic()
        && bytes[1] == b':'
        && (bytes.len() == 2 || bytes[2] == b'/');
    if !(key.starts_with('/') || drive) || key.chars().any(char::is_control) || key.len() > 1024 {
        return None;
    }
    Some(if cfg!(windows) { key.to_lowercase() } else { key })
}

/// A drive, volume or share root: never a working folder an agent is remembered by.
fn root(key: &str) -> bool {
    let parts = key.split('/').filter(|p| !p.is_empty()).collect::<Vec<_>>();
    let bytes = key.as_bytes();
    key.is_empty()
        || key == "/"
        || (bytes.len() == 2 && bytes[1] == b':')
        || (key.starts_with("//") && parts.len() <= 2)
        || (matches!(parts.first(), Some(v) if v.eq_ignore_ascii_case("volumes")) && parts.len() <= 2)
        || (parts.first() == Some(&"mnt") && parts.len() <= 2)
}

/// The user's home folder and every folder above it, and drive, volume or share roots: a terminal
/// opens there by default, so these folders never retain an account.
pub(crate) fn never_remembered(key: &str) -> bool {
    root(key) || home_key().is_some_and(|home| home == key || home.starts_with(&format!("{key}/")))
}

/// The user's home folder, as a folder key.
pub(crate) fn home_key() -> Option<String> {
    let home = if cfg!(windows) { std::env::var("USERPROFILE") } else { std::env::var("HOME") };
    home.ok().and_then(|h| folder_key(&h))
}

/// The parents of a folder, nearest first. The walk stops before the user's home folder (and
/// anything above it) and before a drive or volume root: those are never anyone's folder.
pub(crate) fn parents(key: &str, home: Option<&str>) -> Vec<String> {
    let mut result = Vec::new();
    let mut current = key;
    while let Some((parent, _)) = current.rsplit_once('/') {
        let above_home = home.is_some_and(|h| h == parent || h.starts_with(&format!("{parent}/")));
        if root(parent) || above_home {
            break;
        }
        result.push(parent.to_owned());
        current = parent;
    }
    result
}

impl<R: RepositoryPort, E: ExchangePort> MailboxService<R, E> {
    /// The account last enrolled or resumed by this provider in exactly this folder, while it is
    /// still active on this installation. Parents never bind: see `remembered_parent`.
    pub(crate) async fn remembered(
        &self,
        provider: &str,
        folder: &str,
    ) -> Result<Option<AgentAccount>, MailboxError> {
        match folder_key(folder) {
            Some(key) => self.remembered_at(provider, &key).await,
            None => Ok(None),
        }
    }
    async fn remembered_at(
        &self,
        provider: &str,
        key: &str,
    ) -> Result<Option<AgentAccount>, MailboxError> {
        // A folder several agents of this tool work in names none of them.
        if never_remembered(key) || self.shared_at(provider, key).await?.len() > 1 {
            return Ok(None);
        }
        let saved = self.setting(&format!("identity:{provider}:{key}")).await?;
        let Some(address) = saved.as_ref().and_then(Value::as_str) else {
            return Ok(None);
        };
        let accounts = self.accounts().await?;
        let effective = directory::resolve_address(&accounts, address)?;
        Ok(accounts
            .into_iter()
            .find(|a| a.address == effective && a.active && a.installation == self.installation))
    }
    /// The nearest parent folder where this provider remembered an active account: a hint offered
    /// to the agent, never a binding. Returns the parent's key and its account.
    pub(crate) async fn remembered_parent(
        &self,
        provider: &str,
        folder: &str,
    ) -> Result<Option<(String, AgentAccount)>, MailboxError> {
        let Some(key) = folder_key(folder) else {
            return Ok(None);
        };
        for parent in parents(&key, home_key().as_deref()) {
            if let Some(account) = self.remembered_at(provider, &parent).await? {
                return Ok(Some((parent, account)));
            }
        }
        Ok(None)
    }
    /// The active accounts of this installation that several agents of this tool enrolled or
    /// resumed in exactly this folder. Two or more: the folder rebinds nobody.
    pub(crate) async fn shared(
        &self,
        provider: &str,
        folder: &str,
    ) -> Result<Vec<AgentAccount>, MailboxError> {
        match folder_key(folder) {
            Some(key) => self.shared_at(provider, &key).await,
            None => Ok(Vec::new()),
        }
    }
    async fn shared_at(&self, provider: &str, key: &str) -> Result<Vec<AgentAccount>, MailboxError> {
        let listed = self
            .setting(&format!("identity_shared:{provider}:{key}"))
            .await?
            .and_then(|v| v.as_array().cloned())
            .unwrap_or_default();
        if listed.is_empty() {
            return Ok(Vec::new());
        }
        let accounts = self.accounts().await?;
        let mut result: Vec<AgentAccount> = Vec::new();
        for address in listed.iter().filter_map(Value::as_str) {
            let Ok(effective) = directory::resolve_address(&accounts, address) else {
                continue;
            };
            let found = accounts
                .iter()
                .find(|a| a.address == effective && a.active && a.installation == self.installation);
            if let Some(account) = found.filter(|a| !result.iter().any(|r| r.address == a.address)) {
                result.push(account.clone());
            }
        }
        Ok(result)
    }
    /// Remembers the account for this exact folder only, never for the home folder or a root.
    /// When another active agent of this tool already works there, the folder becomes shared.
    pub(crate) async fn remember_folder(
        &self,
        provider: &str,
        folder: &str,
        account: &str,
    ) -> Result<(), MailboxError> {
        let Some(key) = folder_key(folder).filter(|key| !never_remembered(key)) else {
            return Ok(());
        };
        let name = format!("identity:{provider}:{key}");
        let previous = self.setting(&name).await?.and_then(|v| v.as_str().map(str::to_owned));
        if let Some(previous) = previous.filter(|p| p != account) {
            let accounts = self.accounts().await?;
            let active = directory::resolve_address(&accounts, &previous).ok().filter(|effective| {
                effective != account
                    && accounts
                        .iter()
                        .any(|a| a.address == *effective && a.active && a.installation == self.installation)
            });
            if let Some(previous) = active {
                let list = format!("identity_shared:{provider}:{key}");
                let mut listed = self
                    .setting(&list)
                    .await?
                    .and_then(|v| v.as_array().cloned())
                    .unwrap_or_default();
                for address in [previous.as_str(), account] {
                    if !listed.iter().any(|v| v.as_str() == Some(address)) {
                        listed.push(json!(address));
                    }
                }
                self.set_setting(&list, json!(listed)).await?;
            }
        }
        self.set_setting(&name, json!(account)).await
    }
    /// Binds a session to an account this installation already holds; no key is minted.
    pub(crate) async fn bind_session(
        &self,
        provider: &str,
        session: &str,
        account: &AgentAccount,
    ) -> Result<SessionIdentity, MailboxError> {
        let identity = SessionIdentity {
            session: session.into(),
            provider: provider.into(),
            account: account.address.clone(),
            installation: self.installation.clone(),
            project: account.project.clone(),
        };
        self.set_setting(&format!("session:{provider}:{session}"), json!(identity)).await?;
        Ok(identity)
    }
    /// Active accounts this installation created or resumed for this provider, for an unbound
    /// session. The accounts sharing exactly `folder` come first (`dossier_partage`), then the
    /// account remembered in a parent folder (`dossier_parent`).
    pub(crate) async fn candidates(
        &self,
        provider: &str,
        folder: Option<&str>,
    ) -> Result<Vec<Value>, MailboxError> {
        let key = folder.and_then(folder_key);
        let shared = match &key {
            Some(key) => self.shared_at(provider, key).await?,
            None => Vec::new(),
        };
        let parent = match folder {
            Some(folder) => self.remembered_parent(provider, folder).await?,
            None => None,
        };
        let view = |a: &AgentAccount| json!({"address":a.address,"display":a.display,"role":a.role,"project":a.project});
        let mut result = Vec::new();
        let mut listed: Vec<String> = Vec::new();
        for account in shared.iter().filter(|_| shared.len() > 1) {
            let mut first = view(account);
            first["dossier_partage"] = json!(key);
            result.push(first);
            listed.push(account.address.clone());
        }
        if let Some((parent_key, account)) = parent.filter(|(_, a)| !listed.contains(&a.address)) {
            let mut first = view(&account);
            first["dossier_parent"] = json!(parent_key);
            result.push(first);
            listed.push(account.address);
        }
        for account in self.accounts().await? {
            if account.active && account.installation == self.installation && account.host == provider && !listed.contains(&account.address) {
                result.push(view(&account));
            }
        }
        Ok(result)
    }
    /// A Claude channel sidecar connected: from now on its session can be named as a delivery
    /// route. Nothing is bound from the folder: another session there may be another agent.
    pub fn register_channel(&self, session: &str) {
        let mut channels = self.channels.lock().expect("channel lock");
        channels.retain(|s| s != session);
        channels.push(session.into());
    }
    pub(crate) fn live_channel(&self, session: &str) -> bool {
        self.channels.lock().expect("channel lock").iter().any(|s| s == session)
    }
    pub(crate) async fn set_route(
        &self,
        account: &str,
        provider: &str,
        session: &str,
    ) -> Result<(), MailboxError> {
        let _guard = self.routes.lock().await;
        self.set_setting(&format!("account_route:{account}"), json!({"provider":provider,"session":session}))
            .await
    }
    /// The live route of an account as `(provider, session)`; a removed route reads as none.
    pub(crate) async fn account_route(&self, account: &str) -> Result<Option<(String, String)>, MailboxError> {
        let saved = self.setting(&format!("account_route:{account}")).await?;
        Ok(saved.and_then(|v| Some((v["provider"].as_str()?.to_owned(), v["session"].as_str()?.to_owned()))))
    }
    /// A session that moved to another account no longer carries the pushes of the one it left.
    pub(crate) async fn release_route(
        &self,
        account: &str,
        provider: &str,
        sessions: &[&str],
    ) -> Result<(), MailboxError> {
        let _guard = self.routes.lock().await;
        let name = format!("account_route:{account}");
        let Some(route) = self.setting(&name).await? else {
            return Ok(());
        };
        if route["provider"] == provider && route["session"].as_str().is_some_and(|s| sessions.contains(&s)) {
            self.set_setting(&name, Value::Null).await?;
        }
        Ok(())
    }
    pub(crate) fn note_pushed(&self, provider: &str, session: &str, route: &str) {
        self.pushed.lock().expect("pushed lock").insert(format!("{provider}:{session}"), route.into());
    }
    pub(crate) fn pushed_by(&self, provider: &str, session: &str) -> Option<String> {
        self.pushed.lock().expect("pushed lock").get(&format!("{provider}:{session}")).cloned()
    }
    pub(crate) fn returned_to(&self, session: &str) -> BTreeSet<String> {
        self.returned.lock().expect("returned lock").get(session).cloned().unwrap_or_default()
    }
    pub(crate) fn note_returned<'a>(&self, session: &str, ids: impl IntoIterator<Item = &'a String>) {
        self.returned
            .lock()
            .expect("returned lock")
            .entry(session.into())
            .or_default()
            .extend(ids.into_iter().cloned());
    }
}

impl<R: RepositoryPort + 'static, E: ExchangePort + 'static> MailboxService<R, E> {
    /// Called by the channel server when a sidecar disconnects. Routes that name it stay: delivery
    /// reports no session meanwhile, and pushes resume when the same session reconnects, as every
    /// sidecar does after the app restarts.
    pub fn channel_closed(self: &Arc<Self>, session: &str) {
        self.channels.lock().expect("channel lock").retain(|s| s != session);
    }
}
