# Architecture

arkalabs-messenger uses **hexagonal architecture** in both Python and the UI. The domain knows
nothing about files, command lines, MCP, HTTP, or browsers, so storage and interfaces can change
without changing business rules.

```text
                 driving adapters                         driven adapters
             (trigger use cases)                    (used by application code)

   agent CLI ───────┐                                 ┌─ JSON mailbox + Markdown view
   MCP server ──────├▶  application / use cases  ───▶ ├─ JSON account manifest
   local web API ────┘       ┌─── domain ───┐          ├─ attachment directory
                            │ messages, mailbox, accounts │   ├─ legacy Markdown reader
                            │ validation and status rules │   ├─ system notifications
                            └────────────────────────┘   └─ system clock
```

## Dependency rule

Dependencies point inward, never outward.

| Layer | May import | Must not import |
|---|---|---|
| `domain/` | Python standard library | everything else |
| `application/` | `domain` | `adapters`, `bootstrap` |
| `adapters/driven/` | `application`, `domain`, `adapters/codec` | `adapters/driving` |
| `adapters/driving/` | `application`, `domain`, `adapters/codec` | `adapters/driven` |
| `bootstrap.py` | every layer; it is the composition root | — |

Quick check, expected to print nothing:

```bash
grep -rn "import" src/arkalabs_messenger/domain src/arkalabs_messenger/application | grep -E "adapters|bootstrap"
grep -rn "import" src/arkalabs_messenger/adapters/driving | grep "driven"
```

## Python core

| File | Responsibility |
|---|---|
| `domain/modele.py` | immutable messages, drafts, mailbox and manifest aggregates, accounts, contacts, projects, address resolution, two-line bodies, and per-recipient forward-only statuses |
| `domain/erreurs.py` | actionable domain rejections |
| `application/ports.py` | mailbox, manifest, attachments, clock, notifier, and legacy-source interfaces |
| `application/messagerie.py` | initialize, register, enroll, identify, projects, contacts, send, check, mark, list, watch, merge, and import use cases |
| `application/annonces.py` | system notifications for messages that appear |
| `adapters/codec.py` | JSON contract from `PROTOCOLE.md`, preserving unknown fields |
| `adapters/driven/disposition.py` | canonical `.aimessenger/` layout and legacy layouts |
| `adapters/driven/temoin.py` | stale-read guard: a mailbox may never lose messages |
| `adapters/driven/` | atomic JSON repositories, generated Markdown, legacy reader, attachments, notifications, clock |
| `adapters/driving/cli.py` | agent-facing command line |
| `adapters/driving/mcp.py` | hand-written stdio MCP server |
| `adapters/driving/web.py` | local JSON API and built UI server |
| `adapters/driving/hotes.py` | supported AI-host configuration and hook installation |
| `adapters/driving/poste.py` | machine-local mailbox/project/identity configuration |
| `bootstrap.py` | production wiring |

## Interface

The UI mirrors the same separation:

| Path | Responsibility |
|---|---|
| `ui/src/domain/` | pure calculations: filtering, grouping, threads, traffic, time formatting, bilingual dictionaries |
| `ui/src/application/` | ports, mailbox watch, and language context |
| `ui/src/adapters/` | HTTP API and browser preferences |
| `ui/src/ui/` | React components and styles |
| `ui/src/design/` | arkalabs design tokens and themes |
| `ui/src/main.tsx` | composition root |
| `ui/vite/api-messenger.ts` | development plugin that runs and reloads the Python API |

The interface never decides who may advance a status. The domain computes `suite` per message; the
UI only displays it and requests the transition.

## Structural decisions

- **Python standard library only.** Agents can run the tool anywhere without installing packages.
- **JSON is the source of truth.** Generated Markdown is never read back.
- **Status belongs to each recipient.** One recipient cannot clear another recipient's mail.
- **Protocol values are stable.** `nouveau`, `lu`, and `traité` remain data values even when the UI
  displays English labels.
- **English is the interface default.** Language is a machine-local preference, never mailbox data;
  French remains available through the switch.
- **Every write rereads under lock.** Failed operations write nothing.
- **A shorter read blocks writes.** The machine-local witness turns stale network reads into explicit
  refusal instead of silent message loss.
- **The UI ships prebuilt.** `ui/dist` is versioned and fingerprinted; tests reject stale assets.
- **A project is a label, not a directory.** Organizing a shared account never changes its address.
- **The web API binds only to `127.0.0.1`** and accepts same-origin JSON writes.
- **MCP uses hand-written stdio.** This preserves Python 3.8 support and opens no port.
- **Hosts are equipped per machine.** Repositories only carry `.messenger.json`; host settings live
  in the host's own configuration.

## Extending

For new storage, implement `DepotBoite` and `DepotAnnuaire`, then wire them in
`bootstrap.Usine.ouvrir`. For another driving channel, add an adapter under `adapters/driving/`
that calls `Messagerie`. For another AI host, add its configuration, format, and hook capabilities
to `hotes.HOTES`. Domain and use cases should not change.

## Verification

```bash
python3 -m unittest   # Python domain, use cases, adapters, CLI, API, MCP, and hosts
npm test              # UI domain, watch, HTTP adapter, and dictionary parity
npm run typecheck     # strict TypeScript
npm run build         # production UI and committed ui/dist
```
