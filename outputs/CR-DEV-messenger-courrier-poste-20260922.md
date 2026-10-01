# CR de développement — Courrier d’un poste

- Projet : `messenger-app`
- Agent : `CD_Agent-messenger app_MAC` (`cd-agent-messenger-app-mac@messenger-app`)
- Date : 2026-09-22
- Verdict : PASS

## Livré

- Messages et marquages immuables, un fichier par mutation, écriture temporaire puis renommage atomique.
- Empreinte SHA-256 relue et vérifiée avant confirmation de publication.
- Base locale SurrealKV partagée par la fenêtre Tauri et le serveur MCP local `127.0.0.1:47652/mcp`.
- Outils MCP : `relever`, `lire`, `envoyer`, `repondre`, `marquer`.
- Statut propre à chaque destinataire, monotone (`nouveau` → `lu` → `traité`).
- Interface alimentée par la base réelle ; les 22 courriers simulés ont été retirés.

## Preuves

- `npm test` : PASS — test UI/runtime + 17 tests Rust.
- Scénario MCP : envoi réel → relève → marquage traité → relève vide.
- Corruption d’empreinte : mutation refusée à l’intégration.
- `npm run build -- --bundles app` : PASS.
- Bundle : `src-tauri/target/release/bundle/macos/arkalabs Messenger.app`.
- Contrôle : aucun TODO/FIXME/stub ; tous les fichiers modifiés hors maquette historique font moins de 700 lignes.

## Simplification assumée

Le serveur MCP est local au poste et démarre avec l’application. Le multiposte et le réveil fournisseur restent réservés aux fonctionnalités 3 et 4 de l’ordre produit.

Signé : `cd-agent-messenger-app-mac@messenger-app`
