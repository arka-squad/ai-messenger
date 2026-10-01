use super::*;
use crate::test_support::{tool, Temporary};

async fn enrol<R: RepositoryPort, E: ExchangePort>(
    mailbox: &MailboxService<R, E>,
    provider: &str,
    session: &str,
    arguments: Value,
) -> Value {
    let result = tool(mailbox, provider, session, "m_enroler", arguments).await;
    assert!(result.get("isError").is_none(), "{result}");
    result["structuredContent"].clone()
}
async fn bound<R: RepositoryPort, E: ExchangePort>(mailbox: &MailboxService<R, E>, session: &str) -> String {
    mailbox.identity("codex", session).await.unwrap().unwrap().account
}
#[tokio::test]
async fn a_session_is_never_trapped_in_the_account_it_was_rebound_to() {
    let root = Temporary::new();
    let mailbox = root.mailbox("trap").await;
    let first = enrol(&mailbox, "codex", "s1", json!({"tache":"Alpha","role":"dev","project":"p","dossier":"/srv/R"})).await;
    let alpha = first["identity"]["account"].as_str().unwrap().to_owned();
    let alpha_key = first["recovery_key"].as_str().unwrap().to_owned();
    // A second agent opens in the same folder: it is rebound to the folder's account.
    let who = tool(&mailbox, "codex", "s2", "qui_suis_je", json!({"dossier":"/srv/R"})).await["structuredContent"].clone();
    assert_eq!(who["identity"]["account"], alpha);
    assert_eq!(who["rebound"], true);
    // Its own task gives it its own account, and the session follows.
    let second = enrol(&mailbox, "codex", "s2", json!({"tache":"Gamma","role":"QA","project":"p","dossier":"/srv/R"})).await;
    let gamma = second["identity"]["account"].as_str().unwrap().to_owned();
    assert_ne!(gamma, alpha);
    assert!(second["recovery_key"].is_string());
    assert!(second.get("already_enrolled").is_none());
    assert_eq!(second["rebound_from"], alpha);
    assert_eq!(bound(&mailbox, "s2").await, gamma);
    assert_eq!(bound(&mailbox, "s1").await, alpha, "the first agent keeps its account");
    let sent = tool(&mailbox, "codex", "s2", "envoyer", json!({"message":{"id":"de-gamma","to":[alpha],"subject":"Bonjour"}})).await;
    assert!(sent.get("isError").is_none(), "{sent}");
    assert_eq!(mailbox.message("de-gamma").await.unwrap().unwrap().from, gamma);
    // The same task again changes nothing and mints no key.
    let again = enrol(&mailbox, "codex", "s2", json!({"tache":"Gamma","role":"QA","project":"p"})).await;
    assert_eq!(again["identity"]["account"], gamma);
    assert_eq!(again["already_enrolled"], true);
    assert!(again.get("recovery_key").is_none() && again.get("rebound_from").is_none());
    // A valid key rebinds a session bound elsewhere; a wrong one never does.
    let wrong = tool(&mailbox, "codex", "s2", "me_reconnaitre", json!({"account":alpha,"recovery_key":"faux"})).await;
    assert_eq!(wrong["structuredContent"]["refus"]["reason"], "reprise_refusee");
    assert_eq!(bound(&mailbox, "s2").await, gamma);
    let back = tool(&mailbox, "codex", "s2", "me_reconnaitre", json!({"account":alpha,"recovery_key":alpha_key})).await["structuredContent"].clone();
    assert_eq!(back["identity"]["account"], alpha);
    assert_eq!(back["rebound_from"], gamma);
    assert_eq!(bound(&mailbox, "s2").await, alpha);
    // From Alpha, the Gamma task finds Gamma again (same installation, tool and task) and rebinds.
    let lookup = enrol(&mailbox, "codex", "s2", json!({"tache":"Gamma","role":"QA","project":"p"})).await;
    assert_eq!(lookup["identity"]["account"], gamma);
    assert_eq!(lookup["already_enrolled"], true);
    assert_eq!(lookup["rebound_from"], alpha);
    assert_eq!(bound(&mailbox, "s2").await, gamma);
    assert_eq!(mailbox.accounts().await.unwrap().len(), 2);
    // Two agents of the same tool enrolled in exactly this folder: it is shared and rebinds nobody.
    assert!(mailbox.remembered("codex", "/srv/R").await.unwrap().is_none());
    let shared = mailbox.shared("codex", "/srv/R").await.unwrap().into_iter().map(|a| a.address).collect::<Vec<_>>();
    assert!(shared.contains(&alpha) && shared.contains(&gamma), "{shared:?}");
    assert_eq!(mailbox.setting(&format!("identity:codex:{}", folder_key("/srv/R/sub").unwrap())).await.unwrap(), None);
}
#[tokio::test]
async fn a_session_that_changes_account_takes_its_push_route_along() {
    let root = Temporary::new();
    let mailbox = root.mailbox("route").await;
    let alpha = enrol(&mailbox, "codex", "s3", json!({"tache":"Alpha","role":"dev","delivery_session":"natif-3"})).await["identity"]["account"].as_str().unwrap().to_owned();
    assert_eq!(mailbox.account_route(&alpha).await.unwrap(), Some(("codex".into(), "natif-3".into())));
    let beta = enrol(&mailbox, "codex", "s3", json!({"tache":"Beta","role":"dev","delivery_session":"natif-3"})).await["identity"]["account"].as_str().unwrap().to_owned();
    assert_eq!(mailbox.account_route(&beta).await.unwrap(), Some(("codex".into(), "natif-3".into())));
    assert_eq!(mailbox.account_route(&alpha).await.unwrap(), None, "Alpha's mail no longer wakes Beta's session");
    // The native session this agent session named earlier is released too, even when none is named now.
    let gamma = enrol(&mailbox, "codex", "s4", json!({"tache":"Gamma","role":"dev","delivery_session":"natif-4"})).await["identity"]["account"].as_str().unwrap().to_owned();
    let delta = enrol(&mailbox, "codex", "s5", json!({"tache":"Delta","role":"dev","delivery_session":"natif-5"})).await["identity"]["account"].as_str().unwrap().to_owned();
    enrol(&mailbox, "codex", "s4", json!({"tache":"Beta","role":"dev"})).await;
    assert_eq!(mailbox.account_route(&gamma).await.unwrap(), None);
    assert_eq!(mailbox.account_route(&beta).await.unwrap(), Some(("codex".into(), "natif-3".into())));
    // A route that names another agent's session is left alone.
    assert_eq!(mailbox.account_route(&delta).await.unwrap(), Some(("codex".into(), "natif-5".into())));
}
#[tokio::test]
async fn a_folder_two_agents_share_and_the_home_folder_rebind_nobody() {
    let root = Temporary::new();
    let mailbox = root.mailbox("partage").await;
    let alpha = enrol(&mailbox, "claude-code", "a", json!({"tache":"Alpha","role":"dev","dossier":"/srv/Commun"})).await["identity"]["account"].as_str().unwrap().to_owned();
    // One agent in the folder: a new session there is rebound to it.
    let first = tool(&mailbox, "claude-code", "a2", "qui_suis_je", json!({"dossier":"/srv/Commun"})).await;
    assert_eq!(first["structuredContent"]["identity"]["account"], alpha);
    let beta = enrol(&mailbox, "claude-code", "b", json!({"tache":"Beta","role":"qa","dossier":"/srv/Commun"})).await["identity"]["account"].as_str().unwrap().to_owned();
    // Two agents of the same tool work there: nobody is rebound, both are offered first.
    let next = tool(&mailbox, "claude-code", "c", "qui_suis_je", json!({"dossier":"/srv/Commun"})).await;
    let content = &next["structuredContent"];
    assert!(content["identity"].is_null(), "{content}");
    let offered = content["candidates"].as_array().unwrap();
    let first_two = offered.iter().take(2).map(|c| c["address"].as_str().unwrap().to_owned()).collect::<std::collections::BTreeSet<_>>();
    assert_eq!(first_two, std::collections::BTreeSet::from([alpha.clone(), beta.clone()]));
    assert!(offered.iter().take(2).all(|c| c.get("dossier_partage").is_some()));
    assert!(content["hint"].as_str().unwrap().contains("dossier_partage"));
    // The session-start notice names both accounts and never says "tu es".
    let start = hook::notice(&mailbox, &json!({"provider":"claude-code","event":"SessionStart","cwd":"/srv/Commun"})).await.unwrap().unwrap();
    assert!(start.contains(&alpha) && start.contains(&beta) && !start.contains("tu es"), "{start}");
    // Each agent still resumes its own account there with its own task.
    let again = enrol(&mailbox, "claude-code", "c", json!({"tache":"Beta","role":"qa","dossier":"/srv/Commun"})).await;
    assert_eq!(again["identity"]["account"], beta);
    // The home folder, where a terminal opens by default, never retains an account.
    let home = crate::mailbox::identity::home_key().unwrap();
    enrol(&mailbox, "codex", "h", json!({"tache":"Maison","role":"dev","dossier":home})).await;
    let there = tool(&mailbox, "codex", "h2", "qui_suis_je", json!({"dossier":home})).await;
    assert!(there["structuredContent"]["identity"].is_null(), "{there}");
    assert!(there["structuredContent"]["hint"].as_str().unwrap().contains("dossier personnel"));
    assert!(mailbox.setting(&format!("identity:codex:{home}")).await.unwrap().is_none());
}
#[tokio::test]
async fn a_returning_agent_finds_its_account_even_under_a_doubled_name() {
    let root = Temporary::new();
    let mailbox = root.mailbox("doublon").await;
    // An account enrolled before the task was cleaned up: CL_Agent-Agent-Cortex-5_WIN_WIN.
    let system = crate::mailbox::directory::system();
    let (legacy, display) = crate::mailbox::directory::raw_identity("codex", "Agent-Cortex-5_WIN", system).unwrap();
    let old = format!("{legacy}@cortex");
    mailbox.event(crate::domain::journal::Change::Account { account: crate::domain::journal::AgentAccount {
        address: old.clone(), display, host: "codex".into(), machine: mailbox.machine.clone(), role: "dev".into(),
        active: true, created_at: "2026-10-01T10:00:00+00:00".into(), installation: mailbox.installation.clone(),
        project: Some("cortex".into()), merged_into: None,
    } }).await.unwrap();
    // The same agent, same task: it gets that account back, never a new clean one beside it.
    let back = enrol(&mailbox, "codex", "nouvelle", json!({"tache":"Agent-Cortex-5_WIN","role":"dev","project":"cortex"})).await;
    assert_eq!(back["identity"]["account"], old);
    // A new agent with that task written plainly gets the clean name.
    let fresh = enrol(&mailbox, "claude-code", "autre", json!({"tache":"Cortex-5","role":"dev","project":"cortex"})).await;
    assert!(fresh["account"]["display"].as_str().unwrap().starts_with("CL_Agent-Cortex-5_"));
}
#[tokio::test]
async fn attendre_defaults_below_the_host_timeout_and_records_only_answers_given_in_time() {
    assert!(DEFAULT_WAIT < 60);
    let tools = schema::tools();
    let attendre = tools.as_array().unwrap().iter().find(|t| t["name"] == "attendre").unwrap();
    let secondes = &attendre["inputSchema"]["properties"]["secondes"];
    assert_eq!(secondes["maximum"], crate::mailbox::MAX_WAIT);
    let text = secondes["description"].as_str().unwrap();
    assert!(text.contains("50 par défaut") && text.contains("1800") && text.contains("Codex : 60 s"), "{text}");
    assert!(handed_over(std::time::Instant::now(), 0));
    assert!(handed_over(std::time::Instant::now(), 50));
    let late = std::time::Instant::now() - std::time::Duration::from_secs(3);
    assert!(!handed_over(late, 2), "an answer produced after the wait is not counted as handed over");
    assert!(handed_over(late, 50));
    // Without secondes, mail already waiting is returned at once.
    let root = Temporary::new();
    let mailbox = root.mailbox("wait").await;
    enrol(&mailbox, "codex", "a", json!({"tache":"Alpha","role":"dev"})).await;
    let b = enrol(&mailbox, "codex", "b", json!({"tache":"Beta","role":"dev"})).await["identity"]["account"].clone();
    tool(&mailbox, "codex", "a", "envoyer", json!({"message":{"id":"tout-de-suite","to":[b],"subject":"Info"}})).await;
    let started = std::time::Instant::now();
    let waited = tool(&mailbox, "codex", "b", "attendre", json!({})).await;
    assert_eq!(waited["structuredContent"]["received"][0]["id"], "tout-de-suite");
    assert!(started.elapsed() < std::time::Duration::from_secs(20));
    assert!(mailbox.returned_to("codex:b").contains("tout-de-suite"));
}
