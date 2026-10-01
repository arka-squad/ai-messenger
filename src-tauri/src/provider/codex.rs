pub const ID: &str = "codex";
use std::{
    path::{Path, PathBuf},
    process::Output,
    sync::Mutex,
};

use serde_json::Value;

use crate::domain::{
    models::ProviderStatus,
    ports::{PortError, ProviderPort},
    Reachability,
};

/// Oldest version proven with Messenger; later versions still need the MCP probes.
pub const PROVEN_VERSION: &str = "codex-cli 0.152.0";
const MCP_NAME: &str = "arkalabs-messenger-app";
const MCP_URL: &str = "http://127.0.0.1:47652/mcp";

pub struct Provider {
    command: PathBuf,
    status: Mutex<ProviderStatus>,
}

impl Provider {
    pub fn new() -> Self {
        let command = super::executable("codex");
        if command.is_absolute() {
            return Self::with_command(command);
        }
        Self::with_command(bundled_command().unwrap_or(command))
    }

    fn with_command(command: impl Into<PathBuf>) -> Self {
        let command = command.into();
        let status = probe(&command);
        Self {
            command,
            status: Mutex::new(status),
        }
    }

    fn run(&self, arguments: &[&str]) -> Result<Output, PortError> {
        run(&self.command, arguments)
            .map_err(|_| {
                PortError("Codex ne répond pas sur ce poste. Rouvre-le puis réessaie.".into())
            })
    }

    fn queue(&self, session: &str, text: &str) -> Result<Reachability, PortError> {
        if session.trim().is_empty() || !queue_supported(&self.command) {
            return Ok(Reachability::NoSession);
        }
        let status = self.present();
        if !status.available {
            return Err(PortError(status.detail));
        }
        let output = self.run(&["queue", "--thread", session, "--message", text])?;
        if output.status.success() {
            Ok(Reachability::NextStart)
        } else {
            Err(command_error("Codex n’a pas accepté le message", &output))
        }
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
        let ready = ready_status(current.version, queue_supported(&self.command));
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

fn probe(command: &Path) -> ProviderStatus {
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
    let equipped = run(command, &["mcp", "get", MCP_NAME, "--json"])
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
    if equipped {
        ready_status(Some(version_text), queue_supported(command))
    } else {
        ProviderStatus {
            id: "codex".into(),
            name: "Codex".into(),
            version: Some(version_text),
            state: "à équiper".into(),
            detail: "Codex est compatible ; clique pour lui donner accès à Messenger.".into(),
            available: true,
            equipped: false,
            can_equip: true,
        }
    }
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
    super::command(command).args(arguments).output()
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

fn ready_status(version: Option<String>, queue: bool) -> ProviderStatus {
    ProviderStatus {
        id: "codex".into(),
        name: "Codex".into(),
        version,
        state: "prêt".into(),
        detail: (if queue {"Codex peut relever Messenger et recevoir un verdict dans une session existante."}
            else {"Codex relève Messenger par MCP ; la remise dans une session existante est indisponible."}).into(),
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

    use super::{Provider, ProviderPort, PROVEN_VERSION};
    use crate::domain::Reachability;

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

        let provider = Provider::with_command(command);
        assert!(provider.present().available);
        assert!(provider.equip().unwrap().equipped);
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

        let provider = Provider::with_command(command);
        assert!(provider.equip().is_err());
        assert!(!overwritten.exists());
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
        let provider = Provider::with_command(command);
        assert!(provider.present().equipped);
        assert_eq!(provider.deliver("session-1", "Courrier").unwrap(), Reachability::NoSession);
    }
}

#[cfg(all(test, windows))]
mod windows_tests {
    use super::{Provider, ProviderPort};

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
