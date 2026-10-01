use std::sync::Arc;

use crate::{
    domain::{
        models::ProviderStatus,
        ports::{ExchangePort, PortError, ProviderPort, RepositoryPort},
        Reachability,
    },
    mailbox::MailboxService,
};

macro_rules! providers {
    ($($provider:ident),+ $(,)?) => {
        $(mod $provider;)+

        pub(crate) fn identify(client:&str)->&'static str {
            let name=client.to_lowercase();
            [$($provider::ID),+].into_iter().find(|id|name.contains(id.split('-').next().unwrap_or(id))).unwrap_or("mcp")
        }
        fn installed() -> Vec<Box<dyn ProviderPort>> {
            vec![$(Box::new($provider::Provider::new())),+]
        }
    };
}

mod claude_http;
providers!(codex, claude, kimi);

pub(crate) fn executable(name: &str) -> std::path::PathBuf {
    let files = if cfg!(windows) {
        vec![
            format!("{name}.exe"),
            format!("{name}.cmd"),
            format!("{name}.bat"),
        ]
    } else {
        vec![name.into()]
    };
    if let Some(path) = std::env::var_os("PATH").and_then(|paths| {
        std::env::split_paths(&paths)
            .flat_map(|p| files.iter().map(move |file| p.join(file)))
            .find(|p| p.is_file())
    }) {
        return path;
    }
    let home = std::env::var_os("HOME")
        .or_else(|| std::env::var_os("USERPROFILE"))
        .map(std::path::PathBuf::from)
        .unwrap_or_default();
    [
        home.join(".local/bin"),
        home.join("AppData/Roaming/npm"),
        std::path::PathBuf::from("/usr/local/bin"),
        std::path::PathBuf::from("/opt/homebrew/bin"),
    ]
    .into_iter()
    .flat_map(|p| files.iter().map(move |file| p.join(file)))
    .find(|p| p.is_file())
    .unwrap_or_else(|| name.into())
}

pub async fn serve_claude<R, E>(mailbox: Arc<MailboxService<R, E>>)
where
    R: RepositoryPort + 'static,
    E: ExchangePort + 'static,
{
    claude::serve(mailbox).await;
}

pub struct ProviderRegistry(Vec<Box<dyn ProviderPort>>);

impl ProviderRegistry {
    pub fn new() -> Self {
        Self(installed())
    }

    pub fn statuses(&self) -> Vec<ProviderStatus> {
        self.0.iter().map(|provider| provider.present()).collect()
    }

    pub fn equip(&self, id: &str) -> Result<ProviderStatus, PortError> {
        self.find(id)?.equip()
    }

    pub fn deliver(
        &self,
        id: &str,
        session: &str,
        message: &str,
    ) -> Result<Reachability, PortError> {
        self.find(id)?.deliver(session, message)
    }

    pub fn deliver_verdict(
        &self,
        id: &str,
        session: &str,
        verdict: &str,
    ) -> Result<Reachability, PortError> {
        self.find(id)?.deliver_verdict(session, verdict)
    }

    fn find(&self, id: &str) -> Result<&dyn ProviderPort, PortError> {
        self.0
            .iter()
            .find(|provider| provider.id() == id)
            .map(Box::as_ref)
            .ok_or_else(|| PortError(format!("fournisseur inconnu : {id}")))
    }
}

#[cfg(test)]
struct FakeProvider;

#[cfg(test)]
impl ProviderPort for FakeProvider {
    fn id(&self) -> &'static str {
        "fake"
    }

    fn present(&self) -> ProviderStatus {
        ProviderStatus {
            id: self.id().into(),
            name: "Fictif".into(),
            version: None,
            state: "prêt".into(),
            detail: "test".into(),
            available: true,
            equipped: true,
            can_equip: false,
        }
    }

    fn equip(&self) -> Result<ProviderStatus, PortError> {
        Ok(self.present())
    }

    fn deliver(&self, _: &str, _: &str) -> Result<Reachability, PortError> {
        Ok(Reachability::NoSession)
    }

    fn deliver_verdict(&self, _: &str, _: &str) -> Result<Reachability, PortError> {
        Ok(Reachability::NoSession)
    }

    fn receive(&self) -> bool {
        true
    }
}

#[cfg(test)]
mod tests {
    use super::{FakeProvider, ProviderRegistry};
    use crate::domain::Reachability;

    #[test]
    fn fake_provider_exercises_the_five_capabilities() {
        assert_eq!(super::identify("Claude Code"), "claude-code");
        assert_eq!(super::identify("Codex"), "codex");
        assert_eq!(super::identify("Kimi CLI"), "kimi");
        assert_eq!(super::identify("Autre outil"), "mcp");
        let provider = ProviderRegistry(vec![Box::new(FakeProvider)]);
        assert!(provider.statuses()[0].available);
        assert!(provider.equip("fake").unwrap().equipped);
        assert_eq!(
            provider.deliver("fake", "session", "message").unwrap(),
            Reachability::NoSession
        );
        assert_eq!(
            provider
                .deliver_verdict("fake", "session", "verdict")
                .unwrap(),
            Reachability::NoSession
        );
        assert!(provider.find("fake").unwrap().receive());
    }
}
