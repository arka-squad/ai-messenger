//! The Owner's consent for Cortex to watch projects of this box. It stays on this installation:
//! nothing of it enters the shared journal.
use super::*;
use serde::{Deserialize, Serialize};

const SETTING: &str = "observation";
const LOG: &str = "observation_log";
const LOG_LIMIT: usize = 200;

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct Observation {
    pub projects: Vec<String>,
    /// Accounts that speak for the Owner, such as the dispatcher.
    pub delegates: Vec<String>,
    /// `absente`, `active` or `en_pause`.
    pub state: String,
    /// Hash of the observer key: the key itself is shown once and never kept.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub key: Option<String>,
}

impl Default for Observation {
    fn default() -> Self {
        Self { projects: Vec::new(), delegates: Vec::new(), state: "absente".into(), key: None }
    }
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct ConsentEntry {
    pub at: String,
    pub action: String,
    pub detail: String,
}

impl<R: RepositoryPort, E: ExchangePort> MailboxService<R, E> {
    pub async fn observation(&self) -> Result<Observation, MailboxError> {
        Ok(self
            .setting(SETTING)
            .await?
            .and_then(|value| serde_json::from_value(value).ok())
            .unwrap_or_default())
    }

    pub async fn consent_log(&self) -> Result<Vec<ConsentEntry>, MailboxError> {
        Ok(self
            .setting(LOG)
            .await?
            .and_then(|value| serde_json::from_value(value).ok())
            .unwrap_or_default())
    }

    /// Every change of consent is kept in the local log: who watches what, since when.
    async fn consent(
        &self,
        observation: &Observation,
        action: &str,
        detail: String,
    ) -> Result<(), MailboxError> {
        self.set_setting(SETTING, json!(observation)).await?;
        let mut log = self.consent_log().await?;
        log.push(ConsentEntry { at: now(), action: action.into(), detail });
        let excess = log.len().saturating_sub(LOG_LIMIT);
        log.drain(..excess);
        self.set_setting(LOG, json!(log)).await?;
        // The pushed feed waits on arrivals: a pause, a withdrawal or a new scope applies at once.
        self.arrived.notify_waiters();
        Ok(())
    }

    /// Nothing is watched by default: only the projects the Owner ticks, among those shared here.
    pub async fn watch_projects(&self, projects: Vec<String>) -> Result<Observation, MailboxError> {
        let shared = directory::shared_projects(&self.events().await?, &self.accounts().await?);
        let chosen = projects
            .into_iter()
            .map(|project| project.trim().to_owned())
            .filter(|project| !project.is_empty())
            .collect::<BTreeSet<_>>();
        if let Some(unknown) = chosen.iter().find(|project| !shared.contains(project)) {
            return Err(refusal(
                "projet_inconnu",
                &format!("Le projet {unknown} n’est pas partagé dans cette boîte."),
            ));
        }
        let mut observation = self.observation().await?;
        observation.projects = chosen.into_iter().collect();
        let detail = if observation.projects.is_empty() {
            "aucun projet".into()
        } else {
            observation.projects.join(", ")
        };
        self.consent(&observation, "projets", detail).await?;
        Ok(observation)
    }

    /// The accounts whose « décision Owner » counts as delegated rather than unattested.
    pub async fn set_delegates(&self, delegates: Vec<String>) -> Result<Observation, MailboxError> {
        let accounts = self.accounts().await?;
        let mut chosen = BTreeSet::new();
        for address in delegates.iter().map(|a| a.trim()).filter(|a| !a.is_empty()) {
            let resolved = directory::resolve_address(&accounts, address)?;
            if !accounts.iter().any(|a| a.address == resolved && a.active) {
                return Err(refusal(
                    "compte_inconnu",
                    &format!("Le compte {address} n’existe pas ou n’est plus actif."),
                ));
            }
            chosen.insert(resolved);
        }
        let mut observation = self.observation().await?;
        observation.delegates = chosen.into_iter().collect();
        let detail = if observation.delegates.is_empty() {
            "aucun délégué".into()
        } else {
            observation.delegates.join(", ")
        };
        self.consent(&observation, "délégués", detail).await?;
        Ok(observation)
    }

    /// Opens the observation with a new key, returned once to be given to Cortex. Opening again
    /// replaces the key: the previous one stops working.
    pub async fn open_observation(&self) -> Result<String, MailboxError> {
        let mut observation = self.observation().await?;
        if observation.projects.is_empty() {
            return Err(refusal(
                "aucun_projet",
                "Coche au moins un projet avant d’ouvrir la surveillance.",
            ));
        }
        let key = new_id() + &new_id();
        observation.key = Some(hash(key.as_bytes()));
        observation.state = "active".into();
        self.consent(&observation, "ouverte", "nouvelle clé d’observateur".into()).await?;
        Ok(key)
    }

    /// A pause stops the flow and the reads; the key stays valid for the resumption.
    pub async fn pause_observation(&self, paused: bool) -> Result<Observation, MailboxError> {
        let mut observation = self.observation().await?;
        if observation.key.is_none() {
            return Err(refusal(
                "surveillance_absente",
                "La surveillance n’est pas ouverte.",
            ));
        }
        observation.state = if paused { "en_pause" } else { "active" }.into();
        let action = if paused { "pause" } else { "reprise" };
        self.consent(&observation, action, String::new()).await?;
        Ok(observation)
    }

    /// Withdrawal revokes the key: the observer no longer exists.
    pub async fn revoke_observation(&self) -> Result<Observation, MailboxError> {
        let mut observation = self.observation().await?;
        observation.key = None;
        observation.state = "absente".into();
        self.consent(&observation, "retirée", "clé révoquée".into()).await?;
        Ok(observation)
    }

    /// The observation this key opens, whatever its state; none for an unknown or revoked key.
    pub(crate) async fn observer(&self, key: &str) -> Result<Option<Observation>, MailboxError> {
        let observation = self.observation().await?;
        let presented = hash(key.as_bytes());
        let valid = observation
            .key
            .as_deref()
            .is_some_and(|expected| same(expected.as_bytes(), presented.as_bytes()));
        Ok(valid.then_some(observation))
    }
}

/// Compares two hashes in constant time.
fn same(expected: &[u8], presented: &[u8]) -> bool {
    expected.len() == presented.len()
        && expected.iter().zip(presented).fold(0u8, |diff, (a, b)| diff | (a ^ b)) == 0
}
