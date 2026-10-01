use crate::domain::ports::PortError;
use serde_json::Value;
use std::{fs, path::Path, process::Command};
pub const NAME: &str = "arkalabs-messenger-app";
pub const URL: &str = "http://127.0.0.1:47652/mcp";
pub fn configured(path: &Path) -> Result<bool, PortError> {
    if !path.exists() {
        return Ok(false);
    }
    let bytes = fs::read(path)
        .map_err(|_| PortError("La configuration Claude Code n’est pas lisible.".into()))?;
    let value: Value = serde_json::from_slice(&bytes).map_err(|_| {
        PortError("La configuration Claude Code est illisible ; rien n’a été modifié.".into())
    })?;
    match value.pointer(&format!("/mcpServers/{NAME}")) {
        None => Ok(false),
        Some(v) if v["type"] == "http" && v["url"] == URL => Ok(true),
        _ => Err(PortError(
            "Un raccordement Claude Code du même nom existe autrement ; rien n’a été écrasé."
                .into(),
        )),
    }
}
pub fn equip(command: &Path, config: &Path) -> Result<(), PortError> {
    if !configured(config)? {
        let output = Command::new(command)
            .args([
                "mcp",
                "add",
                "--transport",
                "http",
                "--scope",
                "user",
                NAME,
                URL,
            ])
            .output()
            .map_err(|_| {
                PortError("Claude Code n’a pas pu ajouter les outils Messenger.".into())
            })?;
        if !output.status.success() || !configured(config)? {
            return Err(PortError(
                "Claude Code n’a pas confirmé le raccordement MCP.".into(),
            ));
        }
    }
    Ok(())
}
