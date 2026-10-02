use crate::{
    domain::ports::*,
    mailbox::MailboxService,
    exchange::DirectoryExchange,
    storage::LocalStore,
    test_support::*,
};
use serde_json::{json, Value};
use std::sync::Arc;

type Mailbox = MailboxService<LocalStore, DirectoryExchange>;

async fn member(mailbox: &Mailbox, task: &str, project: &str) -> String {
    mailbox.enroll("test", task, task, "développeur", Some(project.into())).await.unwrap()["identity"]["account"]
        .as_str()
        .unwrap()
        .into()
}

async fn rpc(port: u16, key: &str, body: Value) -> (u16, Value) {
    let host = format!("127.0.0.1:{port}");
    let bearer = format!("Bearer {key}");
    let (status, _, json) = post(port, "/mcp", &[("Host", &host), ("Authorization", &bearer)], body).await;
    (status, json)
}

/// A tool answer, read as Cortex does: JSON in the first text content.
async fn call(port: u16, key: &str, name: &str, arguments: Value) -> (Value, bool) {
    let request = json!({"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":name,"arguments":arguments}});
    let (status, answer) = rpc(port, key, request).await;
    assert_eq!(status, 200);
    let text = answer["result"]["content"][0]["text"].as_str().unwrap();
    (serde_json::from_str(text).unwrap(), answer["result"]["isError"] == true)
}

fn ids(read: &Value) -> Vec<String> {
    read["enregistrements"].as_array().unwrap().iter().map(|r| r["id"].as_str().unwrap().to_owned()).collect()
}

#[tokio::test]
async fn an_observer_key_reads_only_the_ticked_projects_and_writes_nothing() {
    let root = Temporary::new();
    let mailbox = Arc::new(root.mailbox("one").await);
    let alpha = member(&mailbox, "alpha", "cortex").await;
    let beta = member(&mailbox, "beta", "cortex").await;
    let gamma = member(&mailbox, "gamma", "autre").await;
    let delta = member(&mailbox, "delta", "autre").await;
    mailbox.send(message("vu", &alpha, &beta)).await.unwrap();
    mailbox.send(message("cache", &gamma, &delta)).await.unwrap();
    mailbox.watch_projects(vec!["cortex".into()]).await.unwrap();
    let key = mailbox.open_observation().await.unwrap();
    let (port, server) = serve_mcp(mailbox.clone()).await;

    let (status, _) = rpc(port, "pas-la-bonne-cle", json!({"jsonrpc":"2.0","id":1,"method":"tools/list"})).await;
    assert_eq!(status, 401);
    let (status, listed) = rpc(port, &key, json!({"jsonrpc":"2.0","id":1,"method":"tools/list"})).await;
    assert_eq!(status, 200);
    let tools = listed["result"]["tools"].as_array().unwrap();
    let names = tools.iter().map(|t| t["name"].as_str().unwrap()).collect::<Vec<_>>();
    assert_eq!(names, ["observer_projets", "observer_lire", "observer_piece_jointe"]);
    assert!(tools.iter().all(|t| t["annotations"]["readOnlyHint"] == true));

    let journal = mailbox.store.mutations(None, None).await.unwrap();
    let (read, error) = call(port, &key, "observer_lire", json!({})).await;
    assert!(!error);
    assert!(ids(&read).contains(&"vu".to_owned()));
    assert!(!ids(&read).contains(&"cache".to_owned()), "a project not ticked is never served");
    assert_eq!(read["complet"], true);
    let message = read["enregistrements"].as_array().unwrap().iter().find(|r| r["id"] == "vu").unwrap();
    assert_eq!(message["type"], "message");
    assert_eq!(message["provenance"]["expediteur"], alpha);
    assert!(message["curseur"].as_str().is_some());
    assert_eq!(mailbox.store.mutations(None, None).await.unwrap(), journal, "reading writes nothing");

    mailbox.send(message_after("suite", &alpha, &beta)).await.unwrap();
    let (next, _) = call(port, &key, "observer_lire", json!({"depuis":read["curseur"]})).await;
    assert!(ids(&next).contains(&"suite".to_owned()));
    assert!(!ids(&next).contains(&"vu".to_owned()), "a cursor reads what follows it");
    let (latest, _) = call(port, &key, "observer_lire", json!({"recents":1})).await;
    assert_eq!(ids(&latest), ["suite"]);
    let (chosen, _) = call(port, &key, "observer_lire", json!({"ids":["vu","cache"]})).await;
    assert_eq!(ids(&chosen), ["vu"]);
    let (projects, _) = call(port, &key, "observer_projets", json!({})).await;
    assert_eq!(projects["projets"][0]["projet"], "cortex");
    assert_eq!(projects["projets"].as_array().unwrap().len(), 1);

    for (name, arguments, reason) in [
        ("observer_lire", json!({"projet":"autre"}), "projet_hors_portee"),
        ("observer_lire", json!({"depuis":"une-autre-base:3"}), "curseur_inconnu"),
        ("envoyer", json!({"to":[beta],"body":["non"]}), "observateur_lecture_seule"),
        ("marquer", json!({}), "observateur_lecture_seule"),
    ] {
        let (refused, error) = call(port, &key, name, arguments).await;
        assert!(error, "{name}");
        assert_eq!(refused["refus"]["reason"], reason, "{name}");
    }

    mailbox.pause_observation(true).await.unwrap();
    let (paused, error) = call(port, &key, "observer_projets", json!({})).await;
    assert!(error);
    assert_eq!(paused["refus"]["reason"], "observation_en_pause");
    mailbox.revoke_observation().await.unwrap();
    let (status, _) = rpc(port, &key, json!({"jsonrpc":"2.0","id":1,"method":"tools/list"})).await;
    assert_eq!(status, 401, "a withdrawn key opens nothing");
    server.abort();
}

#[tokio::test]
async fn attachments_are_served_as_text_slices_never_as_binaries() {
    let root = Temporary::new();
    let mailbox = Arc::new(root.mailbox("one").await);
    let alpha = member(&mailbox, "alpha", "cortex").await;
    let beta = member(&mailbox, "beta", "cortex").await;
    let text = "# Rapport\n".repeat(3000);
    let report = mailbox.put_attachment("rapport.md".into(), text.clone().into_bytes()).await.unwrap();
    let picture = mailbox.put_attachment("capture.png".into(), vec![137, 80, 78, 71]).await.unwrap();
    let mut first = message("avec-rapport", &alpha, &beta);
    first.attachment = Some(report.clone());
    mailbox.send(first).await.unwrap();
    let mut second = message("avec-image", &alpha, &beta);
    second.attachment = Some(picture.clone());
    mailbox.send(second).await.unwrap();
    mailbox.watch_projects(vec!["cortex".into()]).await.unwrap();
    let key = mailbox.open_observation().await.unwrap();
    let (port, server) = serve_mcp(mailbox.clone()).await;

    let (slice, error) = call(port, &key, "observer_piece_jointe", json!({"empreinte":report.fingerprint,"debut":10,"longueur":20})).await;
    assert!(!error);
    assert_eq!(slice["servie"], true);
    assert_eq!(slice["texte"], text.chars().skip(10).take(20).collect::<String>());
    assert_eq!(slice["total"], text.chars().count());
    assert_eq!(slice["fin"], false);
    let (whole, _) = call(port, &key, "observer_piece_jointe", json!({"empreinte":report.fingerprint})).await;
    assert_eq!(whole["longueur"], 20_000, "a slice never exceeds 20 000 characters");
    let (binary, error) = call(port, &key, "observer_piece_jointe", json!({"empreinte":picture.fingerprint})).await;
    assert!(!error);
    assert_eq!(binary["servie"], false);
    assert_eq!(binary["raison"], "type_non_texte");
    assert!(binary.get("texte").is_none());
    let (unknown, error) = call(port, &key, "observer_piece_jointe", json!({"empreinte":"0".repeat(64)})).await;
    assert!(error);
    assert_eq!(unknown["refus"]["reason"], "piece_jointe_hors_portee");
    server.abort();
}

/// A later message, so that « recents » has a clear latest one.
fn message_after(id: &str, from: &str, to: &str) -> crate::domain::models::MailMessage {
    let mut later = message(id, from, to);
    later.emitted_at = "2099-01-01T00:00:00+00:00".into();
    later
}

/// Reads the pushed feed until `until` appears or `seconds` pass: (status, raw text).
fn listen(port: u16, key: &str, path: &str, extra: &[(&str, &str)], until: &str, seconds: u64) -> (u16, String) {
    use std::io::{Read, Write};
    let mut connection = std::net::TcpStream::connect(("127.0.0.1", port)).unwrap();
    connection.set_read_timeout(Some(std::time::Duration::from_millis(100))).unwrap();
    let head = extra.iter().map(|(k, v)| format!("{k}: {v}\r\n")).collect::<String>();
    write!(connection, "GET {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nAuthorization: Bearer {key}\r\nAccept: text/event-stream\r\n{head}\r\n").unwrap();
    let deadline = std::time::Instant::now() + std::time::Duration::from_secs(seconds);
    let (mut received, mut buffer) = (Vec::new(), [0u8; 8192]);
    while std::time::Instant::now() < deadline && !String::from_utf8_lossy(&received).contains(until) {
        match connection.read(&mut buffer) {
            Ok(0) => break,
            Ok(read) => received.extend_from_slice(&buffer[..read]),
            Err(_) => {}
        }
    }
    let text = String::from_utf8_lossy(&received).into_owned();
    (text.split_whitespace().nth(1).and_then(|s| s.parse().ok()).unwrap_or(0), text)
}

#[tokio::test(flavor = "multi_thread", worker_threads = 2)]
async fn the_pushed_feed_replays_then_follows_the_box_and_the_consent() {
    let root = Temporary::new();
    let mailbox = Arc::new(root.mailbox("one").await);
    let alpha = member(&mailbox, "alpha", "cortex").await;
    let beta = member(&mailbox, "beta", "cortex").await;
    let gamma = member(&mailbox, "gamma", "autre").await;
    let delta = member(&mailbox, "delta", "autre").await;
    mailbox.send(message("vu", &alpha, &beta)).await.unwrap();
    mailbox.send(message("cache", &gamma, &delta)).await.unwrap();
    mailbox.watch_projects(vec!["cortex".into()]).await.unwrap();
    let key = mailbox.open_observation().await.unwrap();
    let (port, server) = serve_mcp(mailbox.clone()).await;
    let feed = |path: &'static str, last: Option<&'static str>, until: &'static str| {
        let key = key.clone();
        tokio::task::spawn_blocking(move || {
            let extra = last.map(|cursor| vec![("Last-Event-ID", cursor)]).unwrap_or_default();
            listen(port, &key, path, &extra, until, 10)
        })
    };

    let (status, replay) = feed("/v1/observe/events", None, "\"id\":\"vu\"").await.unwrap();
    assert_eq!(status, 200);
    assert!(replay.contains("event: record") && replay.contains("\"id\":\"vu\""));
    assert!(!replay.contains("\"id\":\"cache\""), "a project not ticked is never pushed");

    let live = feed("/v1/observe/events?depuis=fin", None, "\"id\":\"direct\"");
    tokio::time::sleep(std::time::Duration::from_millis(500)).await;
    let sent = std::time::Instant::now();
    mailbox.send(message("direct", &alpha, &beta)).await.unwrap();
    let (_, live) = live.await.unwrap();
    assert!(live.contains("\"id\":\"direct\""));
    assert!(sent.elapsed() < std::time::Duration::from_secs(2), "pushed within 2 s");
    assert!(!live.contains("\"id\":\"vu\""), "from the end, the past is not replayed");

    let (status, _) = feed("/v1/observe/events", Some("une-autre-base:4"), "curseur_inconnu").await.unwrap();
    assert_eq!(status, 410);

    let consent = feed("/v1/observe/events?depuis=fin", None, "event: revoked");
    tokio::time::sleep(std::time::Duration::from_millis(500)).await;
    mailbox.pause_observation(true).await.unwrap();
    tokio::time::sleep(std::time::Duration::from_millis(500)).await;
    mailbox.revoke_observation().await.unwrap();
    let (_, consent) = consent.await.unwrap();
    assert!(consent.contains("event: paused"), "{consent}");
    assert!(consent.contains("event: revoked"), "{consent}");
    let (status, _) = feed("/v1/observe/events", None, "refus").await.unwrap();
    assert_eq!(status, 401, "a withdrawn key opens no feed");
    server.abort();
}
