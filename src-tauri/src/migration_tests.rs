use super::*;
use crate::test_support::Temporary;
#[tokio::test]
async fn migration_is_lossless_neutral_and_verified_per_account() {
    let root = Temporary::new();
    let source = root.0.join("old");
    fs::create_dir_all(&source).unwrap();
    let original = json!({"id":"old-id","date":"2025-01-01T01:00:00","de":"legacy","a":["agent","owner"],"objet":"Ancien","corps":["1","2","3"],"pj":"preuve.txt","re":null,"statut":"lu","statuts":{"agent":"traité","owner":"nouveau"},"historique":[{"par":"agent","statut":"traité"}],"unknown":"kept"});
    fs::write(
        source.join("boite.json"),
        serde_json::to_vec(&json!({"version":1,"messages":[original],"extra":"preserved"}))
            .unwrap(),
    )
    .unwrap();
    fs::write(source.join("boite.manifest.json"),serde_json::to_vec(&json!({"version":1,"comptes":[{"nom":"agent","hote":"codex","role":"dev","actif":true},{"nom":"owner","hote":"human"}],"projets":["p"],"extra":"kept"})).unwrap()).unwrap();
    fs::write(source.join("preuve.txt"), b"preuve").unwrap();
    let before = fs::read(source.join("boite.json")).unwrap();
    let plan = preview(&source).unwrap();
    assert_eq!(plan.counts["agent"]["traité"], 1);
    assert_eq!(plan.counts["owner"]["nouveau"], 1);
    let mailbox = root.mailbox("new").await;
    apply(&mailbox, &source, &plan.fingerprint).await.unwrap();
    let raw = mailbox.rows("legacy_message").await.unwrap();
    assert_eq!(raw, vec![Mutation::LegacyMessage(original)]);
    let view = mailbox.message_views().await.unwrap().pop().unwrap();
    assert!(view.complete);
    assert_eq!(view.message.id, "old-id");
    assert_eq!(view.statuses["agent"], "traité");
    assert_eq!(mailbox.accounts().await.unwrap().len(), 1);
    assert!(mailbox.approvals(None).await.unwrap().is_empty());
    assert_eq!(fs::read(source.join("boite.json")).unwrap(), before);
    assert!(apply(&mailbox, &source, &plan.fingerprint).await.is_err());
}
#[test]
fn changed_source_and_traversing_attachments_cannot_pass_the_migration_review() {
    let root = Temporary::new();
    fs::write(
        root.0.join("boite.json"),
        br#"{"version":1,"messages":[{"id":"m","pj":"../secret"}]}"#,
    )
    .unwrap();
    fs::write(root.0.join("boite.manifest.json"), br#"{"comptes":[]}"#).unwrap();
    assert!(preview(&root.0).is_err());
}
#[tokio::test]
async fn a_missing_legacy_attachment_stays_announced_incomplete_and_can_be_requested() {
    let root = Temporary::new();
    let source = root.0.join("old");
    fs::create_dir_all(&source).unwrap();
    fs::write(
        source.join("boite.json"),
        br#"{"messages":[{"id":"missing","de":"a","a":["b"],"pj":"missing.txt"}]}"#,
    )
    .unwrap();
    fs::write(source.join("boite.manifest.json"), br#"{"comptes":[]}"#).unwrap();
    let plan = preview(&source).unwrap();
    let mailbox = root.mailbox("new").await;
    apply(&mailbox, &source, &plan.fingerprint).await.unwrap();
    let view = mailbox.message_views().await.unwrap().pop().unwrap();
    assert!(!view.complete);
    assert_eq!(view.announced_attachment.as_deref(), Some("missing.txt"));
    assert!(mailbox.request_attachment("missing").await.is_ok());
}

#[tokio::test]
#[ignore = "Requires a private prototype snapshot in MESSENGER_MIGRATION_FIXTURE"]
async fn actual_prototype_snapshot_preserves_every_id_status_history_account_and_attachment() {
    let source =
        std::env::var("MESSENGER_MIGRATION_FIXTURE").expect("Set MESSENGER_MIGRATION_FIXTURE");
    let source = Path::new(&source);
    let plan = preview(source).unwrap();
    let original_box = fs::read(source.join("boite.json")).unwrap();
    let original_manifest = fs::read(source.join("boite.manifest.json")).unwrap();
    let root = Temporary::new();
    let mailbox = root.mailbox("migration").await;
    apply(&mailbox, source, &plan.fingerprint).await.unwrap();
    let imported = mailbox.store.mutations(None, None).await.unwrap();
    for mutation in &plan.mutations {
        assert!(
            imported.iter().any(|row| row.mutation == *mutation),
            "Record lost: {}",
            mutation.id()
        );
    }
    let statuses = mailbox.statuses().await.unwrap();
    for mutation in &plan.mutations {
        if let Mutation::LegacyMessage(v) = mutation {
            for recipient in v["a"].as_array().unwrap().iter().filter_map(Value::as_str) {
                let expected = v["statuts"][recipient]
                    .as_str()
                    .or_else(|| v["statut"].as_str())
                    .unwrap_or("nouveau");
                assert_eq!(statuses[v["id"].as_str().unwrap()][recipient], expected);
            }
        }
    }
    for (reference, bytes) in &plan.blobs {
        assert_eq!(
            mailbox
                .store
                .blob(&reference.fingerprint)
                .await
                .unwrap()
                .as_ref(),
            Some(bytes)
        );
    }
    assert_eq!(fs::read(source.join("boite.json")).unwrap(), original_box);
    assert_eq!(
        fs::read(source.join("boite.manifest.json")).unwrap(),
        original_manifest
    );
    assert!(mailbox
        .setting("notified_messages")
        .await
        .unwrap()
        .is_none());
    println!("Empreinte de migration : {}", plan.fingerprint);
    if let Ok(path) = std::env::var("MESSENGER_MIGRATION_VIEW") {
        let messages = mailbox.message_views().await.unwrap();
        let contact_books = mailbox.contact_books().await.unwrap();
        let mut directory = Vec::new();
        for account in mailbox
            .accounts()
            .await
            .unwrap()
            .into_iter()
            .filter(|a| a.active)
        {
            let contacts = contact_books
                .get(&account.address)
                .cloned()
                .unwrap_or_default();
            let waiting = messages
                .iter()
                .filter(|v| {
                    v.message.to.contains(&account.address)
                        && v.statuses
                            .get(&account.address)
                            .is_none_or(|s| s != "traité")
                })
                .count();
            directory.push(json!({"account":account,"contacts":contacts,"waiting":waiting,"last_collection":null,"oldest_waiting":null}));
        }
        let snapshot = json!({"fingerprint":plan.fingerprint,"messages":messages,"directory":directory,"requests":[],"providers":crate::provider::ProviderRegistry::new().statuses(),"projects":[],"incidents":[],"installation":mailbox.installation,"machine":mailbox.machine,"exchange":{"path":source,"configured":true,"reachable":true,"listening":true,"interval_seconds":60},"preferences":{"theme":"dark","lang":"FR","notif":"off"}});
        fs::write(path, serde_json::to_vec(&snapshot).unwrap()).unwrap();
    }
    println!("Migration réelle : {} messages, {} comptes, {} empreintes de pièces jointes, compteurs {:?}",plan.messages,plan.accounts,plan.attachments,plan.counts);
}
