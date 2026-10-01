use super::*;
use crate::test_support::{tool, Temporary};

async fn enrol<R: RepositoryPort, E: ExchangePort>(
    mailbox: &MailboxService<R, E>,
    session: &str,
    task: &str,
    project: Option<&str>,
) -> String {
    tool(mailbox, "codex", session, "m_enroler", json!({"tache":task,"role":"dev","project":project}))
        .await["structuredContent"]["identity"]["account"]
        .as_str()
        .unwrap()
        .to_owned()
}
fn refusal_of(result: &Value) -> (&str, &str) {
    assert_eq!(result["isError"], true, "{result}");
    let refus = &result["structuredContent"]["refus"];
    (refus["reason"].as_str().unwrap(), refus["message"].as_str().unwrap())
}
#[tokio::test]
async fn declared_schemas_and_refusals_name_the_faulty_field() {
    let tools = schema::tools();
    let find = |name: &str| tools.as_array().unwrap().iter().find(|t| t["name"] == name).unwrap().clone();
    let message = &find("envoyer")["inputSchema"]["properties"]["message"];
    assert_eq!(message["required"], json!(["to", "subject"]));
    assert_eq!(message["properties"]["to"]["items"]["type"], "string");
    assert_eq!(message["properties"]["copies"]["type"], "array");
    assert_eq!(message["properties"]["subject"]["type"], "string");
    assert_eq!(message["properties"]["body"]["maxItems"], 2);
    assert!(message["properties"]["id"].is_object());
    assert_eq!(find("repondre")["inputSchema"]["properties"]["message"]["required"], json!(["subject"]));
    assert!(find("envoyer")["inputSchema"]["properties"]["attachment"]["properties"]["path"].is_object());
    assert_eq!(find("marquer")["inputSchema"]["properties"]["marking"]["properties"]["status"]["enum"], json!(["lu", "traité"]));
    let root = Temporary::new();
    let mailbox = root.mailbox("one").await;
    let _a = enrol(&mailbox, "a", "Alpha", None).await;
    let b = enrol(&mailbox, "b", "Beta", None).await;
    let cases = [
        ("envoyer", json!({"message":{"to":[b],"subject":"S","body":["1","2","3"]}}), "argument_invalide", "message.body"),
        ("envoyer", json!({"message":{"to":3,"subject":"S"}}), "argument_invalide", "message.to doit être une liste"),
        ("envoyer", json!({"message":{"to":[b]}}), "argument_manquant", "message.subject"),
        ("envoyer", json!({"message":{"to":[b],"subject":"S"},"attachment":{"name":"x.txt"}}), "argument_invalide", "attachment : indique name et bytes, ou path"),
        ("marquer", json!({"marking":{"status":"lu"}}), "argument_manquant", "marking.message_id"),
        ("marquer", json!({"marking":{"message_id":"m","status":"fait"}}), "argument_invalide", "marking.status doit valoir lu ou traité"),
        ("demander_validation", json!({"request":{"gesture":"Publier"}}), "argument_manquant", "request.scope"),
        ("attendre", json!({"secondes":3600}), "argument_invalide", "secondes"),
    ];
    for (name, arguments, reason, field) in cases {
        let result = tool(&mailbox, "codex", "a", name, arguments).await;
        let (got, message) = refusal_of(&result);
        assert_eq!(got, reason, "{name}: {message}");
        assert!(message.contains(field), "{name}: {message}");
    }
    // A domain refusal is an error too, and speaks French.
    let marked = tool(&mailbox, "codex", "a", "marquer", json!({"marking":{"message_id":"absent","status":"lu"}})).await;
    assert_eq!(refusal_of(&marked), ("UnknownMessage", "Ce message n’existe pas dans cette boîte."));
    // The first mailbox's shapes still work: a text body and a single recipient as text.
    let sent = tool(&mailbox, "codex", "a", "envoyer", json!({"message":{"to":b,"subject":"S","body":"une\ndeux"}})).await;
    assert!(sent.get("isError").is_none(), "{sent}");
    assert_eq!(sent["structuredContent"]["to"], json!([b]));
    assert_eq!(mailbox.messages().await.unwrap()[0].body, vec!["une", "deux"]);
}
#[tokio::test]
async fn short_names_and_aliases_reach_active_accounts_and_unknown_ones_are_named() {
    let root = Temporary::new();
    let mailbox = root.mailbox("one").await;
    let chief = enrol(&mailbox, "chief", "Chef", Some("alpha")).await;
    let near = enrol(&mailbox, "near", "Dev", Some("alpha")).await;
    let far = enrol(&mailbox, "far", "Dev", Some("beta")).await;
    let _outsider = enrol(&mailbox, "outsider", "Autre", Some("gamma")).await;
    let short = near.split('@').next().unwrap().to_owned();
    let send = |session: &'static str, to: Value| {
        let mailbox = &mailbox;
        async move { tool(mailbox, "codex", session, "envoyer", json!({"message":{"to":to,"subject":"Info"}})).await }
    };
    let sent = send("chief", json!([short])).await;
    assert_eq!(sent["structuredContent"]["to"], json!([near]), "the sender's project wins");
    assert_eq!(sent["structuredContent"]["resolved"][&short], json!([near]));
    let ambiguous = send("outsider", json!([short])).await;
    let (reason, message) = refusal_of(&ambiguous);
    assert_eq!(reason, "destinataire_ambigu");
    assert!(message.contains(&near) && message.contains(&far), "{message}");
    let unique = send("outsider", json!([chief.split('@').next().unwrap()])).await;
    assert_eq!(unique["structuredContent"]["to"], json!([chief]));
    let added = tool(&mailbox, "codex", "chief", "contacts", json!({"ajouter":{"alias":"equipe","addresses":[near, far]}})).await;
    assert_eq!(added["structuredContent"]["data"][0]["note"], "");
    let team = send("chief", json!(["equipe"])).await;
    assert_eq!(team["structuredContent"]["to"], json!([near, far]));
    let shadow = tool(&mailbox, "codex", "chief", "contacts", json!({"ajouter":{"alias":near,"addresses":[far]}})).await;
    assert_eq!(refusal_of(&shadow).0, "contact_invalide");
    let unknown = send("chief", json!(["inconnu"])).await;
    let (reason, message) = refusal_of(&unknown);
    assert_eq!(reason, "destinataire_inconnu");
    assert!(message.contains("« inconnu »") && message.contains("agents"), "{message}");
    mailbox.set_active(&far, false).await.unwrap();
    let inactive = send("chief", json!([far])).await;
    let (reason, message) = refusal_of(&inactive);
    assert_eq!(reason, "destinataire_inactif");
    assert!(message.contains(&far), "{message}");
    let removed = tool(&mailbox, "codex", "chief", "contacts", json!({"retirer":"equipe"})).await;
    assert_eq!(removed["structuredContent"]["data"], json!([]));
}
#[tokio::test]
async fn a_reply_without_recipients_goes_back_to_the_original_sender() {
    let root = Temporary::new();
    let mailbox = root.mailbox("one").await;
    let a = enrol(&mailbox, "a", "Alpha", None).await;
    let b = enrol(&mailbox, "b", "Beta", None).await;
    tool(&mailbox, "codex", "a", "envoyer", json!({"message":{"id":"question","to":[b],"subject":"Question"}})).await;
    let answer = tool(&mailbox, "codex", "b", "repondre", json!({"reply_to":"question","message":{"id":"answer","subject":"Réponse"}})).await;
    assert!(answer.get("isError").is_none(), "{answer}");
    assert_eq!(mailbox.message("answer").await.unwrap().unwrap().to, vec![a.clone()]);
    tool(&mailbox, "codex", "a", "repondre", json!({"reply_to":"question","message":{"id":"follow-up","subject":"Précision"}})).await;
    assert_eq!(mailbox.message("follow-up").await.unwrap().unwrap().to, vec![b], "the sender's own follow-up keeps its recipients");
}
#[tokio::test]
async fn attendre_returns_only_mail_new_to_the_session() {
    let root = Temporary::new();
    let mailbox = root.mailbox("one").await;
    let _a = enrol(&mailbox, "a", "Alpha", None).await;
    let b = enrol(&mailbox, "b", "Beta", None).await;
    tool(&mailbox, "codex", "a", "envoyer", json!({"message":{"id":"first","to":[b],"subject":"Un"}})).await;
    let ids = |result: &Value| result["structuredContent"]["received"].as_array().unwrap().iter().map(|v| v["id"].as_str().unwrap().to_owned()).collect::<Vec<_>>();
    // Still nouveau and never handed to this session: returned at once.
    let waited = tool(&mailbox, "codex", "b", "attendre", json!({"secondes":5})).await;
    assert_eq!(ids(&waited), vec!["first"]);
    // Already handed over: the next wait only times out.
    let started = std::time::Instant::now();
    let idle = tool(&mailbox, "codex", "b", "attendre", json!({"secondes":1})).await;
    assert!(ids(&idle).is_empty());
    assert_eq!(idle["structuredContent"]["delai_ecoule"], true);
    assert!(started.elapsed() >= std::time::Duration::from_millis(900));
    // A later arrival ends the wait at once, alone.
    let started = std::time::Instant::now();
    let (waited, _) = tokio::join!(tool(&mailbox, "codex", "b", "attendre", json!({"secondes":30})), async {
        tokio::time::sleep(std::time::Duration::from_millis(300)).await;
        tool(&mailbox, "codex", "a", "envoyer", json!({"message":{"id":"second","to":[b],"subject":"Deux"}})).await
    });
    assert_eq!(ids(&waited), vec!["second"]);
    assert!(started.elapsed() < std::time::Duration::from_secs(20));
    // Another session of the same account has not been handed anything yet.
    tool(&mailbox, "codex", "b2", "m_enroler", json!({"tache":"Beta","role":"dev"})).await;
    let other = tool(&mailbox, "codex", "b2", "attendre", json!({"secondes":5})).await;
    assert_eq!(ids(&other).len(), 2);
}
#[tokio::test]
async fn relever_records_a_collection_at_most_once_every_ten_minutes() {
    let root = Temporary::new();
    let mailbox = root.mailbox("one").await;
    let b = enrol(&mailbox, "b", "Beta", None).await;
    let collected = || async {
        mailbox.events().await.unwrap().iter()
            .filter(|e| matches!(&e.change, crate::domain::journal::Change::Collected { account } if *account == b))
            .count()
    };
    let mut last = String::new();
    for _ in 0..3 {
        assert!(tool(&mailbox, "codex", "b", "relever", json!({})).await.get("isError").is_none());
        // The local collection time follows every relever, for the owner's « dernière relève ».
        let at = mailbox.collected_at(&b).await.unwrap().unwrap();
        assert!(at >= last, "{at} < {last}");
        last = at;
    }
    assert_eq!(collected().await, 1);
    let published = mailbox.events().await.unwrap().into_iter().filter(|e| matches!(&e.change, crate::domain::journal::Change::Collected { .. })).map(|e| e.emitted_at).max().unwrap();
    assert!(crate::mailbox::parse_date(&last) >= crate::mailbox::parse_date(&published));
    let earlier = (chrono::Utc::now() - chrono::Duration::minutes(11)).to_rfc3339();
    mailbox.set_setting(&format!("collection_published:{b}"), json!(earlier)).await.unwrap();
    tool(&mailbox, "codex", "b", "relever", json!({})).await;
    assert_eq!(collected().await, 2);
}
#[tokio::test]
async fn relever_shows_a_copy_until_the_collection_after_its_arrival() {
    let root = Temporary::new();
    let mailbox = root.mailbox("one").await;
    let _a = enrol(&mailbox, "a", "Alpha", None).await;
    let b = enrol(&mailbox, "b", "Beta", None).await;
    let c = enrol(&mailbox, "c", "Copie", None).await;
    let listed = |session: &'static str| {
        let mailbox = &mailbox;
        async move {
            tool(mailbox, "codex", session, "relever", json!({})).await["structuredContent"]["data"]
                .as_array().unwrap().iter().map(|v| v["id"].as_str().unwrap().to_owned()).collect::<Vec<_>>()
        }
    };
    tool(&mailbox, "codex", "a", "envoyer", json!({"message":{"id":"avec-copie","to":[b],"copies":[c],"subject":"Pour info"}})).await;
    assert_eq!(listed("c").await, vec!["avec-copie"]);
    assert!(listed("c").await.is_empty(), "a copy is shown once");
    // The addressed recipient keeps it until traité.
    assert_eq!(listed("b").await, vec!["avec-copie"]);
    assert_eq!(listed("b").await, vec!["avec-copie"]);
    // A later copy appears once, alone.
    tool(&mailbox, "codex", "a", "envoyer", json!({"message":{"id":"seconde-copie","to":[b],"copies":[c],"subject":"Suite"}})).await;
    assert_eq!(listed("c").await, vec!["seconde-copie"]);
    assert!(listed("c").await.is_empty());
    // lire and ou_en_est still reach the copies.
    assert!(tool(&mailbox, "codex", "c", "lire", json!({"id":"avec-copie"})).await.get("isError").is_none());
}
#[tokio::test]
async fn contact_edits_check_only_the_added_alias_and_never_lose_a_concurrent_edit() {
    let root = Temporary::new();
    let mailbox = root.mailbox("one").await;
    let me = enrol(&mailbox, "me", "Moi", None).await;
    let near = enrol(&mailbox, "near", "Proche", None).await;
    let far = enrol(&mailbox, "far", "Loin", None).await;
    tool(&mailbox, "codex", "me", "contacts", json!({"ajouter":{"alias":"loin","addresses":[far]}})).await;
    mailbox.set_active(&far, false).await.unwrap();
    // An unrelated alias is still added, although « loin » now names an inactive account.
    let added = tool(&mailbox, "codex", "me", "contacts", json!({"ajouter":{"alias":"proche","addresses":[near]}})).await;
    assert!(added.get("isError").is_none(), "{added}");
    let removed = tool(&mailbox, "codex", "me", "contacts", json!({"retirer":"proche"})).await;
    assert_eq!(removed["structuredContent"]["data"].as_array().unwrap().len(), 1);
    // A refused alias is named.
    let refused = tool(&mailbox, "codex", "me", "contacts", json!({"ajouter":{"alias":"equipe","addresses":[near, far]}})).await;
    let (reason, message) = refusal_of(&refused);
    assert_eq!(reason, "destinataire_inactif");
    assert!(message.contains("« equipe »") && message.contains(&far), "{message}");
    let empty = tool(&mailbox, "codex", "me", "contacts", json!({"ajouter":{"alias":"vide","addresses":[]}})).await;
    assert!(refusal_of(&empty).1.contains("« vide »"));
    let whole = tool(&mailbox, "codex", "me", "contacts", json!({"contacts":[{"alias":"a","addresses":[near]},{"alias":"a","addresses":[near]}]})).await;
    assert!(refusal_of(&whole).1.contains("« a »"));
    // Two sessions of the same account editing at once both keep their alias.
    let (one, two) = tokio::join!(
        mailbox.edit_contacts(&me, Some(Contact { alias: "un".into(), addresses: vec![near.clone()], note: String::new() }), None),
        mailbox.edit_contacts(&me, Some(Contact { alias: "deux".into(), addresses: vec![near.clone()], note: String::new() }), None),
    );
    assert!(one.unwrap().is_some() && two.unwrap().is_some());
    let book = mailbox.contacts(&me).await.unwrap().into_iter().map(|c| c.alias).collect::<Vec<_>>();
    assert_eq!(book, vec!["loin", "un", "deux"]);
    // Removing an absent alias publishes nothing.
    assert_eq!(mailbox.edit_contacts(&me, None, Some("absent")).await.unwrap(), None);
}
#[tokio::test]
async fn mcp_transports_keep_only_the_most_recent_three_hundred() {
    use crate::mailbox::MailboxService;
    let root = Temporary::new();
    let mailbox: MailboxService<_, _> = root.mailbox("one").await;
    mailbox.set_setting("mcp_transport:ancien-transport", json!({"provider":"codex","session":"s-ancien"})).await.unwrap();
    for index in 0..305 {
        mailbox.save_transport(&format!("transport-{index:03}"), Some(("codex", &format!("s-{index}")))).await.unwrap();
    }
    let index = mailbox.setting("mcp_transports").await.unwrap().unwrap();
    let index = index.as_object().unwrap();
    assert_eq!(index.len(), 300);
    assert!(index.values().all(|v| v["seen_at"].is_string()));
    assert!(index.contains_key("transport-304"));
    assert_eq!(mailbox.transport("transport-304").await.unwrap(), Some(("codex".into(), "s-304".into())));
    // A transport written by the previous version is still found, then moved into the index.
    assert_eq!(mailbox.transport("ancien-transport").await.unwrap(), Some(("codex".into(), "s-ancien".into())));
    assert_eq!(mailbox.setting("mcp_transport:ancien-transport").await.unwrap(), Some(Value::Null));
    assert_eq!(mailbox.setting("mcp_transports").await.unwrap().unwrap().as_object().unwrap().len(), 300);
    // A closed transport is removed, not kept as null.
    mailbox.save_transport("transport-304", None).await.unwrap();
    assert!(!mailbox.setting("mcp_transports").await.unwrap().unwrap().as_object().unwrap().contains_key("transport-304"));
    assert_eq!(mailbox.transport("transport-304").await.unwrap(), None);
    assert_eq!(mailbox.transport("../hors").await.unwrap(), None);
}
