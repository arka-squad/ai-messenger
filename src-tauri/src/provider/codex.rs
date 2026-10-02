pub const ID: &str = "codex";
use std::{
    io::Read,
    path::{Path, PathBuf},
    process::{Output, Stdio},
    sync::{Mutex, OnceLock},
    thread,
    time::{Duration, Instant},
};

use serde_json::Value;

use crate::domain::{
    models::ProviderStatus,
    ports::{PortError, ProviderPort},
    Reachability,
};

use super::equipment;

/// Oldest version proven with Messenger; later versions still need the MCP probes.
pub const PROVEN_VERSION: &str = "codex-cli 0.152.0";
const MCP_NAME: &str = "arkalabs-messenger-app";
const MCP_URL: &str = "http://127.0.0.1:47652/mcp";
/// Every Codex call is bounded, so a Codex that hangs never holds Messenger back.
const CALL_LIMIT: Duration = Duration::from_secs(30);
/// A thread busy with a turn keeps `codex queue` waiting: past this the mail stays in the box.
const QUEUE_LIMIT: Duration = Duration::from_secs(10);

pub struct Provider {
    command: PathBuf,
    /// `CODEX_HOME`: `hooks.json` for the hooks, `skills/` for the skill.
    home: PathBuf,
    sidecar: PathBuf,
    status: Mutex<ProviderStatus>,
    /// Whether this Codex can queue into a thread: probed once, not at every delivery.
    queue: OnceLock<bool>,
}

impl Provider {
    pub fn new() -> Self {
        let command = super::executable("codex");
        let command = if command.is_absolute() {
            command
        } else {
            bundled_command().unwrap_or(command)
        };
        Self::with_paths(command, home_path(), equipment::sidecar())
    }

    fn with_paths(command: impl Into<PathBuf>, home: PathBuf, sidecar: PathBuf) -> Self {
        let command = command.into();
        let status = probe(&command, &home, &sidecar);
        Self {
            command,
            home,
            sidecar,
            status: Mutex::new(status),
            queue: OnceLock::new(),
        }
    }

    fn hooks(&self) -> (PathBuf, Option<equipment::Hook>) {
        (self.home.join("hooks.json"), hook(&self.sidecar))
    }

    fn run(&self, arguments: &[&str]) -> Result<Output, PortError> {
        run(&self.command, arguments)
            .map_err(|_| {
                PortError("Codex ne répond pas sur ce poste. Rouvre-le puis réessaie.".into())
            })
    }

    fn queue(&self, session: &str, text: &str) -> Result<Reachability, PortError> {
        self.queue_within(session, text, QUEUE_LIMIT)
    }

    fn queue_within(
        &self,
        session: &str,
        text: &str,
        limit: Duration,
    ) -> Result<Reachability, PortError> {
        if session.trim().is_empty() || !self.can_queue() {
            return Ok(Reachability::NoSession);
        }
        let status = self.present();
        if !status.available {
            return Err(PortError(status.detail));
        }
        let arguments = ["queue", "--thread", session, "--message", text];
        let output = run_within(&self.command, &arguments, limit).map_err(|error| {
            PortError(if error.kind() == std::io::ErrorKind::TimedOut {
                "Codex n’a pas pris le courrier à temps : son fil est sans doute occupé. Le courrier reste dans la boîte.".into()
            } else {
                "Codex ne répond pas sur ce poste. Rouvre-le puis réessaie.".into()
            })
        })?;
        if output.status.success() {
            Ok(Reachability::NextStart)
        } else {
            Err(command_error("Codex n’a pas accepté le message", &output))
        }
    }

    fn can_queue(&self) -> bool {
        *self.queue.get_or_init(|| queue_supported(&self.command))
    }
}

impl ProviderPort for Provider {
    fn id(&self) -> &'static str {
        ID
    }

    fn present(&self) -> ProviderStatus {
        self.status.lock().expect("provider status lock").clone()
    }

    fn equip(&self) -> Result<ProviderStatus, PortError> {
        let current = self.present();
        if !current.available {
            return Err(PortError(current.detail));
        }
        if current.equipped {
            return Ok(current);
        }
        let (hooks, command) = self.hooks();
        // A hook of another installation or an unreadable file stops everything before a write.
        equipment::ready(&hooks, &self.home, command.as_ref())?;
        let output = self.run(&["mcp", "get", MCP_NAME, "--json"])?;
        if output.status.success() {
            let configuration: Value = serde_json::from_slice(&output.stdout)
                .map_err(|_| PortError("la configuration Codex existante est illisible".into()))?;
            let url = configuration
                .pointer("/transport/url")
                .and_then(Value::as_str);
            if url != Some(MCP_URL) {
                return Err(PortError(format!(
                    "{MCP_NAME} existe déjà avec une autre configuration ; rien n’a été écrasé"
                )));
            }
        } else if stderr(&output).contains("No MCP server named") {
            let added = self.run(&["mcp", "add", MCP_NAME, "--url", MCP_URL])?;
            if !added.status.success() {
                return Err(command_error("Codex n’a pas pu être équipé", &added));
            }
        } else {
            return Err(command_error(
                "la configuration Codex n’a pas pu être lue",
                &output,
            ));
        }
        let verified = self.run(&["mcp", "get", MCP_NAME, "--json"])?;
        if !verified.status.success()
            || serde_json::from_slice::<Value>(&verified.stdout)
                .ok()
                .and_then(|v| {
                    v.pointer("/transport/url")
                        .and_then(Value::as_str)
                        .map(str::to_owned)
                })
                .as_deref()
                != Some(MCP_URL)
        {
            return Err(PortError(
                "Le raccordement Codex n’a pas pu être confirmé. Réessaie depuis les réglages."
                    .into(),
            ));
        }
        let retired = equipment::install(&hooks, &self.home, command.as_ref())?;
        let ready = ready_status(
            current.version,
            queue_supported(&self.command),
            command.is_some(),
            &retired,
        );
        *self.status.lock().expect("provider status lock") = ready.clone();
        Ok(ready)
    }

    fn deliver(&self, session: &str, message: &str) -> Result<Reachability, PortError> {
        self.queue(session, message)
    }

    fn deliver_verdict(&self, session: &str, verdict: &str) -> Result<Reachability, PortError> {
        self.queue(session, verdict)
    }

    fn receive(&self) -> bool {
        self.present().equipped
    }
}

fn probe(command: &Path, home: &Path, sidecar: &Path) -> ProviderStatus {
    let version = run(command, &["--version"]);
    let Ok(version) = version else {
        return unavailable("Codex est introuvable sur cet ordinateur", None);
    };
    let version_text = stdout(&version).trim().to_owned();
    if !version.status.success() {
        return unavailable("Codex ne répond pas", None);
    }
    if !super::at_least(&version_text, PROVEN_VERSION) {
        return unavailable(
            &format!("Version minimale : {PROVEN_VERSION}; installée : {version_text}"),
            Some(version_text),
        );
    }
    if !responds(&run(command, &["mcp", "add", "--help"]), "--url")
        || !responds(&run(command, &["mcp", "get", "--help"]), "--json") {
        return unavailable(
            "Le transport MCP HTTP de Codex n’est pas disponible",
            Some(version_text),
        );
    }
    let tools = run(command, &["mcp", "get", MCP_NAME, "--json"])
        .ok()
        .filter(|output| output.status.success())
        .and_then(|output| serde_json::from_slice::<Value>(&output.stdout).ok())
        .and_then(|value| {
            value
                .pointer("/transport/url")
                .and_then(Value::as_str)
                .map(str::to_owned)
        })
        .as_deref()
        == Some(MCP_URL);
    let hooks = hook(sidecar);
    let file = home.join("hooks.json");
    match equipment::ready(&file, home, hooks.as_ref()) {
        Ok(true) if tools => ready_status(
            Some(version_text),
            queue_supported(command),
            hooks.is_some(),
            &[],
        ),
        Ok(_) => ProviderStatus {
            id: "codex".into(),
            name: "Codex".into(),
            version: Some(version_text),
            state: "à équiper".into(),
            detail: format!(
                "Codex est compatible ; clique pour lui donner les outils Messenger{}{}",
                if hooks.is_some() {
                    ", la relève automatique et la skill partagée. Codex demandera ensuite d’approuver ses nouveaux hooks : Paramètres > Code > Hooks."
                } else {
                    " et la skill partagée."
                },
                if equipment::legacy_present(&file, home) {
                    " L’ancienne consigne Messenger (skill arkalabs-messenger, hooks messenger.py) sera retirée."
                } else {
                    ""
                }
            ),
            available: true,
            equipped: false,
            can_equip: true,
        },
        Err(error) => ProviderStatus {
            id: "codex".into(),
            name: "Codex".into(),
            version: Some(version_text),
            state: "à vérifier".into(),
            detail: error.0,
            available: true,
            equipped: false,
            can_equip: false,
        },
    }
}

/// Codex runs `commandWindows` with PowerShell on Windows: that form is added there.
fn hook(sidecar: &Path) -> Option<equipment::Hook> {
    equipment::hook(sidecar, ID, cfg!(windows))
}

fn home_path() -> PathBuf {
    std::env::var_os("CODEX_HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|| {
            std::env::var_os("HOME")
                .or_else(|| std::env::var_os("USERPROFILE"))
                .map(PathBuf::from)
                .unwrap_or_default()
                .join(".codex")
        })
}

/// The Codex desktop app ships its CLI inside the app, outside PATH. On Windows the Store
/// package folder changes with every update, so it is asked from the system each time.
#[cfg(windows)]
fn bundled_command() -> Option<PathBuf> {
    use std::os::windows::process::CommandExt;
    const CREATE_NO_WINDOW: u32 = 0x0800_0000;
    let output = std::process::Command::new("powershell.exe")
        .args([
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "(Get-AppxPackage -Name OpenAI.Codex).InstallLocation",
        ])
        .creation_flags(CREATE_NO_WINDOW)
        .output()
        .ok()?;
    String::from_utf8_lossy(&output.stdout)
        .lines()
        .map(|root| Path::new(root.trim()).join("app/resources/codex.exe"))
        .find(|command| command.is_file())
}

#[cfg(target_os = "macos")]
fn bundled_command() -> Option<PathBuf> {
    let home = std::env::var_os("HOME").map(PathBuf::from).unwrap_or_default();
    [Path::new("/Applications"), &home.join("Applications")]
        .into_iter()
        .map(|applications| applications.join("Codex.app/Contents/Resources/codex"))
        .find(|command| command.is_file())
}

#[cfg(not(any(windows, target_os = "macos")))]
fn bundled_command() -> Option<PathBuf> {
    None
}

fn run(command: &Path, arguments: &[&str]) -> Result<Output, std::io::Error> {
    run_within(command, arguments, CALL_LIMIT)
}

/// Runs Codex and stops it past `limit`. The pipes are drained beside the wait, so a talkative
/// Codex cannot fill them and stall.
fn run_within(command: &Path, arguments: &[&str], limit: Duration) -> Result<Output, std::io::Error> {
    let mut child = super::command(command)
        .args(arguments)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()?;
    let drain = |pipe: Option<Box<dyn Read + Send>>| {
        thread::spawn(move || {
            let mut bytes = Vec::new();
            if let Some(mut pipe) = pipe {
                let _ = pipe.read_to_end(&mut bytes);
            }
            bytes
        })
    };
    let stdout = drain(child.stdout.take().map(|p| Box::new(p) as Box<dyn Read + Send>));
    let stderr = drain(child.stderr.take().map(|p| Box::new(p) as Box<dyn Read + Send>));
    let deadline = Instant::now() + limit;
    let status = loop {
        if let Some(status) = child.try_wait()? {
            break status;
        }
        if Instant::now() >= deadline {
            let _ = child.kill();
            let _ = child.wait();
            return Err(std::io::Error::new(
                std::io::ErrorKind::TimedOut,
                "Codex n’a pas répondu à temps",
            ));
        }
        thread::sleep(Duration::from_millis(20));
    };
    Ok(Output {
        status,
        stdout: stdout.join().unwrap_or_default(),
        stderr: stderr.join().unwrap_or_default(),
    })
}

fn queue_supported(command: &Path) -> bool {
    responds(&run(command, &["agents", "--help"]), "shared local app-server daemon")
        && responds(&run(command, &["queue", "--help"]), "--thread")
}

fn responds(output: &Result<Output, std::io::Error>, proof: &str) -> bool {
    output
        .as_ref()
        .is_ok_and(|output| output.status.success() && stdout(output).contains(proof))
}

/// `retired`: what this equipment just moved or removed of the first mailbox's guidance.
fn ready_status(version: Option<String>, queue: bool, hooks: bool, retired: &[String]) -> ProviderStatus {
    let mut detail = format!("{}{} Une session ouverte avant l’équipement ne les charge pas : ouvres-en une nouvelle.",
        if queue {"Codex peut relever Messenger et recevoir un verdict dans une session existante."}
        else {"Codex relève Messenger par MCP ; la remise dans une session existante est indisponible."},
        if hooks {" La relève automatique est posée : Codex demande d’approuver les nouveaux hooks dans Paramètres > Code > Hooks."}
        else {""});
    for note in retired {
        detail.push(' ');
        detail.push_str(note);
    }
    ProviderStatus {
        id: "codex".into(),
        name: "Codex".into(),
        version,
        state: "prêt".into(),
        detail,
        available: true,
        equipped: true,
        can_equip: false,
    }
}

fn unavailable(detail: &str, version: Option<String>) -> ProviderStatus {
    ProviderStatus {
        id: "codex".into(),
        name: "Codex".into(),
        version,
        state: "indisponible".into(),
        detail: detail.into(),
        available: false,
        equipped: false,
        can_equip: false,
    }
}

fn stdout(output: &Output) -> String {
    String::from_utf8_lossy(&output.stdout).into_owned()
}

fn stderr(output: &Output) -> String {
    String::from_utf8_lossy(&output.stderr).into_owned()
}

fn command_error(prefix: &str, _: &Output) -> PortError {
    PortError(format!(
        "{prefix}. Vérifie son raccordement dans les réglages puis réessaie."
    ))
}

#[cfg(all(test, unix))]
mod tests {
    use std::{fs, os::unix::fs::PermissionsExt};

    use super::{equipment, Provider, ProviderPort, PROVEN_VERSION};
    use crate::domain::Reachability;

    #[test]
    fn a_busy_codex_thread_never_holds_the_delivery() {
        let root = std::env::temp_dir().join(format!("messenger-codex-busy-{}", std::process::id()));
        let _ = fs::remove_dir_all(&root);
        fs::create_dir_all(&root).unwrap();
        let command = root.join("codex");
        fs::write(
            &command,
            format!("#!/bin/sh\ncase \"$1 $2\" in\n  '--version ') echo '{PROVEN_VERSION}' ;;\n  'agents --help') echo 'shared local app-server daemon' ;;\n  'queue --help') echo '--thread' ;;\n  'mcp add') echo '--url' ;;\n  'mcp get') echo '--json' ;;\n  'queue --thread') exec sleep 30 ;;\nesac\n"),
        )
        .unwrap();
        fs::set_permissions(&command, fs::Permissions::from_mode(0o700)).unwrap();
        let provider = Provider::with_paths(command, root.join("codex-home"), root.join("sidecar"));
        assert!(provider.present().available, "{}", provider.present().detail);
        let started = std::time::Instant::now();
        let refused = provider
            .queue_within("thread", "courrier", std::time::Duration::from_millis(300))
            .unwrap_err();
        assert!(refused.0.contains("pas pris le courrier à temps"), "{}", refused.0);
        assert!(started.elapsed() < std::time::Duration::from_secs(5));
        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn supported_codex_is_probed_and_can_queue_a_verdict() {
        let root = std::env::temp_dir().join(format!("messenger-codex-{}", std::process::id()));
        let _ = fs::remove_dir_all(&root);
        fs::create_dir_all(&root).unwrap();
        let command = root.join("codex");
        fs::write(
            &command,
            format!(
                "#!/bin/sh\ncase \"$1 $2\" in\n  '--version ') echo '{PROVEN_VERSION}' ;;\n  'agents --help') echo 'shared local app-server daemon' ;;\n  'queue --help') echo '--thread' ;;\n  'mcp get') if test \"$3\" = '--help'; then echo '--json'; elif test -f '{}'; then echo '{{\"transport\":{{\"url\":\"http://127.0.0.1:47652/mcp\"}}}}'; else echo \"No MCP server named\" >&2; exit 1; fi ;;\n  'mcp add') if test \"$3\" = '--help'; then echo '--url'; else touch '{}'; fi ;;\n  'queue --thread') exit 0 ;;\nesac\n",root.join("equipped").display(),root.join("equipped").display()
            ),
        )
        .unwrap();
        fs::set_permissions(&command, fs::Permissions::from_mode(0o700)).unwrap();

        let home = root.join("codex-home");
        let sidecar = root.join("messenger-claude-channel");
        fs::write(&sidecar, "channel").unwrap();
        let provider = Provider::with_paths(command, home.clone(), sidecar.clone());
        assert!(provider.present().available);
        assert!(provider.present().detail.contains("Paramètres > Code > Hooks"));
        let ready = provider.equip().unwrap();
        assert!(ready.equipped);
        assert!(ready.detail.contains("Paramètres > Code > Hooks"));
        let hooks: serde_json::Value =
            serde_json::from_slice(&fs::read(home.join("hooks.json")).unwrap()).unwrap();
        let expected = equipment::hook(&sidecar, "codex", false).unwrap();
        assert!(expected.command.ends_with(" hook --host codex"));
        for event in ["SessionStart", "UserPromptSubmit"] {
            assert_eq!(hooks["hooks"][event][0]["hooks"][0]["command"], expected.command.as_str());
        }
        assert!(equipment::skill_ready(&home));
        assert_eq!(
            provider.deliver_verdict("session-1", "validé").unwrap(),
            Reachability::NextStart
        );
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn an_existing_mcp_configuration_is_never_overwritten() {
        let root =
            std::env::temp_dir().join(format!("messenger-codex-safe-{}", std::process::id()));
        let _ = fs::remove_dir_all(&root);
        fs::create_dir_all(&root).unwrap();
        let command = root.join("codex");
        let overwritten = root.join("overwritten");
        fs::write(
            &command,
            format!(
                "#!/bin/sh\ncase \"$1 $2\" in\n  '--version ') echo '{PROVEN_VERSION}' ;;\n  'agents --help') echo 'shared local app-server daemon' ;;\n  'queue --help') echo '--thread' ;;\n  'mcp get') if test \"$3\" = '--help'; then echo '--json'; else echo '{{\"transport\":{{\"type\":\"stdio\",\"command\":\"legacy\"}}}}'; fi ;;\n  'mcp add') if test \"$3\" = '--help'; then echo '--url'; else touch '{}'; fi ;;\nesac\n",
                overwritten.display()
            ),
        )
        .unwrap();
        fs::set_permissions(&command, fs::Permissions::from_mode(0o700)).unwrap();

        let home = root.join("codex-home");
        let provider = Provider::with_paths(command, home.clone(), root.join("absent-channel"));
        assert!(provider.equip().is_err());
        assert!(!overwritten.exists());
        assert!(!home.exists(), "a refused equipment writes no hook and no skill");
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn mcp_collection_does_not_depend_on_queue_or_an_exact_version() {
        let root = crate::test_support::Temporary::new();
        let command = root.0.join("codex");
        fs::write(&command, r#"#!/bin/sh
case "$1 $2" in
  '--version ') echo 'codex-cli 0.153.0' ;;
  'mcp add') echo '--url' ;;
  'mcp get') if test "$3" = '--help'; then echo '--json'; else echo '{"transport":{"url":"http://127.0.0.1:47652/mcp"}}'; fi ;;
  *) exit 1 ;;
esac
"#).unwrap();
        fs::set_permissions(&command, fs::Permissions::from_mode(0o700)).unwrap();
        let home = root.0.join("codex-home");
        let absent = root.0.join("absent-channel");
        let provider = Provider::with_paths(command.clone(), home.clone(), absent.clone());
        assert!(!provider.present().equipped, "the shared skill is still missing");
        assert!(provider.present().can_equip);
        equipment::install_skill(&home).unwrap();
        let provider = Provider::with_paths(command, home, absent);
        assert!(provider.present().equipped);
        assert_eq!(provider.deliver("session-1", "Courrier").unwrap(), Reachability::NoSession);
    }

    #[test]
    fn hooks_of_another_codex_installation_block_equipment_before_any_write() {
        let root = crate::test_support::Temporary::new();
        let command = root.0.join("codex");
        let added = root.0.join("added");
        fs::write(&command, format!(r#"#!/bin/sh
case "$1 $2" in
  '--version ') echo 'codex-cli 0.159.2' ;;
  'mcp add') if test "$3" = '--help'; then echo '--url'; else touch '{}'; fi ;;
  'mcp get') if test "$3" = '--help'; then echo '--json'; else echo "No MCP server named" >&2; exit 1; fi ;;
  *) exit 1 ;;
esac
"#, added.display())).unwrap();
        fs::set_permissions(&command, fs::Permissions::from_mode(0o700)).unwrap();
        let other = root.0.join("other").join("messenger-claude-channel");
        fs::create_dir_all(other.parent().unwrap()).unwrap();
        fs::write(&other, "other").unwrap();
        let home = root.0.join("codex-home");
        fs::create_dir_all(&home).unwrap();
        let foreign = serde_json::json!({"hooks": {"SessionStart": [{"hooks": [
            {"type": "command", "command": format!("\"{}\" hook --host codex", other.display())}
        ]}]}})
        .to_string();
        fs::write(home.join("hooks.json"), &foreign).unwrap();
        let sidecar = root.0.join("messenger-claude-channel");
        fs::write(&sidecar, "channel").unwrap();
        let provider = Provider::with_paths(command, home.clone(), sidecar);
        assert_eq!(provider.present().state, "à vérifier");
        assert!(provider.equip().is_err());
        assert!(!added.exists(), "the MCP entry is not added either");
        assert_eq!(fs::read_to_string(home.join("hooks.json")).unwrap(), foreign);
        assert!(!equipment::skill_path(&home).exists());
    }
}

#[cfg(all(test, windows))]
mod windows_tests {
    use super::{Provider, ProviderPort};

    #[test]
    fn a_codex_that_never_answers_is_stopped_in_time() {
        let root = std::env::temp_dir().join(format!("messenger-codex-hang-{}", std::process::id()));
        std::fs::create_dir_all(&root).unwrap();
        let command = root.join("codex.cmd");
        std::fs::write(&command, "@echo off\r\nping -n 30 127.0.0.1 > nul\r\n").unwrap();
        let started = std::time::Instant::now();
        let error = super::run_within(&command, &["queue"], std::time::Duration::from_millis(500))
            .unwrap_err();
        assert_eq!(error.kind(), std::io::ErrorKind::TimedOut);
        assert!(started.elapsed() < std::time::Duration::from_secs(5));
        let _ = std::fs::remove_dir_all(&root);
    }

    #[test]
    #[ignore = "Requires the Codex desktop app and an isolated CODEX_HOME"]
    fn actual_codex_desktop_cli_is_found_and_equipped() {
        assert!(
            std::env::var_os("CODEX_HOME").is_some(),
            "set CODEX_HOME to a temporary folder: this test writes the Codex MCP configuration"
        );
        let provider = Provider::new();
        assert!(provider.present().available, "{}", provider.present().detail);
        assert!(provider.equip().unwrap().equipped);
    }
}
