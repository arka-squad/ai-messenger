use super::profile::inactive_directory;
use super::*;
use crate::test_support::*;

fn reason<T: std::fmt::Debug>(result: Result<T, MailboxError>) -> String {
    match result {
        Err(MailboxError::Refusal { reason, .. }) => reason,
        other => panic!("refusal expected, got {other:?}"),
    }
}
#[tokio::test]
async fn the_owner_deactivates_reactivates_and_edits_an_account_without_losing_history() {
    let root = Temporary::new();
    let first = root.mailbox("first").await;
    let second = root.mailbox("second").await;
    let a = account(&first, "a").await;
    let b = account(&first, "b").await;
    first.send(message("kept", &a, &b)).await.unwrap();
    first.set_active(&b, false).await.unwrap();
    assert_eq!(reason(first.require_account(&b).await), "compte_inactif");
    assert_eq!(reason(first.send(message("late", &a, &b)).await), "destinataire_inactif");
    let inactive = inactive_directory(&first.accounts().await.unwrap());
    assert_eq!(inactive.len(), 1);
    assert_eq!(inactive[0]["address"], b);
    for key in ["display", "role", "host", "machine", "project"] {
        assert!(inactive[0].get(key).is_some(), "{key}");
    }
    assert!(first.message("kept").await.unwrap().is_some(), "history is kept");
    // The change travels as an account re-publication; every installation folds the last one.
    second.receive().await.unwrap();
    assert!(!second.accounts().await.unwrap().iter().find(|x| x.address == b).unwrap().active);
    first.set_active(&b, true).await.unwrap();
    first.require_account(&b).await.unwrap();
    assert!(inactive_directory(&first.accounts().await.unwrap()).is_empty());
    let edited = first.set_role(&b, "Relecteur").await.unwrap();
    assert_eq!(edited.role, "Relecteur");
    second.receive().await.unwrap();
    let seen = second.accounts().await.unwrap().into_iter().find(|x| x.address == b).unwrap();
    assert!(seen.active);
    assert_eq!(seen.role, "Relecteur");
    assert_eq!(reason(first.set_role(&b, "humain").await), "role_invalide");
    assert_eq!(reason(first.set_active("inconnu@project", false).await), "compte_inconnu");
    assert_eq!(reason(first.set_role("inconnu@project", "dev").await), "compte_inconnu");
    // A merged account stays with its successor and is never offered for reactivation.
    let old = account(&first, "old").await;
    first.merge_accounts(&old, &a).await.unwrap();
    assert_eq!(reason(first.set_active(&old, true).await), "compte_fusionne");
    assert!(inactive_directory(&first.accounts().await.unwrap()).is_empty());
}
#[tokio::test]
async fn the_target_of_a_merge_cannot_be_deactivated_and_the_merge_holds() {
    let root = Temporary::new();
    let mailbox = root.mailbox("merge").await;
    let target = account(&mailbox, "cible").await;
    let old = account(&mailbox, "ancien").await;
    mailbox.merge_accounts(&old, &target).await.unwrap();
    let refused = mailbox.set_active(&target, false).await;
    match &refused {
        Err(MailboxError::Refusal { reason, message }) => {
            assert_eq!(reason, "compte_cible_de_fusion");
            assert!(message.contains(&old) && message.contains("fusion"), "{message}");
        }
        other => panic!("refusal expected, got {other:?}"),
    }
    let accounts = mailbox.accounts().await.unwrap();
    let kept = accounts.iter().find(|x| x.address == old).unwrap();
    assert!(!kept.active);
    assert_eq!(kept.merged_into.as_deref(), Some(target.as_str()));
    assert!(accounts.iter().find(|x| x.address == target).unwrap().active);
    assert_eq!(mailbox.resolve_account(&old).await.unwrap(), target);
    assert!(mailbox.incidents().iter().all(|i| i.kind != "fusion_en_conflit"));
    // Reactivating an active target is a no-op, never a refusal.
    mailbox.set_active(&target, true).await.unwrap();
}
#[tokio::test]
async fn an_imported_account_the_agents_rule_rejects_is_never_published_as_changed() {
    let root = Temporary::new();
    let mailbox = root.mailbox("legacy").await;
    let legacy = |name: &str, role: &str| {
        Mutation::LegacyAccount(json!({"nom":name,"affichage":name,"hote":"codex","machine":"m","role":role,"actif":true,"cree":now()}))
    };
    mailbox.store.save(&legacy("sans-role@project", ""), "integrated").await.unwrap();
    mailbox.store.save(&legacy("adresse:invalide", "dev"), "integrated").await.unwrap();
    let before = mailbox.events().await.unwrap().len();
    let refused = mailbox.set_active("sans-role@project", false).await;
    assert_eq!(reason(refused), "compte_sans_role");
    assert_eq!(reason(mailbox.set_active("adresse:invalide", false).await), "compte_invalide");
    assert_eq!(reason(mailbox.set_role("adresse:invalide", "Relecteur").await), "compte_invalide");
    assert_eq!(mailbox.events().await.unwrap().len(), before, "nothing was published");
    assert!(mailbox.accounts().await.unwrap().iter().all(|a| a.active));
    // Once its role is set, the imported account can be deactivated.
    mailbox.set_role("sans-role@project", "Relecteur").await.unwrap();
    mailbox.set_active("sans-role@project", false).await.unwrap();
    assert!(!mailbox.accounts().await.unwrap().iter().find(|a| a.address == "sans-role@project").unwrap().active);
    assert!(mailbox.incidents().iter().all(|i| i.kind != "compte_invalide"));
}
