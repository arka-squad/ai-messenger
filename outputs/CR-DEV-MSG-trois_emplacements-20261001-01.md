# CR Dev — MSG / boîte locale, partagée et HTTPS

| Champ | Valeur |
| --- | --- |
| Date | 2026-10-01 |
| Agent | Codex |
| Objet | L’application choisit une boîte locale, un dossier réseau monté ou une URL HTTPS et écrit réellement dans l’emplacement choisi. |
| État | Code et livraison Mac réalisés ; recette Windows native en attente d’accès SSH. |

## Livraison

- Le transport HTTPS de l’application reprend le même journal, les mêmes empreintes, les pièces jointes, les repères d’installation et la conservation que le transport par dossier. Les dépôts sont relus et leur reçu vérifié ; une coupure laisse les écritures en attente pour une reprise avec le même identifiant.
- Les réglages acceptent une URL HTTPS racine et une clé privée. La connexion vérifie la lecture et l’écriture avant le basculement. La clé est stockée hors du journal, dans un fichier privé. Chaque emplacement possède sa propre base locale ; revenir à l’ancien partage retrouve son historique sans copier celui-ci sur HCM.
- Le service `server/` expose l’API de boîte en réutilisant le code métier du dépôt par dossier. Il est déployé sur HCM dans un conteneur non privilégié, derrière Caddy et le certificat HTTPS de `messenger.arka-squad.app`. La boîte serveur `/home/ubuntu/aimessenger` et la clé sont privées ; le port du service n’est pas publié directement.
- Le profil de ce Mac pointe maintenant vers `https://messenger.arka-squad.app`. L’ancienne base du partage reste conservée, et la nouvelle base locale a été créée séparément. L’application Mac compilée a écrit son propre repère dans la boîte HCM. Aucun message du prototype n’y a été copié.

## Vérifications

| Contrôle | Résultat |
| --- | --- |
| Suite ordinaire `npm test` | Réussie : 47 tests Rust, canal Claude, interface et architecture. [Journal](VERIF-MSG-tests-url-20261001.log). |
| Protocole isolé `node scripts/test-remote.mjs` | Réussi : authentification, dépôts immuables, conflit, pièce jointe, repère, redémarrage et conservation, avec le vrai client Rust. [Journal](VERIF-MSG-protocole-url-20261001.log). |
| Client Rust → HCM | HTTPS, certificat, lecture et sonde d’écriture réussis. [Journal](VERIF-MSG-https-hcm-20261001.log). |
| Application Mac → HCM | Base locale distincte créée ; un repère distant porte l’identifiant exact de cette installation ; zéro mutation et zéro message. [Preuve](VERIF-MSG-hcm-mac-20261001.log). |
| Serveur HCM | Authentification requise ; dossier 700 et clé 600 ; Caddy redémarré avec la route persistante, puis santé HTTPS 200. |
| Application macOS Intel | Build release réussi, signature locale ad hoc vérifiée. [Journal](VERIF-MSG-build-apple-url-20261001.log). |
| DMG | Image APFS créée et vérifiée par `hdiutil` ; signature de l’app vérifiée aussi après montage du DMG. [Journal](VERIF-MSG-dmg-apple-url-20261001.log), [SHA-256](VERIF-MSG-apple-url-sha256-20261001.txt). |

Application : [arkalabs Messenger.app](../src-tauri/target/release/bundle/macos/arkalabs%20Messenger.app). Installation : [DMG](../src-tauri/target/release/bundle/dmg/arkalabs%20Messenger_0.1.0_x64.dmg).

## Limites vérifiées

La livraison Mac est signée localement ; elle n’a ni certificat Developer ID ni notarisation Apple. L’accès SSH à GrimWorkshop présente bien l’empreinte ED25519 autorisée, mais `grimo` refuse la clé utilisateur actuellement configurée : aucun build ni essai natif Windows n’est déclaré comme réussi. Le code Windows suit le même chemin d’échange, mais la recette réelle sur ce poste reste à effectuer après obtention d’un accès valide.
