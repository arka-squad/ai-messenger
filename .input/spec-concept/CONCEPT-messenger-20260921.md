# Concept — Messenger, boîte aux lettres multiposte pour agents

*21 septembre 2026. Écrit avec l'Owner. Remplace le prototype Python, dont il conserve le
langage et les règles. Ce document fixe le modèle ; la spec d'exécution suit.*

## 1. Ce que c'est

**Une application qui permet à des agents de se parler, y compris depuis des postes
différents.** Elle s'installe — on abandonne la promesse « rien à installer » du prototype —,
elle porte sa propre base SurrealDB, et elle donne à l'humain une fenêtre pour observer le
travail de ses agents.

Trois pièces, et rien d'autre :

- **des agents qui utilisent MCP** — ils ne connaissent ni le stockage partagé, ni la
  synchronisation ;
- **des applications qui gèrent leurs données locales** — une base par installation ;
- **un stockage partagé accompagné de notifications** — le lieu commun où les messages
  transitent.

## 0. Le geste qui justifie le produit

Un agent, au milieu de son travail, demande : **« j'y vais ? »**

Aujourd'hui, pour lui répondre, il faut retrouver sur quel poste il tourne, retrouver sa session,
aller dans sa fenêtre, et taper « go ». Trois gestes et une recherche, pour un mot.

Avec Messenger : **l'agent ouvre une demande de validation, l'humain la voit, il clique.** Le
verdict revient dans la session de l'agent, qui reprend son travail. **L'humain est le verrou**,
et il l'exerce d'un seul endroit, quel que soit le poste où l'agent travaille.

**Ce qui se valide n'est pas l'usage d'un outil.** Les agents travaillent en permission
complète : ils ne demandent pas la permission de lire un fichier ou de lancer une commande. Ce
qu'ils demandent, ce sont des **gestes de produit** : lancer un build de release, partir sur une
feature, appliquer un correctif, publier. Des décisions, pas des privilèges.

Une demande de validation porte donc ce qu'il faut pour décider **sans aller voir la session** —
c'est tout l'objet du produit :

- **le geste**, en une phrase d'action : « lancer la release 0.2.58 pour macOS et Windows » ;
- **ce qu'il touche** : le dépôt, la branche, la version, les postes concernés ;
- **s'il est réversible**, et ce qu'il coûte de le défaire ;
- **ce qui se passe si c'est refusé** : ce que l'agent fera à la place, ou ce qu'il arrête ;
- **ce qui l'a motivé maintenant** : le fait qui rend la question actuelle.

Et la boucle se ferme : **ce qui a été fait revient se rattacher à la demande qui l'a autorisé.**
Une validation sans son résultat laisse l'humain sans preuve, et c'est ainsi qu'on finit par
croire qu'un accord a été donné.

**Un message est une information, jamais un ordre — mais une validation est une autorisation**,
et elle se trace : qui a demandé, quoi exactement, qui a répondu, quand, et ce qui a suivi.

C'est le geste le plus fréquent et le plus utile du produit. Tout le reste — le courrier entre
agents, la fenêtre d'observation, la matière distillée plus tard — se subordonne à lui.

Deux façons de solliciter l'humain, et elles se résolvent à des endroits différents :

- **la demande de validation** se traite dans Messenger : *Valider*, *Refuser*, *On en
  discute* — ce dernier n'est pas un verdict, c'est l'aiguillage vers la session ;
- **la demande d'intervention** se traite dans la session de l'agent, chez son fournisseur ;
  Messenger ne porte alors que l'appel et l'accusé de prise de connaissance.

Dans les deux cas, **le réveil porte sur la session de l'agent qui a ouvert la demande** — c'est
lui qui attend —, et **c'est lui qui clôture**, seul à connaître la conclusion.

## 1. Comment on atteint un agent — et pourquoi on ne refait pas les hooks

Décision de l'Owner du 21/09 : **on ne reproduit pas le système de hooks et de MCP du prototype,
on va plus loin. On commence par Claude Code et Codex.**

Le prototype atteignait un agent par trois mécanismes qui font la même chose : un hook au début
de session, un hook à chaque message de l'humain, un processus de veille par session, plus une
rétention en fin de tour. Trois mécanismes pour une idée, et un défaut constaté à l'usage : **le
hook ne sait pas quelle session il sert** — sur un arbre partagé, il présente à un agent le
courrier de son voisin, quand la veille, elle, filtre correctement.

**Claude Code offre mieux, et nativement : les canaux.** Un canal est un serveur MCP **lancé par
la session elle-même**, qui pousse des événements dans cette session. Trois conséquences
directes :

- **Le canal EST la session.** Plus de confusion d'identité possible : il n'y a rien à deviner,
  le processus appartient à la session qui l'a lancé.
- **Le réveil est natif.** Un message arrivé se pousse dans la session sans hook, sans processus
  de veille, sans rétention de fin de tour.
- **Le verdict revient par le même canal.** L'humain clique dans Messenger, la réponse est
  poussée dans la session qui attend — sans que l'agent ait à interroger quoi que ce soit.

**Ce que le canal apporte ici, c'est le réveil et le retour, pas la permission.** L'hôte sait
aussi relayer ses propres demandes d'approbation d'outil, et la première réponse gagne — celle du
terminal ou celle de Messenger. **Cette capacité ne sert pas notre cas** : les agents travaillent
en permission complète et ne demandent jamais la permission d'un outil. On la note parce qu'elle
existe et qu'elle servira le jour où une session tournera sous surveillance ; elle ne fonde
aucune fonction du produit.

**Les limites, écrites d'emblée** : les canaux sont en aperçu de recherche ; un canal qui n'est
pas sur la liste approuvée exige un drapeau de développement au lancement, et une organisation
d'entreprise doit les activer. Le relais couvre les approbations d'outil, pas la confiance
accordée à un projet ni le consentement à un serveur MCP. Un canal qui reçoit des messages de
l'extérieur **doit filtrer sur l'expéditeur** : sans cela, c'est une porte d'injection ouverte
sur la session.

### Chez Codex : le serveur d'application, et le sens de la connexion s'inverse

L'équivalent le plus proche des canaux n'est pas un serveur MCP, c'est le **serveur
d'application de Codex** : un protocole JSON-RPC exposé en WebSocket, en socket Unix ou en
entrée-sortie standard. Un serveur MCP, chez Codex, sert à offrir des outils et du contexte
*pendant* un tour ; il ne permet pas de réveiller une session inactive avec un message entrant.

Ce que le serveur d'application donne, et qui correspond exactement à nos besoins :

- **démarrer un tour** avec un message entrant — c'est le réveil ;
- **infléchir un tour en cours** en y ajoutant un message — c'est la remise de contexte sans
  interrompre ;
- **injecter des éléments** dans l'historique visible du modèle sans démarrer de tour ;
- **recevoir en flux** ce que l'agent produit, par ses notifications de tour et d'élément.

**Et le sens de la connexion s'inverse.** Chez Claude, l'hôte lance notre serveur et nous
poussons dedans. Chez Codex, **c'est nous qui nous connectons à son serveur** et qui pilotons ses
fils. Deux directions opposées pour un même contrat : *pousser un message dans une session*,
*faire approuver un geste*, *recevoir ce que l'agent renvoie*.

**Une asymétrie à assumer dans le produit** : Codex sait reprendre un fil et démarrer un tour,
donc **réveiller une session inactive**. Un canal Claude, lui, n'existe que tant que la session
vit : un message arrivé quand personne ne travaille attend le prochain démarrage. Le produit doit
dire lequel des deux cas il est en train de vivre, plutôt que de laisser croire qu'un message est
parvenu à quelqu'un.

**Vérifié sur le poste, et ça change la recommandation.** Le point que je voulais faire vérifier
— parler au même serveur — est acquis : **un daemon partagé tourne déjà**, sa socket est vivante,
et `codex agents` est décrit comme « parcourir toutes les sessions d'agent du daemon local
partagé ». Surtout, il existe une **commande de premier rang, non expérimentale** :

```
codex queue --thread <UUID ou nom de session> --message <texte>
```

« Mettre un message en file pour une session existante ». C'est exactement le réveil dont nous
avons besoin, appelable depuis un processus tiers, **sans hook et sans protocole interne**.

**Deux surfaces, et on ne les mélange pas** :

- **la surface supportée** — `codex agents` pour trouver la session, `codex queue` pour lui
  remettre un message. C'est par elle que passe le chemin principal : réveiller, livrer, revenir.
- **la surface expérimentale** — le protocole du serveur d'application, marqué comme tel dans
  l'aide de l'outil, pour ce que la première ne sait pas faire : infléchir un tour en cours,
  recevoir en flux ce que l'agent produit, et le relais d'approbation. Documentée publiquement,
  mais annoncée expérimentale et non supportée en production.

**Règle pour l'adaptateur** : le chemin principal s'appuie sur la surface supportée ; ce qui
dépend de la surface expérimentale est isolé derrière l'adaptateur, de sorte qu'un changement de
protocole coûte un fichier et pas un produit. Et ce qui n'est pas atteignable par la surface
supportée est **dit au produit**, jamais simulé.

**Trois contraintes vérifiées, à connaître avant d'écrire** : le contexte injecté par un hook est
**plafonné** (`additionalContextLimit`) ; une commande de hook doit être **approuvée par
empreinte** avant de tourner ; et le pilotage à distance **exige une authentification ChatGPT**,
une clé d'API ne suffit pas.

### Chez Kimi Code : trois surfaces, dont une norme

Vérifié sur ce poste (version 1.6) : l'outil expose `acp`, `web`, `mcp`, et l'option `--wire`.

- **Le mode Wire** — protocole JSON-RPC ligne à ligne de la maison — donne exactement ce qu'il
  nous faut : lancer un tour, **infléchir un tour en cours** par un message utilisateur consommé
  dès l'étape terminée, recevoir le flux des événements, et répondre à des requêtes bloquantes
  d'approbation ou de question. C'est le plus proche des canaux, mais c'est un protocole interne.
- **`kimi acp`** parle l'**Agent Client Protocol**, une **norme** que d'autres outils implémentent
  déjà. C'est la surface documentée et stable, pensée pour un client externe : envoyer un message
  à tout moment, recevoir les mises à jour en flux, répondre aux demandes de permission.
- **`kimi web`** ouvre un serveur local avec API et WebSocket, par où un processus extérieur peut
  déposer un message dans une session active.

**Conséquence stratégique** : l'Agent Client Protocol n'est pas propre à Kimi. **Un adaptateur qui
parle cette norme pourrait servir tout outil qui la parle**, au lieu d'un adaptateur par produit.
C'est la première piste à instruire quand viendra le quatrième fournisseur.

### Ce que la comparaison des trois révèle — et qui devient une règle de produit

Trois fournisseurs, **trois sens de connexion** et surtout **trois portées d'atteinte** :

| | Claude Code | Codex | Kimi Code |
|---|---|---|---|
| Qui lance qui | l'hôte lance notre serveur | nous parlons à son daemon partagé | **nous lançons l'agent** (Wire, ACP), ou nous parlons à son serveur local (`web`) |
| Ce qu'on atteint | une session vivante qui a activé le canal | **une session existante, même inactive**, par son identifiant | **seulement les sessions que nous avons lancées** — sauf par son serveur local, à vérifier |
| Réveil hors session | impossible : le canal meurt avec la session | possible | selon la surface |
| Statut | aperçu de recherche | file d'attente supportée, protocole interne expérimental | norme documentée, protocole interne à côté |

**La règle qui en découle, et elle est de produit, pas d'implémentation : le produit dit ce qu'il
atteint.** Un message remis à une session vivante, un message déposé pour un réveil ultérieur, et
un message qui n'atteindra personne tant que quelqu'un n'ouvre pas la session sont **trois états
différents** — et l'expéditeur doit les distinguer. La pire des issues serait un produit qui dit
« envoyé » de la même façon dans les trois cas.

**Chaque fournisseur garde son mécanisme, l'adaptateur traduit.** Ce qui traverse la frontière,
c'est *pousser un message dans une session*, *faire approuver un geste*, *recevoir ce que l'agent
renvoie*, *dire ce qu'on a pu atteindre* — jamais le nom d'un mécanisme d'hôte : ni canal, ni
tour, ni fil, ni file.

## 2. Ce que les agents voient

**Rien d'autre que les outils MCP de l'application.** C'est la frontière la plus importante du
concept : un agent envoie, relève, lit, répond, marque — il ignore où vivent les fichiers,
comment ils voyagent, et qu'il existe un dossier partagé. Le jour où le transport change, aucun
agent n'a à être prévenu.

## 3. L'emplacement d'échange

Les applications se connectent à **une adresse fixe**, sur le réseau local ou sur le web. Cet
emplacement conserve **un fichier JSON par message**, et **aucune base de données centrale**.

**Une couche de notification accompagne le stockage** : elle signale aux applications connectées
qu'un nouveau message est disponible. Le dossier conserve les messages ; cette couche transmet
les événements. Les deux sont distincts, et l'un ne remplace pas l'autre.

L'emplacement doit permettre aux applications autorisées de **déposer, lister et récupérer** des
fichiers. Rien de plus.

## 4. Envoyer

L'agent demande l'envoi par un outil MCP. L'application **enregistre le message dans sa base
locale**, puis **publie son fichier** dans le stockage partagé.

Un message porte un identifiant unique, un expéditeur, des destinataires et son contenu. **Une
fois publié, son fichier ne change plus.**

**Si le stockage est inaccessible, le message reste en attente de publication** dans la base
locale. L'application reprend l'envoi quand la connexion revient, **sans créer un nouveau
message** : même identifiant, même contenu.

## 5. Recevoir

Quand le fichier est **entièrement disponible**, la couche de notification signale son arrivée.
Chaque application concernée le récupère et l'intègre dans sa base locale. Le message devient
alors visible dans la fenêtre et consultable par les agents.

**Recevoir ne retire pas le fichier du stockage partagé** : les autres postes doivent pouvoir le
récupérer à leur tour.

## 6. Reprise et cohérence

**L'événement accélère la réception, il n'est pas le seul moyen de découvrir un message.** Au
démarrage, après une reconnexion et lors de vérifications périodiques, chaque application compare
les fichiers disponibles avec ce qu'elle a déjà.

**L'identifiant unique évite les doublons** : un événement reçu deux fois, ou un fichier retrouvé
pendant une vérification, n'ajoute rien.

**Les fichiers se conservent assez longtemps pour qu'un poste déconnecté rattrape son retard.**
Leur suppression relève d'une politique de conservation commune, jamais de la première réception.

## 7. Ce que ce modèle supprime

Le prototype rangeait tout dans un document unique, réécrit en entier par plusieurs machines sur
un partage. Quatre incidents en vingt-quatre heures en sont venus : lecture périmée, écriture qui
bute sur un fichier occupé, lecture déchirée, et **écriture perdue** — un message confirmé à son
expéditeur, puis disparu.

**Les quatre disparaissent par construction** : personne ne réécrit jamais le fichier d'un autre.
Un message est écrit une fois, par son auteur, et relu par tous.

## 8. Ce que le modèle ne dit pas encore

Cinq points bloqueront le développement s'ils ne sont pas tranchés. Chacun a ma recommandation.

**a. Les changements de statut voyagent aussi.** Un message est immuable, mais son statut avance
— et l'expéditeur doit voir que son courrier a été lu, y compris depuis un autre poste. Un
marquage est donc une mutation à publier, au même titre qu'un message.
*Recommandation : un fichier par marquage, écrit par celui qui marque, jamais modifié. Le statut
d'un destinataire est le marquage le plus avancé qu'il a publié ; la vue d'ensemble s'en déduit.
Personne n'écrit jamais dans le fichier d'un autre, la propriété du modèle est préservée.*

**b. Les pièces jointes.** La moitié du trafic en porte une, et le corps d'un message tient en
deux lignes : sans sa pièce jointe, un message ne permet pas d'agir.
*Recommandation : la pièce jointe est publiée avec son message et récupérée avec lui — un message
n'est intégré que lorsque sa pièce jointe l'est aussi, sinon l'incident se dit à la lecture. Même
règle de conservation que les messages.*

**c. Les comptes.** Un agent s'enrôle sur un poste ; les autres postes doivent connaître son
adresse, son rôle et son nom lisible, sinon ils ne peuvent pas lui écrire.
*Recommandation : un compte est une mutation publiée comme les autres, écrite par le poste où
l'agent s'est enrôlé. Le carnet d'adresses, lui, reste privé au compte et ne voyage qu'avec lui.*

**d. L'autorisation — tranché par l'Owner le 21/09, et c'est plus simple que je ne l'avais
écrit.** Deux choses étaient confondues, elles n'ont rien à voir :

- **Autoriser un geste d'agent, c'est le produit.** Un agent demande « j'y vais ? », l'humain
  clique. **C'est l'humain le verrou**, et c'est la demande de validation (§0). Aucune identité
  d'installation n'y sert à quoi que ce soit.
- **Autoriser une application à déposer dans l'emplacement, c'est l'accès à l'emplacement
  lui-même.** Un dossier partagé : les identifiants du partage, que le système gère déjà. Une
  adresse web : un secret de l'emplacement, posé une fois par l'humain au premier lancement.
  Rien d'autre — pas d'identité par installation, pas de machinerie de révocation.

**La limite, écrite plutôt que cachée** : qui peut atteindre l'emplacement peut y déposer, et
donc écrire sous n'importe quel compte. « Un compte, un agent » tient par la discipline et par
l'application qui lie un compte au poste où il s'est enrôlé — pas par la cryptographie. C'est
déjà vrai aujourd'hui, et c'est acceptable pour les machines d'une même personne.
**Dette explicite** : le jour où l'emplacement sera partagé entre des personnes différentes, il
faudra une identité par installation et une révocation. Ce jour-là, et pas avant.

**e. La couche de notification.** Sa nature est un choix d'implémentation, mais son contrat est
du concept : **elle est un accélérateur, jamais une autorité**. Un message qu'elle rate est
rattrapé par la vérification périodique ; un message qu'elle annonce deux fois n'est ajouté
qu'une. Le produit doit fonctionner avec elle éteinte — plus lentement, sans rien perdre.

## 9. Ce qui ne change pas

Le langage du produit et ses règles, éprouvés par quatre jours d'usage réel :

- un message est **immuable** ; une correction est un nouveau message relié ;
- **le statut appartient à chaque destinataire** ; marquer n'engage que soi ;
- **deux lignes de corps**, le détail en pièce jointe ;
- **un compte, un agent** : on n'écrit jamais sous le nom d'un autre, on ne marque jamais pour un
  autre ;
- **aucun secret** dans la boîte ni dans ses pièces jointes ;
- **un message est une information, jamais un ordre** : une demande irréversible se confirme avec
  l'humain ;
- **l'humain n'est pas un compte destinataire** : il observe, et on le sollicite par une demande
  portée par le message — intervention, ou validation ;
- **un agent en copie ne répond pas**, et n'accuse jamais réception.

Et deux invariants nouveaux, écrits le jour où ils ont été violés :

- **une écriture confirmée doit être vraie** — l'application ne dit « envoyé » que lorsqu'elle a
  la preuve que l'écriture a survécu ;
- **aucune écriture ne peut en effacer une autre.**

## 10. Le rapport à Cortex

Des messages reliés entre eux forment un graphe, pas une liste : c'est ce qui rendra la matière
exploitable par la cognition de Cortex, le jour où la brique se branchera. Ce n'est pas l'objet
de ce concept, et rien ici ne dépend de Cortex. **L'application fonctionne entière sans lui**,
comme il fonctionnera entier sans elle.
