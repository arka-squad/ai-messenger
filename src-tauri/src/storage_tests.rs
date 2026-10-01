use super::*;
use crate::test_support::{message, Temporary};
#[tokio::test]
async fn durable_readback_and_identical_replay_preserve_immutable_content() {
    if let Ok(path) = std::env::var("MESSENGER_COLD_TEST_DATABASE") {
        let reopened = LocalStore::open(path).await.unwrap();
        assert_eq!(reopened.schema_version().await.unwrap(), 3);
        let rows = reopened.mutations(Some("message"), None).await.unwrap();
        assert_eq!(rows.len(), 2);
        let expected: Mutation =
            serde_json::from_value(reopened.setting("cold_expectation").await.unwrap().unwrap())
                .unwrap();
        assert!(rows
            .iter()
            .any(|row| row.mutation == expected && row.journey == "published"));
        assert_eq!(
            reopened.setting("preferences").await.unwrap().unwrap()["theme"],
            "dark"
        );
        assert_eq!(
            reopened.setting("nullable").await.unwrap(),
            Some(serde_json::json!({"value":null}))
        );
        return;
    }
    let root = Temporary::new();
    let store = LocalStore::open(root.0.join("db")).await.unwrap();
    let mutation = Mutation::Message(message("m", "a@p", "b@p"));
    assert!(store.save(&mutation, "pending").await.unwrap());
    assert!(!store.save(&mutation, "integrated").await.unwrap());
    let mut changed = message("m", "a@p", "b@p");
    changed.subject = "Autre".into();
    assert_eq!(
        store
            .save(&Mutation::Message(changed), "pending")
            .await
            .unwrap_err()
            .0,
        "mutation_en_conflit"
    );
    store
        .set_journey("message", "m", "published")
        .await
        .unwrap();
    assert_eq!(
        store
            .mutations(Some("message"), Some("published"))
            .await
            .unwrap()[0]
            .mutation,
        mutation
    );
    store
        .set_setting("preferences", serde_json::json!({"theme":"light"}))
        .await
        .unwrap();
    store
        .set_setting("preferences", serde_json::json!({"theme":"dark"}))
        .await
        .unwrap();
    assert_eq!(
        store.setting("preferences").await.unwrap().unwrap()["theme"],
        "dark"
    );
    assert_eq!(store.schema_version().await.unwrap(), 3);
    store
        .set_setting("cold_expectation", serde_json::to_value(mutation).unwrap())
        .await
        .unwrap();
    store
        .set_setting("nullable", serde_json::json!({"value":null}))
        .await
        .unwrap();
    store
        .database
        .query("CREATE mail SET payload=$payload, journey='integrated'; UPDATE app_schema:current SET version=2;")
        .bind((
            "payload",
            serde_json::to_value(message("previous-schema", "a@p", "b@p")).unwrap(),
        ))
        .await
        .unwrap()
        .check()
        .unwrap();
    drop(store);
    // A separate process proves an actual restart, without racing the old SDK's asynchronous teardown.
    let database = root.0.join("db");
    let output = tokio::task::spawn_blocking(move || {
        std::process::Command::new(std::env::current_exe().unwrap())
            .env("MESSENGER_COLD_TEST_DATABASE", database)
            .env("SURREAL_SYNC_DATA", "true")
            .args([
                "--exact",
                "storage::tests::durable_readback_and_identical_replay_preserve_immutable_content",
                "--nocapture",
            ])
            .output()
            .unwrap()
    })
    .await
    .unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
}
#[tokio::test]
async fn corrupt_local_attachment_is_repaired_from_verified_bytes() {
    let root = Temporary::new();
    let store = LocalStore::open(root.0.join("db")).await.unwrap();
    let bytes = b"contenu".to_vec();
    let reference = Attachment {
        name: "rapport.txt".into(),
        fingerprint: format!("{:x}", Sha256::digest(&bytes)),
        size: bytes.len() as u64,
    };
    store.save_blob(&reference, bytes.clone()).await.unwrap();
    fs::write(store.blobs.join(&reference.fingerprint), b"corrompu").unwrap();
    store.save_blob(&reference, bytes.clone()).await.unwrap();
    assert_eq!(
        store.blob(&reference.fingerprint).await.unwrap(),
        Some(bytes)
    );
    assert!(store
        .save_blob(&reference, b"invalide".to_vec())
        .await
        .is_err());
}
