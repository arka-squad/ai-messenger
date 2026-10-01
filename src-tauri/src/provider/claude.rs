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
};

use super::equipment;

/// Oldest version proven with Messenger; later versions are accepted.
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
    /// Claude's own folder: `settings.json` for the hooks, `skills/` for the skill.
    home: PathBuf,
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

    /// `true` when this connection still held the session: a reconnection keeps its binding.
    fn unregister(&self, session: &str, connection: u64) -> bool {
        let mut sessions = self.sessions.lock().expect("Claude session lock");
        let current = sessions
            .get(session)
            .is_some_and(|(current, _)| *current == connection);
        if current {
            sessions.remove(session);
        }
        current
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
        let sidecar = equipment::sidecar();
        let config = config_path();
        let home = home_path();
        let status = probe(&command, &sidecar, &config, &home);
        Self {
            command,
            sidecar,
            config,
            home,
            hub: hub(),
            status: Mutex::new(status),
        }
    }

    #[cfg(all(test, unix))]
    fn with_paths(command: PathBuf, sidecar: PathBuf, config: PathBuf, home: PathBuf) -> Self {
        let status = probe(&command, &sidecar, &config, &home);
        Self {
            command,
            sidecar,
            config,
            home,
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
        let settings = self.home.join("settings.json");
        let hooks = equipment::hook(&self.sidecar, ID, false);
        // Every refusal comes before the first write.
        super::claude_http::configured(&self.config)?;
        equipment::ready(&settings, &self.home, hooks.as_ref())?;
        super::claude_http::equip(&self.command, &self.config)?;
        let retired = equipment::install(&settings, &self.home, hooks.as_ref())?;
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
        let ready = ready_status(current.version, hooks.is_some(), &retired);
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
    let Registration { session, .. } = registration;
    let (sender, mut outbound) = mpsc::unbounded_channel();
    let rpc_sender = sender.clone();
    let connection = state.hub.register(session.clone(), sender);
    let accepted = Message::Text(json!({ "type": "accepted" }).to_string().into());
    if socket.send(accepted).await.is_err() {
        state.hub.unregister(&session, connection);
        return;
    }
    // The session becomes nameable as a delivery route; nothing is bound from its folder.
    state.mailbox.register_channel(&session);
    loop {
        tokio::select! {
            Some(frame) = outbound.recv() => {
                if socket.send(Message::Text(frame.into())).await.is_err() { break; }
            }
            incoming = socket.recv() => {
                let Some(Ok(Message::Text(raw))) = incoming else { break; };
                let Ok(rpc) = serde_json::from_str::<RpcRequest>(&raw) else { continue; };
                if rpc.kind != "rpc" { continue; }
                let frame = json!({ "type": "rpc_result", "id": rpc.id, "response": channel_rpc(&rpc.request) });
                if rpc_sender.send(frame.to_string()).is_err() { break; }
            }
        }
    }
    if state.hub.unregister(&session, connection) {
        state.mailbox.channel_closed(&session);
    }
}

/// The channel only pushes: an older channel binary that still asks for tools gets none.
fn channel_rpc(request: &Value) -> Value {
    let id = request.get("id").cloned().unwrap_or_else(|| json!(null));
    if request.get("method").and_then(Value::as_str) == Some("tools/list") {
        return json!({ "jsonrpc": "2.0", "id": id, "result": { "tools": [] } });
    }
    json!({ "jsonrpc": "2.0", "id": id, "error": { "code": -32601,
        "message": "Ce canal ne fait que pousser les événements Messenger. Utilise les outils arkalabs-messenger-app." } })
}

fn hub() -> Arc<ChannelHub> {
    static HUB: OnceLock<Arc<ChannelHub>> = OnceLock::new();
    HUB.get_or_init(|| Arc::new(ChannelHub::default())).clone()
}

fn probe(command: &Path, sidecar: &Path, config: &Path, home: &Path) -> ProviderStatus {
    let Ok(version) = run(command, &["--version"]) else {
        return unavailable("Claude Code est introuvable sur cet ordinateur", None);
    };
    let version_text = stdout(&version).trim().to_owned();
    if !version.status.success() || !super::at_least(&version_text, PROVEN_VERSION) {
        return unavailable(
            &format!("Version minimale : {PROVEN_VERSION}; installée : {version_text}"),
            Some(version_text),
        );
    }
    let http = run(command, &["mcp", "add", "--help"])
        .is_ok_and(|output| output.status.success()
            && stdout(&output).contains("--transport")
            && stdout(&output).contains("--scope")
            && stdout(&output).contains("http"));
    if !http {
        return unavailable("Le transport MCP HTTP de Claude Code n’est pas disponible", Some(version_text));
    }
    let hooks = equipment::hook(sidecar, ID, false);
    let settings = home.join("settings.json");
    let equipped = super::claude_http::configured(config)
        .and_then(|tools| Ok(equipment::ready(&settings, home, hooks.as_ref())? && tools));
    match equipped {
        Ok(true) => ready_status(Some(version_text), hooks.is_some(), &[]),
        Ok(false) => ProviderStatus {
            id: "claude-code".into(),
            name: "Claude Code".into(),
            version: Some(version_text),
            state: "à équiper".into(),
            detail: format!(
                "Clique pour poser les outils arkalabs-messenger-app et la skill partagée. {}{}",
                if sidecar.is_file() {
                    "La relève s’ajoute à l’ouverture et à chaque message de l’humain ; le canal empaqueté pousse les événements dans les sessions lancées avec l’option des canaux."
                } else {
                    "Le composant empaqueté est absent : ni relève automatique ni canal, les outils restent disponibles."
                },
                if equipment::legacy_present(&settings, home) {
                    " L’ancienne consigne Messenger (skill arkalabs-messenger, hooks messenger.py) sera retirée."
                } else {
                    ""
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

/// `retired`: what this equipment just moved or removed of the first mailbox's guidance.
fn ready_status(version: Option<String>, hooks: bool, retired: &[String]) -> ProviderStatus {
    let mut detail = format!(
        "Claude Code est équipé : outils arkalabs-messenger-app, {}skill partagée. Chaque agent retrouve son compte par son dossier de travail. Une session ouverte avant l’équipement ne les charge pas : ouvres-en une nouvelle.",
        if hooks { "relève à l’ouverture et à chaque message de l’humain, " } else { "" }
    );
    if hooks {
        detail.push_str(&format!(
            " Les événements en direct n’atteignent que les sessions lancées avec l’option des canaux (claude --dangerously-load-development-channels server:{MCP_NAME}) ; les autres sont averties par la relève."
        ));
    }
    for note in retired {
        detail.push(' ');
        detail.push_str(note);
    }
    ProviderStatus {
        id: "claude-code".into(),
        name: "Claude Code".into(),
        version,
        state: "prêt".into(),
        detail,
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

fn config_path() -> PathBuf {
    if let Some(directory) = env::var_os("CLAUDE_CONFIG_DIR") {
        return PathBuf::from(directory).join(".claude.json");
    }
    home_directory().unwrap_or_default().join(".claude.json")
}

fn home_path() -> PathBuf {
    env::var_os("CLAUDE_CONFIG_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|| home_directory().unwrap_or_default().join(".claude"))
}

fn command_path() -> PathBuf {
    if let Some(configured) = env::var_os("MESSENGER_CLAUDE_COMMAND") {
        return PathBuf::from(configured);
    }
    // Shared lookup: it also finds the claude.cmd shim that npm installs on Windows.
    super::executable("claude")
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

#[cfg(test)]
#[path = "claude_channel_tests.rs"]
mod channel_tests;
