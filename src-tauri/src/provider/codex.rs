pub const ID: &str = "codex";
use std::{
    path::{Path, PathBuf},
    process::{Command, Output},
    sync::Mutex,
};

use serde_json::Value;

use crate::domain::{
    models::ProviderStatus,
    ports::{PortError, ProviderPort},
    Reachability,
};

/// Oldest version proven with Messenger; later versions still need the agents and queue probes.
pub const PROVEN_VERSION: &str = "codex-cli 0.152.0";
const MCP_NAME: &str = "arkalabs-messenger-app";
const MCP_URL: &str = "http://127.0.0.1:47652/mcp";

pub struct Provider {
    command: PathBuf,
    status: Mutex<ProviderStatus>,
}

impl Provider {
    pub fn new() -> Self {
        Self::with_command(super::executable("codex"))
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
        Command::new(&self.command)
            .args(arguments)
            .output()
            .map_err(|_| {
                PortError("Codex ne répond pas sur ce poste. Rouvre-le puis réessaie.".into())
            })
    }

    fn queue(&self, session: &str, text: &str) -> Result<Reachability, PortError> {
        if session.trim().is_empty() {
            return Err(PortError("la session de retour manque".into()));
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
        let ready = ready_status(current.version);
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
    let agents = run(command, &["agents", "--help"]);
    let queue = run(command, &["queue", "--help"]);
    if !responds(&agents, "shared local app-server daemon") || !responds(&queue, "--thread") {
        return unavailable(
            "Les commandes Codex agents et queue ne sont pas disponibles",
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
        ready_status(Some(version_text))
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

fn run(command: &Path, arguments: &[&str]) -> Result<Output, std::io::Error> {
    Command::new(command).args(arguments).output()
}

fn responds(output: &Result<Output, std::io::Error>, proof: &str) -> bool {
    output
        .as_ref()
        .is_ok_and(|output| output.status.success() && stdout(output).contains(proof))
}

fn ready_status(version: Option<String>) -> ProviderStatus {
    ProviderStatus {
        id: "codex".into(),
        name: "Codex".into(),
        version,
        state: "prêt".into(),
        detail: "Codex peut relever Messenger et recevoir un verdict dans une session existante."
            .into(),
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
                "#!/bin/sh\ncase \"$1 $2\" in\n  '--version ') echo '{PROVEN_VERSION}' ;;\n  'agents --help') echo 'shared local app-server daemon' ;;\n  'queue --help') echo '--thread' ;;\n  'mcp get') if test -f '{}'; then echo '{{\"transport\":{{\"url\":\"http://127.0.0.1:47652/mcp\"}}}}'; else echo \"No MCP server named\" >&2; exit 1; fi ;;\n  'mcp add') touch '{}' ;;\n  'queue --thread') exit 0 ;;\nesac\n",root.join("equipped").display(),root.join("equipped").display()
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
                "#!/bin/sh\ncase \"$1 $2\" in\n  '--version ') echo '{PROVEN_VERSION}' ;;\n  'agents --help') echo 'shared local app-server daemon' ;;\n  'queue --help') echo '--thread' ;;\n  'mcp get') echo '{{\"transport\":{{\"type\":\"stdio\",\"command\":\"legacy\"}}}}' ;;\n  'mcp add') touch '{}' ;;\nesac\n",
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
}
