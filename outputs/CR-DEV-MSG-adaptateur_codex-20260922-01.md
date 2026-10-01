# CR Dev — MSG / adaptateur_codex

| Champ | Valeur |
|---|---|
| Ref | CR-DEV-MSG-adaptateur_codex-20260922-01 |
| Date | 2026-09-22 |
| Agent | CD_Agent-messenger app_MAC |
| Spec source | `.input/spec-concept/SPEC-messenger-20260921.md` §7.2 et §11 bis |
| Statut | LIVRÉ |

---

## Fichiers livrés

| Fichier | Action | Lignes | Rôle |
|---|---|---:|---|
| `src-tauri/src/provider/codex.rs` | Créé | 279 | Adaptateur Codex supporté : sonde, équipement et remise par `queue` |
| `src-tauri/src/provider.rs` | Modifié | 120 | Registre extensible et fournisseur fictif de contrat |
| `src-tauri/src/domain/models.rs` | Modifié | 122 | État fournisseur et route locale de retour |
| `src-tauri/src/domain/ports.rs` | Modifié | 141 | Contrat commun des cinq capacités et persistance de route |
| `src-tauri/src/domain.rs` | Modifié | 382 | Sérialisation de l’atteinte fournisseur |
| `src-tauri/src/storage.rs` | Modifié | 592 | Schéma v2 et route demande → fournisseur/session persistante |
| `src-tauri/src/mailbox.rs` | Modifié | 514 | Ouverture d’une demande avec route de retour locale |
| `src-tauri/src/mcp.rs` | Modifié | 502 | Session de retour exigée par `demander_validation` |
| `src-tauri/src/lib.rs` | Modifié | 305 | Composition, commandes UI, remise du verdict ou de la discussion |
| `src/runtime.js` | Modifié | 51 | Adaptateur UI vers les commandes fournisseur |
| `src/simulation.js` | Modifié | 67 | Retrait de Codex des fournisseurs simulés |
| `src/ui/controller-core.js` | Modifié | 364 | Chargement du statut réel et signalement des incidents |
| `src/ui/controller-view.js` | Modifié | 441 | Équipement de Codex depuis la fenêtre |
| `src/ui/template-panels.html` | Modifié | 395 | Ligne fournisseur actionnable et erreur lisible |
| `scripts/test-ui.mjs` | Modifié | 65 | Vérification du statut et de l’équipement fournisseur |

---

## Exigences couvertes

| ID | Exigence | Couvert | Fichier:Ligne |
|---|---|---|---|
| F01 | Contrat commun des cinq capacités, sans vocabulaire d’hôte | OUI | `src-tauri/src/domain/ports.rs:32` |
| F02 | Version Codex figée sur la preuve locale | OUI | `src-tauri/src/provider/codex.rs:15` |
| F03 | Sonde de `agents` et `queue` au démarrage | OUI | `src-tauri/src/provider/codex.rs:118` |
| F04 | Remise à une session existante, y compris inactive | OUI | `src-tauri/src/provider/codex.rs:53` |
| F05 | Verdict rapporté à la session qui attend | OUI | `src-tauri/src/lib.rs:226` |
| F06 | Équipement par fusion, sans écraser une configuration existante | OUI | `src-tauri/src/provider/codex.rs:71` |
| F07 | Route de retour persistée sans modifier la mutation partagée | OUI | `src-tauri/src/storage.rs:329` |
| F08 | Statut réel et geste d’équipement visibles dans la fenêtre | OUI | `src/ui/controller-view.js:12` |
| F09 | Ajouter un fournisseur passe par une ligne de registre | OUI | `src-tauri/src/provider.rs:17` |
| F10 | Codex retiré des données simulées | OUI | `src/simulation.js:38` |

---

## Vérifications

| Check | Résultat |
|---|---|
| Build | 0 erreur — bundle macOS produit |
| Tests total | 21/21 passed : 19 Rust + contrôle architecture + simulation UI |
| Nouveaux tests | 4 : sonde/file Codex, équipement, non-écrasement, persistance de route |
| Régressions | 0 |
| Grep `any` | 0 fichier TypeScript, 0 résultat |
| Grep `TODO/stub` | 0 résultat |

---

## Décisions techniques

| Décision | Raison |
|---|---|
| Route fournisseur/session conservée dans la base locale | La session ne fait pas partie de la mutation partagée définie par la spec |
| Version exigée `codex-cli 0.152.0` | Ne pas supposer que `agents` et `queue` existent sur une autre version |
| Remise par `codex queue` sans protocole App Server | Utiliser la surface supportée ; la surface expérimentale reste hors du chemin principal |
| Nouveau MCP nommé `arkalabs-messenger-app` | Ne pas écraser le MCP du prototype déjà installé |
| Atteinte annoncée `next_start` | `queue` garantit la file d’une session existante mais ne prouve pas qu’elle travaille à l’instant présent |

---

## Problèmes détectés hors scope

—

---

## Handoff

→ Prêt pour recette-qa (REC-*)
→ Prêt pour audit-final (AUD-*)
