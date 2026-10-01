# CR Dev — MSG / parcours_claude

| Champ | Valeur |
|---|---|
| Ref | CR-DEV-MSG-parcours_claude-20260922-01 |
| Date | 2026-09-22 |
| Agent | CD_Agent-messenger app_MAC |
| Spec source | Retour utilisateur du 22/09/2026 ; `.input/spec-concept/SPEC-messenger-20260921.md` §12.3 |
| Statut | LIVRÉ PARTIEL |

---

## Fichiers livrés

| Fichier | Action | Lignes | Rôle |
|---|---|---|---|
| `src-tauri/src/provider/claude.rs` | Modifié | 611 | Retrait du lancement de sessions et statut conforme à la portée optionnelle du canal |
| `src-tauri/src/provider/claude_tests.rs` | Modifié | 166 | Preuve qu’un Claude équipé ne propose plus d’action de lancement |
| `src/ui/controller-view.js` | Modifié | 465 | Retour à l’action d’équipement seule |
| `src/ui/template-panels.html` | Modifié | 398 | Parcours explicite : une invite collée dans chaque agent déjà ouvert |

---

## Exigences couvertes

| ID | Exigence | Couvert | Fichier:Ligne |
|---|---|---|---|
| P01 | Messenger ne crée ni ne relance les agents Claude | OUI | `src-tauri/src/provider/claude.rs:186`, `src-tauri/src/provider/claude.rs:439` |
| P02 | L’équipement reste un geste unique par machine | OUI | `src-tauri/src/provider/claude.rs:190`, `src-tauri/src/provider/claude_tests.rs:33` |
| P03 | L’interface indique de coller la même invite dans chaque agent ouvert | OUI | `src/ui/template-panels.html:371` |
| P04 | Le push Claude est un bonus borné à une session vivante ayant activé le canal | OUI | `src-tauri/src/provider/claude.rs:113`, `src-tauri/src/provider/claude.rs:445` |
| P05 | Architecture hexagonale et plafond de 700 lignes pour les sources maintenues | OUI | `scripts/check-architecture.mjs:1` |

---

## Vérifications

| Check | Résultat |
|---|---|
| Build | 0 erreur — bundle macOS reconstruit sans lanceur Claude |
| Tests total | 26/26 passed (23 Rust + canal Claude + architecture + UI) |
| Nouveaux tests | 0 ; assertions Claude mises à jour |
| Régressions | 0 |
| Grep `any` | 0 |
| Grep `TODO/stub` | 0 |

---

## Décisions techniques

| Décision | Raison |
|---|---|
| Supprimer entièrement le lanceur Terminal | Messenger n’orchestre pas les agents ; l’utilisateur invite ceux qui existent déjà |
| Conserver le canal Claude comme push optionnel | La spec garantit la relève par l’agent et interdit de faire dépendre la livraison du push |

---

## Problèmes détectés hors scope

| Problème | Fichier | Sévérité |
|---|---|---|
| La copie d’invite et `m_enroler` restent simulés ; le parcours cinq agents → cinq comptes n’est pas encore exécutable dans la réécriture | `src/simulation.js`, `src/ui/controller-view.js`, `src-tauri/src/mcp.rs` | Majeur |

---

## Handoff

→ Retour développement : implémenter l’invite et l’enrôlement réels
→ Non prêt pour recette du parcours complet
