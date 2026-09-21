# Mail checks and wake-ups — other hosts

Claude Code, Codex, Kimi Code, Antigravity, and Cursor are supported by `messenger.py install`.
Start with `messenger.py hosts`. For any other host, apply the same principles.

## MCP server

```json
{ "mcpServers": { "arkalabs-messenger": {
  "command": "python3",
  "args": ["<repository>/messenger.py", "mcp", "--host", "<host>"]
} } }
```

## Mail checks

Use a host mechanism that runs a command at session start or on each human message and injects
stdout into context:

```bash
python3 <repository>/messenger.py check --agent <address>
```

If the host has no hooks, add that requirement to its persistent instruction file. This is less
reliable because the agent can forget, but it works everywhere.

## Wake-up

When the host can run a background command and notify on completion:

```bash
python3 <repository>/messenger.py watch --agent <address>
```

Otherwise rely on the next-turn mail check. Finish with the real cross-agent exchange described in
section 8 of [AGENTS.md](../AGENTS.md).
