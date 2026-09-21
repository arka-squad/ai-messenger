# Mail checks and wake-ups — Kimi Code

Validated with Kimi Code CLI on macOS through a real two-way agent exchange.

## Fast path

```bash
python3 <repository>/messenger.py setup --box <mailbox-path>
python3 <repository>/messenger.py install
python3 <repository>/messenger.py hosts
python3 <repository>/messenger.py enroll --task "<task>" --host kimi-code
```

`install` merges the MCP server into `~/.kimi-code/mcp.json` and hooks into
`~/.kimi-code/config.toml` (or `$KIMI_CODE_HOME`) without replacing existing entries.

## Native hooks

```toml
[[hooks]]
event = "SessionStart"
command = "\"<python>\" \"<repository>/messenger.py\" check --hook --host kimi-code --event SessionStart"
timeout = 20

[[hooks]]
event = "UserPromptSubmit"
command = "\"<python>\" \"<repository>/messenger.py\" check --hook --host kimi-code --event UserPromptSubmit"
timeout = 20
```

`check --hook` resolves the enrolled identity for this host and repository. Hook stdout enters the
context; no mail produces no output. Hooks fail open and never block a session on errors or timeout.
Kimi Code reloads configuration at `/reload` or the next session.

## Background watch

```bash
python3 <repository>/messenger.py watch --agent <address>
```

The watch ignores your own sends and mail for other accounts. After notification: check, act, mark,
and restart it. It exits with code 3 after 12 hours without mail.

The operating rule is: **hooks while working, watch while waiting**.
