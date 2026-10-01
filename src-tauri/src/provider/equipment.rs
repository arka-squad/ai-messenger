//! What a provider receives besides its MCP entry: the mail-check hooks that run the bundled
//! channel binary, and the shared agent skill. Only Messenger's own entries are ever written;
//! another installation's hook is respected and an unreadable file is never rewritten. The first
//! mailbox's guidance (its `arkalabs-messenger` skill and `messenger.py … --hook` entries) is
//! retired, because it answers the same `MAIL — …` notices with tools that reach nobody.
use std::{
    collections::BTreeSet,
    env,
    ffi::OsString,
    fs,
    path::{Path, PathBuf},
};

use serde_json::{json, Map, Value};

use crate::domain::ports::PortError;

pub const SKILL_NAME: &str = "arkalabs-messenger-app";
pub const SKILL: &str = include_str!("../../../skills/arkalabs-messenger-app/SKILL.md");
/// The first mailbox's skill folder, under `skills/`.
pub const LEGACY_SKILL: &str = "arkalabs-messenger";
const EVENTS: [&str; 2] = ["SessionStart", "UserPromptSubmit"];
const BINARY: &str = "messenger-claude-channel";
/// Seconds; the hook itself gives up after three.
const TIMEOUT: u64 = 10;

/// The hook entry Messenger writes for one host.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Hook {
    /// Quoted path then arguments: read the same way by sh and cmd.
    pub command: String,
    /// Codex runs `commandWindows` with PowerShell on Windows, which needs the call operator.
    pub windows: Option<String>,
}

/// The bundled channel binary: next to the application, or in `binaries/` during development.
pub fn sidecar() -> PathBuf {
    let name = format!("{BINARY}{}", env::consts::EXE_SUFFIX);
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
            path.file_name()
                .is_some_and(|file| file.to_string_lossy().starts_with(&format!("{BINARY}-")))
        })
        .unwrap_or_else(|| directory.join(name))
}

/// The hook for `host`, or `None` when this build ships no channel binary. Forward slashes keep
/// the path readable by cmd, PowerShell and sh without escaping. `windows` adds the PowerShell
/// form for a host that reads `commandWindows`.
pub fn hook(sidecar: &Path, host: &str, windows: bool) -> Option<Hook> {
    sidecar.is_file().then(|| {
        let path = sidecar.to_string_lossy().replace('\\', "/");
        Hook {
            command: format!("\"{path}\" hook --host {host}"),
            windows: windows.then(|| format!("& \"{path}\" hook --host {host}")),
        }
    })
}

/// `Ok(true)` when the hooks (if any) and the skill are in place and no former guidance remains,
/// `Ok(false)` when equipment has something to do, an error when a file must be kept as it is.
pub fn ready(hooks: &Path, root: &Path, hook: Option<&Hook>) -> Result<bool, PortError> {
    Ok(hooks_ready(hooks, hook)? && skill_ready(root))
}

/// Installs what `ready` found missing; refuses before writing anything. Returns what was retired,
/// for the provider's status.
pub fn install(hooks: &Path, root: &Path, hook: Option<&Hook>) -> Result<Vec<String>, PortError> {
    hooks_ready(hooks, hook)?;
    let mut notes = Vec::new();
    notes.extend(install_hooks(hooks, hook)?);
    install_skill(root)?;
    notes.extend(retire_legacy_skill(root)?);
    Ok(notes)
}

/// True when this host still holds the former guidance that equipment retires.
pub fn legacy_present(hooks: &Path, root: &Path) -> bool {
    legacy_skill(root).is_dir()
        || read(hooks).is_ok_and(|data| entries(&data).iter().any(|(_, entry)| legacy(entry)))
}

pub fn hooks_ready(path: &Path, hook: Option<&Hook>) -> Result<bool, PortError> {
    let data = match (read(path), hook) {
        (Ok(data), _) => data,
        // Without a channel binary nothing is written here: an unreadable file is left alone.
        (Err(_), None) => return Ok(true),
        (Err(error), Some(_)) => return Err(error),
    };
    let found = entries(&data);
    // Another installation's live hook is refused first, before any legacy cleanup could reach it.
    if let Some(hook) = hook {
        let expected = binary(&hook.command);
        let foreign = found.iter().any(|(_, entry)| {
            ours(entry)
                && entry_binary(entry).is_some_and(|binary| Some(&binary) != expected.as_ref() && Path::new(&binary).is_file())
        });
        if foreign {
            return Err(PortError(format!(
                "Une relève Messenger d’une autre installation est déjà posée dans {} ; rien n’a été écrasé.",
                path.display()
            )));
        }
    }
    if found.iter().any(|(_, entry)| legacy(entry)) {
        return Ok(false);
    }
    let Some(hook) = hook else {
        return Ok(true);
    };
    let ours = found.iter().filter(|(_, entry)| ours(entry)).collect::<Vec<_>>();
    Ok(ours.len() == EVENTS.len()
        && EVENTS.iter().all(|event| ours.iter().any(|(name, entry)| name == event && exact(entry, hook))))
}

/// Writes the hooks. A stale entry of this binary (a moved build, other arguments) is replaced in
/// place, so the host's index-keyed approvals of the person's other hooks stay valid; former
/// `messenger.py … --hook` entries are removed after the one-time backup.
pub fn install_hooks(path: &Path, hook: Option<&Hook>) -> Result<Option<String>, PortError> {
    if hooks_ready(path, hook)? {
        return Ok(None);
    }
    let mut data = read(path)?;
    let mut placed = BTreeSet::new();
    let mut retired = 0;
    let configuration = data.as_object_mut().expect("checked configuration object");
    let events = configuration
        .entry("hooks")
        .or_insert_with(|| json!({}))
        .as_object_mut()
        .expect("checked hooks object");
    let had_events = !events.is_empty();
    // Only the groups and events this cleanup empties disappear.
    events.retain(|event, groups| {
        let list = groups.as_array_mut().expect("checked hook groups");
        let before = list.len();
        list.retain_mut(|group| {
            let Some(hooks) = group.get_mut("hooks").and_then(Value::as_array_mut) else {
                return true;
            };
            let count = hooks.len();
            hooks.retain_mut(|entry| {
                if legacy(entry) {
                    retired += 1;
                    return false;
                }
                if !ours(entry) {
                    return true;
                }
                match hook {
                    Some(hook) if EVENTS.contains(&event.as_str()) && placed.insert(event.clone()) => {
                        *entry = entry_for(hook);
                        true
                    }
                    Some(_) => false,
                    None => true,
                }
            });
            count == hooks.len() || !hooks.is_empty()
        });
        before == list.len() || !list.is_empty()
    });
    if let Some(hook) = hook {
        for event in EVENTS.into_iter().filter(|event| !placed.contains(*event)) {
            events
                .entry(event)
                .or_insert_with(|| json!([]))
                .as_array_mut()
                .expect("checked hook groups")
                .push(json!({ "hooks": [entry_for(hook)] }));
        }
    }
    if had_events && events.is_empty() {
        configuration.remove("hooks");
    }
    write(path, &data)?;
    Ok((retired > 0).then(|| {
        format!(
            "{retired} ancien(s) hook(s) messenger.py retiré(s) de {} (copie d’origine : {}).",
            path.display(),
            beside(path, ".bak").display()
        )
    }))
}

pub fn skill_path(root: &Path) -> PathBuf {
    root.join("skills").join(SKILL_NAME).join("SKILL.md")
}

pub fn legacy_skill(root: &Path) -> PathBuf {
    root.join("skills").join(LEGACY_SKILL)
}

/// The shared skill is current and the first mailbox's skill no longer loads beside it.
pub fn skill_ready(root: &Path) -> bool {
    skill_current(root) && !legacy_skill(root).is_dir()
}

fn skill_current(root: &Path) -> bool {
    fs::read(skill_path(root)).is_ok_and(|bytes| bytes == SKILL.as_bytes())
}

/// Writes only `skills/arkalabs-messenger-app/SKILL.md`; the folder's other files are kept.
pub fn install_skill(root: &Path) -> Result<(), PortError> {
    if skill_current(root) {
        return Ok(());
    }
    let path = skill_path(root);
    let refused = || {
        PortError(format!(
            "La skill Messenger n’a pas pu être posée dans {}.",
            path.display()
        ))
    };
    fs::create_dir_all(path.parent().expect("skill folder")).map_err(|_| refused())?;
    fs::write(&path, SKILL).map_err(|_| refused())
}

/// Moves the first mailbox's skill out of `skills/` (every `skills/*/SKILL.md` is loaded), next to
/// it as `arkalabs-messenger-skill.bak-<YYYYMMDD>`; nothing is deleted.
pub fn retire_legacy_skill(root: &Path) -> Result<Option<String>, PortError> {
    let legacy = legacy_skill(root);
    if !legacy.is_dir() {
        return Ok(None);
    }
    let stamp = chrono::Local::now().format("%Y%m%d").to_string();
    let base = format!("{LEGACY_SKILL}-skill.bak-{stamp}");
    let mut target = root.join(&base);
    for attempt in 2.. {
        if !target.exists() {
            break;
        }
        target = root.join(format!("{base}-{attempt}"));
    }
    fs::rename(&legacy, &target).map_err(|_| {
        PortError(format!(
            "L’ancienne skill {} n’a pas pu être déplacée ; ferme les sessions qui l’utilisent puis réessaie.",
            legacy.display()
        ))
    })?;
    Ok(Some(format!(
        "Ancienne skill {LEGACY_SKILL} déplacée hors de skills/ : {}.",
        target.display()
    )))
}

/// The configuration as an object whose `hooks` events hold lists; an absent or empty file is `{}`.
fn read(path: &Path) -> Result<Value, PortError> {
    let unreadable = || {
        PortError(format!(
            "La configuration {} est illisible ; rien n’a été modifié.",
            path.display()
        ))
    };
    let text = match fs::read_to_string(path) {
        Ok(text) => text,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => String::new(),
        Err(_) => return Err(unreadable()),
    };
    if text.trim().is_empty() {
        return Ok(Value::Object(Map::new()));
    }
    let value: Value = serde_json::from_str(&text).map_err(|_| unreadable())?;
    let shaped = value.is_object()
        && value.get("hooks").is_none_or(|hooks| {
            hooks
                .as_object()
                .is_some_and(|events| events.values().all(Value::is_array))
        });
    shaped.then_some(value).ok_or_else(unreadable)
}

/// `(event, entry)` of every hook entry in the file.
fn entries(data: &Value) -> Vec<(String, Value)> {
    let mut found = Vec::new();
    for (event, groups) in data["hooks"].as_object().into_iter().flatten() {
        for group in groups.as_array().into_iter().flatten() {
            for entry in group["hooks"].as_array().into_iter().flatten() {
                found.push((event.clone(), entry.clone()));
            }
        }
    }
    found
}

fn entry_for(hook: &Hook) -> Value {
    let mut entry = json!({ "type": "command", "command": hook.command, "timeout": TIMEOUT });
    if let Some(windows) = &hook.windows {
        entry["commandWindows"] = json!(windows);
    }
    entry
}

/// An entry that runs a channel binary of Messenger, whatever its path or arguments.
fn ours(entry: &Value) -> bool {
    entry_binary(entry).is_some_and(|binary| {
        binary
            .rsplit('/')
            .next()
            .is_some_and(|name| name.starts_with(BINARY))
    })
}

/// An entry of the first mailbox: `messenger.py check --hook …`, as text or `command` + `args`.
fn legacy(entry: &Value) -> bool {
    let mut command = entry["command"].as_str().unwrap_or_default().to_owned();
    for argument in entry["args"].as_array().into_iter().flatten().filter_map(Value::as_str) {
        command.push(' ');
        command.push_str(argument);
    }
    command.contains("messenger.py") && command.contains("--hook")
}

fn entry_binary(entry: &Value) -> Option<String> {
    binary(entry["command"].as_str()?)
}

/// Exactly the expected entry: same command, and the same Windows form when one is expected.
fn exact(entry: &Value, hook: &Hook) -> bool {
    let command = |key: &str| entry[key].as_str().map(|text| text.trim_start_matches('&').trim());
    entry["type"] == "command"
        && command("command").is_some_and(|found| same(found, &hook.command))
        && hook.windows.as_deref().is_none_or(|expected| {
            command("commandWindows").is_some_and(|found| same(found, expected.trim_start_matches('&').trim()))
        })
}

/// The same hook whatever the path's separators (and case, on Windows).
fn same(found: &str, expected: &str) -> bool {
    found == expected || parts(found).is_some_and(|found| parts(expected) == Some(found))
}

fn binary(command: &str) -> Option<String> {
    parts(command).map(|(binary, _)| binary)
}

/// `(binary, arguments)` of a hook command.
fn parts(command: &str) -> Option<(String, Vec<String>)> {
    let command = command.trim();
    let (binary, rest) = match command.strip_prefix('"') {
        Some(quoted) => quoted.split_once('"')?,
        None => command.split_once(' ').unwrap_or((command, "")),
    };
    if binary.is_empty() {
        return None;
    }
    let binary = binary.replace('\\', "/");
    let binary = if cfg!(windows) { binary.to_lowercase() } else { binary };
    Some((binary, rest.split_whitespace().map(str::to_owned).collect()))
}

fn write(path: &Path, data: &Value) -> Result<(), PortError> {
    let refused = || {
        PortError(format!(
            "La configuration {} n’a pas pu être écrite.",
            path.display()
        ))
    };
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|_| refused())?;
    }
    // The person's own file is copied once, before Messenger first changes it.
    let backup = beside(path, ".bak");
    if path.is_file() && !backup.exists() {
        fs::copy(path, &backup).map_err(|_| refused())?;
    }
    let text = serde_json::to_string_pretty(data).map_err(|_| refused())? + "\n";
    let temporary = beside(path, &format!(".{SKILL_NAME}.tmp"));
    fs::write(&temporary, text).map_err(|_| refused())?;
    fs::rename(&temporary, path).map_err(|_| {
        let _ = fs::remove_file(&temporary);
        refused()
    })
}

fn beside(path: &Path, suffix: &str) -> PathBuf {
    let mut name = OsString::from(path.as_os_str());
    name.push(suffix);
    PathBuf::from(name)
}

#[cfg(test)]
#[path = "equipment_tests.rs"]
mod tests;
