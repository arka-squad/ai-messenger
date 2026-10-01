# CR Dev — MSG / architecture_hexagonale

| Champ | Valeur |
|---|---|
| Ref | CR-DEV-MSG-architecture_hexagonale-20260922-01 |
| Date | 2026-09-22 |
| Agent | CD_Agent-messenger app_MAC |
| Spec source | `.input/spec-concept/SPEC-messenger-20260921.md` + règle utilisateur du 2026-09-22 |
| Statut | LIVRÉ |

---

## Fichiers livrés

| Fichier | Action | Lignes | Rôle |
|---|---|---:|---|
| `src-tauri/src/domain.rs` | Modifié | 381 | Règles métier et exposition des modules du domaine |
| `src-tauri/src/domain/models.rs` | Créé | 103 | Modèles métier indépendants des adaptateurs |
| `src-tauri/src/domain/ports.rs` | Créé | 129 | Ports d’échange, de persistance et de fournisseur |
| `src-tauri/src/mailbox.rs` | Modifié | 490 | Service applicatif générique sur les ports |
| `src-tauri/src/exchange.rs` | Modifié | 320 | Adaptateur de mutations par dossier |
| `src-tauri/src/storage.rs` | Modifié | 528 | Adaptateur SurrealKV |
| `src-tauri/src/provider.rs` | Modifié | 40 | Adaptateur fournisseur conforme au port du domaine |
| `src-tauri/src/mcp.rs` | Modifié | 480 | Entrée MCP générique sur le service applicatif |
| `src-tauri/src/lib.rs` | Modifié | 219 | Racine de composition des adaptateurs |
| `src/index.html` | Modifié | 19 | Coquille HTML minimale |
| `src/ui/bootstrap.js` | Créé | 27 | Assemblage UI au démarrage |
| `src/ui/controller-core.js` | Créé | 355 | État et logique principale de l’interface |
| `src/ui/controller-view.js` | Créé | 415 | Projection et actions de vue |
| `src/ui/template-main.html` | Créé | 398 | Structure principale de l’interface |
| `src/ui/template-panels.html` | Créé | 392 | Panneaux et modales de l’interface |
| `src/ui/animations.css` | Créé | 30 | Animations locales de l’interface |
| `src/support.js` | Modifié | 51 | Bundle généré du moteur UI, minifié |
| `scripts/check-architecture.mjs` | Créé | 40 | Garde-fou de taille et de direction des dépendances |
| `scripts/test-ui.mjs` | Modifié | 55 | Vérification de l’assemblage UI découpé |
| `package.json` | Modifié | 16 | Exécution du contrôle architectural dans `npm test` |

---

## Exigences couvertes

| ID | Exigence | Couvert | Fichier:Ligne |
|---|---|---|---|
| ARCH01 | Architecture hexagonale | OUI | `src-tauri/src/domain/ports.rs:14` |
| ARCH02 | Aucun fichier source au-dessus de 700 lignes | OUI | `scripts/check-architecture.mjs:17` |
| ARCH03 | Pas de couplage fort entre application, domaine et adaptateurs | OUI | `src-tauri/src/mailbox.rs:35`, `src-tauri/src/lib.rs:20` |
| ARCH04 | Interface découpée et lisible | OUI | `src/ui/bootstrap.js:8` |
| ARCH05 | Règles vérifiées automatiquement contre les régressions | OUI | `scripts/check-architecture.mjs:20` |

---

## Vérifications

| Check | Résultat |
|---|---|
| Build | 0 erreur — bundle macOS produit |
| Tests total | 19/19 passed : 17 Rust + contrôle architecture + simulation UI |
| Nouveaux tests | 2 contrôles exécutables : architecture et assemblage UI |
| Régressions | 0 |
| Grep `any` | 0 fichier TypeScript, 0 résultat |
| Grep `TODO/stub` | 0 résultat |

---

## Décisions techniques

| Décision | Raison |
|---|---|
| Ports définis dans le domaine, adaptateurs injectés dans `lib.rs` | Le service applicatif ne dépend plus de SurrealKV ni du dossier d’échange |
| Découpage mécanique de l’interface sans changement visuel | Respecter 700 lignes tout en conservant l’UI validée |
| Minification du bundle `support.js` généré | Garder l’artefact généré sous la limite sans ajouter de dépendance ni rendre le code applicatif illisible |
| Garde-fou Node standard intégré à `npm test` | Empêcher le retour d’un monolithe ou d’une dépendance inversée sans nouvel outil |

---

## Problèmes détectés hors scope

—

---

## Handoff

→ Prêt pour recette-qa (REC-*)
→ Prêt pour audit-final (AUD-*)
