use super::*;
use crate::test_support::{post, serve_mcp, tool, Temporary};

async fn enrol<R: RepositoryPort, E: ExchangePort>(
    mailbox: &MailboxService<R, E>,
    provider: &str,
    session: &str,
    arguments: Value,
) -> Value {
    tool(mailbox, provider, session, "m_enroler", arguments).await["structuredContent"].clone()
}
fn transport(head: &str) -> String {
    head.lines()
        .find_map(|h| h.to_ascii_lowercase().strip_prefix("mcp-session-id: ").map(str::to_owned))
        .unwrap()
}
#[test]
fn folder_keys_are_absolute_and_name_one_folder_however_it_is_written() {
    use crate::mailbox::identity::parents;
    assert_eq!(folder_key("src"), None);
    assert_eq!(folder_key(""), None);
    assert_eq!(folder_key("/srv/Depot/").unwrap(), if cfg!(windows) { "/srv/depot" } else { "/srv/Depot" });
    if cfg!(windows) {
        for written in ["C:\\Work\\Repo\\", "c:/work/repo", "/c/Work/Repo/"] {
            assert_eq!(folder_key(written).unwrap(), "c:/work/repo", "{written}");
        }
    }
    // The parent walk never reaches a drive, volume or share root, nor the home folder or above it.
    assert_eq!(parents("/srv/a/b", None), vec!["/srv/a", "/srv"]);
    assert_eq!(parents("c:/work/repo/sub", None), vec!["c:/work/repo", "c:/work"]);
    assert!(parents("c:/work", None).is_empty());
    assert_eq!(parents("/Volumes/Data/repo/sub", None), vec!["/Volumes/Data/repo"]);
    assert_eq!(parents("/mnt/c/work/repo", None), vec!["/mnt/c/work"]);
    assert_eq!(parents("//server/share/repo/sub", None), vec!["//server/share/repo"]);
    let home = Some("c:/users/grimo");
    assert_eq!(parents("c:/users/grimo/projets/repo/sub", home), vec!["c:/users/grimo/projets/repo", "c:/users/grimo/projets"]);
    assert!(parents("c:/users/grimo/repo", home).is_empty());
    assert_eq!(parents("c:/users/autre/repo", home), vec!["c:/users/autre"]);
    assert_eq!(parents("/home/ana/code/app", Some("/home/ana")), vec!["/home/ana/code"]);
}
#[tokio::test]
async fn a_new_session_in_a_known_folder_is_rebound_to_its_account() {
    let root = Temporary::new();
    let mailbox = root.mailbox("one").await;
    let enrolled = enrol(&mailbox, "codex", "first", json!({"tache":"Alpha","role":"dev","project":"test","dossier":"/srv/Depot/"})).await;
    let address = enrolled["identity"]["account"].as_str().unwrap().to_owned();
    // The directory is readable before any identity.
    let directory = tool(&mailbox, "codex", "second", "agents", json!({})).await;
    assert!(directory.get("isError").is_none());
    assert_eq!(directory["structuredContent"]["data"][0]["address"], address);
    // Without a folder, the unbound session is offered this installation's accounts for its tool.
    let unbound = tool(&mailbox, "codex", "second", "qui_suis_je", json!({})).await["structuredContent"].clone();
    assert!(unbound["identity"].is_null());
    assert_eq!(unbound["candidates"], json!([{"address":address,"display":"CD_Agent-Alpha_".to_owned()+&crate::mailbox::directory::system().to_uppercase(),"role":"dev","project":"test"}]));
    assert!(unbound["hint"].as_str().unwrap().contains("me_reconnaitre"));
    // Below the folder, the account is only offered first, marked with the parent folder: never bound.
    let below = tool(&mailbox, "codex", "second", "qui_suis_je", json!({"dossier":"/srv/Depot/src"})).await["structuredContent"].clone();
    assert!(below["identity"].is_null(), "{below}");
    assert!(below.get("rebound").is_none());
    assert_eq!(below["candidates"][0]["address"], address);
    assert_eq!(below["candidates"][0]["dossier_parent"], folder_key("/srv/Depot").unwrap());
    assert_eq!(below["candidates"].as_array().unwrap().len(), 1, "the parent's account is listed once");
    assert!(below["hint"].as_str().unwrap().contains("dossier parent"));
    assert!(mailbox.identity("codex", "second").await.unwrap().is_none());
    // In exactly the same folder, the session is rebound without any key.
    let rebound = tool(&mailbox, "codex", "second", "qui_suis_je", json!({"dossier":"/srv/Depot/"})).await["structuredContent"].clone();
    assert_eq!(rebound["identity"]["account"], address);
    assert_eq!(rebound["rebound"], true);
    assert!(rebound["hint"].as_str().unwrap().contains("m_enroler"));
    assert!(tool(&mailbox, "codex", "second", "relever", json!({})).await.get("isError").is_none());
    // Another tool working in the same folder is not handed this account.
    let other = tool(&mailbox, "claude-code", "third", "qui_suis_je", json!({"dossier":"/srv/Depot"})).await["structuredContent"].clone();
    assert!(other["identity"].is_null());
    assert_eq!(other["candidates"], json!([]));
    let relative = tool(&mailbox, "codex", "fourth", "qui_suis_je", json!({"dossier":"src"})).await;
    assert_eq!(relative["isError"], true);
    assert_eq!(relative["structuredContent"]["refus"]["reason"], "dossier_invalide");
}
#[tokio::test]
async fn the_same_task_returns_the_same_account_and_a_homonym_elsewhere_gets_a_suffix() {
    let root = Temporary::new();
    let one = root.mailbox("one").await;
    let two = root.mailbox("two").await;
    let arguments = json!({"tache":"Alpha","role":"dev","project":"test"});
    let first = enrol(&one, "codex", "a", arguments.clone()).await;
    let address = first["identity"]["account"].as_str().unwrap().to_owned();
    let key = first["recovery_key"].as_str().unwrap().to_owned();
    let again = enrol(&one, "codex", "b", arguments.clone()).await;
    assert_eq!(again["identity"]["account"], address);
    assert_eq!(again["already_enrolled"], true);
    assert!(again.get("recovery_key").is_none(), "no new key is minted");
    assert_eq!(one.accounts().await.unwrap().len(), 1);
    assert!(tool(&one, "codex", "b", "relever", json!({})).await.get("isError").is_none());
    let resumed = tool(&one, "codex", "c", "me_reconnaitre", json!({"account":address,"recovery_key":key})).await;
    assert_eq!(resumed["structuredContent"]["identity"]["account"], address, "the first key stays valid");
    two.receive().await.unwrap();
    let homonym = enrol(&two, "codex", "x", arguments).await;
    let local = address.split('@').next().unwrap();
    assert_eq!(homonym["identity"]["account"], format!("{local}-1@test"));
    assert!(homonym["recovery_key"].is_string());
}
#[tokio::test]
async fn an_agent_session_keeps_its_identity_across_an_app_restart() {
    let root = Temporary::new();
    let mailbox = Arc::new(root.mailbox("restart").await);
    let (port, service) = serve_mcp(mailbox.clone()).await;
    let host = format!("127.0.0.1:{port}");
    let (_, head, _) = post(port, "/mcp", &[("Host", &host)], json!({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"clientInfo":{"name":"codex"}}})).await;
    let id = transport(&head);
    let (_, _, enrolled) = post(port, "/mcp", &[("Host", &host), ("Mcp-Session-Id", &id)], json!({"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"m_enroler","arguments":{"tache":"Durable","role":"dev"}}})).await;
    let address = enrolled["result"]["structuredContent"]["identity"]["account"].clone();
    assert!(address.is_string());
    service.abort();
    // A restarted app starts with an empty memory: the transport is found again in the local store.
    let (port, service) = serve_mcp(mailbox.clone()).await;
    let host = format!("127.0.0.1:{port}");
    let (status, _, who) = post(port, "/mcp", &[("Host", &host), ("Mcp-Session-Id", &id)], json!({"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"qui_suis_je","arguments":{}}})).await;
    assert_eq!(status, 200);
    assert_eq!(who["result"]["structuredContent"]["identity"]["account"], address);
    let (status, _, _) = post(port, "/mcp", &[("Host", &host), ("Mcp-Session-Id", "0000-inconnu")], json!({"jsonrpc":"2.0","id":4,"method":"tools/list"})).await;
    assert_eq!(status, 404);
    service.abort();
}
#[tokio::test]
async fn hook_notices_follow_the_folder_identity_and_refuse_browsers() {
    let root = Temporary::new();
    let mailbox = Arc::new(root.mailbox("hook").await);
    let (port, service) = serve_mcp(mailbox.clone()).await;
    let host = format!("127.0.0.1:{port}");
    let ask = |event: &str| json!({"provider":"codex","event":event,"cwd":"/srv/Hook","session_id":"s-1"});
    let notice = |body: Value| {
        let host = host.clone();
        async move { post(port, "/hook", &[("Host", &host)], body).await.2["notice"].clone() }
    };
    let start = notice(ask("SessionStart")).await;
    assert_eq!(start, "Messenger : aucun compte pour ce dossier. Si tu dois échanger du courrier entre agents : qui_suis_je (dossier=/srv/Hook), puis m_enroler (tache, role, project, dossier).");
    assert!(notice(ask("UserPromptSubmit")).await.is_null());
    let enrolled = enrol(&*mailbox, "codex", "agent", json!({"tache":"Crochet","role":"dev","dossier":"/srv/Hook"})).await;
    let address = enrolled["identity"]["account"].as_str().unwrap().to_owned();
    let key = enrolled["recovery_key"].as_str().unwrap().to_owned();
    assert_eq!(notice(ask("SessionStart")).await, format!("Messenger : tu es {address} ; aucun nouveau courrier."));
    assert!(notice(ask("UserPromptSubmit")).await.is_null());
    let sender = enrol(&*mailbox, "codex", "sender", json!({"tache":"Expediteur","role":"dev"})).await["identity"]["account"].clone();
    assert!(sender.is_string());
    let sent = tool(&*mailbox, "codex", "sender", "envoyer", json!({"message":{"id":"pour-crochet","to":[address],"subject":"Info"}})).await;
    assert!(sent.get("isError").is_none(), "{sent}");
    let mail = format!("MAIL — 1 nouveau(x) courrier(s) pour {address} : appelle relever (outils arkalabs-messenger-app).");
    for event in ["SessionStart", "UserPromptSubmit", "Stop"] {
        let text = notice(ask(event)).await;
        assert_eq!(text, mail.as_str());
        assert!(!text.as_str().unwrap().contains(&key));
    }
    // Below the remembered folder, the account is only named as the parent's: never "tu es", no mail count.
    let below = |event: &str| json!({"provider":"codex","event":event,"cwd":"/srv/Hook/src"});
    assert!(notice(below("Stop")).await.is_null());
    assert!(notice(below("UserPromptSubmit")).await.is_null());
    let parent = notice(below("SessionStart")).await;
    let parent = parent.as_str().unwrap();
    assert_eq!(parent, format!("Messenger : aucun compte pour ce dossier ; le dossier parent {} est retenu pour {address}. Si c’est ton compte : qui_suis_je (dossier=/srv/Hook/src), puis m_enroler avec la même tâche ou me_reconnaitre. Sinon, si tu dois échanger du courrier entre agents : m_enroler (tache, role, project, dossier).", folder_key("/srv/Hook").unwrap()));
    assert!(!parent.contains("tu es") && !parent.contains("MAIL"));
    // Without a working folder, the notice still names the argument to give.
    let blank = notice(json!({"provider":"codex","event":"SessionStart"})).await;
    assert!(blank.as_str().unwrap().contains("dossier=<chemin absolu de ton dossier de travail>"));
    tool(&*mailbox, "codex", "agent", "marquer", json!({"marking":{"message_id":"pour-crochet","status":"lu"}})).await;
    assert!(notice(ask("UserPromptSubmit")).await.is_null());
    assert!(notice(json!({"provider":"autre","event":"SessionStart","cwd":"/srv/Hook"})).await.is_null());
    let browser = post(port, "/hook", &[("Host", &host), ("Origin", "https://evil.example")], ask("SessionStart")).await;
    assert_eq!(browser.0, 403);
    let same_origin = post(port, "/hook", &[("Host", &host), ("Origin", &format!("http://{host}"))], ask("SessionStart")).await;
    assert_eq!(same_origin.0, 403, "a hook never carries an Origin");
    let rebinding = post(port, "/hook", &[("Host", &format!("localhost:{port}"))], ask("SessionStart")).await;
    assert_eq!(rebinding.0, 403);
    service.abort();
}
#[tokio::test]
async fn a_claude_push_route_is_only_the_delivery_id_the_agent_names() {
    let root = Temporary::new();
    let mailbox = Arc::new(root.mailbox("channel").await);
    let channel = "0123456789abcdef-channel";
    mailbox.register_channel(channel);
    // A channel open in the agent's folder is never bound by guess: it may be another agent's session.
    let enrolled = enrol(&*mailbox, "claude-code", "http", json!({"tache":"Canal","role":"dev","dossier":"/srv/Claude"})).await;
    let address = enrolled["identity"]["account"].as_str().unwrap().to_owned();
    let route = format!("account_route:{address}");
    assert!(mailbox.setting(&route).await.unwrap().is_none());
    // The agent names the delivery id its own channel gave it: that live channel becomes its route.
    let named = tool(&*mailbox, "claude-code", "http", "qui_suis_je", json!({"dossier":"/srv/Claude","delivery_session":channel})).await;
    assert!(named["structuredContent"].get("remise").is_none(), "{named}");
    assert_eq!(named["structuredContent"]["account"]["role"], "dev");
    assert_eq!(mailbox.setting(&route).await.unwrap().unwrap(), json!({"provider":"claude-code","session":channel}));
    // An id that no connected channel carries is refused and the route stays.
    let unknown = tool(&*mailbox, "claude-code", "http", "qui_suis_je", json!({"delivery_session":"0123456789abcdef-unknown"})).await;
    assert_eq!(unknown["structuredContent"]["remise"], "aucune session de canal active pour cet identifiant");
    assert_eq!(mailbox.setting(&route).await.unwrap().unwrap()["session"], channel);
    // A channel that closes keeps its route: the same session resumes its pushes when it reconnects,
    // as every sidecar does after the app restarts.
    mailbox.channel_closed(channel);
    assert!(!mailbox.live_channel(channel));
    assert_eq!(mailbox.setting(&route).await.unwrap().unwrap()["session"], channel);
    mailbox.register_channel(channel);
    assert!(mailbox.live_channel(channel));
    // Another tool never takes the Claude channel.
    let codex = enrol(&*mailbox, "codex", "other", json!({"tache":"Autre","role":"dev","dossier":"/srv/Claude"})).await;
    let other = format!("account_route:{}", codex["identity"]["account"].as_str().unwrap());
    assert!(mailbox.setting(&other).await.unwrap().is_none());
}
#[tokio::test]
async fn an_agent_changes_only_its_own_role() {
    let root = Temporary::new();
    let mailbox = root.mailbox("role").await;
    assert_eq!(schema::tools().as_array().unwrap().len(), 16);
    let address = enrol(&mailbox, "codex", "a", json!({"tache":"Role","role":"Développeur polyvalent — recette"})).await["identity"]["account"].clone();
    let changed = tool(&mailbox, "codex", "a", "modifier_mon_role", json!({"role":"Relecteur"})).await;
    assert_eq!(changed["structuredContent"]["account"]["role"], "Relecteur");
    let accounts = mailbox.accounts().await.unwrap();
    assert_eq!(accounts.iter().find(|a| json!(a.address) == address).unwrap().role, "Relecteur");
    for (arguments, reason) in [(json!({"role":"humain"}), "role_invalide"), (json!({"role":"deux\nlignes"}), "role_invalide"), (json!({}), "argument_manquant")] {
        let refused = tool(&mailbox, "codex", "a", "modifier_mon_role", arguments).await;
        assert_eq!(refused["isError"], true);
        assert_eq!(refused["structuredContent"]["refus"]["reason"], reason);
    }
    let unbound = tool(&mailbox, "codex", "z", "modifier_mon_role", json!({"role":"Autre"})).await;
    assert_eq!(unbound["structuredContent"]["refus"]["reason"], "session_non_enrolee");
}
