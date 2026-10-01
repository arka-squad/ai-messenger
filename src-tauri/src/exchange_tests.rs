use super::*;
use crate::test_support::{message, Temporary};
#[test]
fn publication_never_overwrites_another_mutation_and_is_idempotent() {
    let root = Temporary::new();
    let exchange = DirectoryExchange::new(&root.0);
    let original = Mutation::Message(message("m1", "a@p", "b@p"));
    let proof = exchange.deposit(ExchangeItem::Mutation(&original)).unwrap();
    assert_eq!(
        proof,
        exchange.deposit(ExchangeItem::Mutation(&original)).unwrap()
    );
    let mut changed = message("m1", "a@p", "b@p");
    changed.subject = "Conflit".into();
    assert_eq!(
        exchange
            .deposit(ExchangeItem::Mutation(&Mutation::Message(changed)))
            .unwrap_err()
            .0,
        "mutation_en_conflit"
    );
    assert_eq!(exchange.list(None, &[]).unwrap().mutations, vec![original]);
}
#[test]
fn a_missing_share_is_not_silently_created_by_any_deposit() {
    let root = Temporary::new();
    let absent = root.0.join("absent");
    let exchange = DirectoryExchange::new(&absent);
    let mutation = Mutation::Message(message("m", "a@p", "b@p"));
    assert_eq!(
        exchange
            .deposit(ExchangeItem::Mutation(&mutation))
            .unwrap_err()
            .0,
        "emplacement_injoignable"
    );
    let bytes = b"x";
    let reference = Attachment {
        name: "x".into(),
        fingerprint: fingerprint(bytes),
        size: 1,
    };
    assert!(exchange
        .deposit(ExchangeItem::Attachment {
            reference: &reference,
            bytes
        })
        .is_err());
    assert!(!absent.exists());
}
#[test]
fn late_publication_uses_the_deposit_day_and_incremental_scan_skips_old_history() {
    let root = Temporary::new();
    let exchange = DirectoryExchange::new(&root.0);
    let mut old = message("late", "a@p", "b@p");
    old.emitted_at = "2020-01-01T00:00:00Z".into();
    exchange
        .deposit(ExchangeItem::Mutation(&Mutation::Message(old)))
        .unwrap();
    let ancient = root.0.join("2020/01/01");
    fs::create_dir_all(&ancient).unwrap();
    fs::write(ancient.join("bad.json"), b"truncated").unwrap();
    let batch = exchange
        .list(Some(&Utc::now().date_naive().to_string()), &[])
        .unwrap();
    assert_eq!(batch.mutations.len(), 1);
    assert!(batch.incidents.is_empty());
}
#[test]
fn incomplete_mutation_is_not_integrated_or_reported_as_a_valid_proof() {
    let root = Temporary::new();
    let today = Utc::now().date_naive().to_string().replace('-', "/");
    fs::create_dir_all(root.0.join(&today)).unwrap();
    fs::write(root.0.join(today).join("message-bad.json"), b"{").unwrap();
    let batch = DirectoryExchange::new(&root.0).list(None, &[]).unwrap();
    assert!(batch.mutations.is_empty());
    assert_eq!(batch.incidents[0].kind, "lecture_incomplete");
}
#[tokio::test]
#[ignore = "Requires a writable SMB share in MESSENGER_EXCHANGE_FIXTURE"]
async fn actual_share_supports_publication_readback_attachments_and_native_listening() {
    let share =
        std::env::var("MESSENGER_EXCHANGE_FIXTURE").expect("Set MESSENGER_EXCHANGE_FIXTURE");
    let root =
        PathBuf::from(share).join(format!(".messenger-verification-{}", uuid::Uuid::new_v4()));
    fs::create_dir(&root).unwrap();
    let exchange = DirectoryExchange::new(&root);
    let mut listener = exchange.listen().unwrap();
    let mutation = Mutation::Message(message("smb-test", "a@test", "b@test"));
    exchange.deposit(ExchangeItem::Mutation(&mutation)).unwrap();
    let bytes = b"SMB attachment proof";
    let reference = Attachment {
        name: "preuve.txt".into(),
        fingerprint: fingerprint(bytes),
        size: bytes.len() as u64,
    };
    exchange
        .deposit(ExchangeItem::Attachment {
            reference: &reference,
            bytes,
        })
        .unwrap();
    let read = exchange.list(None, &[reference.clone()]).unwrap();
    assert_eq!(read.mutations, vec![mutation]);
    assert_eq!(read.attachments[&reference.fingerprint], bytes);
    assert!(
        tokio::time::timeout(std::time::Duration::from_secs(10), listener.changed())
            .await
            .is_ok()
    );
    println!(
        "SMB : dépôt relu, pièce jointe vérifiée, écoute native active, publication atomique={}",
        exchange.atomic_publication()
    );
    drop(exchange);
    fs::remove_dir_all(&root).unwrap();
}
