# CR Dev — MSG / multiposte

| Champ | Valeur |
|---|---|
| Ref | CR-DEV-MSG-multiposte-20260922-01 |
| Date | 2026-09-22 |
| Agent | CD_Agent-messenger app_MAC |
| Spec source | `.input/spec-concept/SPEC-messenger-20260921.md` §4, §11 bis lot 4, §12.1 et §12.4 |
| Statut | LIVRÉ |

---

## Fichiers livrés

| Fichier | Action | Lignes | Rôle |
|---|---|---|---|
| `src-tauri/Cargo.toml` | Modifié | 24 | Sélecteur natif de dossier et temporisation asynchrone |
| `src-tauri/Cargo.lock` | Modifié | 7675 | Verrouillage reproductible de la dépendance native |
| `src-tauri/src/exchange.rs` | Modifié | 535 | Dossier interchangeable, publication concurrente sans écrasement, reprise indexée et relecture vérifiée |
| `src-tauri/src/lib.rs` | Modifié | 392 | Composition multiposte, choix/persistance du dossier et relève automatique |
| `src-tauri/src/mailbox.rs` | Modifié | 529 | Preuve d’échange entre deux installations et retour du marquage |
| `src/runtime.js` | Modifié | 57 | Adapter UI des commandes d’emplacement |
| `src/simulation.js` | Modifié | 66 | Retrait du chemin et de la veille simulés |
| `src/ui/controller-core.js` | Modifié | 364 | Chargement de l’état réel de l’emplacement |
| `src/ui/controller-view.js` | Modifié | 465 | Branchement du sélecteur et état réel de la relève |
| `src/ui/template-main.html` | Modifié | 398 | Affichage du dossier et de la cadence réels |
| `src/ui/template-panels.html` | Modifié | 398 | Choix natif du dossier partagé et erreur lisible |
| `scripts/test-ui.mjs` | Modifié | 74 | Vérification du branchement UI de l’emplacement |

---

## Exigences couvertes

| ID | Exigence | Couvert | Fichier:Ligne |
|---|---|---|---|
| M01 | Le dossier partagé se choisit dans la fenêtre et se mémorise localement | OUI | `src-tauri/src/lib.rs:93`, `src/ui/controller-view.js:350` |
| M02 | Deux installations gardent leurs bases locales et visent le même journal partagé | OUI | `src-tauri/src/lib.rs:343`, `src-tauri/src/mailbox.rs:491` |
| M03 | Une publication confirmée est relue et aucune publication concurrente n’en écrase une autre | OUI | `src-tauri/src/exchange.rs:165`, `src-tauri/src/exchange.rs:508` |
| M04 | Une lecture incomplète ou d’empreinte invalide est réessayée avant d’être ignorée | OUI | `src-tauri/src/exchange.rs:401` |
| M05 | La reprise se fait au démarrage puis toutes les 10 secondes sans écoute active | OUI | `src-tauri/src/lib.rs:357` |
| M06 | Après la première synchronisation complète, le listage se limite au nouveau et à sept jours de rattrapage | OUI | `src-tauri/src/exchange.rs:256` |
| M07 | Changer de boîte remet le curseur local à zéro pour reprendre tout le nouvel emplacement | OUI | `src-tauri/src/exchange.rs:72` |
| M08 | L’interface affiche le chemin, la joignabilité et la cadence réels | OUI | `src/runtime.js:39`, `src/ui/controller-view.js:89` |
| M09 | Le chemin et la veille multiposte ne viennent plus de la simulation | OUI | `src/simulation.js:1`, `src/ui/controller-core.js:10` |
| M10 | Message aller, marquage retour et rejeu idempotent fonctionnent entre deux installations | OUI | `src-tauri/src/mailbox.rs:491` |
| M11 | Architecture hexagonale et plafond de 700 lignes pour les sources maintenues | OUI | `scripts/check-architecture.mjs:1` |

---

## Vérifications

| Check | Résultat |
|---|---|
| Build | 0 erreur — bundle macOS produit |
| Tests total | 22/22 passed (20 Rust + architecture + UI) |
| Nouveaux tests | 2 |
| Régressions | 0 |
| Grep `any` | 0 |
| Grep `TODO/stub` | 0 |

---

## Décisions techniques

| Décision | Raison |
|---|---|
| `rfd` pour choisir le dossier | Sélecteur natif macOS/Windows sans demander de chemin à l’utilisateur |
| Écoute déclarée inactive et relève toutes les 10 secondes | Le contrat autorise l’échec de l’écoute ; le listage garantit la correction sans ajouter un watcher et ses modes de panne |
| Lien dur atomique puis repli vérifié sans remplacement | Le lien dur empêche l’écrasement concurrent ; sur un partage qui ne le supporte pas, l’empreinte devient la preuve annoncée |

---

## Problèmes détectés hors scope

—

---

## Handoff

→ Prêt pour recette-qa (REC-*)
→ Prêt pour audit-final (AUD-*)
