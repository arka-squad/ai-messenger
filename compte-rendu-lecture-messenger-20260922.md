# Compte rendu de lecture — Messenger

## 1. Produit et personnes

Messenger est une application multiposte qui permet aux agents de se parler et, surtout, de demander à une personne de décider d’un geste de produit depuis une seule fenêtre. Cette personne est la cible principale : elle travaille avec des agents sans être développeuse, et ne doit ni ouvrir un terminal ni comprendre la configuration. Les agents restent des clients MCP ; l’application locale, sa base et l’emplacement partagé absorbent le transport, la reprise et l’observation.

## 2. Le geste « j’y vais ? »

L’agent ouvre une demande de validation via MCP avec le geste, son périmètre, sa réversibilité, l’alternative en cas de refus et le motif immédiat. L’application publie la demande ; l’humain la voit dans Messenger et choisit *Valider*, *Refuser* ou *On en discute*, puis la réponse revient vers la session qui a ouvert la demande (push si l’adaptateur le peut, relève de l’agent dans tous les cas). L’agent ouvrant, et lui seul, clôture ensuite la demande en y rattachant le résultat ; *On en discute* bascule vers la session, ce n’est pas une autorisation.

## 3. Les trois états d’atteinte

- **Remis à une session vivante** : l’adaptateur a livré le contexte à la session ; l’interface peut dire qu’elle est atteinte maintenant.
- **Déposé pour le prochain démarrage** : le message est durablement disponible, mais aucune session vivante ne l’a reçu ; l’interface doit dire qu’il attend la reprise de l’agent.
- **Personne à atteindre** : l’adaptateur ne connaît aucune session atteignable ; l’interface ne doit pas présenter cela comme une remise, seulement comme une livraison par relève ultérieure.

Ces trois états ne sont pas les trois états de publication (**en attente de publication**, **publié**, **remis à l’application destinataire**). Ce sont deux dimensions distinctes et l’interface doit les afficher séparément.

## 4. Publication en quatre temps

La mutation est d’abord enregistrée localement en attente, puis son fichier immuable est déposé, relu depuis l’emplacement pour prouver qu’il a survécu, et seulement alors marqué publié. La troisième étape empêche de confirmer une écriture perdue ou incomplète après un dépôt apparemment réussi. La retirer recrée précisément l’incident observé : l’expéditeur voit « envoyé », alors que les autres postes ne peuvent jamais récupérer la mutation.

## 5. Premier lot et risque principal

Je commencerais par le noyau local des mutations immuables — message, marquage, compte, demande, verdict, clôture — avec un test isolé pour chaque invariant, puis par la reprise idempotente et le dépôt/relecture sur un emplacement de dossier. C’est le plus petit chemin qui remplace la cause des pertes du prototype ; Tauri, migration et push fournisseur viennent après ce contrat prouvable. Le risque majeur est la frontière entre stockage partagé et pièces jointes : prouver qu’un fichier, puis son attachement, sont complètement visibles de façon cohérente sur macOS et Windows, malgré les délais et les échecs du partage.

## 6. Flous, contradictions et décisions à prendre

1. « Trois états » est ambigu : §5 définit trois états de publication, puis trois états d’atteinte de session. Il faut deux champs et deux libellés, sinon la maquette finira par les fusionner sous « remis ».
2. `déposer`, `lister`, `écouter` ne définissent pas comment prouver qu’un fichier est entier. Il manque le protocole de publication (temporaire + renommage atomique, manifeste, ou autre) et ses garanties sur chaque emplacement ; sans lui, la relecture peut voir une écriture déchirée.
3. Pièce jointe : le concept dit de ne pas intégrer le message avant l’attachement, la spec dit qu’il reste lisible mais incomplet. Je recommande d’intégrer le message comme **incomplet** (jamais comme remis/complet), mais cette règle doit être unique et testée.
4. Le verdict doit tracer qui a répondu, mais son modèle ne contient pas `rendu_par`. L’humain n’ayant pas de compte, il faut définir l’identité auditée (propriétaire/installation) et qui publie techniquement cette mutation.
5. `discuter` est annoncé comme non-verdict mais figure dans l’énumération `reponse` du verdict. Il manque la mutation/lifecycle exact qui transforme une validation en intervention et cible la bonne session.
6. L’invariant « aucun secret », surtout dans une pièce jointe libre, n’est pas testable tel quel. Il faut choisir une règle réaliste et testable (politique déclarative, motifs bloqués, ou simple responsabilité de l’agent) ; sinon le test promis ne peut pas exister honnêtement.
7. La conservation exige de connaître les installations, leurs repères et leur dormance ; le modèle ne définit pas encore l’entité installation ni le format de son repère. Elle est décidée comme produit, mais pas encore implémentable.
8. Le contrat fournisseur dit « faire approuver un geste », alors que la validation est rendue dans Messenger et non par le fournisseur. Je le formulerais « remettre le verdict à la session » pour éviter de reconstruire par erreur un relais de permissions d’outil.
9. La référence Codex fournie documente l’app-server comme surface expérimentale ; elle ne documente pas la commande supportée `codex queue` dont dépend le chemin principal. Avant de coder l’adaptateur Codex, il faut figer une preuve/version de CLI pour `agents` et `queue`, plus leurs erreurs et leurs identifiants de session.
