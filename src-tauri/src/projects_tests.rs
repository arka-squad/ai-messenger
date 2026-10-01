use crate::{
    domain::{
        journal::{Change, Event, ExchangeItem, Mutation},
        ports::{ExchangePort, RepositoryPort},
    },
    mailbox::{now, MailboxError, MailboxService},
    test_support::*,
};
use serde_json::json;
async fn declarations<R: RepositoryPort, E: ExchangePort>(mailbox: &MailboxService<R, E>) -> usize {
    mailbox
        .events()
        .await
        .unwrap()
        .iter()
        .filter(|e| matches!(e.change, Change::Project { .. }))
        .count()
}
fn reason(result: Result<String, MailboxError>) -> String {
    match result {
        Err(MailboxError::Refusal { reason, .. }) => reason,
        other => panic!("refus attendu : {other:?}"),
    }
}
#[tokio::test]
async fn a_project_declared_without_any_folder_appears_on_every_installation() {
    let root = Temporary::new();
    let first = root.mailbox("first").await;
    let second = root.mailbox("second").await;
    assert_eq!(
        first.declare_project("  Mon Projet ").await.unwrap(),
        "mon-projet"
    );
    assert_eq!(first.projects().await.unwrap(), vec!["mon-projet"]);
    assert!(second.projects().await.unwrap().is_empty());
    second.receive().await.unwrap();
    assert_eq!(second.projects().await.unwrap(), vec!["mon-projet"]);
}
#[tokio::test]
async fn duplicate_and_concurrent_declarations_produce_a_single_project() {
    let root = Temporary::new();
    let first = root.mailbox("first").await;
    let second = root.mailbox("second").await;
    first.declare_project("alpha").await.unwrap();
    assert_eq!(first.declare_project(" Alpha ").await.unwrap(), "alpha");
    assert_eq!(declarations(&first).await, 1);
    // The second machine has not read the box yet: both declarations coexist under distinct ids.
    second.declare_project("alpha").await.unwrap();
    first.receive().await.unwrap();
    second.receive().await.unwrap();
    for mailbox in [&first, &second] {
        assert_eq!(mailbox.projects().await.unwrap(), vec!["alpha"]);
        assert_eq!(declarations(mailbox).await, 2);
        assert!(!mailbox
            .incidents()
            .iter()
            .any(|i| i.kind == "mutation_en_conflit"));
    }
    second.declare_project("ALPHA").await.unwrap();
    assert_eq!(declarations(&second).await, 2);
}
#[tokio::test]
async fn names_are_normalized_and_invalid_or_reserved_names_are_refused() {
    let root = Temporary::new();
    let mailbox = root.mailbox("one").await;
    assert_eq!(
        mailbox.declare_project("  Mon   Projet\t2 ").await.unwrap(),
        "mon-projet-2"
    );
    for name in [
        "",
        "   ",
        "a/b",
        "..",
        "équipe",
        "x:y",
        "x".repeat(121).as_str(),
    ] {
        assert_eq!(
            reason(mailbox.declare_project(name).await),
            "projet_invalide",
            "{name}"
        );
    }
    for name in ["commun", " Commun "] {
        assert_eq!(
            reason(mailbox.declare_project(name).await),
            "projet_reserve"
        );
    }
    assert_eq!(declarations(&mailbox).await, 1);
    assert_eq!(mailbox.projects().await.unwrap(), vec!["mon-projet-2"]);
}
#[tokio::test]
async fn active_accounts_contribute_their_projects_and_malformed_declarations_are_ignored() {
    let root = Temporary::new();
    let mailbox = root.mailbox("one").await;
    let alpha = account(&mailbox, "alpha").await;
    let solo = mailbox
        .enroll("test", "solo", "solo", "développeur", None)
        .await
        .unwrap()["identity"]["account"]
        .as_str()
        .unwrap()
        .to_owned();
    mailbox
        .file_account(&solo, Some("range".into()))
        .await
        .unwrap();
    let gone = mailbox
        .enroll("test", "gone", "gone", "développeur", Some("ancien".into()))
        .await
        .unwrap()["identity"]["account"]
        .as_str()
        .unwrap()
        .to_owned();
    mailbox.merge_accounts(&gone, &alpha).await.unwrap();
    mailbox.declare_project("declare").await.unwrap();
    for (id, name) in [
        ("evil", "../evil"),
        ("reserved", "commun"),
        ("upper", "Upper"),
    ] {
        let forged = Mutation::Event(Event {
            id: format!("forged-{id}"),
            emitted_at: now(),
            installation: "other".into(),
            change: Change::Project { name: name.into() },
        });
        mailbox
            .exchange
            .deposit(ExchangeItem::Mutation(&forged))
            .unwrap();
    }
    assert_eq!(mailbox.receive().await.unwrap(), 3);
    assert_eq!(
        mailbox.projects().await.unwrap(),
        vec!["declare", "project", "range"]
    );
}
#[tokio::test]
async fn legacy_local_projects_are_shared_once_and_the_setting_is_kept() {
    let root = Temporary::new();
    let first = root.mailbox("first").await;
    let second = root.mailbox("second").await;
    let legacy = json!([
        {"name":"ancien","directory":"C:\\Projets\\ancien"},
        {"name":"sans-dossier"},
        {"name":"bad name/","directory":"/tmp"},
        {"name":"commun","directory":"/tmp"},
        42
    ]);
    first.set_setting("projects", legacy.clone()).await.unwrap();
    assert_eq!(first.share_legacy_projects().await.unwrap(), 2);
    assert_eq!(
        first.setting("projects_shared").await.unwrap(),
        Some(json!(true))
    );
    assert_eq!(first.setting("projects").await.unwrap(), Some(legacy));
    first
        .set_setting("projects", json!([{"name":"plus-tard","directory":"/tmp"}]))
        .await
        .unwrap();
    assert_eq!(first.share_legacy_projects().await.unwrap(), 0);
    assert_eq!(declarations(&first).await, 2);
    second.receive().await.unwrap();
    assert_eq!(
        second.projects().await.unwrap(),
        vec!["ancien", "sans-dossier"]
    );
}
