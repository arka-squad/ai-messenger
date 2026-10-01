pub const ID: &str = "kimi";
use crate::domain::{
    models::ProviderStatus,
    ports::{PortError, ProviderPort},
    Reachability,
};
use serde_json::Value;
use std::{
    env, fs,
    path::{Path, PathBuf},
    process::Command,
    sync::Mutex,
};
const NAME: &str = "arkalabs-messenger-app";
const URL: &str = "http://127.0.0.1:47652/mcp";
pub struct Provider {
    command: PathBuf,
    config: PathBuf,
    status: Mutex<ProviderStatus>,
}
impl Provider {
    pub fn new() -> Self {
        let command = super::executable("kimi");
        let version = Command::new(&command)
            .arg("--version")
            .output()
            .ok()
            .filter(|o| o.status.success())
            .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_owned());
        let legacy = version.as_deref() == Some("kimi, version 1.6");
        let home = env::var_os("HOME")
            .or_else(|| env::var_os("USERPROFILE"))
            .map(PathBuf::from)
            .unwrap_or_default();
        let config = if legacy {
            env::var_os("KIMI_SHARE_DIR")
                .map(PathBuf::from)
                .unwrap_or_else(|| home.join(".kimi"))
        } else {
            env::var_os("KIMI_CODE_HOME")
                .map(PathBuf::from)
                .unwrap_or_else(|| home.join(".kimi-code"))
        }
        .join("mcp.json");
        let compatible = legacy
            && (Command::new(&command)
                .args(["mcp", "add", "--help"])
                .output()
                .is_ok_and(|o| {
                    o.status.success() && String::from_utf8_lossy(&o.stdout).contains("http")
                }));
        let equipped = configuration(&config).is_ok_and(|v| v);
        let status=ProviderStatus {id:"kimi".into(),name:"Kimi Code".into(),version,
            state:if equipped {"prêt"} else if compatible {"à équiper"} else {"indisponible"}.into(),
            detail:if !compatible {"Kimi est introuvable ou son transport MCP HTTP n’est pas disponible."}
                else {"Relève garantie par les outils MCP. L’atteinte des sessions ouvertes par l’humain n’est pas attestée ; Messenger ne lance pas une nouvelle session."}.into(),
            available:compatible,equipped,can_equip:compatible && !equipped};
        Self {
            command,
            config,
            status: Mutex::new(status),
        }
    }
}
impl ProviderPort for Provider {
    fn id(&self) -> &'static str {
        ID
    }
    fn present(&self) -> ProviderStatus {
        self.status.lock().expect("Kimi status lock").clone()
    }
    fn equip(&self) -> Result<ProviderStatus, PortError> {
        let mut status = self.present();
        if !status.available {
            return Err(PortError(status.detail));
        }
        if !configuration(&self.config)? {
            let output = Command::new(&self.command)
                .args(["mcp", "add", "--transport", "http", NAME, URL])
                .output()
                .map_err(|_| PortError("Kimi n’a pas pu être équipé.".into()))?;
            if !output.status.success() {
                return Err(PortError(
                    "Kimi n’a pas confirmé l’ajout des outils Messenger.".into(),
                ));
            }
        }
        if !configuration(&self.config)? {
            return Err(PortError(
                "Kimi n’a pas conservé le raccordement Messenger.".into(),
            ));
        }
        status.equipped = true;
        status.can_equip = false;
        status.state = "prêt".into();
        *self.status.lock().expect("Kimi status lock") = status.clone();
        Ok(status)
    }
    fn deliver(&self, _: &str, _: &str) -> Result<Reachability, PortError> {
        Ok(Reachability::NoSession)
    }
    fn deliver_verdict(&self, session: &str, text: &str) -> Result<Reachability, PortError> {
        self.deliver(session, text)
    }
    fn receive(&self) -> bool {
        self.present().equipped
    }
}
fn configuration(path: &Path) -> Result<bool, PortError> {
    if !path.exists() {
        return Ok(false);
    }
    let value: Value = serde_json::from_slice(
        &fs::read(path)
            .map_err(|_| PortError("La configuration Kimi n’est pas accessible.".into()))?,
    )
    .map_err(|_| PortError("La configuration Kimi est illisible ; rien n’a été modifié.".into()))?;
    match value.pointer(&format!("/mcpServers/{NAME}")) {
        None => Ok(false),
        Some(entry) if entry["url"] == URL && entry.get("command").is_none() => Ok(true),
        _ => Err(PortError(
            "Un raccordement Kimi du même nom existe autrement ; rien n’a été écrasé.".into(),
        )),
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn kimi_equipment_preserves_other_servers_and_refuses_an_existing_conflict() {
        let root = crate::test_support::Temporary::new();
        let config = root.0.join("mcp.json");
        fs::write(
            &config,
            br#"{"mcpServers":{"arkalabs-messenger-app":{"url":"http://elsewhere"}}}"#,
        )
        .unwrap();
        assert!(configuration(&config).is_err());
        fs::write(&config,br#"{"mcpServers":{"arkalabs-messenger-app":{"url":"http://127.0.0.1:47652/mcp"},"other":{"command":"existing"}}}"#).unwrap();
        assert!(configuration(&config).unwrap());
    }
}
