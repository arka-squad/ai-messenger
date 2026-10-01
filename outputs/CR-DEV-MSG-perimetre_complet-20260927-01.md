# CR Dev — MSG / perimetre_complet

| Champ | Valeur |
| --- | --- |
| Ref CR | CR-DEV-MSG-perimetre_complet-20260927-01 |
| Date | 2026-09-27 |
| Agent | Codex |
| Spec source | [SPEC-messenger-20260921.md](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/.input/spec-concept/SPEC-messenger-20260921.md) et [concept](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/.input/spec-concept/CONCEPT-messenger-20260921.md) |
| Statut | LIVRÉ PARTIEL — pause demandée après le build macOS ; recette native exhaustive et Windows restantes |

Le périmètre fonctionnel est branché aux données et commandes natives. La simulation a été supprimée. Ce compte rendu sépare le code produit des preuves encore manquantes ; il ne vaut pas clôture du périmètre multiposte.

---

## Fichiers livrés

| Fichier | Action | Lignes | Rôle |
| --- | --- | ---: | --- |
| [src/assets/fonts/Inter.ttf](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src/assets/fonts/Inter.ttf) | Créé | binaire | Polices embarquées, licences et empreintes |
| [src/assets/fonts/JetBrainsMono.ttf](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src/assets/fonts/JetBrainsMono.ttf) | Créé | binaire | Polices embarquées, licences et empreintes |
| [src/assets/fonts/Poppins-Black.ttf](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src/assets/fonts/Poppins-Black.ttf) | Créé | binaire | Polices embarquées, licences et empreintes |
| [src/assets/fonts/Poppins-Bold.ttf](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src/assets/fonts/Poppins-Bold.ttf) | Créé | binaire | Polices embarquées, licences et empreintes |
| [src/assets/fonts/Poppins-ExtraBold.ttf](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src/assets/fonts/Poppins-ExtraBold.ttf) | Créé | binaire | Polices embarquées, licences et empreintes |
| [src/assets/fonts/Poppins-Light.ttf](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src/assets/fonts/Poppins-Light.ttf) | Créé | binaire | Polices embarquées, licences et empreintes |
| [src/assets/fonts/Poppins-Medium.ttf](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src/assets/fonts/Poppins-Medium.ttf) | Créé | binaire | Polices embarquées, licences et empreintes |
| [src/assets/fonts/Poppins-Regular.ttf](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src/assets/fonts/Poppins-Regular.ttf) | Créé | binaire | Polices embarquées, licences et empreintes |
| [src/assets/fonts/Poppins-SemiBold.ttf](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src/assets/fonts/Poppins-SemiBold.ttf) | Créé | binaire | Polices embarquées, licences et empreintes |
| [src/assets/fonts/inter-OFL.txt](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src/assets/fonts/inter-OFL.txt) | Créé | 93 | Polices embarquées, licences et empreintes |
| [src/assets/fonts/jetbrainsmono-OFL.txt](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src/assets/fonts/jetbrainsmono-OFL.txt) | Créé | 93 | Polices embarquées, licences et empreintes |
| [src/assets/fonts/poppins-OFL.txt](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src/assets/fonts/poppins-OFL.txt) | Créé | 93 | Polices embarquées, licences et empreintes |
| [src/assets/fonts/sources.json](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src/assets/fonts/sources.json) | Créé | 62 | Polices embarquées, licences et empreintes |
| [src/index.html](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src/index.html) | Modifié | 18 | Chargement local et démarrage |
| [src/presentation.js](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src/presentation.js) | Créé | 19 | Styles et état initial sans données simulées |
| [src/runtime.js](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src/runtime.js) | Modifié | 35 | Unique adaptateur UI → commandes natives |
| [src/tokens/fonts.css](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src/tokens/fonts.css) | Modifié | 22 | Polices locales et licences |
| [src/ui/animations.css](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src/ui/animations.css) | Modifié | 34 | Animations et chargement |
| [src/ui/bootstrap.js](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src/ui/bootstrap.js) | Modifié | 62 | Chargement de l’interface et accès clavier |
| [src/ui/controller-core.js](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src/ui/controller-core.js) | Modifié | 375 | Projections et actions réelles |
| [src/ui/controller-view.js](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src/ui/controller-view.js) | Modifié | 455 | Vues et dialogues branchés |
| [src/ui/i18n.js](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src/ui/i18n.js) | Créé | 212 | Libellés français et anglais |
| [src/ui/template-main.html](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src/ui/template-main.html) | Modifié | 399 | Écran principal de la maquette |
| [src/ui/template-panels.html](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src/ui/template-panels.html) | Modifié | 420 | Panneaux, demandes et maintenance |
| [src-tauri/src/delivery.rs](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/delivery.rs) | Créé | 165 | Remises et décisions confirmées |
| [src-tauri/src/domain/journal.rs](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/domain/journal.rs) | Créé | 220 | Mutations immuables et sérialisation canonique |
| [src-tauri/src/domain/models.rs](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/domain/models.rs) | Modifié | 185 | Contrats de données |
| [src-tauri/src/domain/ports.rs](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/domain/ports.rs) | Modifié | 62 | Ports d’échange, de stockage et de fournisseurs |
| [src-tauri/src/domain.rs](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/domain.rs) | Modifié | 393 | Invariants du domaine et types des mutations |
| [src-tauri/src/exchange.rs](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/exchange.rs) | Modifié | 599 | Journal daté, dépôt immuable, écoute et reprise |
| [src-tauri/src/exchange_tests.rs](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/exchange_tests.rs) | Créé | 117 | Vérifications métier et régressions |
| [src-tauri/src/lib.rs](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/lib.rs) | Modifié | 404 | Composition native et services de l’application |
| [src-tauri/src/mailbox/directory.rs](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/mailbox/directory.rs) | Créé | 458 | Comptes, identités, fusions et carnets |
| [src-tauri/src/mailbox/receive.rs](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/mailbox/receive.rs) | Créé | 311 | Relève, reprises et repères d’installation |
| [src-tauri/src/mailbox/requests.rs](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/mailbox/requests.rs) | Créé | 300 | Demandes, verdicts, réorientations et résultats |
| [src-tauri/src/mailbox/views.rs](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/mailbox/views.rs) | Créé | 297 | Lecture, fils et preuves visibles |
| [src-tauri/src/mailbox.rs](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/mailbox.rs) | Modifié | 432 | Cas d’usage et projections du courrier |
| [src-tauri/src/mailbox_tests.rs](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/mailbox_tests.rs) | Créé | 392 | Vérifications métier et régressions |
| [src-tauri/src/main.rs](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/main.rs) | Modifié | 5 | Bootstrap de la durabilité avant les threads |
| [src-tauri/src/mcp.rs](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/mcp.rs) | Modifié | 379 | Contrat des quinze outils des agents |
| [src-tauri/src/mcp_tests.rs](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/mcp_tests.rs) | Créé | 223 | Vérifications métier et régressions |
| [src-tauri/src/migration.rs](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/migration.rs) | Créé | 338 | Reprise neutre et vérification du prototype |
| [src-tauri/src/migration_tests.rs](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/migration_tests.rs) | Créé | 149 | Vérifications métier et régressions |
| [src-tauri/src/notifications.rs](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/notifications.rs) | Créé | 64 | Notifications natives et retour au message |
| [src-tauri/src/owner_commands.rs](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/owner_commands.rs) | Créé | 368 | Gestes de la fenêtre, sélecteurs et presse-papiers |
| [src-tauri/src/provider/claude.rs](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/provider/claude.rs) | Modifié | 597 | MCP et canal Claude authentifié |
| [src-tauri/src/provider/claude_http.rs](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/provider/claude_http.rs) | Créé | 48 | MCP et canal Claude authentifié |
| [src-tauri/src/provider/claude_tests.rs](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/provider/claude_tests.rs) | Modifié | 175 | Vérifications métier et régressions |
| [src-tauri/src/provider/codex.rs](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/provider/codex.rs) | Modifié | 297 | Adaptateur Codex vérifié et mise en file |
| [src-tauri/src/provider/kimi.rs](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/provider/kimi.rs) | Créé | 142 | Adaptateur Kimi, équipement MCP sans fausse atteinte |
| [src-tauri/src/provider.rs](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/provider.rs) | Modifié | 177 | Registre des fournisseurs |
| [src-tauri/src/retention.rs](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/retention.rs) | Créé | 335 | Conservation, dormance et suppression manuelle |
| [src-tauri/src/retention_tests.rs](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/retention_tests.rs) | Créé | 97 | Vérifications métier et régressions |
| [src-tauri/src/storage.rs](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/storage.rs) | Modifié | 311 | SurrealKV, schéma 3, reprise et blobs vérifiés |
| [src-tauri/src/storage_tests.rs](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/storage_tests.rs) | Créé | 129 | Vérifications métier et régressions |
| [src-tauri/src/test_support.rs](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/test_support.rs) | Créé | 82 | Support de livraison |
| [scripts/test-mcp-http.mjs](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/scripts/test-mcp-http.mjs) | Créé | 44 | Parcours réel avec le SDK MCP |
| [scripts/test-native.mjs](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/scripts/test-native.mjs) | Créé | 8 | Pilote des tests natifs avec WAL synchronisé |
| [scripts/test-ui.mjs](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/scripts/test-ui.mjs) | Modifié | 101 | Régressions des commandes et du clavier |
| [channel/claude-channel.test.ts](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/channel/claude-channel.test.ts) | Modifié | 124 | Vérifications métier et régressions |
| [channel/claude-channel.ts](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/channel/claude-channel.ts) | Modifié | 141 | Composant natif autonome du canal Claude |
| [package.json](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/package.json) | Modifié | 20 | Commandes de build et tests |
| [README.md](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/README.md) | Créé | 118 | Guide d’usage et de développement |
| [src-tauri/Cargo.toml](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/Cargo.toml) | Modifié | 33 | Dépendances natives et verrouillage |
| [src-tauri/Cargo.lock](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/Cargo.lock) | Modifié | 8236 | Dépendances natives et verrouillage |
| [src-tauri/tauri.conf.json](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/tauri.conf.json) | Modifié | 31 | Configuration de la fenêtre et du paquet |
| `src/simulation.js` | Supprimé | 0 | Suppression de la source de données fictives |

Le verrou Cargo est un fichier généré. Les 52 fichiers source contrôlés respectent la limite de 700 lignes.

---

## Exigences couvertes

Les identifiants I01–I11 reprennent l’ordre des invariants de la spécification.

| ID | Exigence | Couvert OUI–NON | Fichier:ligne |
| --- | --- | --- | --- |
| I01 | Message immuable et correction reliée | OUI | [src-tauri/src/mailbox.rs:122](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/mailbox.rs:122) |
| I02 | Statut propre à chaque destinataire, copies en lecture seule | OUI | [src-tauri/src/mailbox.rs:201](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/mailbox.rs:201) |
| I03 | Convergence monotone des statuts | OUI | [src-tauri/src/mailbox/views.rs:116](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/mailbox/views.rs:116) |
| I04 | Objet sur une ligne, corps de zéro à deux lignes réelles | OUI | [src-tauri/src/mailbox.rs:377](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/mailbox.rs:377) |
| I05 | Identité de session, enrôlement et reprise privée | OUI | [src-tauri/src/mailbox/directory.rs:123](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/mailbox/directory.rs:123) |
| I06 | Secrets de l’application absents du journal partagé | OUI | [src-tauri/src/mcp_tests.rs:164](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/mcp_tests.rs:164) |
| I07 | Courrier informatif et demande humaine précise pour un geste irréversible | OUI | [src-tauri/src/mcp.rs:10](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/mcp.rs:10) |
| I08 | Humain hors des comptes et de tout nouveau courrier | OUI | [src-tauri/src/domain.rs:25](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/domain.rs:25) |
| I09 | Publication confirmée par relecture et empreinte | OUI | [src-tauri/src/exchange.rs:167](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/exchange.rs:167) |
| I10 | Aucun dépôt n’écrase une autre mutation | OUI | [src-tauri/src/exchange.rs:188](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/exchange.rs:188) |
| I11 | Publication, intégration et portée de session distinctes | OUI | [src-tauri/src/mailbox/views.rs:169](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/mailbox/views.rs:169) |
| §2.3 | Validation, refus, discussion, prise en charge, clôture et résultat | OUI | [src-tauri/src/mailbox/requests.rs:1](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/mailbox/requests.rs:1) |
| §2.4 | Fusions, projets, contacts privés, PJ incomplètes et redemande | OUI | [src-tauri/src/mailbox/directory.rs:270](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/mailbox/directory.rs:270) |
| §2.6/12.2 | Repères exacts par installation, dormance et avertissement au retour | OUI | [src-tauri/src/retention.rs:42](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/retention.rs:42) |
| §3 | Base locale idempotente, migration de schéma, réouverture par second processus | OUI | [src-tauri/src/storage_tests.rs:7](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/storage_tests.rs:7) |
| §4/12.1/12.4 | Journal par jour de dépôt, reprise incrémentale, écoute 60 s / secours 10 s | OUI | [src-tauri/src/exchange.rs:1](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/exchange.rs:1) |
| §6 | Quinze outils MCP, refus métier et contrôle de l’acteur | OUI | [src-tauri/src/mcp.rs:179](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/mcp.rs:179) |
| §7 | Trois fournisseurs, registre extensible et fournisseur de test | OUI | [src-tauri/src/provider.rs:153](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/provider.rs:153) |
| §8 | Interface réelle, réglages persistés et gestes natifs | OUI — recette native exhaustive restante | [src-tauri/src/owner_commands.rs:13](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/owner_commands.rs:13) |
| §9 | Incidents nommés, reprise et pièces jointes lisibles incomplètes | OUI | [src-tauri/src/mailbox/receive.rs:1](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/mailbox/receive.rs:1) |
| §10 | Migration réelle, neutre et sans perte vérifiée compte par compte | OUI | [src-tauri/src/migration_tests.rs:68](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/migration_tests.rs:68) |
| §11bis/4 | Installation et concurrence native macOS ↔ Windows | NON — accès SSH Windows refusé | [README.md:116](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/README.md:116) |
| §11bis/B | Conformité visuelle intégrale dans les deux applications installées | NON — vérification navigateur seulement | [src/ui/template-main.html:1](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src/ui/template-main.html:1) |
| §12.2 | Un an minimum, aperçu annulable, références protégées, aucune purge automatique | OUI | [src-tauri/src/retention.rs:300](/Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/src/retention.rs:300) |

---

## Vérifications

| Vérification | Résultat |
| --- | --- |
| Build | Build macOS Intel final réussi en 8 min 27 s. Application signée localement (ad hoc), signature vérifiée. DMG UDZO créé et somme de contrôle vérifiée par hdiutil. Build Windows non exécuté. |
| Tests total | Suite finale : 45 Rust réussis, 2 vérifications externes hors suite ; canal Bun réussi, UI et architecture réussies. Les 2 vérifications externes ont été exécutées séparément et réussissent. |
| Nouveaux tests | +22 tests Rust ordinaires par rapport aux 23 du point de départ, plus 2 vérifications réelles du prototype et du SMB. Contrôles UI et canal étendus. |
| Régressions | Invariants, SDK MCP réel, corps multilignes, acteur usurpé, copies, concurrence, résultats, reprise après coupure et second processus vérifiés. |
| Grep any | Aucun type TypeScript `any` ajouté ; occurrences Rust `any()` et `cfg(any(...))` légitimes. |
| Grep TODO / stub | Aucun TODO ou stub de production trouvé dans le périmètre. Fournisseur fictif limité à `cfg(test)`. |
| Prototype réel | 430 messages, 27 comptes bruts et 150 empreintes PJ ; identifiants, statuts, historiques, métadonnées et octets conservés. Vérification finale après optimisation réussie en 147,54 s. Source inchangée, aucun réveil historique. |
| SMB réel | Dépôt, relecture, empreinte PJ et écoute native réussis dans un sous-dossier isolé. Publication atomique par lien non disponible sur ce partage ; relecture et empreinte restent requises. |
| Build dev réel | Reprise terminée sur le partage indiqué ; SDK MCP connecté, 15 outils présents, contrôle en lecture seule sans compte ni courrier créé. |
| Réouverture native | Copie du profil après arrêt relue dans un nouveau processus : schéma 3, empreinte de reprise exacte et 430 messages conservés. |
| Interface | Rendu et arbre d’accessibilité du navigateur vérifiés sur les vues réelles ; clavier, confinement du focus et fermeture des dialogues FR/EN contrôlés. Accès natif CUA indisponible. Recette native exhaustive et clic sur notification restent à réaliser. |

Artefacts Apple : [application macOS Intel](</Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/target/release/bundle/macos/arkalabs Messenger.app>) et [DMG](</Users/jeremygrimonpont/workspace/ARKA_LABS/LABS_PRODUCTS/messenger/src-tauri/target/release/bundle/dmg/arkalabs Messenger_0.1.0_x64.dmg>). Signature locale ad hoc ; aucune signature Developer ID ni notarisation effectuée.

Empreinte de la copie du prototype vérifiée : `80862634bad6282f3a504a5d0a5f0f32c76de68d6ff9da99f4e6a299d387bf5b`. La migration est une reprise unique de cette copie à date ; les nouvelles écritures ultérieures du prototype ne sont pas synchronisées automatiquement.

---

## Décisions techniques

| Décision | Raison |
| --- | --- |
| JSON canonique conservé comme texte dans Surreal | Éviter la disparition des champs null lors de la conversion des anciennes mutations immuables. |
| WAL synchronisé au bootstrap avant les threads | Les écritures locales confirmées doivent survivre au redémarrage du processus. |
| Test de réouverture dans un second processus | Vérifier le redémarrage réel, indépendamment du cycle de fermeture asynchrone du SDK dans un même processus. |
| Prédicats SQL concrets et carnets projetés une fois | La mesure sur la boîte réelle montre 1 296 ms pour le filtre OR générique, 349 ms pour le filtre indexé. Éviter de relire tous les comptes pour chaque carnet. |
| Codex : file acceptée = prochaine ouverture | Ne pas annoncer une remise dans une session vivante sans preuve. |
| Claude et Kimi : MCP garanti ; push déclaré séparément | Ne pas créer une autre session pour prétendre atteindre celle ouverte par l’humain. |
| Arrêt de l’application et de ses outils décrit dans la fenêtre | La composition native arrête ses services avec le processus ; le libellé de la maquette promettant une continuité a été corrigé pour rester vrai. |
| Polices et composant Claude embarqués | L’usage de l’application installée ne dépend pas de runtimes ou de ressources web à installer. |

---

## Problèmes détectés hors scope

| Problème | Fichier / système | Sévérité |
| --- | --- | --- |
| Compte `grimo` et clé SSH du Mac refusés par GrimWorkshop.local. Clé d’hôte vérifiée et autorisée par l’Owner ; moyen d’authentification attendu. | Accès SSH Windows | Bloque la recette et la clôture multiposte. |
| `hdiutil create` attendait le service DiskImages sans produire d’image. Essai `makehybrid` puis conversion UDZO réussi. | Outil de packaging Apple | Résolu : paquet final créé par makehybrid puis conversion UDZO, vérification réussie. |
| Contrôle natif de l’interface indisponible dans cette session. | CUA macOS | Empêche de certifier la conformité visuelle et les gestes natifs exhaustifs. |

---

## Handoff

→ Travail mis en pause à la demande de l’Owner après production du build macOS. Code fonctionnel et preuves conservés pour la reprise de recette-qa (REC-*).
→ Audit-final (AUD-*) et statut de livraison complète **non prononcés** : installation Windows, redémarrage Windows, concurrence réelle Mac/Windows et recette native de la fenêtre restent nécessaires.

Signé : Codex, le 2026-09-27. Périmètre et preuves fondés sur les fichiers et exécutions listés, sans commit Git (ce dossier n’est pas un dépôt Git).
