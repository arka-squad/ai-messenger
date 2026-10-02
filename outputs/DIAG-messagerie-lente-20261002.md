# Diagnostic — messagerie lente (02/10/2026)

| Champ | Valeur |
| --- | --- |
| Auteur | Messenger-Tauri-1 (`messenger-tauri-1@messenger`) |
| Demande | L’Owner, 02/10 : « beaucoup de remontées de messagerie lente » |
| Méthode | Lecture du code installé (0.1.5, `949188e`) et construit (0.1.6, `8a1ec90`), mesure de la boîte HTTPS. Rien n’a été lancé ni modifié dans l’app (pause). |

## 1. Cause principale : chaque relève retraite 7 jours de boîte

- **Le serveur n’est pas lent.** `/v1/list` répond en 0,18 s.
- **Mais il renvoie tout ce qui a été écrit depuis « aujourd’hui moins 7 jours »** (`src-tauri/src/exchange.rs:521-524`). L’app place ce repère à aujourd’hui (`src-tauri/src/mailbox/receive.rs:185`). La boîte n’a que 2 jours, donc chaque relève reçoit tout : 1 496 écritures, soit 1,1 Mo.
- **L’app intègre chaque écriture, même déjà connue.** Elle fait un enregistrement en base par écriture (`receive.rs:80`), parfois suivi d’un parcours des écritures en attente (`receive.rs:93-98`).
- **Ce travail se répète souvent.** Il a lieu toutes les 10 s sur chaque poste (`src-tauri/src/lib.rs:423`). Il a aussi lieu à chaque `relever` d’un agent, qui lance sa propre relève complète (`receive.rs:323-324`).
- **Le coût grandit avec la boîte.** Au rythme actuel, la boîte reçoit environ 2 600 écritures par jour. Au bout de 7 jours, chaque relève en traitera près de 18 000.
- C’est cohérent avec les `relever` de 30 à 120 s observés par Cortex-6.

## 2. Amplificateur : les comptes republiés à chaque reprise

- `me_reconnaitre` republie le compte à chaque nouvelle session, même quand rien n’a changé (`src-tauri/src/mailbox/enrolment.rs:190-197`).
- **Mesure :** 444 publications de comptes pour 18 états distincts en 16 heures. Il y en a eu 132 dans les 3 dernières heures, dont 37 pour le dispatcheur. Cela fait environ 4 écritures sur 10 de la boîte.
- **Cause probable :** un veilleur relancé après chaque courrier ouvre une nouvelle session, et republie donc son compte.

## 3. Blocages ponctuels : la remise Codex

Déjà décrit dans le tri du retour de Cortex-6 (message `f2e1567a`), et retenu par l’Owner comme lot prioritaire pour 0.3.7.

## 4. Correctifs proposés

**Côté app seulement, sans redéploiement HCM**
1. Sauter sans passer par la base une écriture déjà intégrée, grâce à un ensemble des ids connus gardé en mémoire. Une relève ne coûte plus que ses nouveautés.
2. Une seule relève à la fois : un `relever` réutilise une relève de moins de 10 s au lieu d’en lancer une autre.
3. Ne republier un compte que s’il a changé (`enrolment.rs:194`).

**Ensuite, avec redéploiement HCM**
4. Un curseur de liste (`/v1/list?apres=<repère>`), pour ne plus transférer 7 jours à chaque relève.

**Proposition.** Ajouter 1 à 3 au lot prioritaire 0.3.7, avec le correctif de remise Codex. Attendu : une relève de l’ordre de la seconde, quel que soit l’âge de la boîte.

## 5. En attendant, sans code

- Espacer les `relever` : pas de boucle sous 5 minutes. La remise par canal suffit quand elle est active.
- Veilleurs : attendre 5 minutes au lieu de 60 s, et ne pas les relancer après chaque courrier, puisque chaque relance republie le compte.
