use std::{fs, os::unix::fs::PermissionsExt};

use super::*;

fn command(root: &Path) -> PathBuf {
    let path = root.join("claude");
    fs::write(&path, format!("#!/bin/sh\nif test \"$1 $2 $3\" = 'mcp add --help'; then echo '--transport http --scope'; else echo '{PROVEN_VERSION}'; fi\n")).unwrap();
    fs::set_permissions(&path, fs::Permissions::from_mode(0o700)).unwrap();
    path
}

/// Hooks and skill as a previous equipment left them in `home`.
fn equipped_home(home: &Path, sidecar: &Path) {
    let hooks = equipment::hook(sidecar, ID, false);
    equipment::install(&home.join("settings.json"), home, hooks.as_ref()).unwrap();
}

#[test]
fn configured_channel_delivers_only_to_its_live_session() {
    let root = env::temp_dir().join(format!("messenger-claude-{}", std::process::id()));
    let _ = fs::remove_dir_all(&root);
    fs::create_dir_all(&root).unwrap();
    let sidecar = root.join("messenger-claude-channel");
    fs::write(&sidecar, "channel").unwrap();
    let config = root.join("claude.json");
    fs::write(
        &config,
        json!({ "mcpServers": { super::super::claude_http::NAME: { "type": "http", "url": super::super::claude_http::URL }, MCP_NAME: {
            "type": "stdio", "command": sidecar, "args": []
        } } })
        .to_string(),
    )
    .unwrap();
    let home = root.join("claude-home");
    equipped_home(&home, &sidecar);
    let provider = Provider::with_paths(command(&root), sidecar, config, home);
    assert!(provider.present().equipped);
    assert!(!provider.present().can_equip);
    assert_eq!(provider.present().state, "prêt");
    let (sender, mut receiver) = mpsc::unbounded_channel();
    let session = "0123456789abcdef-session";
    provider.hub.register(session.into(), sender);
    assert_eq!(
        provider.deliver_verdict(session, "validé").unwrap(),
        Reachability::LiveSession
    );
    assert!(receiver.try_recv().unwrap().contains("validé"));
    assert_eq!(
        provider
            .deliver("0123456789abcdef-absent", "message")
            .unwrap(),
        Reachability::NoSession
    );
    fs::remove_dir_all(root).unwrap();
}

#[test]
fn newer_claude_code_stays_equipped_and_an_older_one_is_refused() {
    let root = env::temp_dir().join(format!("messenger-claude-version-{}", std::process::id()));
    let _ = fs::remove_dir_all(&root);
    fs::create_dir_all(&root).unwrap();
    let config = root.join("claude.json");
    fs::write(
        &config,
        json!({ "mcpServers": { super::super::claude_http::NAME: {
            "type": "http", "url": super::super::claude_http::URL
        } } })
        .to_string(),
    )
    .unwrap();
    let home = root.join("claude-home");
    equipment::install_skill(&home).unwrap();
    for (index, (version, ready)) in [("2.1.285 (Claude Code)", true), ("2.1.200 (Claude Code)", false)]
        .into_iter()
        .enumerate()
    {
        let command = root.join(format!("claude-{index}"));
        fs::write(&command, format!("#!/bin/sh\nif test \"$1 $2 $3\" = 'mcp add --help'; then echo '--transport http --scope'; else echo '{version}'; fi\n")).unwrap();
        fs::set_permissions(&command, fs::Permissions::from_mode(0o700)).unwrap();
        let provider = Provider::with_paths(command, root.join("absent-channel"), config.clone(), home.clone());
        assert_eq!(provider.present().equipped, ready, "{version}");
        assert_eq!(provider.present().available, ready, "{version}");
    }
    fs::remove_dir_all(root).unwrap();
}

#[test]
fn conflicting_configuration_is_never_overwritten() {
    let root = env::temp_dir().join(format!("messenger-claude-safe-{}", std::process::id()));
    let _ = fs::remove_dir_all(&root);
    fs::create_dir_all(&root).unwrap();
    let sidecar = root.join("messenger-claude-channel");
    fs::write(&sidecar, "channel").unwrap();
    let config = root.join("claude.json");
    fs::write(
        &config,
        json!({ "mcpServers": { super::super::claude_http::NAME: {
            "type": "stdio", "command": "legacy", "args": []
        } } })
        .to_string(),
    )
    .unwrap();
    let home = root.join("claude-home");
    let provider = Provider::with_paths(command(&root), sidecar, config.clone(), home.clone());
    let before = fs::read(&config).unwrap();
    assert!(provider.equip().is_err());
    assert_eq!(fs::read(config).unwrap(), before);
    assert!(!home.exists(), "a refused equipment writes no hook and no skill");
    fs::remove_dir_all(root).unwrap();
}

#[test]
fn equipment_adds_the_mail_hooks_and_the_skill_once() {
    let root = crate::test_support::Temporary::new();
    let sidecar = root.0.join("messenger-claude-channel");
    fs::write(&sidecar, "channel").unwrap();
    let config = root.0.join("claude.json");
    fs::write(
        &config,
        json!({ "mcpServers": { super::super::claude_http::NAME: {
            "type": "http", "url": super::super::claude_http::URL
        } } })
        .to_string(),
    )
    .unwrap();
    let home = root.0.join("claude-home");
    fs::create_dir_all(&home).unwrap();
    fs::write(home.join("settings.json"), r#"{"theme":"dark","hooks":{"Stop":[{"hooks":[{"type":"command","command":"notify.sh"}]}]}}"#).unwrap();
    let provider = Provider::with_paths(command(&root.0), sidecar.clone(), config.clone(), home.clone());
    assert_eq!(provider.present().state, "à équiper");
    assert!(provider.equip().unwrap().equipped);
    let settings: Value = serde_json::from_slice(&fs::read(home.join("settings.json")).unwrap()).unwrap();
    let expected = format!("\"{}\" hook --host claude-code", sidecar.display());
    for event in ["SessionStart", "UserPromptSubmit"] {
        assert_eq!(settings["hooks"][event][0]["hooks"][0]["command"], expected.as_str());
    }
    assert_eq!(settings["theme"], "dark");
    assert_eq!(settings["hooks"]["Stop"][0]["hooks"][0]["command"], "notify.sh");
    assert!(home.join("settings.json.bak").is_file());
    assert!(equipment::skill_ready(&home));
    let again = Provider::with_paths(command(&root.0), sidecar, config, home);
    assert!(again.present().equipped);
}

#[test]
fn newer_claude_with_http_mcp_can_collect_mail_without_a_live_channel() {
    let root = crate::test_support::Temporary::new();
    let command = root.0.join("claude");
    fs::write(&command, "#!/bin/sh\nif test \"$1 $2 $3\" = 'mcp add --help'; then echo '--transport http --scope'; else echo '2.1.286 (Claude Code)'; fi\n").unwrap();
    fs::set_permissions(&command, fs::Permissions::from_mode(0o700)).unwrap();
    let provider = Provider::with_paths(command, root.0.join("missing-channel"), root.0.join("missing-config"), root.0.join("missing-home"));
    assert!(provider.present().available);
    assert!(provider.present().can_equip);
}
