use super::{hash, MailboxError};
use crate::{domain::ports::*, test_support::*};

fn reason(error: MailboxError) -> String {
    match error {
        MailboxError::Refusal { reason, .. } => reason,
        other => panic!("expected a refusal, got {other}"),
    }
}

#[tokio::test]
async fn nothing_is_watched_by_default_and_only_shared_projects_can_be_ticked() {
    let root = Temporary::new();
    let mailbox = root.mailbox("one").await;
    let observation = mailbox.observation().await.unwrap();
    assert_eq!(observation.state, "absente");
    assert!(observation.projects.is_empty() && observation.key.is_none());
    let refused = mailbox.watch_projects(vec!["cortex".into()]).await.unwrap_err();
    assert_eq!(reason(refused), "projet_inconnu");
    mailbox.declare_project("cortex").await.unwrap();
    let watched = mailbox.watch_projects(vec![" cortex ".into(), "cortex".into()]).await.unwrap();
    assert_eq!(watched.projects, vec!["cortex".to_owned()]);
}

#[tokio::test]
async fn opening_shows_the_key_once_and_keeps_only_its_hash() {
    let root = Temporary::new();
    let mailbox = root.mailbox("one").await;
    assert_eq!(reason(mailbox.open_observation().await.unwrap_err()), "aucun_projet");
    mailbox.declare_project("cortex").await.unwrap();
    mailbox.watch_projects(vec!["cortex".into()]).await.unwrap();
    let journal = mailbox.store.mutations(None, None).await.unwrap().len();
    let key = mailbox.open_observation().await.unwrap();
    assert!(key.len() >= 48);
    let observation = mailbox.observation().await.unwrap();
    assert_eq!(observation.state, "active");
    assert_eq!(observation.key, Some(hash(key.as_bytes())));
    let stored = mailbox.setting("observation").await.unwrap().unwrap().to_string();
    assert!(!stored.contains(&key), "the clear key is never stored");
    assert!(mailbox.observer(&key).await.unwrap().is_some());
    assert!(mailbox.observer("une-autre-cle").await.unwrap().is_none());
    let renewed = mailbox.open_observation().await.unwrap();
    assert!(mailbox.observer(&key).await.unwrap().is_none(), "a new key replaces the old one");
    assert!(mailbox.observer(&renewed).await.unwrap().is_some());
    assert_eq!(mailbox.store.mutations(None, None).await.unwrap().len(), journal, "consent never enters the shared journal");
}

#[tokio::test]
async fn pause_keeps_the_key_and_withdrawal_revokes_it() {
    let root = Temporary::new();
    let mailbox = root.mailbox("one").await;
    assert_eq!(reason(mailbox.pause_observation(true).await.unwrap_err()), "surveillance_absente");
    mailbox.declare_project("cortex").await.unwrap();
    mailbox.watch_projects(vec!["cortex".into()]).await.unwrap();
    let key = mailbox.open_observation().await.unwrap();
    assert_eq!(mailbox.pause_observation(true).await.unwrap().state, "en_pause");
    assert_eq!(mailbox.observer(&key).await.unwrap().unwrap().state, "en_pause");
    assert_eq!(mailbox.pause_observation(false).await.unwrap().state, "active");
    let revoked = mailbox.revoke_observation().await.unwrap();
    assert_eq!(revoked.state, "absente");
    assert!(mailbox.observer(&key).await.unwrap().is_none());
    let actions = mailbox.consent_log().await.unwrap().into_iter().map(|entry| entry.action).collect::<Vec<_>>();
    assert_eq!(actions, ["projets", "ouverte", "pause", "reprise", "retirée"]);
}

#[tokio::test]
async fn delegates_must_be_active_accounts() {
    let root = Temporary::new();
    let mailbox = root.mailbox("one").await;
    assert_eq!(reason(mailbox.set_delegates(vec!["personne@cortex".into()]).await.unwrap_err()), "compte_inconnu");
    let dispatcher = account(&mailbox, "dispatcher").await;
    let observation = mailbox.set_delegates(vec![dispatcher.clone(), String::new()]).await.unwrap();
    assert_eq!(observation.delegates, vec![dispatcher]);
    assert_eq!(mailbox.consent_log().await.unwrap().last().unwrap().action, "délégués");
}
