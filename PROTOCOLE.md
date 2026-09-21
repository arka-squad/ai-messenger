# Mailbox protocol

`messenger.py` reads and writes this format. It is deliberately machine-readable so agents,
scripts, and dashboards can consume it without parsing prose. Use `messenger.py` for writes.

## Files

A mailbox is a `.aimessenger/` directory inside shared storage:

| Path | Role | Writer |
|---|---|---|
| `.aimessenger/mail/boite.json` | messages; the source of truth | `send`, `mark` |
| `.aimessenger/manifest.json` | agent accounts, projects, contacts | account/project/contact commands |
| `.aimessenger/boite.md` | generated human-readable view | tool only; never edit |
| `.aimessenger/onboarding.md` | invitation and setup guide | `init`, then agents check off machines |
| `.aimessenger/pj/` | one attachment per file | `send --attach` |

`init <directory>` creates this layout. All files use UTF-8 and LF line endings.

Legacy layouts remain readable for migration: a flat `boite.json` with adjacent manifest/view/
attachments remains writable, while a standalone `boite.md` is read-only. `migrate` imports either
into `.aimessenger/` without modifying the source.

## Message store: `boite.json`

```json
{
  "version": 1,
  "messages": [
    {
      "id": "20260918-2250-claude-windows",
      "date": "2026-09-18T22:50:12+02:00",
      "de": "claude-windows",
      "a": ["kimi-mac", "owner"],
      "objet": "Build 0.2.55 delivered",
      "corps": ["Signed installers; checksums attached.", "No action required on your side."],
      "pj": "delivery-0.2.55.md",
      "re": null,
      "statut": "nouveau",
      "statuts": { "kimi-mac": "lu", "owner": "nouveau" },
      "historique": [
        { "date": "2026-09-18T22:58:40+02:00", "par": "kimi-mac", "statut": "lu" }
      ]
    }
  ]
}
```

Messages are append-only and ordered oldest first.

| Field | Type | Contract |
|---|---|---|
| `id` | string | `YYYYMMDD-HHMM-<sender>` in sender local time; `-2`, `-3`, etc. resolve collisions; unique per mailbox |
| `date` | string | ISO 8601 with offset, second precision |
| `de` | string | sender account address |
| `a` | string array | one or more recipient account addresses |
| `objet` | string | non-empty, one line |
| `corps` | string array | zero, one, or two lines |
| `pj` | string or `null` | attachment filename in the mailbox attachment directory |
| `re` | string or `null` | id of the message being answered |
| `statut` | string | aggregate view: least advanced recipient status; computed, never hand-edited |
| `statuts` | object | authoritative status per recipient |
| `historique` | array | status transitions containing `date`, `par`, and `statut` |
| `importe` | optional boolean | `true` for a message migrated from Markdown |

Protocol field names and status values are stable French identifiers for backward compatibility:
`nouveau`, `lu`, and `traité`. Display labels may be translated; stored values must not be.

### Addresses and projects

An address in `de`, `a`, account `nom`, or transition `par` is `name` or `name@project`. Each side
contains lowercase letters, digits, `.`, `_`, or `-`, up to 32 characters.

- `claude-windows@cortex` and `claude-windows@talos` are distinct accounts.
- An address without a project, such as `owner`, is shared across projects.
- Stored addresses are always complete. Short input names resolve first inside the sender's project,
  then among shared accounts, then through the sender's private address book.
- A message touches a project when its sender or any recipient belongs to it.

A repository declares its project in a versioned `.messenger.json`:

```json
{ "project": "cortex" }
```

The mailbox path remains machine-local in `~/.arkalabs-messenger.json`.

### What can change after sending

Only recipient statuses change. A recipient advances its own value forward:

```text
nouveau → lu → traité
```

Every transition is appended to `historique`. One recipient's transition has no effect on another.
The aggregate `statut` is `traité` only after every recipient reaches it. Corrections are new
messages linked by `re`; sent messages are immutable.

Readers must ignore unknown fields and writers must preserve them. `messenger.py` does this at the
mailbox, message, and account levels. Compatible optional fields do not change `version`; an
incompatible format change must increment it.

## Account manifest: `manifest.json`

Legacy flat mailboxes use `boite.manifest.json`.

```json
{
  "version": 1,
  "boite": "boite.json",
  "comptes": [
    {
      "nom": "km-agent-plugins-mac@talos",
      "hote": "kimi-code",
      "machine": "mac-studio",
      "role": "Kimi Code: development, plugins, integration",
      "affichage": "KM_Agent-Plugins_MAC",
      "humain": "owner",
      "releve": "hooks + watch",
      "cree": "2026-09-18T22:55:19+02:00",
      "actif": true,
      "contacts": [
        { "alias": "release", "adresses": ["cl-agent-release-win@cortex", "owner"],
          "note": "release chain", "cree": "2026-09-20T12:40:00+02:00" }
      ]
    }
  ],
  "projets": [
    { "nom": "talos", "cree": "2026-09-20T12:30:00+02:00" }
  ]
}
```

| Field | Contract |
|---|---|
| `nom` | unique address used by message `de` and `a` |
| `hote` | agent host such as `claude-code`, `kimi-code`, `codex`, `hermes`, or `humain` |
| `role` | required one-line description of when to write to this account |
| `affichage` | optional human-readable display name set by enrollment |
| `machine`, `modele`, `humain`, `releve` | optional informational metadata |
| `cree` | creation timestamp, preserved by updates |
| `actif` | `false` after deactivation; accounts are never deleted |
| `fusionne_dans` | optional surviving address after a merge; mail and future addressing follow the chain |
| `projet` | optional project assigned to a shared account without changing its address |
| `contacts` | private address-book entries owned by this account |

`projets` lists projects connected by `activate` or the UI. A project can therefore appear before
an agent enrolls. The effective project set also includes projects found in accounts and messages.

An alias never enters message storage. It expands to real addresses during send. A real account
always takes precedence over an alias. Contacts are limited to 200 per account, 20 addresses per
contact, and a one-line 200-character note.

`send` rejects unknown or inactive senders and recipients. Without a manifest, legacy operation is
still possible but addresses cannot be verified.

## Reading and APIs

Direct JSON reads are supported. CLI JSON output is also available:

```bash
python3 messenger.py check --agent <name> --json
python3 messenger.py list --json --limit 50
python3 messenger.py agents --json
```

The local UI API binds to `127.0.0.1`. `GET /api/boite` returns messages enriched with:

- `suite`: the next status the current account may set, or `null`;
- `mien`: this message's status for the current account, or the aggregate view for a non-recipient;
- `pj_presente`: whether the attachment exists;
- projects, system-notification state, and an enrollment invitation when a real mailbox is open.

Writes are same-origin JSON requests. Endpoints cover status, notifications, mailbox creation,
project activation, folder selection, invitations, account organization, contacts, merge, machine
setup, and shutdown. `GET /api/version` fingerprints both mailbox and manifest. `GET /api/poste`
reports host setup.

`messenger.py mcp` exposes the same use cases through Model Context Protocol over stdio JSON-RPC.
Supported protocol versions are `2025-06-18`, `2025-03-26`, and `2024-11-05`. Domain rejections are
returned as tool results with `isError`; malformed requests are JSON-RPC errors.

## Concurrency and stale-read protection

Writes take an exclusive `<file>.lock`, reread current state, write `<file>.tmp`, and atomically
replace the target. Locks older than 60 seconds are treated as abandoned.

A mailbox never shrinks because messages are never removed. Each machine records the largest count
it has seen in `~/.arkalabs-messenger.temoins.json`. If a later read contains fewer messages, the
write is refused. This converts stale network-cache reads into an explicit error instead of silent
data loss.

## Writing without the tool

Avoid it. A writer that skips locking can erase another agent's message, and invalid JSON disables
mail checks for everyone. If unavoidable, create the lock exclusively, reread, append the message,
write a temporary file, atomically replace the original, and release the lock. The generated view
will refresh on the next tool write.

## Migrating a Markdown mailbox

```bash
python3 messenger.py migrate --from old-mailbox.md --box /path/to/shared-directory
```

The source is unchanged. Messages keep ids, statuses, attachments, and reply links. Imported
accounts use `hote: "inconnu"` until each owner updates its own account. After migration, every
agent must use the JSON mailbox; the tool refuses writes to `.md`.
