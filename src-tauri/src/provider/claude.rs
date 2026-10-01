pub const ID: &str = "claude-code";
use std::{
    collections::HashMap,
    env, fs,
    path::{Path, PathBuf},
    process::{Command, Output},
    sync::{Arc, Mutex, OnceLock},
};

use axum::{
    extract::{
        ws::{Message, WebSocket, WebSocketUpgrade},
        State,
    },
    response::Response,
    routing::get,
    Router,
};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use tokio::sync::mpsc;

use crate::{
    domain::{
        models::ProviderStatus,
        ports::{ExchangePort, PortError, ProviderPort, RepositoryPort},
        Reachability,
    },
    mailbox::MailboxService,
    mcp::{self, RouteContext},
};

pub const PROVEN_VERSION: &str = "2.1.274 (Claude Code)";
const MCP_NAME: &str = "arkalabs-messenger-channel";

type SessionSender = mpsc::UnboundedSender<String>;

#[derive(Default)]
struct ChannelHub {
    sessions: Mutex<HashMap<String, (u64, SessionSender)>>,
    next_connection: Mutex<u64>,
}

pub struct Provider {
    command: PathBuf,
    sidecar: PathBuf,
    config: PathBuf,
    hub: Arc<ChannelHub>,
    status: Mutex<ProviderStatus>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
struct ConnectionDescriptor {
    port: u16,
    token: String,
}

#[derive(Deserialize)]
struct Registration {
    #[serde(rename = "type")]
    kind: String,
    token: String,
    session: String,
}

#[derive(Deserialize)]
struct RpcRequest {
    #[serde(rename = "type")]
    kind: String,
    id: String,
    request: Value,
}

struct ChannelState<R, E> {
    mailbox: Arc<MailboxService<R, E>>,
    hub: Arc<ChannelHub>,
    token: String,
}

impl<R, E> Clone for ChannelState<R, E> {
    fn clone(&self) -> Self {
        Self {
            mailbox: self.mailbox.clone(),
            hub: self.hub.clone(),
            token: self.token.clone(),
        }
    }
}

impl ChannelHub {
    fn register(&self, session: String, sender: SessionSender) -> u64 {
        let mut next = self.next_connection.lock().expect("Claude connection lock");
        *next += 1;
        let connection = *next;
        self.sessions
            .lock()
            .expect("Claude session lock")
            .insert(session, (connection, sender));
        connection
    }

    fn unregister(&self, session: &str, connection: u64) {
        let mut sessions = self.sessions.lock().expect("Claude session lock");
        if sessions
            .get(session)
            .is_some_and(|(current, _)| *current == connection)
        {
            sessions.remove(session);
        }
    }

    fn deliver(&self, session: &str, content: &str) -> Result<Reachability, PortError> {
        if !valid_session(session) {
            return Err(PortError("identifiant de session Claude invalide".into()));
        }
        let sender = self
            .sessions
            .lock()
            .expect("Claude session lock")
            .get(session)
            .map(|(_, sender)| sender.clone());
        let Some(sender) = sender else {
            return Ok(Reachability::NoSession);
        };
        let frame = json!({
            "type": "event",
            "sender": "messenger-app",
            "content": content
        })
        .to_string();
        if sender.send(frame).is_ok() {
            Ok(Reachability::LiveSession)
        } else {
            Ok(Reachability::NoSession)
        }
    }
}

impl Provider {
    pub fn new() -> Self {
        let command = command_path();
        let sidecar = sidecar_path();
        let config = config_path();
        let status = probe(&command, &sidecar, &config);
        Self {
            command,
            sidecar,
            config,
            hub: hub(),
            status: Mutex::new(status),
        }
    }

    #[cfg(test)]
    fn with_paths(command: PathBuf, sidecar: PathBuf, config: PathBuf) -> Self {
        let status = probe(&command, &sidecar, &config);
        Self {
            command,
            sidecar,
            config,
            hub: Arc::new(ChannelHub::default()),
            status: Mutex::new(status),
        }
    }

    fn run(&self, arguments: &[&str]) -> Result<Output, PortError> {
        Command::new(&self.command)
            .args(arguments)
            .output()
            .map_err(|error| PortError(format!("Claude Code ne répond pas : {error}")))
    }
}

impl ProviderPort for Provider {
    fn id(&self) -> &'static str {
        ID
    }

    fn present(&self) -> ProviderStatus {
        self.status.lock().expect("Claude status lock").clone()
    }

    fn equip(&self) -> Result<ProviderStatus, PortError> {
        let current = self.present();
        if !current.available {
            return Err(PortError(current.detail));
        }
        super::claude_http::equip(&self.command, &self.config)?;
        // The ordinary MCP connection works even when the optional live channel is unavailable.
        if self.sidecar.is_file()
            && matches!(
                configuration(&self.config, &self.sidecar),
                Configuration::Missing
            )
        {
            let sidecar = self.sidecar.to_string_lossy();
            let _ = self.run(&["mcp", "add", "--scope", "user", MCP_NAME, "--", &sidecar]);
        }
        let ready = ready_status(current.version);
        *self.status.lock().expect("Claude status lock") = ready.clone();
        Ok(ready)
    }

    fn deliver(&self, session: &str, message: &str) -> Result<Reachability, PortError> {
        self.hub.deliver(session, message)
    }

    fn deliver_verdict(&self, session: &str, verdict: &str) -> Result<Reachability, PortError> {
        self.hub.deliver(session, verdict)
    }

    fn receive(&self) -> bool {
        self.present().equipped
    }
}

pub async fn serve<R, E>(mailbox: Arc<MailboxService<R, E>>)
where
    R: RepositoryPort + 'static,
    E: ExchangePort + 'static,
{
    let root = runtime_directory();
    if let Err(error) = secure_directory(&root) {
        eprintln!("Messenger Claude channel unavailable: {error}");
        return;
    }
    let token = token();
    let listener = match tokio::net::TcpListener::bind("127.0.0.1:0").await {
        Ok(listener) => listener,
        Err(error) => {
            eprintln!("Messenger Claude channel unavailable: {error}");
            return;
        }
    };
    let port = match listener.local_addr() {
        Ok(address) => address.port(),
        Err(error) => {
            eprintln!("Messenger Claude channel unavailable: {error}");
            return;
        }
    };
    if let Err(error) = write_descriptor(
        &root,
        &ConnectionDescriptor {
            port,
            token: token.clone(),
        },
    ) {
        eprintln!("Messenger Claude channel unavailable: {error}");
        return;
    }
    let state = ChannelState {
        mailbox,
        hub: hub(),
        token,
    };
    let app = Router::new()
        .route("/claude-channel", get(upgrade::<R, E>))
        .with_state(state);
    if let Err(error) = axum::serve(listener, app).await {
        eprintln!("Messenger Claude channel stopped: {error}");
    }
}

async fn upgrade<R, E>(
    websocket: WebSocketUpgrade,
    State(state): State<ChannelState<R, E>>,
) -> Response
where
    R: RepositoryPort + 'static,
    E: ExchangePort + 'static,
{
    websocket.on_upgrade(move |socket| connection(socket, state))
}

async fn connection<R, E>(mut socket: WebSocket, state: ChannelState<R, E>)
where
    R: RepositoryPort + 'static,
    E: ExchangePort + 'static,
{
    let Some(Ok(Message::Text(raw))) = socket.recv().await else {
        return;
    };
    let Ok(registration) = serde_json::from_str::<Registration>(&raw) else {
        return;
    };
    if registration.kind != "register"
        || !authorized(&registration.token, &state.token)
        || !valid_session(&registration.session)
    {
        return;
    }
    let session = registration.session;
    let (sender, mut outbound) = mpsc::unbounded_channel();
    let rpc_sender = sender.clone();
    let connection = state.hub.register(session.clone(), sender);
    let accepted = Message::Text(json!({ "type": "accepted" }).to_string().into());
    if socket.send(accepted).await.is_err() {
        state.hub.unregister(&session, connection);
        return;
    }
    loop {
        tokio::select! {
            Some(frame) = outbound.recv() => {
                if socket.send(Message::Text(frame.into())).await.is_err() { break; }
            }
            incoming = socket.recv() => {
                let Some(Ok(Message::Text(raw))) = incoming else { break; };
                let Ok(rpc) = serde_json::from_str::<RpcRequest>(&raw) else { continue; };
                if rpc.kind != "rpc" { continue; }
                let mailbox = state.mailbox.clone();
                let session = session.clone();
                let sender = rpc_sender.clone();
                tokio::spawn(async move {
                    let response = channel_rpc(&mailbox, &session, rpc.request).await;
                    let frame = json!({ "type": "rpc_result", "id": rpc.id, "response": response });
                    let _ = sender.send(frame.to_string());
                });
            }
        }
    }
    state.hub.unregister(&session, connection);
}

async fn channel_rpc<R: RepositoryPort, E: ExchangePort>(
    mailbox: &MailboxService<R, E>,
    session: &str,
    request: Value,
) -> Value {
    let id = request.get("id").cloned().unwrap_or_else(|| json!(null));
    if request.get("method").and_then(Value::as_str) == Some("tools/list") {
        return json!({ "jsonrpc": "2.0", "id": id, "result": { "tools": mcp::channel_tools() } });
    }
    mcp::dispatch(
        mailbox,
        &request,
        id,
        Some(RouteContext {
            provider: "claude-code",
            session,
            live_session: true,
        }),
    )
    .await
}

fn hub() -> Arc<ChannelHub> {
    static HUB: OnceLock<Arc<ChannelHub>> = OnceLock::new();
    HUB.get_or_init(|| Arc::new(ChannelHub::default())).clone()
}

fn probe(command: &Path, sidecar: &Path, config: &Path) -> ProviderStatus {
    let Ok(version) = run(command, &["--version"]) else {
        return unavailable("Claude Code est introuvable sur cet ordinateur", None);
    };
    let version_text = stdout(&version).trim().to_owned();
    if !version.status.success() || version_text != PROVEN_VERSION {
        return unavailable(
            &format!("Version attendue : {PROVEN_VERSION}; installée : {version_text}"),
            Some(version_text),
        );
    }
    match super::claude_http::configured(config) {
        Ok(true) => ready_status(Some(version_text)),
        Ok(false) => ProviderStatus {
            id: "claude-code".into(),
            name: "Claude Code".into(),
            version: Some(version_text),
            state: "à équiper".into(),
            detail: format!(
                "La relève MCP fonctionne sans canal. {}",
                if sidecar.is_file() {
                    "Le canal empaqueté ajoute une remise dans les sessions qui l’activent."
                } else {
                    "Le canal empaqueté est absent ; la relève reste disponible."
                }
            ),
            available: true,
            equipped: false,
            can_equip: true,
        },
        Err(error) => blocked_status(&error.0, Some(version_text)),
    }
}

#[derive(Clone, Copy)]
enum Configuration {
    Missing,
    Exact,
    Conflict,
    Unreadable,
}

fn configuration(path: &Path, sidecar: &Path) -> Configuration {
    let bytes = match fs::read(path) {
        Ok(bytes) => bytes,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => {
            return Configuration::Missing
        }
        Err(_) => return Configuration::Unreadable,
    };
    let Ok(value) = serde_json::from_slice::<Value>(&bytes) else {
        return Configuration::Unreadable;
    };
    let Some(entry) = value.pointer(&format!("/mcpServers/{MCP_NAME}")) else {
        return Configuration::Missing;
    };
    let command = entry.get("command").and_then(Value::as_str);
    let args = entry.get("args").and_then(Value::as_array);
    if command == Some(sidecar.to_string_lossy().as_ref())
        && args.is_some_and(|args| args.is_empty())
        && entry.get("type").and_then(Value::as_str) == Some("stdio")
    {
        Configuration::Exact
    } else {
        Configuration::Conflict
    }
}

fn ready_status(version: Option<String>) -> ProviderStatus {
    ProviderStatus {
        id: "claude-code".into(),
        name: "Claude Code".into(),
        version,
        state: "prêt".into(),
        detail: "Claude Code est équipé. Colle la même invite dans chaque agent : chacun crée son propre compte. Le canal temps réel reste optionnel et limité aux sessions qui l’ont activé."
            .into(),
        available: true,
        equipped: true,
        can_equip: false,
    }
}

fn blocked_status(detail: &str, version: Option<String>) -> ProviderStatus {
    ProviderStatus {
        id: "claude-code".into(),
        name: "Claude Code".into(),
        version,
        state: "à vérifier".into(),
        detail: detail.into(),
        available: true,
        equipped: false,
        can_equip: false,
    }
}

fn unavailable(detail: &str, version: Option<String>) -> ProviderStatus {
    ProviderStatus {
        id: "claude-code".into(),
        name: "Claude Code".into(),
        version,
        state: "indisponible".into(),
        detail: detail.into(),
        available: false,
        equipped: false,
        can_equip: false,
    }
}

fn sidecar_path() -> PathBuf {
    let name = format!("messenger-claude-channel{}", env::consts::EXE_SUFFIX);
    if let Ok(executable) = env::current_exe() {
        let bundled = executable.parent().unwrap_or(Path::new(".")).join(&name);
        if bundled.is_file() {
            return bundled;
        }
    }
    let directory = Path::new(env!("CARGO_MANIFEST_DIR")).join("binaries");
    fs::read_dir(&directory)
        .ok()
        .into_iter()
        .flatten()
        .filter_map(Result::ok)
        .map(|entry| entry.path())
        .find(|path| {
            path.file_name().is_some_and(|file| {
                file.to_string_lossy()
                    .starts_with("messenger-claude-channel-")
            })
        })
        .unwrap_or_else(|| directory.join(name))
}

fn config_path() -> PathBuf {
    if let Some(directory) = env::var_os("CLAUDE_CONFIG_DIR") {
        return PathBuf::from(directory).join(".claude.json");
    }
    home_directory().unwrap_or_default().join(".claude.json")
}

fn command_path() -> PathBuf {
    if let Some(configured) = env::var_os("MESSENGER_CLAUDE_COMMAND") {
        return PathBuf::from(configured);
    }
    let executable = format!("claude{}", env::consts::EXE_SUFFIX);
    if let Some(path) = env::var_os("PATH") {
        if let Some(found) = env::split_paths(&path)
            .map(|directory| directory.join(&executable))
            .find(|candidate| candidate.is_file())
        {
            return found;
        }
    }
    if let Some(home) = home_directory() {
        for relative in [".local/bin/claude", ".claude/local/claude"] {
            let candidate = home.join(relative);
            if candidate.is_file() {
                return candidate;
            }
        }
    }
    for candidate in ["/opt/homebrew/bin/claude", "/usr/local/bin/claude"] {
        let path = PathBuf::from(candidate);
        if path.is_file() {
            return path;
        }
    }
    PathBuf::from(executable)
}

fn home_directory() -> Option<PathBuf> {
    env::var_os("HOME")
        .or_else(|| env::var_os("USERPROFILE"))
        .map(PathBuf::from)
}

fn runtime_directory() -> PathBuf {
    env::temp_dir().join("arkalabs-messenger-channel")
}

fn secure_directory(path: &Path) -> std::io::Result<()> {
    fs::create_dir_all(path)?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        fs::set_permissions(path, fs::Permissions::from_mode(0o700))?;
    }
    #[cfg(windows)]
    {
        let user = env::var("USERNAME")
            .map_err(|_| std::io::Error::other("Utilisateur Windows inconnu."))?;
        let grant = format!("{user}:(OI)(CI)F");
        let status = Command::new("icacls.exe")
            .arg(path)
            .args(["/inheritance:r", "/grant:r", &grant])
            .output()?;
        if !status.status.success() {
            return Err(std::io::Error::other(
                "Le raccordement privé n’a pas pu être protégé.",
            ));
        }
    }
    Ok(())
}

fn write_descriptor(root: &Path, descriptor: &ConnectionDescriptor) -> std::io::Result<()> {
    let path = root.join("connection.json");
    fs::write(&path, serde_json::to_vec(descriptor)?)?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        fs::set_permissions(path, fs::Permissions::from_mode(0o600))?;
    }
    Ok(())
}

fn token() -> String {
    format!(
        "{}{}",
        uuid::Uuid::new_v4().simple(),
        uuid::Uuid::new_v4().simple()
    )
}

fn authorized(candidate: &str, expected: &str) -> bool {
    Sha256::digest(candidate.as_bytes()) == Sha256::digest(expected.as_bytes())
}

fn valid_session(session: &str) -> bool {
    (16..=96).contains(&session.len())
        && session
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || byte == b'-')
}

fn run(command: &Path, arguments: &[&str]) -> Result<Output, std::io::Error> {
    Command::new(command).args(arguments).output()
}

fn stdout(output: &Output) -> String {
    String::from_utf8_lossy(&output.stdout).into_owned()
}

#[cfg(all(test, unix))]
#[path = "claude_tests.rs"]
mod tests;
