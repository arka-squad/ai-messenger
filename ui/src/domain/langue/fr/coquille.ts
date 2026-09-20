/**
 * La coquille : écran éteint, en-tête, rail, liste des messages.
 * Typographie française : apostrophes ’, et espace fine insécable (U+202F) avant ; : ! ? —
 * deux caractères invisibles à ne pas « réparer » en espace ordinaire.
 */
export const FR_COQUILLE = {
  // Écran « boîte éteinte » (App.tsx) — le nom Messenger reste en dur, entre les deux segments.
  'coquille.eteinteTitre': 'La boîte est éteinte',
  'coquille.eteinteTexteAvant': 'Tes agents continuent de s’écrire : seule cette fenêtre s’est arrêtée. Pour la rouvrir, double-clique sur l’icône ',
  'coquille.eteinteTexteApres': '. Tu peux fermer cet onglet.',
  // Motifs d'indisponibilité de la création (App.tsx → Rail.tsx).
  'coquille.creationLectureSeule': 'Boîte en lecture seule (ancienne boîte Markdown) — migre-la en JSON (messenger.py migrate) pour créer des projets.',
  'coquille.creationIndisponible': 'Création indisponible pour cette boîte.',
  // En-tête (Entete.tsx).
  'coquille.boiteDemonstration': 'Boîte de démonstration',
  'coquille.boitePartagee': 'Boîte partagée',
  'coquille.nouveaux__1': '{n} NOUVEAU',
  'coquille.nouveaux__n': '{n} NOUVEAUX',
  'coquille.veilleActive': 'Veille active',
  'coquille.veilleSuspendue': 'Veille suspendue',
  'coquille.veilleSuspendre': 'Suspendre la relève automatique',
  'coquille.veilleReprendre': 'Reprendre la relève automatique',
  'coquille.notificationsIndisponibles': 'Notifications système indisponibles',
  'coquille.notificationsActives': 'Notifications système actives : chaque message qui passe est signalé — cliquer pour couper',
  'coquille.notificationsCoupees': 'Notifications système coupées — cliquer pour les rétablir',
  'coquille.themeSombre': 'Passer en sombre',
  'coquille.themeClair': 'Passer en clair',
  'coquille.agirEnTant': 'Vous agissez en tant que {compte}',
  // Rail (Rail.tsx) — les couloirs gardent leurs valeurs 'toutes'/'fils'/'pj'/'moi', seuls les libellés bougent.
  'coquille.navBoites': 'Boîtes',
  'coquille.tousMessages': 'Tous les messages',
  'coquille.reponses': 'Réponses',
  'coquille.avecPieceJointe': 'Avec pièce jointe',
  'coquille.adressesA': 'Adressés à {compte}',
  'coquille.proprietaire': 'l’Owner',
  'coquille.projets': 'Projets',
  'coquille.tousProjets': 'Tous les projets',
  'coquille.agents': 'Agents',
  'coquille.projetAgents__1': '{n} agent',
  'coquille.projetAgents__n': '{n} agents',
  'coquille.projetMessages__1': '{n} message',
  'coquille.projetMessages__n': '{n} messages',
  'coquille.projetEchanges': 'dont les échanges avec les autres projets',
  'coquille.projetNouveaux__1': '{n} nouveau',
  'coquille.projetNouveaux__n': '{n} nouveaux',
  'coquille.voirTousProjets': 'Voir tous les projets',
  'coquille.voirProjetSeul': 'Ne voir que le projet {projet}',
  'coquille.groupeVide': 'Aucun agent encore — copie l’invite et colle-la à ton agent.',
  // Une ligne d'agent : infobulle de la fiche, dernier envoi, attente.
  'coquille.agentSilencieux': 'silencieux',
  'coquille.agentDernier': 'dernier {quand}',
  'coquille.agentEnvois__1': '{n} envoi',
  'coquille.agentEnvois__n': '{n} envois',
  'coquille.agentCarnet': 'carnet : {carnet}',
  'coquille.agentEnAttente__1': '{n} en attente',
  'coquille.agentEnAttente__n': '{n} en attente',
  'coquille.agentAttenteDepuis': 'Le plus ancien attend {anciennete}',
  // Le bloc Relève et le constat de la dernière relève.
  'coquille.releve': 'Relève',
  'coquille.releveExplication': 'Toute écriture dans la boîte réveille l’agent en session ; sinon il relève au démarrage suivant.',
  'coquille.relevePremiere': 'Première relève…',
  'coquille.releveDerniere': 'Dernière relève {heure} · {constat}',
  // Liste des messages (Liste.tsx).
  'coquille.messages': 'Messages',
  'coquille.listeVide': 'La boîte est vide.',
  'coquille.listeAucun': 'Aucun message ne correspond.',
  'coquille.panneTitre': 'La boîte n’a pas pu être lue',
  'coquille.panneIndique': 'Indique la boîte : ',
  'coquille.panneDans': ' dans ',
  'coquille.panneOu': ', ou ',
  'coquille.panneTerminal': 'Le détail est dans le terminal où tourne ',
} as const;
