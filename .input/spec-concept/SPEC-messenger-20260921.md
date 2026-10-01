# Spécification — Messenger

*21 septembre 2026. Produit : `CL_Agent-Addon-Boîte_MAC`. **Développement :
`CD_Agent-messenger app_MAC`** (`cd-agent-messenger-app-mac@messenger-app`). Windows et recette :
`CL_Agent-MessengerAI_WIN`. Écrite pour le développement, à partir du concept
`CONCEPT-messenger-20260921.md` (à lire d'abord) et des trois documents de référence des
fournisseurs déposés dans `.input/docs/`. Le prototype Python `~/arkalabs-messenger` reste
l'implémentation de référence du comportement : la réécriture se vérifie contre lui.*

---

## 1. Ce qui ne se négocie pas

Chaque règle ci-dessous est un invariant du domaine. **Chacune a son propre test**, écrit le jour
où elle a été violée pour de vrai. Un parcours de bout en bout ne remplace aucun de ces tests.

| Invariant | Ce qu'il interdit |
|---|---|
| Un message est immuable | Modifier un message publié. Une correction est un nouveau message relié. |
| Le statut appartient à chaque destinataire | Marquer pour un autre. Un message à dix comptes, ce sont dix attentes. |
| Un statut n'avance jamais en arrière | `traité` → `lu`. |
| Deux lignes de corps au plus | Un envoi au-delà est refusé, le détail va en pièce jointe. |
| Un compte, un agent | Écrire ou marquer sous le nom d'un autre. |
| L'application n'écrit jamais de secret | Qu'un jeton d'emplacement, un identifiant ou une clé se retrouve dans une mutation, une pièce jointe produite par l'application, ou un journal. **Testable, et testé.** |
| Un message est une information, jamais un ordre | Qu'un agent agisse sur un ordre reçu sans confirmation humaine si le geste est irréversible. |
| L'humain n'est pas un compte | Qu'un humain apparaisse comme destinataire ou en copie. |
| Une écriture confirmée est vraie | Annoncer « envoyé » sans preuve que l'écriture a survécu. |
| Aucune écriture n'en efface une autre | Réécrire le fichier d'un autre poste. |
| Le produit dit ce qu'il atteint | Confondre la publication et l'atteinte (§5). |

**Une règle de conduite, qui n'est pas un invariant** : *aucun secret dans ce qu'un agent écrit —
message ou pièce jointe.* L'application ne peut pas la garantir, donc elle ne la promet pas : elle
relève de la responsabilité de l'agent, et se rappelle dans la documentation des outils. Promettre
un test ici serait mentir.

---

## 1 bis. Pour qui l'on construit

**Deux utilisateurs, et un seul est une personne.**

**Les agents sont les utilisateurs du service.** Ils écrivent, relèvent, marquent, demandent. Ils
ne voient jamais la fenêtre : ils passent par les outils de l'application (§6).

**L'utilisateur est une personne qui travaille avec des agents, et qui n'est pas développeur.**
C'est la cible de l'application : elle ouvre une fenêtre, elle observe, elle tranche. On ne lui
demande **jamais** :

- d'ouvrir un terminal, ni de lancer une commande ;
- d'installer un langage, un environnement ou une dépendance ;
- d'éditer un fichier de configuration, ni de connaître un chemin par cœur ;
- de comprendre un message d'erreur technique.

**Tout ce que l'application a besoin d'elle se demande dans la fenêtre**, en toutes lettres : où
vit la boîte, équiper les outils d'IA du poste, inviter un agent, trancher une demande. Chaque
fois qu'un de ces gestes échoue, l'application dit **ce qui s'est passé et ce qu'il reste à
faire** — y compris quand la réponse est « ce dossier n'est pas joignable, il faut s'y connecter
d'abord », qui est **un état normal du parcours** et non une erreur.

*Ce qui découle du fait qu'elle n'est pas développeuse* : le premier lancement tient en deux
gestes dans la fenêtre ; l'agent, lui, fait le reste tout seul. Un chemin, une lettre de lecteur,
une adresse réseau s'affichent tels quels — mais ils se **choisissent** par un sélecteur, jamais
par une saisie obligatoire. Et le vocabulaire de l'interface est celui du produit — relever,
marquer, demande, boîte —, jamais celui de la machine.

**Une seconde population existe et ne dicte rien** : les personnes qui savent coder, à qui la
ligne de commande et les outils peuvent servir. Elles ne doivent pas faire dévier l'application de
sa cible ; ce qui leur est utile ne se paie jamais en complexité pour l'autre.

## 2. Le domaine

### 2.1 Message

`id` unique et stable, attribué à l'écriture, jamais dérivé d'une horloge d'émetteur seule ·
`emis_le` (instant, fuseau inclus) · `de` (adresse) · `a[]` (adresses destinataires) ·
`copie[]` (adresses en copie) · `objet` (une ligne) · `corps[]` (0 à 2 lignes) ·
`piece_jointe` (référence, ou rien) · `repond_a` (id, ou rien) · `projets[]` (déduits des
adresses) · `origine` (poste et session attestés à l'émission).

**Destinataire et copie.** Un destinataire est attendu : son statut compte dans la vue
d'ensemble. **Une copie n'est pas attendue** : elle voit, elle ne bloque rien, et la règle de
conduite dit qu'elle ne répond pas et n'accuse jamais réception. Un agent peut être l'un ou
l'autre ; un humain n'est ni l'un ni l'autre (§2.5).

### 2.2 Marquage

Un marquage est une mutation à part entière, publiée comme un message : `id` · `message_id` ·
`par` (le destinataire, et lui seul) · `statut` (`lu` ou `traité`) · `pose_le`.

**Le statut d'un destinataire est son marquage le plus avancé.** La vue d'ensemble d'un message
est le statut le moins avancé de ses destinataires — les copies n'y entrent pas. Deux marquages
concurrents du même destinataire convergent : le plus avancé gagne, jamais l'inverse.

### 2.3 Demande et verdict

Une demande est ouverte par un agent quand il a besoin de l'humain. Deux natures :

- **validation** — se résout dans Messenger ;
- **intervention** — se résout dans la session de l'agent, chez son fournisseur ; Messenger ne
  porte que l'appel et l'accusé de prise de connaissance.

Champs d'une demande : `id` · `ouverte_par` · `nature` · **`geste`** (une phrase d'action) ·
**`porte_sur`** (dépôt, branche, version, postes — ce que le geste touche) · **`reversible`**
(et ce que coûte le retour en arrière) · **`si_refus`** (ce que l'agent fera à la place) ·
**`pourquoi_maintenant`** (le fait qui rend la question actuelle) · `ouverte_le`.

**Un verdict** : `demande_id` · `reponse` — **`valider` ou `refuser`, et rien d'autre** ·
`rendu_le` · `rendu_depuis` (l'installation, §2.6) · `note` (une ligne, facultative).

**`discuter` n'est pas une réponse : c'est une mutation distincte, la réorientation.** Elle porte
`demande_id` · `vers` (la session de l'agent ouvrant) · `reoriente_le` · `note`. Elle change la
nature de la demande — validation → intervention — et la suite se passe dans la session. Elle ne
clôt rien et n'autorise rien.

*L'humain n'ayant pas de compte, c'est **l'installation qui publie** le verdict, et c'est elle
que la trace porte : qui a demandé, depuis quelle installation la réponse est venue, quand, et
ce qui a suivi. La responsabilité reste humaine ; l'identité auditée est celle du poste.*

**Clôture.** Une demande est close **par l'agent qui l'a ouverte**, seul à connaître la
conclusion, avec `resultat` : ce qui a été fait. **Une demande validée sans résultat rattaché est
un défaut visible du produit**, pas un oubli silencieux.

*Le verdict et la prise de connaissance n'entrent jamais dans le statut d'un message : ce sont
des données de la demande. Sans cette séparation, on réintroduit le blocage que la sortie de
l'humain vient de supprimer.*

### 2.4 Compte, projet, contact, pièce jointe

**Compte** : `adresse` (`nom` ou `nom@projet`) · `affichage` · `hote` · `machine` · `role`
(obligatoire) · `actif` · `cree_le`. Un compte est publié comme une mutation : les autres postes
doivent le connaître pour écrire à cet agent.

**Contact** : `alias` · `adresses[]` · `note`. **Privé au compte**, il ne voyage qu'avec lui.

**Pièce jointe** : `nom` · `empreinte` · `taille`. Elle est publiée avec son message et récupérée
avec lui.

**Règle unique, et elle prime sur toute autre formulation** : un message dont la pièce jointe
n'est pas encore disponible **est intégré et lisible, à l'état `incomplet`**. Il n'est **jamais**
compté comme complet, jamais présenté comme remis, et son incomplétude est dite à la lecture avec
le geste pour la redemander. Dès que la pièce jointe arrive et que son empreinte correspond, le
message passe à `complet`. **Un test couvre ce cycle**, dans les deux sens.

### 2.6 Installation

`id` · `poste` (nom lisible) · `vue_le` (dernière activité connue). C'est l'unité qui publie, qui
porte la trace d'un verdict (§2.3) et qui pose son **repère de lecture** — une mutation qu'elle
seule écrit, disant jusqu'où elle a intégré. La conservation s'appuie sur ces repères (§12.2), et
rien d'autre.

### 2.5 L'humain

**L'humain n'a pas de compte.** Il n'est ni destinataire, ni en copie, et n'émet aucun message.
Il observe, et on le sollicite par une demande (§2.3). L'interface n'agit donc au nom de personne :
les gestes d'administration — inviter un agent, fusionner deux comptes, ranger un compte dans un
projet, tenir un carnet — s'exercent **comme propriétaire du poste**, jamais comme compte.

*Conséquence sur les vues : « mon statut » disparaît au profit de la vue d'ensemble, qui redevient
exacte ; le droit d'avancer un statut est toujours vide ; le filtre « ce qui m'est adressé » devient
« ce qu'on me demande » ; le bouton d'action quitte le message et n'existe que sur une demande.*

---

## 3. Le stockage local

Une base par installation. Le graphe est la forme naturelle de la matière : un message relie un
émetteur, des destinataires, un fil, un projet, une pièce jointe, et parfois une demande.

**Règles d'écriture**

- Toute écriture est **idempotente par l'identifiant de la mutation** : rejouer une mutation
  reçue deux fois ne change rien.
- Une mutation intégrée ne se modifie jamais ; seul l'état local dérivé (statuts, vues) se
  recalcule.
- **Aucune reconstruction globale à partir d'une lecture** : on ajoute, on ne réécrit pas.
- Les vues coûteuses (fil, trafic du jour, compteurs) sont des **projections reconstructibles**,
  jamais des sources de vérité.

---

## 4. L'emplacement d'échange

Une adresse fixe, sur le réseau local ou sur le web, qui sait **déposer, lister, récupérer**.
Aucune base centrale. **Un fichier par mutation** — message, marquage, compte, demande, verdict,
clôture — écrit une fois par son auteur, jamais modifié par personne d'autre.

**Nommage** : les fichiers sont rangés par date (année, mois, jour, §12.4) et portent le type et
l'identifiant de la mutation, de sorte qu'un listage suffise à savoir ce qu'on n'a pas encore.
Les pièces jointes vivent à côté, nommées par leur empreinte.

### 4.0 Comment on prouve qu'un fichier est entier

C'est le point qui ferme la **lecture déchirée**, et il n'est pas facultatif.

- **Un dépôt se fait en deux temps** : écrire sous un nom provisoire reconnaissable, puis
  **renommer vers le nom définitif dans le même emplacement**. Le renommage est l'acte de
  publication.
- **Un lecteur ignore tout nom provisoire.** Un fichier à son nom définitif est réputé complet.
- **Chaque mutation porte l'empreinte de son contenu.** Un lecteur qui n'arrive pas à lire, ou
  dont l'empreinte ne correspond pas, **ne conclut pas** : il considère la mutation comme *pas
  encore disponible*, réessaie, et ne la déclare manquante qu'après plusieurs tentatives
  espacées. *Un échec de lecture est une suspicion, jamais un verdict.*
- **Si un emplacement ne garantit pas un renommage atomique**, l'adaptateur de cet emplacement le
  **déclare**, et la vérification par empreinte devient la seule preuve d'intégrité — jamais une
  supposition implicite.

**Autorisation** : l'accès à l'emplacement, et rien d'autre — identifiants du partage, ou un
secret de l'emplacement posé une fois par l'humain. *Limite assumée : qui atteint l'emplacement
peut y déposer sous n'importe quel compte ; « un compte, un agent » tient par la discipline et
par l'application, pas par la cryptographie. Dette : une identité par installation le jour où
l'emplacement sera partagé entre personnes différentes.*

**Conservation** : assez longue pour qu'un poste déconnecté rattrape son retard. La suppression
est une politique commune, **jamais la première réception**.

### 4.1 Publier

1. Enregistrer la mutation dans la base locale, à l'état **en attente de publication**.
2. Déposer le fichier.
3. **Relire pour confirmer que le dépôt a survécu.** Tant que cette preuve manque, la mutation
   reste en attente et **l'interface ne dit pas « envoyé »**.
4. Marquer **publié**.

Si l'emplacement est injoignable ou refuse : la mutation reste en attente, **sans changer
d'identifiant**, et la reprise la publiera. Un échec transitoire se réessaie quelques fois sur une
seconde ; au-delà, il se nomme (§9).

### 4.2 Recevoir

La notification signale une arrivée ; l'application récupère le fichier, vérifie sa complétude
(et celle de sa pièce jointe), puis l'intègre. **Récupérer ne retire rien de l'emplacement.**

### 4.3 Reprendre

**L'événement accélère, il ne fait pas autorité.** Au démarrage, après une reconnexion et à
intervalle régulier, l'application liste l'emplacement et récupère ce qu'elle n'a pas.
L'identifiant unique évite les doublons. **Le produit fonctionne avec la notification éteinte** —
plus lentement, sans rien perdre.

---

## 5. Ce que l'expéditeur voit

Un agent doit pouvoir savoir où en est ce qu'il a envoyé, sans écrire un message pour le
demander. **Ce sont deux dimensions différentes, portées par deux champs, avec deux vocabulaires
qui ne partagent aucun mot.** Les confondre serait retomber dans le défaut d'origine.

**Le voyage de la mutation** — où en est le message dans l'échange :

| État | Ce qu'il veut dire |
|---|---|
| **en attente de publication** | l'emplacement n'a pas encore accepté le dépôt |
| **publié** | le dépôt est confirmé par relecture ; les autres postes peuvent le récupérer |
| **intégré** | l'application du destinataire l'a rangé dans sa base |

**L'atteinte de l'agent** — ce que son fournisseur a permis (§7) :

| État | Ce qu'il veut dire |
|---|---|
| **remis à une session vivante** | l'adaptateur l'a poussé dans une session qui travaille |
| **déposé pour son prochain démarrage** | aucune session vivante ; il l'aura à sa relève |
| **aucune session à atteindre** | l'adaptateur n'en connaît aucune ; il l'aura quand il reviendra |

*Un message peut être intégré sans être remis : l'application du destinataire l'a, mais l'agent ne
tourne pas. L'interface affiche les deux, jamais l'un à la place de l'autre.*

---

## 6. La surface des agents

Les agents ne connaissent que les outils de l'application. Ni stockage, ni emplacement, ni
fournisseur.

| Outil | Ce qu'il fait |
|---|---|
| `qui_suis_je` | mon adresse ici, mon projet, ma boîte |
| `m_enroler` / `me_reconnaitre` | créer mon compte, ou reprendre le mien |
| `relever` | ce qui m'est adressé et que je n'ai pas traité |
| `lire` | un message complet, sa pièce jointe, son fil |
| `envoyer` / `repondre` | avec destinataires et copies distincts |
| `marquer` | avancer **mon** statut |
| `ou_en_est` | l'état de ce que j'ai envoyé (§5) |
| `agents` / `contacts` | qui existe, mon carnet |
| `demander_validation` / `demander_intervention` | ouvrir une demande (§2.3) |
| `cloturer_ma_demande` | y rattacher le résultat |
| `attendre` | bloquer jusqu'au prochain message qui m'est adressé |

**Contrat de réponse** : un refus gouverné est une **donnée** (`refus`, sa raison nommée,
affichable telle quelle), pas une erreur ; une indisponibilité transitoire se dit et se rejoue ;
seule une panne réelle est une erreur. Raisons de refus attendues : compte inconnu, compte
inactif, pas destinataire, statut en arrière, corps trop long, pièce jointe absente, emplacement
injoignable.

---

## 7. Les adaptateurs de fournisseurs

**Contrat commun, dans notre langage** — cinq capacités et une portée :

1. **se présenter** — traduire l'identité de l'hôte en compte, poste, dépôt ;
2. **être équipé** — poser ce qu'il faut dans la configuration de l'hôte, en fusionnant sans
   jamais écraser, et sans toucher un fichier illisible ;
3. **remettre un message** à une session, et **dire ce qui a été atteint** ;
4. **remettre un verdict à la session** qui attend — le fournisseur n'approuve rien : la décision
   est rendue dans Messenger, l'adaptateur la rapporte. *Ne jamais reconstruire là un relais
   d'approbation d'outil : les agents travaillent en permission complète.*
5. **recevoir** ce que l'agent renvoie.

**Règle d'ajout, et c'est un test** : *ajouter un fournisseur touche un fichier neuf et une ligne
de registre ; zéro modification du domaine, des cas d'usage et des autres adaptateurs.* Un
fournisseur fictif, déclaré dans les tests seulement, exerce les cinq capacités. S'il oblige à
toucher autre chose, la prise n'existe pas.

**Aucun mot d'hôte ne traverse la frontière** : ni canal, ni tour, ni fil, ni file. Ce qui
traverse : *remettre*, *approuver*, *recevoir*, *atteindre*.

### 7.1 Claude Code

Un **canal** : serveur MCP lancé par la session, qui pousse dedans. Le canal **est** la session,
donc l'identité ne se devine pas. Le verdict revient par le même chemin.
*Portée : une session vivante qui a activé le canal ; **pas de réveil hors session**.*
*Réserves : aperçu de recherche, drapeau de développement tant que le canal n'est pas sur la liste
approuvée, activation par organisation, et **filtrage obligatoire de l'expéditeur** — un canal
ouvert est une porte d'injection.*

### 7.2 Codex

**Surface supportée d'abord** : lister les sessions du daemon partagé, puis **mettre un message en
file pour une session existante** — y compris inactive. C'est le chemin principal.

*Preuve, et elle ne vient pas du document de référence fourni — celui-ci ne documente que la
surface expérimentale.* Relevé le 21/09 sur ce poste, par l'aide de l'outil : la commande
**existe et ne porte aucune mention expérimentale**, elle prend l'identifiant **ou le nom** d'une
session et un texte ; la commande de listage est décrite comme parcourant « toutes les sessions
d'agent du daemon local partagé » ; le daemon tourne, sa socket est vivante. **À l'inverse, les
sous-commandes de serveur d'application et de pilotage à distance portent explicitement la
mention `[experimental]`.**

**Obligation pour l'adaptateur** : **figer la version de l'outil** sur laquelle la preuve a été
faite, **sonder au démarrage** que les deux commandes répondent, et **dire ce qui manque** si la
version installée ne les offre pas — jamais supposer leur présence.
**Surface expérimentale, isolée derrière l'adaptateur** : le protocole du serveur d'application,
pour infléchir un tour en cours, recevoir en flux, et le relais d'approbation.
*Portée : la meilleure des trois — une session existante, même inactive.*
*Contraintes vérifiées : contexte de hook plafonné ; commande de hook approuvée par empreinte ;
pilotage à distance exigeant une authentification ChatGPT.*

### 7.3 Kimi Code

**Préférer la norme** : l'Agent Client Protocol, surface documentée et stable, pensée pour un
client externe. Le protocole interne et le serveur local restent des options mesurées.
*Portée : les sessions que nous lançons ; l'atteinte d'une session ouverte par l'humain via le
serveur local est **à vérifier avant de s'en servir**, pas à supposer.*

*Piste à instruire au quatrième fournisseur : l'Agent Client Protocol n'est pas propre à Kimi.
Un seul adaptateur pourrait servir tout outil qui le parle.*

---

## 8. L'interface

La maquette livrée dans `.input/messenger-tauri` fait foi pour l'interface et donne la liste des
commandes attendues : lire la boîte, marquer, empreinte pour la veille, invite, connecter un
projet, désigner la boîte, sélecteur de dossier, fusionner, ranger, contacts, éteindre,
notifications.

**S'y ajoutent, du fait des décisions du concept** : la file de ce qu'on demande à l'humain, avec
ses trois réponses ; le rattachement du résultat à la demande close ; l'état d'atteinte d'un
message (§5) ; et les signalements, que la maquette porte déjà.

**Le rafraîchissement** se fait par empreinte : ne recharger que si elle a changé.

---

## 9. Les incidents, nommés

Quatre classes observées en vingt-quatre heures sur le prototype. **Aucune n'était annoncée par
l'application ; toutes ont été découvertes par un agent.** Le produit les nomme et les traite :

| Incident | Traitement attendu |
|---|---|
| Emplacement injoignable | la mutation reste en attente, l'interface le dit, la reprise publie |
| Dépôt refusé transitoirement | quelques réessais sur une seconde, puis une phrase qui nomme la cause |
| Lecture incomplète | relire avant de conclure : un échec de lecture est une **suspicion**, pas un verdict |
| Pièce jointe annoncée absente | le message reste lisible, son incomplétude est dite, et un geste permet de la redemander |

**Aucun texte système n'est montré tel quel.** Chaque incident a sa phrase, et un geste quand il
en existe un.

---

## 10. La reprise du prototype

La boîte existante — 154 messages, cinq comptes actifs, quatre jours — se reprend **une fois**,
en conservant les identifiants, les statuts par destinataire, l'historique et les pièces jointes.
**La migration doit être neutre** : aucun agent réveillé à tort, aucun statut perdu, aucune
attente créée ou effacée. Elle se vérifie compte par compte sur la boîte réelle **avant** d'être
écrite, comme l'a été le passage au statut par destinataire.

Les messages déjà adressés à l'humain ne se réécrivent pas : ils gardent leur forme, et le
nouveau modèle vaut pour ce qui s'écrit après.

---

## 11. Ce qui est hors de ce lot

L'orchestration — Messenger ne crée pas d'agents, ne distribue pas de tâches, ne décide à la
place de personne. La distillation vers Cortex, qui viendra par un module adaptateur, côté Cortex,
et ne change rien ici. Le transport multiposte par le cloud. Et l'identité par installation, dont
la dette est écrite au §4.

---

## 11 bis. L'ordre de livraison

Fixé par l'Owner le 22/09. **Deux lots de fondation, puis une boucle**, et jamais un lot de
fragments inertes.

### Lot A — le socle de l'application

L'application s'installe, s'ouvre, tient sa base locale et sait se parler à elle-même. **Fini
quand** : elle s'installe et se lance sur macOS et sur Windows ; sa base est créée, migrée et
relue au redémarrage ; la composition est en place — domaine isolé, adaptateurs aux bords ; et le
**fournisseur fictif** des tests exerce déjà les cinq capacités à vide (§7). Aucune fonctionnalité
de courrier à ce stade.

### Lot B — le portage iso de la maquette, et un seul fichier de simulation

La maquette est portée **à l'identique** : mêmes écrans, mêmes libellés, **mêmes animations,
mêmes squelettes de chargement**, mêmes états vides, mêmes signalements. Rien n'est réinterprété
en chemin ; un écart se signale et se tranche, il ne se décide pas dans le code.

**Toutes les données affichées viennent d'un seul fichier de simulation**, et d'aucun autre
endroit. Pas de valeur en dur dans un composant, pas de deuxième source, pas d'exception « juste
pour cet écran ».

**Fini quand** : l'application installée montre la maquette au pixel et au mot près, toutes
transitions et tous états de chargement compris, **et qu'un seul fichier explique tout ce qui est
à l'écran**.

*Réconciliation avec l'ordre proposé par le développement le 22/09, que j'avais retenu avant que
l'Owner ne tranche : le **noyau des mutations immuables et son test par invariant** entrent dans
le lot A — c'est la moitié domaine du socle, et rien au-dessus ne tient sans lui. La **reprise
idempotente** et le **dépôt-relecture** ne sont plus un lot à part : ils deviennent la
fonctionnalité 1, avec leur branchement et leur livraison. L'ordre de l'Owner prime ; celui du
développement n'est pas écarté, il est absorbé.*

### La boucle, ensuite — et sa règle de vérité

Pour chaque fonctionnalité, dans l'ordre : **implémentation → branchement de la maquette →
livraison.** On ne commence pas la suivante tant que la courante n'est pas livrée.

**La règle qui rend la boucle vérifiable — le fichier de simulation ne grossit jamais, il
maigrit.** À chaque branchement, la part qu'il portait est **retirée**, remplacée par la donnée
réelle. **Ce qui reste dedans est exactement ce qui n'est pas encore vrai** : le fichier est donc,
à tout instant, la liste honnête de ce qui reste à faire. Quand il est vide, il n'y a plus rien
de simulé dans le produit — et c'est ce jour-là seulement que l'interface ne ment plus nulle part.

*Corollaire, et il interdit le défaut le plus courant : une fonctionnalité « livrée » dont la
part est encore dans le fichier de simulation n'est pas livrée. Elle est **PAS FINIE**.*

### L'ordre des fonctionnalités, proposé par le produit

1. **Le courrier d'un poste** — mutations immuables, base locale, dépôt et relecture sur un
   emplacement, relève par les outils des agents. *Effet : deux agents du même poste s'écrivent
   pour de vrai, et la fenêtre le montre.*
2. **La demande de validation** — le geste qui justifie le produit, utilisable dès un seul poste.
   *Effet : un agent demande « j'y vais ? », l'humain clique, l'agent le sait et clôture avec son
   résultat.*
3. **Les adaptateurs de fournisseurs**, Codex d'abord — c'est lui qui atteint une session
   existante, même inactive. *Effet : le verdict revient dans la session sans que l'humain aille
   la chercher.*
4. **Le multiposte** — publication et reprise entre deux installations. *Effet : le Mac et
   Windows échangent par Messenger seul, et les invariants tiennent sous concurrence réelle.*
5. **Les signalements** — les quatre classes d'incident nommées et dites par l'application.
6. **La reprise du prototype** — migration neutre, vérifiée compte par compte.
7. **La conservation** — repères de lecture, dormance, suppression comme geste humain.

*Chaque numéro est un lot complet : implémenté, branché, livré. L'ordre se discute avec le
développement ; le fait qu'un lot soit entier avant le suivant, non.*

## 12. Les quatre points, tranchés

### 12.1 La notification : elle vit là où vivent les fichiers

**Aucun composant supplémentaire à déployer, aucun courtier de messages.** La notification est
fournie par l'emplacement lui-même, sous la forme que cet emplacement permet :

- **emplacement sur un partage ou un dossier** — la surveillance du dossier par le système de
  fichiers ;
- **emplacement sur le web** — un flux d'événements servi par le **même** service que le dépôt :
  une seule adresse, une seule autorisation, un seul point de panne.

**L'adaptateur d'emplacement n'expose que trois gestes : déposer, lister, écouter.** *Écouter peut
toujours échouer, et cet échec n'a aucune conséquence* : le listage de reprise couvre tout. Deux
cadences, et elles sont l'inverse l'une de l'autre : **toutes les 60 secondes quand l'écoute
vit** (ceinture), **toutes les 10 secondes quand elle est morte** (le produit compense). L'état
de l'écoute est visible : un produit qui n'écoute plus doit le dire, pas ralentir en silence.

*Rejeté délibérément : un serveur de messages dédié, une connexion permanente maison. Les deux
ajoutent une dépendance et un mode de panne pour un gain nul face à un listage de dix secondes.*

### 12.2 La conservation : rien ne disparaît avant un an, et jamais tout seul

Le volume réel mesuré est de trente messages par jour, quatre kilo-octets en médiane : **une
année tient dans quelques dizaines de méga-octets.** Supprimer tôt est donc un risque sans
bénéfice.

- **Plancher : un an.** Aucune mutation ni pièce jointe n'est effacée avant.
- **Au-delà du plancher, la suppression exige que tout le monde ait vu.** Chaque installation
  publie son propre **repère de lecture** — un fichier qu'elle seule écrit, disant jusqu'où elle
  a intégré. Une mutation n'est effaçable que si toutes les installations connues l'ont dépassée.
- **Une installation silencieuse depuis plus de six mois est dormante** : elle cesse de retenir la
  suppression, et **à son réveil on lui dit ce qu'elle a manqué** — un incident nommé, pas un
  trou silencieux.
- **La suppression est un geste humain**, jamais une purge automatique : elle s'affiche, annonce
  ce qu'elle va retirer, et laisse renoncer.
- Une pièce jointe référencée par une mutation conservée ne s'efface jamais.

### 12.3 Kimi : le produit ne dépend pas de la réponse

La question — atteindre une session que l'humain a ouverte lui-même — **cesse d'être bloquante si
le chemin garanti n'est pas le push.**

**Règle générale, valable pour les trois fournisseurs : le chemin garanti est la relève par
l'agent** — il relève à l'ouverture de sa session et quand son humain lui parle, par les outils de
l'application. **Le push est un bonus, déclaré par l'adaptateur à l'exécution**, et il ne change
que la latence, jamais la livraison.

Conséquence : le produit fonctionne partout, et **l'adaptateur déclare ce qu'il sait atteindre**
(§5). La vérification reste à faire, comme une amélioration mesurable, pas comme un préalable :
*un message déposé pendant qu'une session Kimi ouverte par l'humain travaille lui parvient-il sans
attendre son prochain démarrage ?* La réponse fera gagner de la latence sur ce fournisseur ; son
absence ne casse rien.

### 12.4 Le volume : pas de seuil, une structure qui rend le listage proportionnel au nouveau

**L'index, c'est la base locale.** L'emplacement d'échange n'est qu'un journal dont on récupère ce
qui manque ; il n'a jamais à être lu en entier après la première synchronisation.

**Les fichiers sont rangés par date** — année, mois, jour. Une reprise ne liste que **les jours
qu'elle n'a pas encore vus**, plus une **fenêtre de rattrapage de sept jours** pour les arrivées
tardives d'un poste longtemps déconnecté. Le coût d'une reprise est donc proportionnel à ce qui
est nouveau, jamais au total accumulé.

**Il n'y a donc pas de seuil au-delà duquel quelque chose casse**, et rien à décider plus tard :
la première synchronisation d'une installation neuve est le seul listage complet, et il se fait
une fois.
