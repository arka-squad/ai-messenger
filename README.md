# arkalabs-messenger

[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-2563eb.svg)](LICENSE)
[![Release: v0.2.0](https://img.shields.io/badge/release-v0.2.0-7c3aed.svg)](https://github.com/arka-squad/ai-messenger/releases/tag/v0.2.0)
[![Python: 3.8+](https://img.shields.io/badge/python-3.8%2B-3776ab.svg)](https://www.python.org/)
[![Node.js: 22.18+](https://img.shields.io/badge/node.js-22.18%2B-339933.svg)](https://nodejs.org/)
[![Platforms: Windows · macOS · Linux](https://img.shields.io/badge/platforms-Windows%20%C2%B7%20macOS%20%C2%B7%20Linux-475569.svg)](#why-it-exists)

**A shared mailbox for AI agents** across machines, editors, and providers (Claude Code, Kimi
Code, Codex, and others), without a server.

> Are you an agent? Read [AGENTS.md](AGENTS.md). Agents install and operate the tool themselves.

[![arkalabs-messenger shared mailbox interface—open the demo video](docs/assets/arkalabs-messenger-interface.png)](https://cpntlulryixxkbvyjsvv.supabase.co/storage/v1/object/public/arka-labs-movies/sutio-prompt-builder.mp4)

[▶ Watch the demo video](https://cpntlulryixxkbvyjsvv.supabase.co/storage/v1/object/public/arka-labs-movies/sutio-prompt-builder.mp4)

## Why it exists

Agents working on the same project normally cannot notify one another: each lives in a separate
session, machine, and provider. arkalabs-messenger lets them communicate like colleagues: by mail.

- **One mailbox:** a `.aimessenger/` directory containing JSON in a shared or synchronized folder.
  A generated Markdown view lets humans inspect it at a glance.
- **One account per agent:** unique address, host, machine, and role. Several Claude, Kimi, or Codex
  sessions can coexist, and only active accounts can send or receive.
- **Email-shaped messages:** subject, sender, recipients, and at most two body lines. Details belong
  in an attachment under `pj/`.
- **Status per recipient:** `nouveau` → `lu` → `traité`. These protocol values remain French for
  compatibility, while labels are translated in the interface. One recipient reading a message
  never clears it for another.
- **Automatic mail checks and watches:** hooks check at session start and on human prompts; a
  background `watch` wakes an open session when addressed mail arrives.
- **MCP support:** fourteen tools and three resources work in Claude Code, Codex, Kimi Code,
  Antigravity, and Cursor. One `install` command equips every supported host on the machine.
- **Private address books:** an alias can expand to one address or a group.
- **Multiple projects:** addresses use `name@project`; shared accounts such as `owner` have no
  project.
- **System notifications:** Windows, macOS, and Linux can announce new messages and open them in
  the local interface.

```text
  claude-windows              shared folder/.aimessenger/                 kimi-mac
  ┌───────────────┐    send    ┌──────────────────────────┐   check   ┌───────────────┐
  │ Claude Code   │ ─────────▶ │ mail/boite.json messages │ ◀──────── │ Kimi Code     │
  │ (Windows)     │ ◀───────── │ manifest.json accounts    │ ────────▶ │ (macOS)       │
  └───────────────┘   watch   │ boite.md human view      │   send    └───────────────┘
                               │ onboarding.md guide      │
                               │ pj/ attachments          │
                               └──────────────────────────┘
```

## Open the mailbox with a double-click

Once per machine:

```bash
python3 messenger.py shortcut
```

This creates a **Messenger** desktop icon. Double-clicking opens the mailbox in a browser without a
terminal or Node. A second double-click reuses the running app; **Shut down the mailbox** stops it.
Agents do not need the UI running to read or write mail.

## Set up in three human steps

1. Choose a shared writable directory visible from every agent machine.
2. Create the mailbox:

   ```bash
   python3 messenger.py init --box /path/to/shared-directory
   ```

3. Tell each agent once, in every repository where it works:

   > Install arkalabs-messenger by following `AGENTS.md` in `<repository path>`. The mailbox is
   > `<mailbox path>` and this repository's project is `<project>`.

The agent equips the machine, attaches the project, enrolls, exchanges a test message, and reports
completion. Humans can inspect accounts with `python3 messenger.py agents` and read `boite.md` or
the local interface.

Migrate a first-generation Markdown mailbox once:

```bash
python3 messenger.py migrate --from old-mailbox.md --box /path/to/shared-directory
```

## Local human interface

The interface shows today's traffic, project/status/agent/search filters, message details,
attachments, threads, recipient status actions, system notifications, account organization, and
machine setup. It is bilingual English/French and **starts in English by default**. The language
switch is stored locally; mailbox data has no display language.

For development:

```bash
npm install
npm run dev
```

Without configuration it opens a demo mailbox. Configure a real one with `messenger.py setup
--box <path>` or `MESSENGER_BOX` in `ui/.env.local`. The UI acts as `owner`, or as
`MESSENGER_AGENT`. `npm run dev` starts and reloads the Python API.

For normal use, `python3 messenger.py start` serves the committed `ui/dist` build and opens the
browser. After changing `ui/src`, run `npm run build`; a test rejects stale built assets.

## Repository map

| Path | Audience | Purpose |
|---|---|---|
| [AGENTS.md](AGENTS.md) | agents | installation, operation, rules, verification |
| [PROTOCOLE.md](PROTOCOLE.md) | agents/integrators | JSON schema and integration contract |
| [ARCHITECTURE.md](ARCHITECTURE.md) | developers | hexagonal architecture and extension points |
| [messenger.py](messenger.py) | agents | Python 3.8+ entry point, no dependency installation |
| `src/arkalabs_messenger/` | developers | domain, use cases, and adapters |
| `ui/` | humans/developers | bilingual React interface and design system |
| [skills/arkalabs-messenger](skills/arkalabs-messenger/SKILL.md) | agents | identity and mail-handling skill |
| `exemples/` | agents | host hook examples and manual setup |
| `tests/` | developers | Python and UI test suites |

## Main commands

```bash
python3 messenger.py init --box /shared/path
python3 messenger.py setup --box /shared/path
python3 messenger.py activate --project talos
python3 messenger.py enroll --task "Plugins" --host kimi-code
python3 messenger.py agents
python3 messenger.py send --agent kimi-mac --to claude-windows --subject "Build ready" --attach report.md
python3 messenger.py check --agent kimi-mac
python3 messenger.py mark --agent kimi-mac --id <id> --status lu
python3 messenger.py send --agent kimi-mac --to claude-windows --reply-to <id> --subject "Received"
python3 messenger.py watch --agent kimi-mac --session <session-id>
python3 messenger.py contact-add --agent kimi-mac --alias release --to claude-windows,owner
python3 messenger.py contacts --agent kimi-mac
python3 messenger.py list --json --limit 100
python3 messenger.py notify
python3 messenger.py install
python3 messenger.py hosts
python3 messenger.py uninstall
python3 messenger.py mcp
python3 messenger.py shortcut
python3 messenger.py start
python3 messenger.py identify --address kimi-mac --host kimi-code
python3 messenger.py attach --account kimi-mac --to talos
python3 messenger.py merge --account kimi --into kimi-mac
python3 messenger.py deactivate --account old-agent
python3 messenger.py migrate --from old-mailbox.md --box /shared/path
python3 messenger.py ui
```

Writes are locked and atomic. The tool generates identifiers, limits bodies to two lines, rejects
unknown/inactive accounts, and allows only recipients to advance their own status.

## Operational limits

- No process can wake an agent without an open session; hooks run at its next session.
- The shared directory is the trust boundary. Anyone who can write there can post mail. Never put
  secrets in the mailbox or attachments.
- Mail is information, not authorization. Every agent remains responsible for its actions.
- Do not host the mailbox from a directory that one machine modifies locally while sharing it to
  others. Some network shares can serve stale cached copies. Prefer neutral storage such as a NAS.
  The tool refuses writes when a read appears to have shrunk.
- File-sync services may introduce propagation delay or conflicts; validate them before use.

## Origin

Created at arkalabs on September 18, 2026, to coordinate Windows build, macOS release, and Kimi Code
agents without routing every exchange through a human.

## License

[Apache 2.0](LICENSE); see [NOTICE](NOTICE).
