"""La ligne de commande — l'interface des agents.

Codes de sortie : 0 succès ; 1 erreur ; 2 courrier présent (`check --wake`) ;
3 rien reçu avant l'échéance (`watch`).
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import threading
import time
from typing import Optional, Protocol, Sequence

from ... import __version__
from ...application import Annonceur, BoiteIndisponible, Messagerie, Notificateur, SourceAncienne
from ...domain import (
    STATUTS,
    Annuaire,
    ErreurMessenger,
    Message,
    qualifier,
    valider_adresse,
    valider_nom,
)
from ..codec import annuaire_vers_dict, contact_vers_dict, en_json, message_vers_dict
from . import hotes, poste, raccourci

SORTIE_ERREUR, SORTIE_COURRIER, SORTIE_ECHEANCE = 1, 2, 3


class Usine(Protocol):
    """Ce que la ligne de commande attend de l'assemblage (voir bootstrap.py)."""

    def ouvrir(self, chemin: str) -> Messagerie: ...
    def ancienne_boite(self, chemin: str) -> SourceAncienne: ...
    def interface(self) -> Optional[str]: ...
    def demonstration(self) -> str: ...
    def notificateur(self) -> Notificateur: ...
    def depot(self) -> str: ...
    def poser_onboarding(self, chemin: str) -> str: ...


class _Refus(ErreurMessenger):
    """Une erreur d'usage détectée par la ligne de commande elle-même."""


def executer(argv: Optional[Sequence[str]], usine: Usine) -> int:
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass
    args = _parseur().parse_args(argv)
    try:
        return args.commande(args, usine)
    except ErreurMessenger as e:
        sys.stderr.write(f"{e}\n")
        return SORTIE_ERREUR
    except KeyboardInterrupt:
        return 130


# --------------------------------------------------------------------------- #
# Commandes
# --------------------------------------------------------------------------- #
def _init(args: argparse.Namespace, usine: Usine) -> int:
    messagerie = usine.ouvrir(_boite(args))
    if messagerie.lecture_seule:
        raise _Refus("on n'initialise pas une boîte Markdown : donne un dossier (arbo .aimessenger/) ou un fichier .json")
    messagerie.initialiser()
    onboarding = usine.poser_onboarding(_boite(args))
    print(f"boîte créée : {messagerie.emplacement}")
    print(f"guide d'accueil des agents : {onboarding}")
    print("comptes, vue humaine et pièces jointes sont rangés à côté (voir PROTOCOLE.md).")
    return 0


def _setup(args: argparse.Namespace, usine: Usine) -> int:
    if args.box is None and args.project is None:
        raise _Refus("rien à mémoriser : passe --box (la boîte de ce poste) et/ou --project (le projet de ce dépôt)")
    if args.box is not None:
        messagerie = usine.ouvrir(args.box)
        messagerie.instantane()  # refuse une boîte illisible
        config = poste.memoriser_boite(messagerie.emplacement)
        print(f"boîte mémorisée pour ce poste dans {config} : {messagerie.emplacement}")
    if args.project:
        fichier = poste.attacher_projet(os.getcwd(), valider_nom(args.project, "projet"))
        print(f"projet « {args.project} » attaché à ce dépôt : {fichier} (à versionner)")
    return 0


def _enroll(args: argparse.Namespace, usine: Usine) -> int:
    """S'inscrire avec une identité lisible déduite de l'hôte, de la tâche et du poste."""
    hote = args.host or "claude-code"
    compte, cree = usine.ouvrir(_boite(args)).enroler(
        hote, args.task, args.poste or poste.code_du_poste(), _projet(args), args.machine or platform.node(),
        role=args.role, humain=args.human, releve=args.wake or "hooks (messenger.py check --hook)",
        mise_a_jour=args.update)
    etat = "compte créé" if cree else "compte mis à jour" if args.update else "déjà inscrit"
    poste.memoriser_identite(hote, os.getcwd(), compte.nom)
    if args.session:
        poste.memoriser_session(args.session, compte.nom)
    print(f"{etat} : {compte.affichage or compte.nom}  (adresse {compte.nom})")
    if args.session:
        print(f"session {args.session} rattachée à {compte.nom} : cette session te reconnaît sans variable")
    return 0


def _identify(args: argparse.Namespace, usine: Usine) -> int:
    """Reprendre son compte depuis son dossier de travail : la relève de ce dossier saura qui tu es."""
    hote = args.host or "claude-code"
    messagerie = usine.ouvrir(_boite(args))
    compte = messagerie.reprendre(messagerie.adresse(args.address, _projet(args)), hote, platform.node())
    poste.memoriser_identite(hote, os.getcwd(), compte.nom)
    if args.session:
        poste.memoriser_session(args.session, compte.nom)
    print(f"c'est bien toi : {compte.affichage or compte.nom}  (adresse {compte.nom})")
    print(f"ta relève te reconnaît désormais dans {os.getcwd()} — relève ton courrier : check --agent {compte.nom}")
    return 0


def _attach(args: argparse.Namespace, usine: Usine) -> int:
    """Ranger un compte commun dans un projet, ou l'en sortir : le geste de l'humain qui organise sa boîte."""
    compte = usine.ouvrir(_boite(args)).rattacher(args.account, args.to or None)
    print(f"{compte.nom} → {'projet ' + compte.projet if compte.projet else 'sans projet (compte commun)'}")
    return 0


def _merge(args: argparse.Namespace, usine: Usine) -> int:
    """Fusionner deux comptes d'un même agent : le geste de l'humain qui range sa boîte."""
    messagerie = usine.ouvrir(_boite(args))
    marque = messagerie.fusionner(args.account, args.into)
    herites = messagerie.releve(args.into)
    print(f"{marque.nom} → fusionné dans {args.into}")
    print(f"  son courrier en attente arrive à {args.into} ({len(herites)} message(s) « nouveau » à relever) ;")
    print(f"  écrire à {marque.nom} mène désormais à {args.into} ; les messages déjà envoyés ne changent pas.")
    return 0


def _activate(args: argparse.Namespace, usine: Usine) -> int:
    """Connecter ce dépôt à la boîte : boîte du poste, projet du dépôt, hôtes IA du poste équipés."""
    if args.box is not None:
        messagerie = usine.ouvrir(args.box)
        messagerie.instantane()  # refuse une boîte illisible
        chemin = messagerie.emplacement
    else:
        chemin = poste.resoudre_boite(None)
        if not chemin:
            raise _Refus("aucune boîte sur ce poste : passe --box <dossier>, "
                         "ou fais d'abord `messenger.py setup --box <dossier>`")
    projet = valider_nom(args.project, "projet") if args.project else None
    try:
        resume = poste.activer_depot(os.getcwd(), projet, usine.depot(), box=chemin, releve=not args.no_releve)
    except poste.ActivationRefusee as e:
        raise _Refus(str(e)) from None
    if resume["projet"]:
        _declarer_projet(usine, chemin, resume["projet"])
    print(f"dépôt connecté : {resume['dossier']}")
    print(f"  boîte (poste) : {resume['boite']}")
    print(f"  projet        : {resume['projet'] or '— (compte commun)'}")
    _afficher_hotes(resume["hotes"])
    print("Chaque session ouverte ici sera invitée à s'enrôler, puis relèvera seule.")
    return 0


def _declarer_projet(usine: Usine, boite: str, projet: str) -> None:
    """Note le projet dans le manifeste de la boîte : l'interface le montre avant qu'un agent s'y enrôle.
    Une boîte en lecture seule ou injoignable n'empêche pas de connecter le dépôt."""
    try:
        messagerie = usine.ouvrir(boite)
        if not messagerie.lecture_seule and messagerie.annuaire_present():
            messagerie.declarer_projet(projet)
    except (ErreurMessenger, BoiteIndisponible, OSError):
        pass


def _install(args: argparse.Namespace, usine: Usine) -> int:
    """Équiper les hôtes IA de ce poste : serveur MCP et relève, dans la configuration de chacun."""
    try:
        etats = hotes.equiper_presents(hotes.contexte(usine.depot()), releve=not args.no_releve,
                                       forcer=args.force, seulement=args.host or None)
    except hotes.EquipementRefuse as e:
        raise _Refus(str(e)) from None
    if not etats:
        print("aucun hôte IA trouvé sur ce poste (Claude Code, Codex, Kimi Code, Antigravity, Cursor)")
        return 0
    _afficher_hotes(etats)
    print("Pris en compte à la prochaine session de chaque hôte (Codex peut demander de valider ses hooks).")
    return 0


def _uninstall(args: argparse.Namespace, usine: Usine) -> int:
    ctx = hotes.contexte(usine.depot())
    try:
        etats = [hotes.retirer(h, ctx) for h in ([hotes.hote(i) for i in args.host] if args.host
                                                 else hotes.presents(ctx))]
    except hotes.EquipementRefuse as e:
        raise _Refus(str(e)) from None
    _afficher_hotes(etats)
    return 0


def _hosts(args: argparse.Namespace, usine: Usine) -> int:
    etats = hotes.etats(hotes.contexte(usine.depot()))
    if args.json:
        print(en_json([e.vers_dict() for e in etats]), end="")
    else:
        _afficher_hotes(etats)
    return 0


def _mcp(args: argparse.Namespace, usine: Usine) -> int:
    from .mcp import servir  # chargé à la demande : la CLI des agents n'en a pas besoin

    return servir(usine, args.box, args.agent, args.project, args.host)


def _start(args: argparse.Namespace, usine: Usine) -> int:
    """Le point d'entrée humain : allume la boîte — l'interface web locale et son API — d'un double-clic.

    Déjà allumée ? On rouvre simplement sa fenêtre. Port pris par autre chose ? On prend le suivant :
    un humain ne passe pas `--port`. Lancée sans console (raccourci du bureau), elle écrit son journal
    dans un fichier, sinon une panne resterait invisible.
    """
    if args.log:
        _journaliser(args.log)
    if not usine.interface():
        raise _Refus("l'interface n'est pas là (ui/dist) : récupère le dépôt en entier, ou lance `npm run build`")
    import webbrowser
    from .web import OUTIL

    port = args.port
    for port in range(args.port, args.port + 20):
        outil = _qui_ecoute(port)
        if outil == OUTIL:
            print(f"la boîte est déjà allumée : http://127.0.0.1:{port}/", flush=True)
            if not args.no_browser:
                webbrowser.open(f"http://127.0.0.1:{port}/")
            return 0
        if outil is None and _port_libre(port):
            break
    else:
        raise _Refus(f"aucun port libre entre {args.port} et {args.port + 19} : ferme ce qui les occupe")
    args.port = port
    args.api = False
    args.front = None
    args.exit_with_parent = False
    args.link = None
    return _ui(args, usine)


def _shortcut(args: argparse.Namespace, usine: Usine) -> int:
    """Poser l'icône « Messenger » sur le bureau : un double-clic allumera la boîte, sans terminal."""
    try:
        if args.remove:
            print("raccourci retiré du bureau" if raccourci.retirer() else "aucun raccourci sur le bureau")
            return 0
        if not usine.interface():
            raise _Refus("l'interface n'est pas là (ui/dist) : récupère le dépôt en entier, ou lance `npm run build`")
        cible = raccourci.poser(usine.depot())
    except raccourci.RaccourciImpossible as e:
        raise _Refus(str(e)) from None
    print(f"icône posée sur le bureau : {cible}")
    print("Double-clique dessus pour allumer la boîte : elle s'ouvre dans ton navigateur.")
    if not poste.resoudre_boite(None):
        print("(aucune boîte sur ce poste pour l'instant : l'interface proposera « Créer la boîte »)")
    return 0


def _qui_ecoute(port: int) -> Optional[str]:
    """Le nom de l'outil qui répond sur ce port (`arkalabs-messenger`…), `""` si c'est autre chose, None si personne."""
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/version", timeout=1.5) as r:
            reponse = json.loads(r.read().decode("utf-8"))
        return str(reponse.get("outil") or "") if isinstance(reponse, dict) else ""
    except urllib.error.HTTPError:
        return ""
    except (OSError, ValueError):
        return None


def _port_libre(port: int) -> bool:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def _journaliser(chemin: str) -> None:
    """Envoie la sortie et les erreurs dans un fichier : sans console, elles seraient perdues (ou fatales)."""
    chemin = os.path.abspath(os.path.expanduser(chemin))
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    if os.path.isfile(chemin) and os.path.getsize(chemin) > 1_000_000:
        os.replace(chemin, chemin + ".1")  # un seul ancien journal : il ne grossit pas sans fin
    journal = open(chemin, "a", encoding="utf-8", buffering=1)  # noqa: SIM115 — vit autant que le processus
    journal.write(f"\n--- {time.strftime('%Y-%m-%d %H:%M:%S')} — messenger.py start ({__version__})\n")
    sys.stdout = sys.stderr = journal


def _register(args: argparse.Namespace, usine: Usine) -> int:
    compte, cree = usine.ouvrir(_boite(args)).inscrire(
        qualifier(_nom_agent(args), _projet(args)), args.host, args.role,
        machine=args.machine or (None if args.update else platform.node()),
        modele=args.model, humain=args.human, releve=args.wake, affichage=args.display,
        mise_a_jour=args.update)
    print(f"compte {'créé' if cree else 'mis à jour'} : {compte.nom} ({compte.hote}, {compte.machine})")
    return 0


def _agents(args: argparse.Namespace, usine: Usine) -> int:
    messagerie = usine.ouvrir(_boite(args))
    racine = os.path.splitext(messagerie.emplacement)[0]
    if not messagerie.annuaire_present():
        print(f"pas de manifeste pour cette boîte ({racine}.manifest.json) : aucun compte")
        return 0
    comptes = messagerie.comptes(tous=True, projet=args.project or None)
    if args.json:
        print(en_json(annuaire_vers_dict(Annuaire(comptes), os.path.basename(messagerie.emplacement))), end="")
        return 0
    for c in comptes:
        if c.actif or args.all:
            etat = "" if c.actif else "  [désactivé]"
            print(f"{c.nom:28} {c.hote:12} {c.machine or '?':22} {c.role}{etat}")
    return 0


def _deactivate(args: argparse.Namespace, usine: Usine) -> int:
    messagerie = usine.ouvrir(_boite(args))
    nom = _agent(args, messagerie)
    messagerie.desactiver(nom)
    print(f"compte désactivé : {nom} (conservé dans le manifeste, réactivable par register --update)")
    return 0


def _send(args: argparse.Namespace, usine: Usine) -> int:
    messagerie = usine.ouvrir(_boite(args))
    envoi = messagerie.envoyer(
        _agent(args, messagerie), args.to.split(","), args.subject, args.body or "", args.attach, args.reply_to)
    if not envoi.adresses_verifiees:
        sys.stderr.write("(boîte sans manifeste : destinataires non vérifiés — crée les comptes avec `register`)\n")
    for alias, adresses in envoi.alias_developpes:
        sys.stderr.write(f"(carnet : {alias} → {', '.join(adresses)})\n")
    print(envoi.message.id)
    return 0


def _contacts(args: argparse.Namespace, usine: Usine) -> int:
    messagerie = usine.ouvrir(_boite(args))
    carnet = messagerie.carnet(_agent(args, messagerie))
    if args.json:
        print(en_json({"contacts": [contact_vers_dict(c) for c in carnet.contacts], "masques": carnet.masques}),
              end="")
        return 0
    if not carnet.contacts:
        print("carnet vide : `contact-add --alias <alias> --to <adresse>[,<autre>] --note \"quand lui écrire\"`")
        return 0
    for c in carnet.contacts:
        masque = f"  [masqué par le compte {carnet.masques[c.alias]} : renomme-le]" if c.alias in carnet.masques else ""
        print(f"{c.alias:20} → {', '.join(c.adresses)}{('  — ' + c.note) if c.note else ''}{masque}")
    return 0


def _contact_add(args: argparse.Namespace, usine: Usine) -> int:
    messagerie = usine.ouvrir(_boite(args))
    contact = messagerie.noter_contact(_agent(args, messagerie), args.alias, args.to.split(","), args.note,
                                       remplacer=args.replace)
    print(f"contact noté : {contact.alias} → {', '.join(contact.adresses)}")
    return 0


def _contact_remove(args: argparse.Namespace, usine: Usine) -> int:
    messagerie = usine.ouvrir(_boite(args))
    contact = messagerie.retirer_contact(_agent(args, messagerie), args.alias)
    print(f"contact retiré : {contact.alias} (était {', '.join(contact.adresses)})")
    return 0


def _check(args: argparse.Namespace, usine: Usine) -> int:
    """Silencieuse, en code 0, si la boîte est injoignable : une relève ne bloque jamais une session.

    Avec `--hook`, lit la charge JSON que l'hôte donne à ses hooks sur l'entrée standard, quand il en
    donne une : le `session_id` rattache la session à son agent, le `cwd` donne le dépôt. La relève est
    posée par machine : elle tourne donc dans toutes les sessions de l'hôte, et ne dit rien hors d'un
    dépôt connecté. Dans un dépôt connecté, une session sans identité est invitée, à son démarrage,
    à s'enrôler.
    """
    session, dossier, evenement = args.session, os.getcwd(), args.event
    charge = {}
    if args.hook:
        charge = _lire_hook()
        session = session or (charge.get("session_id") if isinstance(charge.get("session_id"), str) else None)
        dossier = charge.get("cwd") if isinstance(charge.get("cwd"), str) else dossier
        evenement = evenement or charge.get("hook_event_name")
    fin_de_tour = evenement == "Stop"
    try:
        chemin = poste.resoudre_boite(args.box)
        nom = poste.resoudre_agent(args.agent, session, args.host, dossier)
        if not nom:
            # Une session sans identité ne se relance pas en fin de tour : elle est prévenue aux
            # moments où sa sortie entre dans le contexte (démarrage, message de l'humain).
            if args.hook and not fin_de_tour \
                    and not _annoncer_courrier_en_attente(chemin, session, evenement, usine, args.host) \
                    and evenement == "SessionStart" and poste.trouver_fichier_projet(dossier):
                _annoncer_enrolement(chemin, _projet(args, dossier), session, usine.depot(), args.host)
            return 0
        if not chemin:
            return 0
        messagerie = usine.ouvrir(chemin)
        agent = messagerie.adresse(nom, _projet(args, dossier))
        trouves = messagerie.releve(agent)
    except (ErreurMessenger, OSError):
        return 0
    if fin_de_tour:
        # Fin de tour : du courrier arrivé pendant le travail se traite avant de s'endormir, et une
        # session joignable garde sa veille armée. `stop_hook_active` = déjà une prolongation : on
        # laisse s'arrêter, jamais de boucle.
        if charge.get("stop_hook_active") is True:
            return 0
        veille = poste.veille_armee(session)
        consigne_veille = [] if veille else [_consigne_veille(agent, session, usine.depot())]
        if trouves:
            print(json.dumps({"decision": "block", "reason": "\n".join([
                f"COURRIER — {len(trouves)} message(s) pour {agent}, arrivé(s) pendant que tu travaillais. "
                "Avant de t'arrêter :",
                *(_resume(m) for m in trouves),
                "Lis chaque pièce jointe, agis, puis marque « lu » ou « traité » (outil MCP `mark`, ou "
                f"`messenger.py mark --agent {agent} --id <id> --status lu|traité`). Si un message ne te "
                "demande rien, marque-le simplement.",
                *consigne_veille,
            ])}, ensure_ascii=False))
            return 0
        # Pas de courrier : on ne retient la session qu'une fois, pour qu'elle arme sa veille.
        if veille or not session or poste.deja_annonce(session, ["veille"]):
            return 0
        poste.noter_annonce(session, ["veille"])
        print(json.dumps({"decision": "block",
                          "reason": "Avant de t'arrêter — " + _consigne_veille(agent, session, usine.depot())},
                         ensure_ascii=False))
        return 0
    if not trouves:
        return 0
    flux = sys.stderr if args.wake else sys.stdout
    if args.json:
        flux.write(en_json({"agent": agent, "nouveaux": [message_vers_dict(m) for m in trouves]}))
    else:
        flux.write("\n".join([
            f"COURRIER — {len(trouves)} message(s) au statut « nouveau » pour {agent}.",
            # Un hook peut injecter ce courrier dans une session voisine : elle doit savoir l'ignorer.
            f"Si tu n'es pas {agent}, ce courrier ne t'est pas adressé : ignore-le — n'agis pas, "
            "ne le marque pas, ne réponds pas à sa place.",
            f"Boîte : {messagerie.emplacement}",
            *(_resume(m) for m in trouves),
            f"À faire : lire chaque pièce jointe, agir, puis "
            f"`messenger.py mark --agent {agent} --id <id> --status lu|traité`.",
        ]) + "\n")
    return SORTIE_COURRIER if args.wake else 0


def _mark(args: argparse.Namespace, usine: Usine) -> int:
    messagerie = usine.ouvrir(_boite(args))
    messagerie.marquer(_agent(args, messagerie), args.id, args.status)
    print(f"{args.id} → {args.status}")
    return 0


def _list(args: argparse.Namespace, usine: Usine) -> int:
    messagerie = usine.ouvrir(_boite(args))
    agent = messagerie.adresse(args.agent, _projet(args)) if args.agent else None
    messages = messagerie.lister(agent, args.status, args.limit, args.project or None)
    if args.json:
        print(en_json([message_vers_dict(m) for m in messages]), end="")
    else:
        for m in messages:
            print(f"{(m.statut_vu_par([agent]) if agent else m.statut):8} {_resume(m)}")
    return 0


def _watch(args: argparse.Namespace, usine: Usine) -> int:
    """Attend le prochain message. Avec `--session`, tient la **veille** de cette session : tant qu'elle
    tourne, la relève de fin de tour sait que la session sera réveillée, et ne la retient pas pour rien."""
    messagerie = usine.ouvrir(_boite(args))
    agent = args.agent or poste.resoudre_agent(None, args.session, args.host, os.getcwd())
    if not agent:
        raise _Refus("dis-moi qui tu es : --agent <adresse> (ou enrôle-toi d'abord)")
    agent = messagerie.adresse(valider_adresse(agent), _projet(args))
    battement = _tenir_la_veille(args.session, agent) if args.session else None
    try:
        recus = messagerie.guetter(agent, args.interval, args.max_hours)
    finally:
        if battement:
            battement.set()
        if args.session:
            poste.desarmer_veille(args.session)
            # la veille est finie : au prochain tour, la fin de tour rappellera de la relancer
            poste.oublier_annonce(args.session, "veille")
    if not recus:
        print(f"aucun message pour {agent} en {args.max_hours:g} h — relance la veille si tu attends toujours")
        return SORTIE_ECHEANCE
    print(f"COURRIER — {len(recus)} nouveau(x) message(s) pour {agent}.")
    for m in recus:
        print(_resume(m))
    print("À faire : lire, agir, marquer (`mark`) — puis relance ta veille (watch).")
    return 0


def _tenir_la_veille(session: str, agent: str) -> threading.Event:
    """Rafraîchit la trace de veille en boucle, dans un fil : c'est sa fraîcheur qui fait foi."""
    arret = threading.Event()

    def battre() -> None:
        while not arret.is_set():
            try:
                poste.armer_veille(session, agent)
            except OSError:
                pass
            arret.wait(5.0)

    threading.Thread(target=battre, daemon=True).start()
    return arret


def _migrate(args: argparse.Namespace, usine: Usine) -> int:
    cible = usine.ouvrir(_boite(args))
    if cible.lecture_seule:
        raise _Refus("la boîte cible ne peut pas être une boîte Markdown : donne un dossier ou un fichier .json")
    resultat = cible.importer(usine.ancienne_boite(args.source))
    print(f"{resultat.messages} messages importés dans {cible.emplacement}")
    print(f"comptes importés, à compléter par chaque agent : {', '.join(resultat.comptes)}")
    return 0


def _ui(args: argparse.Namespace, usine: Usine) -> int:
    from .web import servir  # chargé à la demande : la CLI des agents n'en a pas besoin

    compte = valider_nom(poste.resoudre_agent(args.agent) or "owner")
    front = None if args.api else (args.front or usine.interface())

    def resolveur():
        # La boîte est résolue à chaque requête : elle peut apparaître en cours de route
        # (création depuis l'interface). Sans boîte configurée, on ouvre la démonstration.
        chemin = poste.resoudre_boite(args.box)
        if chemin:
            try:
                return usine.ouvrir(chemin), False
            except ErreurMessenger:
                pass
        return usine.ouvrir(usine.demonstration()), True

    messagerie, demo = resolveur()
    if demo:
        print("aucune boîte configurée : ouverture de la boîte de démonstration "
              "(crée la tienne depuis l'interface, ou `messenger.py setup --box <chemin>`)", flush=True)
    adresse = args.link or (f"http://127.0.0.1:{args.port}/" if front else None)
    annonceur = None if args.no_notify else Annonceur(
        messagerie, usine.notificateur(), compte,
        lien=(lambda m: f"{adresse}?message={m.id}") if adresse else None)
    return servir(messagerie, compte, args.port, front, ouvrir_navigateur=not args.no_browser,
                  lie_au_parent=args.exit_with_parent, demonstration=demo, annonceur=annonceur,
                  depot=usine.depot(), resolveur=resolveur, usine=usine)


def _notify(args: argparse.Namespace, usine: Usine) -> int:
    compte = valider_nom(poste.resoudre_agent(args.agent) or "owner")
    messagerie = usine.ouvrir(_boite(args))
    annonceur = Annonceur(messagerie, usine.notificateur(), compte)
    annonceur.relever()
    print(f"notifications système pour {messagerie.emplacement} — Ctrl+C pour arrêter", flush=True)
    while True:
        time.sleep(args.interval)
        try:
            arrives = annonceur.relever()
        except (ErreurMessenger, OSError):
            continue  # boîte momentanément injoignable : on réessaie au tour suivant
        for m in arrives:
            print(_resume(m), flush=True)


# --------------------------------------------------------------------------- #
def _boite(args: argparse.Namespace) -> str:
    chemin = poste.resoudre_boite(getattr(args, "box", None))
    if not chemin:
        raise _Refus("boîte inconnue : passe --box, ou MESSENGER_BOX, ou `messenger.py setup --box <chemin>`")
    return chemin


def _nom_agent(args: argparse.Namespace) -> str:
    agent = poste.resoudre_agent(getattr(args, "agent", None))
    if not agent:
        raise _Refus("agent inconnu : passe --agent <nom>, ou MESSENGER_AGENT")
    return valider_adresse(agent)


def _agent(args: argparse.Namespace, messagerie: Messagerie) -> str:
    """L'adresse de l'agent : son nom, rattaché au projet du dépôt s'il y en a un."""
    return messagerie.adresse(_nom_agent(args), _projet(args))


def _projet(args: argparse.Namespace, dossier: Optional[str] = None) -> Optional[str]:
    projet = poste.resoudre_projet(getattr(args, "project", None), dossier)
    return valider_nom(projet, "projet") if projet else None


def _afficher_hotes(etats) -> None:
    for e in etats:
        if not e.present:
            print(f"  {e.nom:12} non installé sur ce poste")
            continue
        marque = "équipé" if e.equipe else "à équiper"
        print(f"  {e.nom:12} {marque:10} serveur MCP : {e.mcp} · relève : {e.releve} · skill : {e.skill}")
        if e.note:
            print(f"  {'':12} {e.note}")


def _lire_hook() -> dict:
    """La charge JSON d'un hook Claude Code, sur l'entrée standard ; {} si absente ou illisible."""
    try:
        if sys.stdin is None or sys.stdin.isatty():
            return {}
        donnee = sys.stdin.read()
    except (OSError, ValueError):
        return {}
    try:
        charge = json.loads(donnee or "{}")
        return charge if isinstance(charge, dict) else {}
    except ValueError:
        return {}


def _consigne_veille(agent: str, session: Optional[str], depot: str) -> str:
    """Le rappel d'armer sa veille : la session sera réveillée à l'arrivée d'un message, au lieu de dormir dessus."""
    messenger = os.path.join(depot, "messenger.py")
    options = f" --session {session}" if session else ""
    return ("ARME TA VEILLE : lance en tâche de fond (outil Bash, run_in_background) "
            f"`python \"{messenger}\" watch --agent {agent}{options}` — tu seras réveillé dès qu'un message "
            "t'arrive, au lieu de dormir dessus. Quand elle rend la main : lis, marque, et relance-la.")


def _annoncer_courrier_en_attente(chemin: Optional[str], session: Optional[str], evenement: Optional[str],
                                  usine: Usine, hote: Optional[str]) -> bool:
    """Une session sans identité, mais du courrier attend un compte créé par cet hôte sur ce poste : on le lui
    dit — c'est peut-être elle, enrôlée depuis un autre dossier. Une fois par session (ou au démarrage, faute
    de `session_id`) : une session qui n'est pas ce compte n'est pas relancée à chaque message. Rend True si annoncé."""
    if not chemin or not hote or not (session or evenement == "SessionStart"):
        return False
    messagerie = usine.ouvrir(chemin)
    if not messagerie.annuaire_present():
        return False
    attendus = messagerie.en_attente_sur_ce_poste(hote, platform.node())
    adresses = [c.nom for c, _ in attendus]
    if not attendus or poste.deja_annonce(session, adresses):
        return False
    if session:
        poste.noter_annonce(session, adresses)
    messenger = os.path.join(usine.depot(), "messenger.py")
    options = f" --host {hote}" + (f" --session {session}" if session else "")
    sys.stdout.write("\n".join([
        f"📬 arkalabs-messenger — du courrier attend un compte créé par {hote} sur ce poste, et cette session "
        "n'a pas d'identité ici :",
        *(f"- {c.nom}{' (' + c.affichage + ')' if c.affichage else ''} — {n} message(s) · {c.role}"
          for c, n in attendus),
        "Si l'un de ces comptes est le tien, reprends-le depuis ce dossier :",
        "- si ton hôte a le serveur MCP « arkalabs-messenger » : outil `identify` (argument `address`), puis `check` ;",
        f"- sinon : \"{sys.executable}\" \"{messenger}\" identify --address <adresse>{options}",
        "Sinon, ignore ceci : ce courrier n'est pas pour toi — n'agis pas, ne le marque pas.",
    ]) + "\n")
    return True


def _annoncer_enrolement(chemin: Optional[str], projet: Optional[str], session: Optional[str],
                         depot: str, hote: Optional[str]) -> None:
    """Invite une session sans identité à s'enrôler, dans un dépôt connecté à la boîte."""
    messenger = os.path.join(depot, "messenger.py")
    options = (f" --host {hote}" if hote else "") + (f" --session {session}" if session else "")
    boite = f" · Boîte : {chemin}" if chemin else (
        " · Boîte : non configurée sur ce poste (`messenger.py setup --box <dossier>`, ou demande à ton humain)")
    sys.stdout.write("\n".join([
        "📬 arkalabs-messenger — ce dépôt est connecté à une boîte aux lettres, mais tu n'y es pas encore enrôlé.",
        f"Projet : {projet or '— (compte commun)'}" + boite,
        "Choisis un intitulé de tâche court et durable, puis crée ton compte :",
        "- si ton hôte a le serveur MCP « arkalabs-messenger » : appelle son outil `enroll` ;",
        f"- sinon : \"{sys.executable}\" \"{messenger}\" enroll --task \"<ta tâche>\"{options}",
        "Ton adresse (cl-agent-<tâche>-win) et ton nom lisible (CL_Agent-<Tâche>_WIN) se déduisent de ton",
        "hôte et de ton poste. Ensuite, ta relève se fait toute seule.",
    ]) + "\n")


def _resume(m: Message) -> str:
    return f"- {m.id} · {m.titre}  (de {m.de} · PJ : {m.pj or '—'})"


class _Parseur(argparse.ArgumentParser):
    """Une erreur d'usage sort en code 1 : le code 2 signifie « courrier présent »."""

    def error(self, message: str) -> None:  # type: ignore[override]
        self.print_usage(sys.stderr)
        self.exit(SORTIE_ERREUR, f"{self.prog} : {message}\n")


def _parseur() -> argparse.ArgumentParser:
    p = _Parseur(prog="messenger.py", description="Boîte aux lettres JSON partagée entre agents IA.")
    p.add_argument("--version", action="version", version=__version__)
    s = p.add_subparsers(dest="nom", required=True, parser_class=_Parseur)

    def commande(nom: str, aide: str, fonction, agent: bool = True, projet: bool = True) -> argparse.ArgumentParser:
        sp = s.add_parser(nom, help=aide, description=aide)
        sp.add_argument("--box", help="chemin de la boîte .json (sinon MESSENGER_BOX, sinon setup)")
        if agent:
            sp.add_argument("--agent", help="ton nom d'agent (sinon MESSENGER_AGENT)")
        if projet:
            sp.add_argument("--project", help="le projet (sinon MESSENGER_PROJECT, sinon le .messenger.json du dépôt)")
        sp.set_defaults(commande=fonction)
        return sp

    commande("init", "crée une boîte vide, son manifeste et sa vue", _init, agent=False, projet=False)
    commande("setup", "mémorise la boîte de ce poste (--box) et/ou le projet de ce dépôt (--project)", _setup,
             agent=False)
    x = commande("activate", "connecte ce dépôt à la boîte : boîte du poste, projet, hôtes IA équipés", _activate,
                 agent=False)
    x.add_argument("--no-releve", action="store_true", help="poser le serveur MCP sans la relève (hooks)")

    ids = ", ".join(h.id for h in hotes.HOTES)
    x = commande("install", "équipe les hôtes IA de ce poste : serveur MCP et relève", _install,
                 agent=False, projet=False)
    x.add_argument("--host", action="append", help=f"un hôte précis, répétable ({ids}) ; défaut : ceux du poste")
    x.add_argument("--no-releve", action="store_true", help="poser le serveur MCP sans la relève (hooks)")
    x.add_argument("--force", action="store_true",
                   help="remplacer l'entrée d'une autre installation d'arkalabs-messenger")
    x = commande("uninstall", "retire des hôtes IA ce que `install` y a posé", _uninstall, agent=False, projet=False)
    x.add_argument("--host", action="append", help=f"un hôte précis, répétable ({ids})")
    x = commande("hosts", "où en sont les hôtes IA de ce poste", _hosts, agent=False, projet=False)
    x.add_argument("--json", action="store_true", help="sortie JSON")
    x = commande("mcp", "le serveur MCP de la boîte, sur l'entrée et la sortie standard (lancé par l'hôte)", _mcp)
    x.add_argument("--host", help=f"l'hôte qui lance ce serveur ({ids})")

    x = commande("register", "crée ou met à jour ton compte", _register)
    x.add_argument("--host", required=True, help="ton hôte : claude-code, kimi-code, codex, hermes, humain…")
    x.add_argument("--role", required=True, help="en une ligne : ce que tu fais, pour qu'on sache quand t'écrire")
    x.add_argument("--machine", help="où tu tournes (défaut : nom du poste)")
    x.add_argument("--model", help="ton modèle, si utile")
    x.add_argument("--human", help="l'humain responsable")
    x.add_argument("--wake", help="comment tu relèves ton courrier (hooks, watch…)")
    x.add_argument("--display", help="nom lisible pour un humain (sinon déduit par enroll)")
    x.add_argument("--update", action="store_true", help="mettre à jour ton compte existant")

    x = commande("enroll", "s'inscrire avec une identité lisible déduite (hôte, tâche, poste)", _enroll, agent=False)
    x.add_argument("--task", required=True, help="l'intitulé de ta tâche, court et durable (ex. « MessengerAI »)")
    x.add_argument("--host", help="ton hôte : claude-code, codex, kimi-code… (défaut : claude-code)")
    x.add_argument("--poste", help="le code du poste : win, mac, lnx (défaut : d'après le système)")
    x.add_argument("--machine", help="où tu tournes (défaut : nom du poste)")
    x.add_argument("--role", help="ce que tu fais, en une ligne (défaut : d'après l'hôte et la tâche)")
    x.add_argument("--human", help="l'humain responsable")
    x.add_argument("--wake", help="comment tu relèves (défaut : hooks check --hook)")
    x.add_argument("--session", help="l'id de session à rattacher à cet agent")
    x.add_argument("--update", action="store_true", help="mettre à jour ton compte existant")

    x = commande("identify", "reprendre ton compte depuis ton dossier de travail (la relève saura qui tu es)",
                 _identify, agent=False)
    x.add_argument("--address", required=True, help="ton adresse : nom, ou nom@projet")
    x.add_argument("--host", help="ton hôte : claude-code, codex, kimi-code… (défaut : claude-code)")
    x.add_argument("--session", help="l'id de session à rattacher à cet agent")

    x = commande("attach", "range un compte commun dans un projet, ou l'en sort (geste de l'humain)", _attach,
                 agent=False, projet=False)
    x.add_argument("--account", required=True, help="l'adresse du compte (sans @projet)")
    x.add_argument("--to", default="", help="le projet ; vide pour le sortir de tout projet")

    x = commande("merge", "fusionne deux comptes d'un même agent : courrier en attente et adresse suivent",
                 _merge, agent=False, projet=False)
    x.add_argument("--account", required=True, help="l'adresse absorbée (l'ancien compte, en entier)")
    x.add_argument("--into", required=True, help="l'adresse qui absorbe (le compte gardé, en entier)")

    x = commande("agents", "liste les comptes", _agents, agent=False)
    x.add_argument("--all", action="store_true", help="inclure les comptes désactivés")
    x.add_argument("--json", action="store_true", help="sortie JSON (le manifeste)")

    commande("deactivate", "désactive un compte (jamais supprimé)", _deactivate)

    x = commande("send", "poste un message", _send)
    x.add_argument("--to", required=True,
                   help="destinataires, séparés par des virgules : adresses, noms courts, ou alias de ton carnet")
    x.add_argument("--subject", required=True)
    x.add_argument("--body", default="", help="deux lignes au plus")
    x.add_argument("--attach", help="fichier joint (copié dans le dossier de la boîte s'il n'y est pas)")
    x.add_argument("--reply-to", help="identifiant du message auquel tu réponds")

    x = commande("contacts", "ton carnet d'adresses : des alias pour une adresse, ou pour un groupe", _contacts)
    x.add_argument("--json", action="store_true", help="sortie JSON")

    x = commande("contact-add", "note un contact dans ton carnet (utilisable dans `send --to`)", _contact_add)
    x.add_argument("--alias", required=True, help="l'alias court : minuscules, chiffres, . _ - (32 max)")
    x.add_argument("--to", required=True, help="l'adresse, ou plusieurs séparées par des virgules (un groupe)")
    x.add_argument("--note", help="une ligne : qui c'est, quand lui écrire")
    x.add_argument("--replace", action="store_true", help="remplacer un contact existant")

    x = commande("contact-remove", "retire un contact de ton carnet", _contact_remove)
    x.add_argument("--alias", required=True)

    x = commande("check", "relève le courrier « nouveau » (hooks)", _check)
    x.add_argument("--wake", action="store_true", help="résumé sur stderr et code 2 s'il y a du courrier")
    x.add_argument("--json", action="store_true", help="sortie JSON")
    x.add_argument("--hook", action="store_true",
                   help="lit la charge JSON du hook Claude Code (session_id, cwd) sur l'entrée standard")
    x.add_argument("--session", help="l'id de session (sinon lu du hook avec --hook)")
    x.add_argument("--host", help="l'hôte qui lance cette relève (posé par `install`)")
    x.add_argument("--event", help="le moment de la relève : SessionStart ou UserPromptSubmit (posé par `install`)")

    x = commande("mark", "fait avancer le statut d'un message reçu", _mark)
    x.add_argument("--id", required=True)
    x.add_argument("--status", required=True, choices=STATUTS[1:])

    x = commande("list", "affiche les messages, du plus récent au plus ancien", _list)
    x.add_argument("--status", choices=STATUTS)
    x.add_argument("--limit", type=int, default=20)
    x.add_argument("--json", action="store_true", help="sortie JSON")

    x = commande("watch", "attend le prochain message pour un agent (et tient la veille de sa session)", _watch)
    x.add_argument("--interval", type=float, default=10.0, help="secondes entre deux relèves")
    x.add_argument("--max-hours", type=float, default=12.0)
    x.add_argument("--session", help="l'id de la session couverte : sa relève de fin de tour saura qu'elle veille")
    x.add_argument("--host", help="ton hôte, pour retrouver ton identité mémorisée (sinon --agent)")

    x = commande("migrate", "importe une ancienne boîte Markdown", _migrate, agent=False, projet=False)
    x.add_argument("--from", dest="source", required=True, help="la boîte Markdown à importer")

    x = commande("ui", "ouvre l'interface web locale (et son API)", _ui, projet=False)
    x.add_argument("--port", type=int, default=8765)
    x.add_argument("--api", action="store_true", help="API seule, sans interface (utilisé par `npm run dev`)")
    x.add_argument("--front", help="dossier de l'interface construite (défaut : ui/dist)")
    x.add_argument("--no-browser", action="store_true", help="ne pas ouvrir le navigateur")
    x.add_argument("--exit-with-parent", action="store_true",
                   help="s'arrêter quand l'entrée standard se ferme (utilisé par `npm run dev`)")
    x.add_argument("--no-notify", action="store_true", help="sans notifications système")
    x.add_argument("--link", help="adresse de l'interface, ouverte au clic sur une notification")

    x = commande("start", "ouvre l'interface web locale — le point d'entrée humain (raccourci de `ui`)",
                 _start, projet=False)
    x.add_argument("--port", type=int, default=8765)
    x.add_argument("--no-browser", action="store_true", help="ne pas ouvrir le navigateur")
    x.add_argument("--no-notify", action="store_true", help="sans notifications système")
    x.add_argument("--log", help="écrire le journal dans ce fichier (lancement sans console : raccourci du bureau)")

    x = commande("shortcut", "pose l'icône « Messenger » sur le bureau : un double-clic allume la boîte", _shortcut,
                 agent=False, projet=False)
    x.add_argument("--remove", action="store_true", help="retirer l'icône du bureau")

    x = commande("notify", "notifie chaque message qui passe, sans interface", _notify, projet=False)
    x.add_argument("--interval", type=float, default=5.0, help="secondes entre deux relèves")
    return p
