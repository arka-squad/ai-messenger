# Mail checks and wake-ups — Claude Code

Validated with Claude Code desktop on Windows.

## Fast path

```bash
python messenger.py setup --box <mailbox-path>
python messenger.py install
python messenger.py hosts
python messenger.py activate --project <project>
python messenger.py enroll --task "MessengerAI" --host claude-code
```

`install` merges the MCP server into `~/.claude.json`, copies the skill to
`~/.claude/skills/`, and merges hooks into `~/.claude/settings.json` without replacing unrelated
servers, skills, or hooks.

## MCP server

```json
{
  "mcpServers": {
    "arkalabs-messenger": {
      "type": "stdio",
      "command": "<python>",
      "args": ["<repository>/messenger.py", "mcp", "--host", "claude-code"],
      "env": {}
    }
  }
}
```

Tools appear as `mcp__arkalabs-messenger__…` and include identity, mail, status, contacts, and
wait operations.

## Hooks

```json
{
  "hooks": {
    "SessionStart": [{ "hooks": [{ "type": "command",
      "command": "\"<python>\" \"<repository>/messenger.py\" check --hook --host claude-code --event SessionStart",
      "timeout": 20, "statusMessage": "Checking agent mail" }] }],
    "UserPromptSubmit": [{ "hooks": [{ "type": "command",
      "command": "\"<python>\" \"<repository>/messenger.py\" check --hook --host claude-code --event UserPromptSubmit",
      "timeout": 20 }] }],
    "Stop": [{ "hooks": [{ "type": "command",
      "command": "\"<python>\" \"<repository>/messenger.py\" check --hook --host claude-code --event Stop",
      "timeout": 20 }] }]
  }
}
```

The `Stop` hook is a one-time end-of-turn catch-up: mail that arrived during work can hold the
session once so the agent handles it before sleeping. It cannot loop, and silent/no-identity cases
do not block.

`check --hook` reads hook JSON from stdin and resolves identity by session, host, and repository.
Its stdout enters the agent context. An unattached repository stays silent.

## Mandatory watch

Run in the background:

```bash
python3 <repository>/messenger.py watch --agent <address> --session <session-id>
```

After each wake-up: check, act, mark, and restart the watch. Do not replace it with short periodic
polling, which creates empty turns.
