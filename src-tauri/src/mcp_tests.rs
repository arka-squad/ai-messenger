use super::*;
use crate::test_support::Temporary;
async fn call<R: RepositoryPort, E: ExchangePort>(
    mailbox: &MailboxService<R, E>,
    session: &str,
    name: &str,
    arguments: Value,
) -> Value {
    dispatch(
        mailbox,
        &json!({"method":"tools/call","params":{"name":name,"arguments":arguments}}),
        json!(1),
        Some(RouteContext {
            provider: "codex",
            session,
            live_session: false,
        }),
    )
    .await["result"]["structuredContent"]
        .clone()
}
#[tokio::test]
async fn complete_mcp_contract_binds_actor_and_attests_origin_without_trusting_client_fields() {
    let root = Temporary::new();
    let mailbox = root.mailbox("one").await;
    let names = tools()
        .as_array()
        .unwrap()
        .iter()
        .map(|t| t["name"].as_str().unwrap().to_owned())
        .collect::<Vec<_>>();
    for name in [
        "qui_suis_je",
        "m_enroler",
        "me_reconnaitre",
        "agents",
        "contacts",
        "attendre",
        "demander_intervention",
    ] {
        assert!(names.contains(&name.into()));
    }
    assert_eq!(
        call(&mailbox, "a", "relever", json!({})).await["refus"]["reason"],
        "session_non_enrolee"
    );
    let a = call(
        &mailbox,
        "a",
        "m_enroler",
        json!({"tache":"Alpha","role":"dev"}),
    )
    .await["identity"]["account"]
        .as_str()
        .unwrap()
        .to_owned();
    let system = crate::mailbox::directory::system();
    assert_eq!(a, format!("cd-agent-alpha-{system}"), "The account names its provider, task and system");
    let b = call(
        &mailbox,
        "b",
        "m_enroler",
        json!({"tache":"Beta","role":"dev"}),
    )
    .await["identity"]["account"]
        .as_str()
        .unwrap()
        .to_owned();
    let refused = call(
        &mailbox,
        "a",
        "envoyer",
        json!({"message":{"from":b,"to":[a],"subject":"Usurpation"}}),
    )
    .await;
    assert_eq!(refused["refus"]["reason"], "identite_refusee");
    let sent=call(&mailbox,"a","envoyer",json!({"message":{"to":[b],"subject":"Information","origin":{"host":"FAUX","session":"autre"}}})).await;
    assert_eq!(sent["publication"], "publié");
    assert!(sent["proof"].as_str().unwrap().len() == 64);
    let mail = mailbox.messages().await.unwrap().pop().unwrap();
    assert_eq!(mail.from, a);
    assert_eq!(mail.origin.host, "machine-one");
    assert_eq!(mail.origin.session, "a");
    assert_eq!(
        call(&mailbox, "b", "relever", json!({"account":a})).await["refus"]["reason"],
        "identite_refusee"
    );
    let repeat = call(
        &mailbox,
        "a",
        "envoyer",
        json!({"message":{"id":mail.id,"to":[b],"subject":"Information"}}),
    )
    .await;
    assert_eq!(repeat["proof"], sent["proof"]);
    assert_eq!(mailbox.messages().await.unwrap().len(), 1);
    let c = call(
        &mailbox,
        "c",
        "m_enroler",
        json!({"tache":"Gamma","role":"dev"}),
    )
    .await["identity"]["account"]
        .as_str()
        .unwrap()
        .to_owned();
    for (session, id, to, parent) in [
        ("b", "reply", &a, &mail.id),
        ("a", "grandchild", &b, &"reply".to_owned()),
        ("b", "private-branch", &c, &mail.id),
    ] {
        let result = call(
            &mailbox,
            session,
            "repondre",
            json!({"reply_to":parent,"message":{"id":id,"to":[to],"subject":"Suite"}}),
        )
        .await;
        assert!(result.get("refus").is_none(), "{result}");
    }
    let read = call(&mailbox, "a", "lire", json!({"id":mail.id})).await;
    let thread = read["thread"].as_array().unwrap();
    assert_eq!(thread.len(), 3);
    assert!(thread.iter().any(|v| v["id"] == "grandchild"));
    assert!(!thread.iter().any(|v| v["id"] == "private-branch"));
    assert!(thread
        .iter()
        .all(|v| v["complete"] == true && v["history"].is_array()));
}
#[test]
fn local_http_rejects_browser_origin_and_dns_rebinding() {
    let mut headers = HeaderMap::new();
    headers.insert("host", "127.0.0.1:47652".parse().unwrap());
    assert!(local_headers(&headers));
    headers.insert("origin", "https://evil.example".parse().unwrap());
    assert!(!local_headers(&headers));
    headers.remove("origin");
    headers.insert("host", "evil.example:47652".parse().unwrap());
    assert!(!local_headers(&headers));
}

async fn http(port: u16, session: Option<String>, request: Value) -> (String, Value) {
    tokio::task::spawn_blocking(move || {
        use std::io::{Read,Write};
        let body=request.to_string();let mut connection=std::net::TcpStream::connect(("127.0.0.1",port)).unwrap();
        connection.set_read_timeout(Some(std::time::Duration::from_secs(15))).unwrap();
        let header=session.map(|s|format!("Mcp-Session-Id: {s}\r\n")).unwrap_or_default();
        write!(connection,"POST /mcp HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nContent-Type: application/json\r\nConnection: close\r\n{header}Content-Length: {}\r\n\r\n{body}",body.len()).unwrap();
        let mut response=String::new();connection.read_to_string(&mut response).unwrap();
        let (headers,body)=response.split_once("\r\n\r\n").unwrap();
        (headers.to_owned(),serde_json::from_str(body).unwrap())
    }).await.unwrap()
}
#[tokio::test]
async fn real_http_sessions_do_not_publish_the_private_transport_credential() {
    let root = Temporary::new();
    let mailbox = Arc::new(root.mailbox("http").await);
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let port = listener.local_addr().unwrap().port();
    let served = mailbox.clone();
    let service = tokio::spawn(async move {
        axum::serve(listener, router(served)).await.unwrap();
    });
    let (headers,initial)=http(port,None,json!({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"clientInfo":{"name":"codex"}}})).await;
    assert_eq!(
        initial["result"]["serverInfo"]["name"],
        "arkalabs-messenger"
    );
    let transport = headers
        .lines()
        .find_map(|h| {
            h.to_ascii_lowercase()
                .strip_prefix("mcp-session-id: ")
                .map(str::to_owned)
        })
        .unwrap();
    let (_,enrolled)=http(port,Some(transport.clone()),json!({"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"m_enroler","arguments":{"tache":"Agent","role":"dev"}}})).await;
    assert_ne!(
        enrolled["result"]["structuredContent"]["identity"]["session"],
        transport
    );
    let journal =
        serde_json::to_string(&mailbox.store.mutations(None, None).await.unwrap()).unwrap();
    assert!(!journal.contains(&transport));
    let (_, tools) = http(
        port,
        Some(transport),
        json!({"jsonrpc":"2.0","id":3,"method":"tools/list"}),
    )
    .await;
    assert_eq!(tools["result"]["tools"].as_array().unwrap().len(), 15);
    service.abort();
}
#[tokio::test]
async fn standard_sdk_exercises_the_real_agent_contract_over_http() {
    let root = Temporary::new();
    let mailbox = Arc::new(root.mailbox("sdk").await);
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let port = listener.local_addr().unwrap().port();
    let service = tokio::spawn(async move {
        axum::serve(listener, router(mailbox)).await.unwrap();
    });
    let output = tokio::task::spawn_blocking(move || {
        std::process::Command::new("node")
            .current_dir(
                std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
                    .parent()
                    .unwrap(),
            )
            .args([
                "scripts/test-mcp-http.mjs",
                &format!("http://127.0.0.1:{port}/mcp"),
            ])
            .output()
            .unwrap()
    })
    .await
    .unwrap();
    service.abort();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
}
