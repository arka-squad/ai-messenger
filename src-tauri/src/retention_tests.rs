use super::*;
use crate::{
    domain::ports::ExchangePort,
    test_support::{message, Temporary},
};
fn old_mail(root: &Temporary) -> (DirectoryExchange, Mutation, PathBuf) {
    let exchange = DirectoryExchange::new(&root.0);
    let mut message = message("old", "a@p", "b@p");
    message.emitted_at = "2020-01-01T00:00:00Z".into();
    let mutation = Mutation::Message(message);
    let folder = root.0.join("2020/01/01");
    fs::create_dir_all(&folder).unwrap();
    let path = folder.join("message-old.json");
    fs::write(&path,serde_json::to_vec(&serde_json::json!({"mutation":mutation,"fingerprint":hash(&serde_json::to_vec(&mutation).unwrap())})).unwrap()).unwrap();
    (exchange, mutation, path)
}
fn checkpoint(exchange: &DirectoryExchange, mutation: &Mutation, id: &str, date: &str, seen: bool) {
    let integrated = if seen {
        BTreeMap::from([(
            format!("{}:{}", mutation.kind(), mutation.id()),
            hash(&canonical_bytes(mutation).unwrap()),
        )])
    } else {
        BTreeMap::new()
    };
    exchange
        .deposit(ExchangeItem::Checkpoint(&ReadCheckpoint {
            id: id.into(),
            machine: id.into(),
            seen_at: date.into(),
            integrated,
            missed_before: None,
        }))
        .unwrap();
}
#[test]
fn retention_requires_every_active_installation_and_never_runs_without_human_apply() {
    let root = Temporary::new();
    let (exchange, mutation, path) = old_mail(&root);
    checkpoint(&exchange, &mutation, "one", &now(), true);
    checkpoint(&exchange, &mutation, "two", &now(), false);
    assert_eq!(preview(&exchange).unwrap().mutations, 0);
    assert!(path.exists());
    checkpoint(&exchange, &mutation, "two", &now(), true);
    let plan = preview(&exchange).unwrap();
    assert_eq!(plan.mutations, 1);
    assert!(path.exists());
    apply(&exchange, &plan.fingerprint, "one").unwrap();
    assert!(!path.exists());
    assert!(exchange
        .list(None, &[])
        .unwrap()
        .mutations
        .iter()
        .any(|m| matches!(
            m,
            Mutation::Event(Event {
                change: Change::Purged { .. },
                ..
            })
        )));
}
#[test]
fn dormant_installations_are_named_and_a_changed_review_is_rejected() {
    let root = Temporary::new();
    let (exchange, mutation, path) = old_mail(&root);
    checkpoint(&exchange, &mutation, "active", &now(), true);
    checkpoint(
        &exchange,
        &mutation,
        "dormant",
        "2020-01-01T00:00:00Z",
        false,
    );
    let plan = preview(&exchange).unwrap();
    assert_eq!(plan.mutations, 1);
    assert_eq!(plan.dormant, vec!["dormant"]);
    checkpoint(&exchange, &mutation, "new", &now(), false);
    assert_eq!(
        apply(&exchange, &plan.fingerprint, "active").unwrap_err().0,
        "apercu_conservation_modifie"
    );
    assert!(path.exists());
}
#[test]
fn a_recent_reply_protects_its_ancestor_and_the_one_year_floor() {
    let root = Temporary::new();
    let (exchange, mutation, path) = old_mail(&root);
    checkpoint(&exchange, &mutation, "one", &now(), true);
    let mut reply = message("reply", "b@p", "a@p");
    reply.reply_to = Some("old".into());
    exchange
        .deposit(ExchangeItem::Mutation(&Mutation::Message(reply)))
        .unwrap();
    assert_eq!(preview(&exchange).unwrap().mutations, 0);
    assert!(path.exists());
}
