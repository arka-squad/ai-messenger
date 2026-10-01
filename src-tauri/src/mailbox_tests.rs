use crate::{
    domain::{models::*, ports::*},
    test_support::*,
};
use std::fs;
#[tokio::test]
async fn complete_exchange_has_independent_monotone_recipient_statuses_and_read_only_copies() {
    let root = Temporary::new();
    let first = root.mailbox("first").await;
    let second = root.mailbox("second").await;
    let a = account(&first, "alpha").await;
    let b = account(&first, "beta").await;
    let c = account(&first, "copy").await;
    let mut mail = message("m", &a, &b);
    mail.copies.push(c.clone());
    first.send(mail.clone()).await.unwrap();
    second.receive().await.unwrap();
    assert_eq!(
        second.read("m", &c).await.unwrap(),
        first.message("m").await.unwrap().unwrap()
    );
    assert!(second
        .mark(marking("bad", "m", &c, MailStatus::Read))
        .await
        .is_err());
    assert!(second
        .reply(message("badreply", &c, &a), "m")
        .await
        .is_err());
    second
        .mark(marking("done", "m", &b, MailStatus::Done))
        .await
        .unwrap();
    assert!(second
        .mark(marking("back", "m", &b, MailStatus::Read))
        .await
        .is_err());
    first.receive().await.unwrap();
    assert_eq!(first.statuses().await.unwrap()["m"][&b], "traité");
    assert!(!first.statuses().await.unwrap()["m"].contains_key(&c));
    assert!(first.inbox(&b).await.unwrap().is_empty());
    assert_eq!(first.message_views().await.unwrap()[0].overall, "traité");
}
#[tokio::test]
async fn concurrent_old_read_mark_cannot_regress_a_completed_recipient() {
    let root = Temporary::new();
    let first = root.mailbox("first").await;
    let second = root.mailbox("second").await;
    let a = account(&first, "a").await;
    let b = account(&first, "b").await;
    first.send(message("m", &a, &b)).await.unwrap();
    second.receive().await.unwrap();
    first
        .mark(marking("done", "m", &b, MailStatus::Done))
        .await
        .unwrap();
    second
        .mark(marking("read", "m", &b, MailStatus::Read))
        .await
        .unwrap();
    first.receive().await.unwrap();
    second.receive().await.unwrap();
    assert_eq!(first.statuses().await.unwrap()["m"][&b], "traité");
    assert_eq!(second.statuses().await.unwrap()["m"][&b], "traité");
}
#[tokio::test]
async fn human_accounts_and_multiline_payloads_are_refused_before_publication() {
    let root = Temporary::new();
    let mailbox = root.mailbox("one").await;
    assert!(mailbox
        .enroll("test", "human", "Owner", "humain", None)
        .await
        .is_err());
    let a = account(&mailbox, "a").await;
    let b = account(&mailbox, "b").await;
    let mut mail = message("bad", &a, &b);
    mail.body = vec!["ligne 1\nligne 2\nligne 3".into()];
    assert!(mailbox.send(mail).await.is_err());
    assert!(mailbox.send(message("human", &a, "owner")).await.is_err());
    assert!(mailbox.messages().await.unwrap().is_empty());
    let forged = crate::domain::journal::Mutation::Event(crate::domain::journal::Event {
        id: "invalid-shared-account".into(),
        emitted_at: crate::mailbox::now(),
        installation: "other".into(),
        change: crate::domain::journal::Change::Account {
            account: crate::domain::journal::AgentAccount {
                address: "person".into(),
                display: "Personne".into(),
                host: "test".into(),
                machine: "test".into(),
                role: " HUMAIN ".into(),
                active: true,
                created_at: crate::mailbox::now(),
                installation: "other".into(),
                project: None,
                merged_into: None,
            },
        },
    });
    mailbox
        .exchange
        .deposit(crate::domain::journal::ExchangeItem::Mutation(&forged))
        .unwrap();
    mailbox.receive().await.unwrap();
    assert!(!mailbox
        .accounts()
        .await
        .unwrap()
        .iter()
        .any(|a| a.address == "person"));
    assert!(mailbox
        .incidents()
        .iter()
        .any(|i| i.kind == "compte_invalide"));
}
#[tokio::test]
async fn pending_outbox_survives_disconnect_and_retries_with_its_original_id() {
    let root = Temporary::new();
    let mailbox = root.mailbox("one").await;
    let a = account(&mailbox, "a").await;
    let b = account(&mailbox, "b").await;
    let shared = root.0.join("shared");
    let offline = root.0.join("offline");
    fs::rename(&shared, &offline).unwrap();
    assert_eq!(
        mailbox.send(message("pending", &a, &b)).await.unwrap(),
        "pending"
    );
    assert_eq!(mailbox.message_views().await.unwrap()[0].journey, "pending");
    assert!(!shared.exists());
    fs::rename(offline, shared).unwrap();
    mailbox.receive().await.unwrap();
    assert_eq!(
        mailbox.message_views().await.unwrap()[0].journey,
        "integrated"
    );
    assert_eq!(mailbox.messages().await.unwrap().len(), 1);
    mailbox.receive().await.unwrap();
    assert_eq!(mailbox.messages().await.unwrap().len(), 1);
}
#[tokio::test]
async fn attachment_completeness_is_verified_both_ways_and_can_be_restored() {
    let root = Temporary::new();
    let sender = root.mailbox("sender").await;
    let recipient = root.mailbox("recipient").await;
    let a = account(&sender, "a").await;
    let b = account(&sender, "b").await;
    let reference = sender
        .put_attachment("résultat.txt".into(), "résultat".as_bytes().to_vec())
        .await
        .unwrap();
    let mut mail = message("attachment", &a, &b);
    mail.attachment = Some(reference.clone());
    sender.send(mail).await.unwrap();
    recipient.receive().await.unwrap();
    assert!(recipient.message_views().await.unwrap()[0].complete);
    fs::write(
        root.0
            .join("recipient.attachments")
            .join(&reference.fingerprint),
        "abîmé".as_bytes(),
    )
    .unwrap();
    assert!(!recipient.message_views().await.unwrap()[0].complete);
    assert!(recipient.attachment("attachment").await.unwrap().is_none());
    recipient.request_attachment("attachment").await.unwrap();
    recipient.receive().await.unwrap();
    assert!(recipient.message_views().await.unwrap()[0].complete);
}
#[tokio::test]
async fn verdict_requires_the_opener_to_report_a_result_and_discussion_is_not_authorization() {
    let root = Temporary::new();
    let mailbox = root.mailbox("one").await;
    let a = account(&mailbox, "a").await;
    let b = account(&mailbox, "b").await;
    mailbox
        .request_approval(request("approve", &a))
        .await
        .unwrap();
    mailbox
        .answer(Verdict {
            request_id: "approve".into(),
            response: VerdictResponse::Approve,
            rendered_at: crate::mailbox::now(),
            rendered_from: "human-installation".into(),
            note: None,
        })
        .await
        .unwrap();
    assert!(mailbox.approvals(None).await.unwrap()[0].closure.is_none());
    let closure = RequestClosure {
        id: "result".into(),
        request_id: "approve".into(),
        by: b,
        result: "Publié".into(),
        closed_at: crate::mailbox::now(),
    };
    assert!(mailbox.close_request(closure.clone()).await.is_err());
    mailbox
        .close_request(RequestClosure {
            by: a.clone(),
            ..closure
        })
        .await
        .unwrap();
    mailbox
        .request_approval(request("discussion", &a))
        .await
        .unwrap();
    mailbox
        .redirect(Reorientation {
            request_id: "discussion".into(),
            to: a.clone(),
            redirected_at: crate::mailbox::now(),
            note: None,
        })
        .await
        .unwrap();
    let views = mailbox.approvals(None).await.unwrap();
    let view = views.iter().find(|v| v.request.id == "discussion").unwrap();
    assert_eq!(view.effective_nature, RequestNature::Intervention);
    assert!(view.verdict.is_none());
    mailbox.take_intervention("discussion").await.unwrap();
    assert!(mailbox
        .answer(Verdict {
            request_id: "discussion".into(),
            response: VerdictResponse::Approve,
            rendered_at: crate::mailbox::now(),
            rendered_from: "human".into(),
            note: None
        })
        .await
        .is_err());
}
#[tokio::test]
async fn session_binding_and_private_recovery_keys_never_enter_the_shared_journal() {
    let root = Temporary::new();
    let mailbox = root.mailbox("one").await;
    let enrolled = mailbox
        .enroll("codex", "session-a", "Alice", "développeur", None)
        .await
        .unwrap();
    let address = enrolled["identity"]["account"].as_str().unwrap();
    let key = enrolled["recovery_key"].as_str().unwrap();
    assert!(mailbox
        .recognize("codex", "session-b", address, "wrong")
        .await
        .is_err());
    assert_eq!(
        mailbox
            .recognize("codex", "session-b", address, key)
            .await
            .unwrap()
            .account,
        address
    );
    let journal =
        serde_json::to_string(&mailbox.store.mutations(None, None).await.unwrap()).unwrap();
    assert!(!journal.contains(key));
    assert!(!journal.contains("recovery"));
    let other = account(&mailbox, "other").await;
    let contact = crate::domain::journal::Contact {
        alias: "Mon relais".into(),
        addresses: vec![other.clone()],
        note: "Carnet personnel".into(),
    };
    mailbox
        .set_contacts(address, vec![contact.clone()])
        .await
        .unwrap();
    assert_eq!(
        mailbox.contacts(address).await.unwrap(),
        vec![contact.clone()]
    );
    assert!(mailbox.contacts(&other).await.unwrap().is_empty());
    assert_eq!(
        mailbox.contact_books().await.unwrap()[address],
        vec![contact]
    );
}
#[tokio::test]
async fn merge_redirects_pending_mail_without_rewriting_the_original_message() {
    let root = Temporary::new();
    let mailbox = root.mailbox("one").await;
    let a = account(&mailbox, "a").await;
    let old = account(&mailbox, "old").await;
    let next = account(&mailbox, "next").await;
    mailbox.send(message("original", &a, &old)).await.unwrap();
    let original = mailbox.message("original").await.unwrap().unwrap();
    mailbox.merge_accounts(&old, &next).await.unwrap();
    assert_eq!(mailbox.inbox(&next).await.unwrap().len(), 1);
    mailbox
        .mark(marking("taken", "original", &next, MailStatus::Done))
        .await
        .unwrap();
    assert_eq!(
        mailbox.statuses().await.unwrap()["original"][&old],
        "traité"
    );
    assert_eq!(
        mailbox.message("original").await.unwrap().unwrap(),
        original
    );
    assert!(mailbox.inbox(&next).await.unwrap().is_empty());
}
#[tokio::test]
async fn an_unconfirmed_decision_cannot_authorize_an_agent_or_close_its_request() {
    let root = Temporary::new();
    let mailbox = root.mailbox("one").await;
    let a = account(&mailbox, "a").await;
    mailbox.request_approval(request("r", &a)).await.unwrap();
    fs::rename(root.0.join("shared"), root.0.join("offline")).unwrap();
    let verdict = Verdict {
        request_id: "r".into(),
        response: VerdictResponse::Approve,
        rendered_at: crate::mailbox::now(),
        rendered_from: "human".into(),
        note: None,
    };
    assert_eq!(mailbox.answer(verdict).await.unwrap(), "pending");
    assert!(mailbox.approvals(None).await.unwrap()[0].verdict.is_some());
    assert!(mailbox.agent_approvals(&a).await.unwrap()[0]
        .verdict
        .is_none());
    let closure = RequestClosure {
        id: "c".into(),
        request_id: "r".into(),
        by: a.clone(),
        result: "Fait".into(),
        closed_at: crate::mailbox::now(),
    };
    assert!(mailbox.close_request(closure.clone()).await.is_err());
    fs::rename(root.0.join("offline"), root.0.join("shared")).unwrap();
    mailbox.receive().await.unwrap();
    assert!(mailbox.agent_approvals(&a).await.unwrap()[0]
        .verdict
        .is_some());
    mailbox.close_request(closure).await.unwrap();
}
#[tokio::test]
async fn simultaneous_approval_and_discussion_preserve_the_single_published_decision() {
    let root = Temporary::new();
    let first = root.mailbox("first").await;
    let second = root.mailbox("second").await;
    let a = account(&first, "a").await;
    first.request_approval(request("r", &a)).await.unwrap();
    second.receive().await.unwrap();
    first
        .answer(Verdict {
            request_id: "r".into(),
            response: VerdictResponse::Approve,
            rendered_at: crate::mailbox::now(),
            rendered_from: "human-first".into(),
            note: None,
        })
        .await
        .unwrap();
    assert!(second
        .redirect(Reorientation {
            request_id: "r".into(),
            to: a,
            redirected_at: crate::mailbox::now(),
            note: None
        })
        .await
        .is_err());
    first.receive().await.unwrap();
    second.receive().await.unwrap();
    assert!(second.approvals(None).await.unwrap()[0]
        .reorientation
        .is_none());
    assert!(second.approvals(None).await.unwrap()[0].verdict.is_some());
}
#[tokio::test]
async fn merged_copies_keep_read_access_without_gaining_recipient_rights() {
    let root = Temporary::new();
    let mailbox = root.mailbox("one").await;
    let a = account(&mailbox, "a").await;
    let b = account(&mailbox, "b").await;
    let copy = account(&mailbox, "copy").await;
    let successor = account(&mailbox, "next").await;
    let mut mail = message("m", &a, &b);
    mail.copies.push(copy.clone());
    mailbox.send(mail).await.unwrap();
    mailbox.merge_accounts(&copy, &successor).await.unwrap();
    assert!(mailbox.read("m", &successor).await.is_ok());
    assert_eq!(mailbox.inbox(&successor).await.unwrap().len(), 1);
    assert!(mailbox
        .mark(marking("bad", "m", &successor, MailStatus::Read))
        .await
        .is_err());
}

#[test]
fn agent_names_follow_the_box_rule_and_name_their_post() {
    use crate::mailbox::directory::agent_identity;
    assert_eq!(
        agent_identity("claude-code", "MessengerAI", "win"),
        Some(("cl-agent-messengerai-win".into(), "CL_Agent-MessengerAI_WIN".into()))
    );
    assert_eq!(
        agent_identity("codex", "  Cortex   Core 2 ", "mac"),
        Some(("cd-agent-cortex-core-2-mac".into(), "CD_Agent-Cortex Core 2_MAC".into()))
    );
    assert_eq!(agent_identity("kimi", "Équipe Été", "lnx").unwrap().0, "km-agent-equipe-ete-lnx");
    let (long, _) = agent_identity("claude-code", "Une tâche au titre vraiment beaucoup trop long", "win").unwrap();
    assert!(long.len() <= 32 && long.starts_with("cl-agent-") && long.ends_with("-win"), "{long}");
    assert_eq!(agent_identity("mcp", "???", "win").unwrap().0, "mc-agent-agent-win");
    assert_eq!(agent_identity("codex", "  ", "win"), None);
    // A task written as a whole account name is never doubled.
    assert_eq!(
        agent_identity("claude-code", "Agent-Cortex-5_WIN", "win"),
        Some(("cl-agent-cortex-5-win".into(), "CL_Agent-Cortex-5_WIN".into()))
    );
    assert_eq!(
        agent_identity("claude-code", "CL_Agent-Cortex-vocal-1_MAC", "mac"),
        Some(("cl-agent-cortex-vocal-1-mac".into(), "CL_Agent-Cortex-vocal-1_MAC".into()))
    );
    assert_eq!(agent_identity("codex", "deux\nlignes", "win"), None);
}
