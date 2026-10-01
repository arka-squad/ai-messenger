# CR Dev — MSG / adaptateur_claude

| Champ | Valeur |
|---|---|
| Ref | CR-DEV-MSG-adaptateur_claude-20260922-01 |
| Date | 2026-09-22 |
| Agent | CD_Agent-messenger app_MAC |
| Spec source | `.input/spec-concept/SPEC-messenger-20260921.md` §7 et §7.1 ; `.input/docs/docs-claude-reveille.md` |
| Statut | LIVRÉ |

---

## Fichiers livrés

| Fichier | Action | Lignes | Rôle |
|---|---|---|---|
| `package.json` | Modifié | 20 | SDK MCP officiel, compilation du canal et validation globale |
| `package-lock.json` | Modifié | 1481 | Verrouillage reproductible du SDK MCP 1.30.0 |
| `.gitignore` | Modifié | 5 | Exclusion du binaire sidecar généré |
| `channel/claude-channel.ts` | Créé | 141 | Canal MCP stdio Claude, outils bidirectionnels et filtrage de l’expéditeur |
| `channel/claude-channel.test.ts` | Créé | 124 | Preuve du contrat MCP, du proxy d’outils et du filtrage entrant |
| `scripts/build-claude-channel.mjs` | Créé | 20 | Compilation autonome et multi-cible du sidecar avec Bun |
| `src-tauri/Cargo.toml` | Modifié | 28 | WebSocket Axum et dépendances du test d’intégration |
| `src-tauri/Cargo.lock` | Modifié | 7714 | Verrouillage des dépendances Rust |
| `src-tauri/tauri.conf.json` | Modifié | 26 | Embarquement du sidecar dans le bundle natif |
| `src-tauri/src/provider/claude.rs` | Créé | 611 | Adaptateur Claude, équipement sûr, sessions vivantes et transport authentifié |
| `src-tauri/src/provider/claude_tests.rs` | Créé | 166 | Tests de configuration, portée de session et trajet WebSocket complet |
| `src-tauri/src/provider.rs` | Modifié | 133 | Enregistrement de l’adaptateur et composition du serveur Claude |
| `src-tauri/src/mcp.rs` | Modifié | 564 | Contexte de route injecté sans exposer la session aux outils Claude |
| `src-tauri/src/lib.rs` | Modifié | 393 | Démarrage du canal avec la boîte applicative réelle |
| `src/simulation.js` | Modifié | 65 | Retrait du fournisseur Claude simulé |
| `scripts/test-ui.mjs` | Modifié | 74 | Mise à jour de la preuve UI après retrait de la simulation |

---

## Exigences couvertes

| ID | Exigence | Couvert | Fichier:Ligne |
|---|---|---|---|
| C01 | Le fournisseur respecte les cinq capacités du port commun | OUI | `src-tauri/src/provider/claude.rs:175` |
| C02 | Claude Code lance un serveur MCP de canal sur stdio | OUI | `channel/claude-channel.ts:29`, `channel/claude-channel.ts:139` |
| C03 | Le canal déclare `claude/channel` et émet `notifications/claude/channel` | OUI | `channel/claude-channel.ts:32`, `channel/claude-channel.ts:105` |
| C04 | Le canal vivant est l’identité de session ; elle n’est pas devinée ni exposée à Claude | OUI | `src-tauri/src/provider/claude.rs:291`, `src-tauri/src/mcp.rs:171` |
| C05 | Message et verdict reviennent par la même session vivante | OUI | `src-tauri/src/provider/claude.rs:113`, `src-tauri/src/provider/claude_tests.rs:155` |
| C06 | Une session absente n’est jamais annoncée comme atteinte | OUI | `src-tauri/src/provider/claude.rs:124`, `src-tauri/src/provider/claude_tests.rs:44` |
| C07 | L’expéditeur entrant est filtré avant injection dans Claude | OUI | `channel/claude-channel.ts:104`, `channel/claude-channel.test.ts:106` |
| C08 | Le transport local est authentifié et les identifiants sont protégés par les permissions du système | OUI | `src-tauri/src/provider/claude.rs:302`, `src-tauri/src/provider/claude.rs:550`, `src-tauri/src/provider/claude.rs:560` |
| C09 | L’équipement fusionne sans écraser un homonyme ni un fichier illisible | OUI | `src-tauri/src/provider/claude.rs:186`, `src-tauri/src/provider/claude_tests.rs:53` |
| C10 | Le push est annoncé comme optionnel et borné aux sessions qui ont activé le canal | OUI | `src-tauri/src/provider/claude.rs:439` |
| C11 | Le sidecar autonome est embarqué avec l’application | OUI | `src-tauri/tauri.conf.json:24`, `scripts/build-claude-channel.mjs:1` |
| C12 | Aucun relais d’approbation d’outil Claude n’est déclaré | OUI | `channel/claude-channel.ts:32` |
| C13 | Architecture hexagonale et plafond de 700 lignes pour les sources maintenues | OUI | `scripts/check-architecture.mjs:1` |

---

## Vérifications

| Check | Résultat |
|---|---|
| Build | 0 erreur — bundle macOS produit avec `Contents/MacOS/messenger-claude-channel` |
| Tests total | 26/26 passed (23 Rust + canal Claude + architecture + UI) |
| Nouveaux tests | 4 |
| Régressions | 0 |
| Grep `any` | 0 |
| Grep `TODO/stub` | 0 |

---

## Décisions techniques

| Décision | Raison |
|---|---|
| SDK MCP officiel 1.30.0 compilé en sidecar autonome Bun | Respecter le contrat Claude sans imposer Node, Bun ou des dépendances dans `.input` sur le poste cible |
| WebSocket local éphémère authentifié entre l’application et le sidecar | Conserver un canal temps réel bidirectionnel, borné à la machine et à une session vivante |
| Jeton aléatoire dans un descripteur temporaire privé | Refuser toute connexion locale non autorisée sans exposer de secret au domaine |
| Version Claude Code 2.1.274 sondée avec le drapeau de canal | N’activer que la surface locale effectivement prouvée |
| Aucun stockage différé pour Claude | La spécification interdit le réveil hors session : l’adaptateur retourne `NoSession` |
| Aucun relais `claude/channel/permission` | Les agents travaillent en permission complète et Messenger ne doit pas recréer l’approbation d’outils |

---

## Problèmes détectés hors scope

—

---

## Handoff

→ Prêt pour recette-qa (REC-*)
→ Prêt pour audit-final (AUD-*)
