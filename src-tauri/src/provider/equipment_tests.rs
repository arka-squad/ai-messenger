use std::fs;

use serde_json::{json, Value};

use super::*;
use crate::test_support::Temporary;

fn fake_binary(root: &Path) -> PathBuf {
    let path = root
        .join("arkalabs Messenger")
        .join(format!("{BINARY}{}", env::consts::EXE_SUFFIX));
    fs::create_dir_all(path.parent().unwrap()).unwrap();
    fs::write(&path, "channel").unwrap();
    path
}

fn read_json(path: &Path) -> Value {
    serde_json::from_slice(&fs::read(path).unwrap()).unwrap()
}

fn commands(data: &Value, event: &str) -> Vec<String> {
    data["hooks"][event]
        .as_array()
        .into_iter()
        .flatten()
        .flat_map(|group| group["hooks"].as_array().unwrap().clone())
        .map(|hook| hook["command"].as_str().unwrap().to_owned())
        .collect()
}

fn command_hook(command: &str) -> Value {
    json!({"type": "command", "command": command})
}

#[test]
fn provider_hooks_and_skill_are_installed_once_in_a_fresh_folder() {
    let root = Temporary::new();
    let home = root.0.join(".claude");
    let settings = home.join("settings.json");
    let expected = hook(&fake_binary(&root.0), "claude-code", false).unwrap();
    let command = expected.command.clone();
    assert!(command.starts_with('"') && command.ends_with("\" hook --host claude-code"));
    assert!(!command.contains('\\'));
    assert_eq!(expected.windows, None);
    assert!(!ready(&settings, &home, Some(&expected)).unwrap());

    assert!(install(&settings, &home, Some(&expected)).unwrap().is_empty());
    let data = read_json(&settings);
    for event in EVENTS {
        assert_eq!(commands(&data, event), vec![command.clone()]);
        assert_eq!(data["hooks"][event][0]["hooks"][0]["type"], "command");
        assert_eq!(data["hooks"][event][0]["hooks"][0]["timeout"], TIMEOUT);
        assert!(data["hooks"][event][0]["hooks"][0].get("commandWindows").is_none());
    }
    assert_eq!(fs::read_to_string(skill_path(&home)).unwrap(), SKILL);
    assert!(SKILL.starts_with("---\nname: arkalabs-messenger-app\n") || SKILL.starts_with("---\r\nname: arkalabs-messenger-app\r\n"));
    assert!(!beside(&settings, ".bak").exists(), "no original file, nothing to back up");
    assert!(ready(&settings, &home, Some(&expected)).unwrap());

    let before = fs::read(&settings).unwrap();
    install(&settings, &home, Some(&expected)).unwrap();
    assert_eq!(fs::read(&settings).unwrap(), before, "a second run writes nothing");
    assert!(!beside(&settings, ".bak").exists());
    assert!(!beside(&settings, &format!(".{SKILL_NAME}.tmp")).exists());
}

#[test]
fn provider_codex_hooks_carry_the_powershell_form_for_windows() {
    let root = Temporary::new();
    let settings = root.0.join("hooks.json");
    let expected = hook(&fake_binary(&root.0), "codex", true).unwrap();
    let windows = expected.windows.clone().unwrap();
    assert_eq!(windows, format!("& {}", expected.command));
    install_hooks(&settings, Some(&expected)).unwrap();
    let data = read_json(&settings);
    for event in EVENTS {
        assert_eq!(data["hooks"][event][0]["hooks"][0]["commandWindows"], windows.as_str());
    }
    assert!(hooks_ready(&settings, Some(&expected)).unwrap());

    // An entry written before the Windows form existed is stale: it is completed in place.
    let mut older = data.clone();
    older["hooks"]["SessionStart"][0]["hooks"][0]
        .as_object_mut()
        .unwrap()
        .remove("commandWindows");
    fs::write(&settings, older.to_string()).unwrap();
    assert!(!hooks_ready(&settings, Some(&expected)).unwrap());
    install_hooks(&settings, Some(&expected)).unwrap();
    assert_eq!(read_json(&settings), data);
}

#[test]
fn provider_hooks_keep_unrelated_entries_retire_the_first_mailbox_and_back_up_once() {
    let root = Temporary::new();
    let settings = root.0.join(".codex").join("hooks.json");
    fs::create_dir_all(settings.parent().unwrap()).unwrap();
    let legacy = "\"C:/Python/python.exe\" \"C:/arkalabs-messenger/messenger.py\" check --hook --host codex --event SessionStart";
    let original = json!({
        "model": "keep-me",
        "hooks": {
            "SessionStart": [
                {"matcher": "startup", "hooks": [command_hook(legacy), command_hook("audit-start.sh")]},
                {"hooks": [{"command": "python", "args": ["messenger.py", "check", "--hook"]}]}
            ],
            "PreToolUse": [{"matcher": "Bash", "hooks": [command_hook("audit.sh")]}],
            "Stop": [{"hooks": [command_hook("python messenger.py check --hook --host codex --event Stop")]}],
            "SessionEnd": []
        }
    });
    let text = serde_json::to_string_pretty(&original).unwrap();
    fs::write(&settings, &text).unwrap();
    let expected = hook(&fake_binary(&root.0), "codex", false).unwrap();
    assert!(legacy_present(&settings, &root.0));
    assert!(!hooks_ready(&settings, Some(&expected)).unwrap());

    let note = install_hooks(&settings, Some(&expected)).unwrap().unwrap();
    assert!(note.contains("3 ancien(s) hook(s) messenger.py") && note.contains("hooks.json.bak"), "{note}");
    let data = read_json(&settings);
    assert_eq!(data["model"], "keep-me");
    assert_eq!(data["hooks"]["PreToolUse"], original["hooks"]["PreToolUse"]);
    assert_eq!(data["hooks"]["SessionEnd"], json!([]), "an event left empty by its owner is kept");
    assert!(data["hooks"].get("Stop").is_none(), "the event only the first mailbox used disappears");
    assert_eq!(data["hooks"]["SessionStart"][0]["matcher"], "startup");
    assert_eq!(commands(&data, "SessionStart"), vec!["audit-start.sh".to_owned(), expected.command.clone()]);
    assert_eq!(commands(&data, "UserPromptSubmit"), vec![expected.command.clone()]);
    assert_eq!(fs::read_to_string(beside(&settings, ".bak")).unwrap(), text);
    assert!(!legacy_present(&settings, &root.0));
    assert!(hooks_ready(&settings, Some(&expected)).unwrap());
    let keys = data.as_object().unwrap().keys().collect::<Vec<_>>();
    assert_eq!(keys, ["model", "hooks"], "the person's key order is kept");

    // A later repair never replaces the first backup.
    let moved = serde_json::to_string(&data).unwrap().replace("arkalabs Messenger", "moved build");
    fs::write(&settings, moved).unwrap();
    assert!(!hooks_ready(&settings, Some(&expected)).unwrap(), "a removed build is stale, not foreign");
    assert_eq!(install_hooks(&settings, Some(&expected)).unwrap(), None);
    assert_eq!(read_json(&settings), data, "the stale entries are replaced where they were");
    assert_eq!(fs::read_to_string(beside(&settings, ".bak")).unwrap(), text);
}

#[test]
fn provider_hook_of_this_binary_with_other_arguments_is_replaced_in_place() {
    let root = Temporary::new();
    let settings = root.0.join("settings.json");
    let expected = hook(&fake_binary(&root.0), "claude-code", false).unwrap();
    let wrong_host = expected.command.replace("claude-code", "codex");
    let extra = format!("{} --verbose", expected.command);
    let text = json!({"hooks": {
        "SessionStart": [
            {"hooks": [command_hook("before.sh")]},
            {"matcher": "startup|resume", "hooks": [command_hook("person.sh"), command_hook(&wrong_host)]},
            {"hooks": [command_hook("after.sh")]}
        ],
        "UserPromptSubmit": [{"hooks": [command_hook(&extra)]}, {"hooks": [command_hook(&wrong_host)]}],
        "Stop": [{"hooks": [command_hook(&extra)]}]
    }})
    .to_string();
    fs::write(&settings, &text).unwrap();
    assert!(!hooks_ready(&settings, Some(&expected)).unwrap(), "stale, never foreign");
    install(&settings, &root.0, Some(&expected)).unwrap();
    let data = read_json(&settings);
    let start = &data["hooks"]["SessionStart"];
    assert_eq!(start[0]["hooks"][0]["command"], "before.sh");
    assert_eq!(start[1]["matcher"], "startup|resume");
    assert_eq!(start[1]["hooks"][0]["command"], "person.sh");
    assert_eq!(start[1]["hooks"][1]["command"], expected.command.as_str(), "same group, same index");
    assert_eq!(start[2]["hooks"][0]["command"], "after.sh", "later groups keep their index");
    assert_eq!(commands(&data, "UserPromptSubmit"), vec![expected.command.clone()]);
    assert!(data["hooks"].get("Stop").is_none(), "an entry of this binary on another event is removed");
    assert!(hooks_ready(&settings, Some(&expected)).unwrap());
}

#[test]
fn provider_hooks_of_another_installation_or_an_unreadable_file_are_never_overwritten() {
    let root = Temporary::new();
    let settings = root.0.join("settings.json");
    let expected = hook(&fake_binary(&root.0), "claude-code", false).unwrap();
    let other = root.0.join("other").join(format!("{BINARY}{}", env::consts::EXE_SUFFIX));
    fs::create_dir_all(other.parent().unwrap()).unwrap();
    fs::write(&other, "other channel").unwrap();
    let foreign = format!("\"{}\" hook --host claude-code", other.to_string_lossy().replace('\\', "/"));
    let conflicting = json!({"hooks": {"SessionStart": [{"hooks": [command_hook(&foreign)]}]}}).to_string();
    fs::write(&settings, &conflicting).unwrap();
    let legacy = legacy_skill(&root.0);
    fs::create_dir_all(&legacy).unwrap();
    let error = install(&settings, &root.0, Some(&expected)).unwrap_err();
    assert!(error.0.contains("rien n’a été écrasé"), "{}", error.0);
    assert_eq!(fs::read_to_string(&settings).unwrap(), conflicting);
    assert!(!beside(&settings, ".bak").exists());
    assert!(!skill_path(&root.0).exists(), "a refusal writes nothing at all");
    assert!(legacy.is_dir(), "a refusal moves nothing either");

    // A first-mailbox entry beside it changes nothing: the other installation's hook is still refused.
    let legacy_hook = "\"C:/Python/python.exe\" \"C:/arkalabs-messenger/messenger.py\" check --hook --host claude-code --event SessionStart";
    let mixed = json!({"hooks": {"SessionStart": [{"hooks": [command_hook(legacy_hook), command_hook(&foreign)]}]}}).to_string();
    fs::write(&settings, &mixed).unwrap();
    assert!(hooks_ready(&settings, Some(&expected)).unwrap_err().0.contains("rien n’a été écrasé"));
    assert!(install_hooks(&settings, Some(&expected)).is_err());
    assert_eq!(fs::read_to_string(&settings).unwrap(), mixed);

    for unreadable in ["{ not json", "[]", r#"{"hooks": {"SessionStart": {"command": "x"}}}"#] {
        fs::write(&settings, unreadable).unwrap();
        assert!(install_hooks(&settings, Some(&expected)).unwrap_err().0.contains("illisible"));
        assert_eq!(fs::read_to_string(&settings).unwrap(), unreadable);
        assert!(hooks_ready(&settings, None).unwrap(), "without a binary nothing is read or written");
    }
}

#[test]
fn provider_hooks_recognize_the_same_binary_written_with_backslashes() {
    let root = Temporary::new();
    let settings = root.0.join("settings.json");
    let expected = hook(&fake_binary(&root.0), "claude-code", false).unwrap();
    let native = expected.command.replace('/', "\\");
    let entry = |command: &str| json!([{"hooks": [command_hook(command)]}]);
    let text = json!({"hooks": {"SessionStart": entry(&native), "UserPromptSubmit": entry(&native)}}).to_string();
    fs::write(&settings, &text).unwrap();
    assert!(hooks_ready(&settings, Some(&expected)).unwrap());
    install_hooks(&settings, Some(&expected)).unwrap();
    assert_eq!(fs::read_to_string(&settings).unwrap(), text);
}

#[test]
fn provider_skill_copy_overwrites_only_its_own_file_and_retires_the_first_mailbox_skill() {
    let root = Temporary::new();
    let folder = skill_path(&root.0).parent().unwrap().to_owned();
    fs::create_dir_all(&folder).unwrap();
    fs::write(folder.join("SKILL.md"), "ancienne version").unwrap();
    fs::write(folder.join("notes.md"), "à garder").unwrap();
    let legacy = legacy_skill(&root.0);
    fs::create_dir_all(&legacy).unwrap();
    fs::write(legacy.join("SKILL.md"), "skill historique").unwrap();
    let settings = root.0.join("settings.json");
    assert!(!skill_ready(&root.0));
    assert!(legacy_present(&settings, &root.0));

    let notes = install(&settings, &root.0, None).unwrap();
    assert!(skill_ready(&root.0));
    assert_eq!(fs::read_to_string(skill_path(&root.0)).unwrap(), SKILL);
    assert_eq!(fs::read_to_string(folder.join("notes.md")).unwrap(), "à garder");
    let stamp = chrono::Local::now().format("%Y%m%d").to_string();
    let moved = root.0.join(format!("arkalabs-messenger-skill.bak-{stamp}"));
    assert!(!legacy.exists(), "no longer under skills/");
    assert_eq!(fs::read_to_string(moved.join("SKILL.md")).unwrap(), "skill historique");
    assert_eq!(notes.len(), 1);
    assert!(notes[0].contains("Ancienne skill arkalabs-messenger") && notes[0].contains(&moved.display().to_string()));
    assert!(SKILL.contains("qui_suis_je") && SKILL.contains("modifier_mon_role"));

    // Put back by an old installer the same day: the first copy is kept, the second sits beside it.
    fs::create_dir_all(&legacy).unwrap();
    fs::write(legacy.join("SKILL.md"), "réinstallée").unwrap();
    assert!(!ready(&settings, &root.0, None).unwrap());
    install(&settings, &root.0, None).unwrap();
    assert_eq!(fs::read_to_string(moved.join("SKILL.md")).unwrap(), "skill historique");
    let second = root.0.join(format!("arkalabs-messenger-skill.bak-{stamp}-2"));
    assert_eq!(fs::read_to_string(second.join("SKILL.md")).unwrap(), "réinstallée");
    assert!(ready(&settings, &root.0, None).unwrap());
}

#[test]
fn provider_without_a_channel_binary_installs_the_skill_and_still_retires_old_hooks() {
    let root = Temporary::new();
    let settings = root.0.join("settings.json");
    assert_eq!(hook(&root.0.join("absent"), "codex", true), None);
    install(&settings, &root.0, None).unwrap();
    assert!(!settings.exists());
    assert!(ready(&settings, &root.0, None).unwrap());

    let legacy = json!({"theme": "dark", "hooks": {"UserPromptSubmit": [{"hooks": [command_hook("python messenger.py check --hook")]}]}});
    fs::write(&settings, legacy.to_string()).unwrap();
    assert!(!ready(&settings, &root.0, None).unwrap());
    let notes = install(&settings, &root.0, None).unwrap();
    assert!(notes[0].contains("messenger.py"), "{notes:?}");
    assert_eq!(read_json(&settings), json!({"theme": "dark"}));
    assert!(ready(&settings, &root.0, None).unwrap());
}
