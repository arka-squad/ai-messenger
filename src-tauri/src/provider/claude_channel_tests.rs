use std::time::Duration;

use futures_util::{SinkExt, StreamExt};
use tokio_tungstenite::{connect_async, tungstenite::Message as ClientMessage};

use super::*;
use crate::{exchange::DirectoryExchange, storage::LocalStore, test_support::Temporary};

type Mailbox = Arc<MailboxService<LocalStore, DirectoryExchange>>;
type Client = tokio_tungstenite::WebSocketStream<tokio_tungstenite::MaybeTlsStream<tokio::net::TcpStream>>;

async fn text(socket: &mut (impl StreamExt<Item = Result<ClientMessage, tokio_tungstenite::tungstenite::Error>> + Unpin)) -> Value {
    let frame = socket.next().await.unwrap().unwrap().into_text().unwrap();
    serde_json::from_str(&frame).unwrap()
}

/// A channel server on a free local port; the caller aborts the returned task.
async fn channel_server(mailbox: &Mailbox, hub: &Arc<ChannelHub>) -> (std::net::SocketAddr, tokio::task::JoinHandle<()>) {
    let state = ChannelState { mailbox: mailbox.clone(), hub: hub.clone(), token: "secret".into() };
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let address = listener.local_addr().unwrap();
    let app = Router::new()
        .route("/claude-channel", get(upgrade::<LocalStore, DirectoryExchange>))
        .with_state(state);
    (address, tokio::spawn(async move { axum::serve(listener, app).await.unwrap() }))
}

/// Registers a channel and waits until the server has handled the registration.
async fn register(address: std::net::SocketAddr, session: &str, cwd: Option<&str>) -> Client {
    let (mut socket, _) = connect_async(format!("ws://{address}/claude-channel")).await.unwrap();
    let mut frame = json!({ "type": "register", "token": "secret", "session": session });
    if let Some(cwd) = cwd {
        frame["cwd"] = json!(cwd);
    }
    socket.send(ClientMessage::Text(frame.to_string().into())).await.unwrap();
    assert_eq!(text(&mut socket).await["type"], "accepted");
    // Frames are handled in order: this answer proves the registration already happened.
    let list = json!({ "type": "rpc", "id": "rpc-1", "request": { "jsonrpc": "2.0", "id": 1, "method": "tools/list" } });
    socket.send(ClientMessage::Text(list.to_string().into())).await.unwrap();
    assert_eq!(text(&mut socket).await["response"]["result"]["tools"], json!([]));
    socket
}

async fn route(mailbox: &Mailbox, account: &str) -> Option<String> {
    mailbox.account_route(account).await.unwrap().map(|(_, session)| session)
}

/// Closing a channel is handled after its socket loop ends: waits until it is no longer live.
async fn closed(mailbox: &Mailbox, session: &str) {
    for _ in 0..150 {
        if !mailbox.live_channel(session) {
            return;
        }
        tokio::time::sleep(Duration::from_millis(20)).await;
    }
    assert!(!mailbox.live_channel(session), "the closed channel is no longer live");
}

#[test]
fn provider_channel_is_a_live_session_but_never_bound_from_its_folder() {
    let root = Temporary::new();
    tauri::async_runtime::block_on(async {
        let mailbox: Mailbox = Arc::new(root.mailbox("poste").await);
        let hub = Arc::new(ChannelHub::default());
        let (address, server) = channel_server(&mailbox, &hub).await;
        let folder = "/srv/projets/messenger-app";
        let account = crate::test_support::account(&mailbox, "revue").await;
        mailbox.remember_folder(ID, folder, &account).await.unwrap();

        // An older sidecar still sends its folder: it is ignored, the session is only made nameable.
        let session = "0123456789abcdef-live";
        let mut socket = register(address, session, Some(folder)).await;
        assert!(mailbox.live_channel(session));
        assert_eq!(route(&mailbox, &account).await, None, "another session of the folder may be another agent");
        let call = json!({ "type": "rpc", "id": "rpc-2", "request": { "jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": { "name": "relever" } } });
        socket.send(ClientMessage::Text(call.to_string().into())).await.unwrap();
        let refused = text(&mut socket).await;
        assert!(refused["response"]["error"]["message"].as_str().unwrap().contains("arkalabs-messenger-app"));

        assert_eq!(hub.deliver(session, "Demande validée").unwrap(), Reachability::LiveSession);
        let event = text(&mut socket).await;
        assert_eq!(event["sender"], "messenger-app");
        assert_eq!(event["content"], "Demande validée");

        socket.close(None).await.unwrap();
        closed(&mailbox, session).await;
        assert_eq!(hub.deliver(session, "Plus personne").unwrap(), Reachability::NoSession);
        server.abort();
    });
}

#[test]
fn provider_channel_keeps_a_declared_route_across_a_reconnection() {
    let root = Temporary::new();
    tauri::async_runtime::block_on(async {
        let mailbox: Mailbox = Arc::new(root.mailbox("poste").await);
        let hub = Arc::new(ChannelHub::default());
        let (address, server) = channel_server(&mailbox, &hub).await;
        let account = crate::test_support::account(&mailbox, "revue").await;
        let session = "0123456789abcdef-declared";
        let socket = register(address, session, None).await;
        // The agent named this session as its delivery_session.
        mailbox.set_route(&account, ID, session).await.unwrap();

        // The sidecar drops, as when the app restarts: the route stays and pushes resume on reconnection.
        drop(socket);
        closed(&mailbox, session).await;
        assert_eq!(route(&mailbox, &account).await.as_deref(), Some(session));
        let mut again = register(address, session, None).await;
        assert!(mailbox.live_channel(session));
        assert_eq!(hub.deliver(session, "De retour").unwrap(), Reachability::LiveSession);
        assert_eq!(text(&mut again).await["content"], "De retour");
        server.abort();
    });
}

#[test]
fn provider_channel_with_a_wrong_token_is_refused_and_binds_nothing() {
    let root = Temporary::new();
    tauri::async_runtime::block_on(async {
        let mailbox: Mailbox = Arc::new(root.mailbox("poste").await);
        let hub = Arc::new(ChannelHub::default());
        let (address, server) = channel_server(&mailbox, &hub).await;
        let account = crate::test_support::account(&mailbox, "revue").await;
        mailbox.remember_folder(ID, "/srv/projet", &account).await.unwrap();

        let (mut intruder, _) = connect_async(format!("ws://{address}/claude-channel")).await.unwrap();
        let wrong = json!({ "type": "register", "token": "guess", "session": "0123456789abcdef-intrus", "cwd": "/srv/projet" });
        intruder.send(ClientMessage::Text(wrong.to_string().into())).await.unwrap();
        assert!(intruder.next().await.is_none_or(|frame| !matches!(frame, Ok(ClientMessage::Text(_)))));
        assert!(!mailbox.live_channel("0123456789abcdef-intrus"));

        let session = "0123456789abcdef-ancien";
        let _plain = register(address, session, None).await;
        assert_eq!(mailbox.setting(&format!("account_route:{account}")).await.unwrap(), None);
        assert_eq!(hub.deliver(session, "Toujours joignable").unwrap(), Reachability::LiveSession);
        server.abort();
    });
}
