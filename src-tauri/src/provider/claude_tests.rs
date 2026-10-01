use std::{fs, os::unix::fs::PermissionsExt};

use futures_util::{SinkExt, StreamExt};
use tokio_tungstenite::{connect_async, tungstenite::Message as ClientMessage};

use super::*;
use crate::{exchange::DirectoryExchange, storage::LocalStore};

fn command(root: &Path) -> PathBuf {
    let path = root.join("claude");
    fs::write(&path, format!("#!/bin/sh\nif test \"$1 $2 $3\" = 'mcp add --help'; then echo '--transport http --scope'; else echo '{PROVEN_VERSION}'; fi\n")).unwrap();
    fs::set_permissions(&path, fs::Permissions::from_mode(0o700)).unwrap();
    path
}

#[test]
fn configured_channel_delivers_only_to_its_live_session() {
    let root = env::temp_dir().join(format!("messenger-claude-{}", std::process::id()));
    let _ = fs::remove_dir_all(&root);
    fs::create_dir_all(&root).unwrap();
    let sidecar = root.join("messenger-claude-channel");
    fs::write(&sidecar, "channel").unwrap();
    let config = root.join("claude.json");
    fs::write(
        &config,
        json!({ "mcpServers": { super::super::claude_http::NAME: { "type": "http", "url": super::super::claude_http::URL }, MCP_NAME: {
            "type": "stdio", "command": sidecar, "args": []
        } } })
        .to_string(),
    )
    .unwrap();
    let provider = Provider::with_paths(command(&root), sidecar, config);
    assert!(provider.present().equipped);
    assert!(!provider.present().can_equip);
    assert_eq!(provider.present().state, "prêt");
    let (sender, mut receiver) = mpsc::unbounded_channel();
    let session = "0123456789abcdef-session";
    provider.hub.register(session.into(), sender);
    assert_eq!(
        provider.deliver_verdict(session, "validé").unwrap(),
        Reachability::LiveSession
    );
    assert!(receiver.try_recv().unwrap().contains("validé"));
    assert_eq!(
        provider
            .deliver("0123456789abcdef-absent", "message")
            .unwrap(),
        Reachability::NoSession
    );
    fs::remove_dir_all(root).unwrap();
}

#[test]
fn newer_claude_code_stays_equipped_and_an_older_one_is_refused() {
    let root = env::temp_dir().join(format!("messenger-claude-version-{}", std::process::id()));
    let _ = fs::remove_dir_all(&root);
    fs::create_dir_all(&root).unwrap();
    let config = root.join("claude.json");
    fs::write(
        &config,
        json!({ "mcpServers": { super::super::claude_http::NAME: {
            "type": "http", "url": super::super::claude_http::URL
        } } })
        .to_string(),
    )
    .unwrap();
    for (index, (version, ready)) in [("2.1.285 (Claude Code)", true), ("2.1.200 (Claude Code)", false)]
        .into_iter()
        .enumerate()
    {
        let command = root.join(format!("claude-{index}"));
        fs::write(&command, format!("#!/bin/sh\nif test \"$1 $2 $3\" = 'mcp add --help'; then echo '--transport http --scope'; else echo '{version}'; fi\n")).unwrap();
        fs::set_permissions(&command, fs::Permissions::from_mode(0o700)).unwrap();
        let provider = Provider::with_paths(command, root.join("absent-channel"), config.clone());
        assert_eq!(provider.present().equipped, ready, "{version}");
        assert_eq!(provider.present().available, ready, "{version}");
    }
    fs::remove_dir_all(root).unwrap();
}

#[test]
fn conflicting_configuration_is_never_overwritten() {
    let root = env::temp_dir().join(format!("messenger-claude-safe-{}", std::process::id()));
    let _ = fs::remove_dir_all(&root);
    fs::create_dir_all(&root).unwrap();
    let sidecar = root.join("messenger-claude-channel");
    fs::write(&sidecar, "channel").unwrap();
    let config = root.join("claude.json");
    fs::write(
        &config,
        json!({ "mcpServers": { super::super::claude_http::NAME: {
            "type": "stdio", "command": "legacy", "args": []
        } } })
        .to_string(),
    )
    .unwrap();
    let provider = Provider::with_paths(command(&root), sidecar, config.clone());
    let before = fs::read(&config).unwrap();
    assert!(provider.equip().is_err());
    assert_eq!(fs::read(config).unwrap(), before);
    fs::remove_dir_all(root).unwrap();
}

#[test]
fn newer_claude_with_http_mcp_can_collect_mail_without_a_live_channel() {
    let root = crate::test_support::Temporary::new();
    let command = root.0.join("claude");
    fs::write(&command, "#!/bin/sh\nif test \"$1 $2 $3\" = 'mcp add --help'; then echo '--transport http --scope'; else echo '2.1.286 (Claude Code)'; fi\n").unwrap();
    fs::set_permissions(&command, fs::Permissions::from_mode(0o700)).unwrap();
    let provider = Provider::with_paths(command, root.0.join("missing-channel"), root.0.join("missing-config"));
    assert!(provider.present().available);
    assert!(provider.present().can_equip);
}

#[test]
fn websocket_routes_claude_tools_and_events_end_to_end() {
    let root = env::temp_dir().join(format!("messenger-claude-ws-{}", std::process::id()));
    let _ = fs::remove_dir_all(&root);
    tauri::async_runtime::block_on(async {
        fs::create_dir_all(root.join("exchange")).unwrap();
        let mailbox = Arc::new(MailboxService::new(
            LocalStore::open(root.join("database")).await.unwrap(),
            DirectoryExchange::new(root.join("exchange")),
        ));
        let hub = Arc::new(ChannelHub::default());
        let state = ChannelState {
            mailbox: mailbox.clone(),
            hub: hub.clone(),
            token: "secret".into(),
        };
        let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
        let address = listener.local_addr().unwrap();
        let app = Router::new()
            .route(
                "/claude-channel",
                get(upgrade::<LocalStore, DirectoryExchange>),
            )
            .with_state(state);
        let server = tokio::spawn(async move { axum::serve(listener, app).await.unwrap() });
        let (mut socket, _) = connect_async(format!("ws://{address}/claude-channel"))
            .await
            .unwrap();
        let session = "0123456789abcdef-live";
        socket
            .send(ClientMessage::Text(
                json!({ "type": "register", "token": "secret", "session": session })
                    .to_string()
                    .into(),
            ))
            .await
            .unwrap();
        let accepted = socket.next().await.unwrap().unwrap().into_text().unwrap();
        assert_eq!(
            serde_json::from_str::<Value>(&accepted).unwrap()["type"],
            "accepted"
        );

        mailbox
            .enroll(
                "claude-code",
                session,
                "claude",
                "développeur",
                Some("messenger-app".into()),
            )
            .await
            .unwrap();
        socket
            .send(ClientMessage::Text(
                json!({
                    "type": "rpc", "id": "rpc-1", "request": {
                        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                        "params": { "name": "demander_validation", "arguments": { "request": {
                            "id": "claude-approval", "opened_by": "claude@messenger-app",
                            "gesture": "Publier la version", "scope": "messenger-app/main",
                            "reversible": "Retour à la version précédente",
                            "if_refused": "Conserver la version actuelle",
                            "why_now": "Les tests sont verts",
                            "opened_at": "2026-09-22T12:00:00+02:00"
                        } } }
                    }
                })
                .to_string()
                .into(),
            ))
            .await
            .unwrap();
        let response = socket.next().await.unwrap().unwrap().into_text().unwrap();
        let response: Value = serde_json::from_str(&response).unwrap();
        assert_eq!(response["type"], "rpc_result");
        assert_eq!(
            response["response"]["result"]["structuredContent"]["publication"],
            "publié"
        );
        let route = mailbox
            .delivery_route("claude-approval")
            .await
            .unwrap()
            .unwrap();
        assert_eq!(route.provider, "claude-code");
        assert_eq!(route.session, session);

        assert_eq!(
            hub.deliver(session, "Demande validée").unwrap(),
            Reachability::LiveSession
        );
        let event = socket.next().await.unwrap().unwrap().into_text().unwrap();
        let event: Value = serde_json::from_str(&event).unwrap();
        assert_eq!(event["sender"], "messenger-app");
        assert_eq!(event["content"], "Demande validée");
        server.abort();
    });
    fs::remove_dir_all(root).unwrap();
}
