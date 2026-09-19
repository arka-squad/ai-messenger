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
import time
from typing import Optional, Protocol, Sequence

from ... import __version__
from ...application import Annonceur, Messagerie, Notificateur, SourceAncienne
from ...domain import (
    STATUTS,
    Annuaire,
    ErreurMessenger,
    Message,
    composer_identite,
    qualifier,
    slugifier,
    valider_adresse,
    valider_nom,
)
from ..codec import annuaire_vers_dict, en_json, message_vers_dict
from . import poste

SORTIE_ERREUR, SORTIE_COURRIER, SORTIE_ECHEANCE = 1, 2, 3


class Usine(Protocol):
    """Ce que la ligne de commande attend de l'assemblage (voir bootstrap.py)."""

    def ouvrir(self, chemin: str) -> Messagerie: ...
    def ancienne_boite(self, chemin: str) -> SourceAncienne: ...
    def interface(self) -> Optional[str]: ...
    def demonstration(self) -> str: ...
    def notificateur(self) -> Notificateur: ...
    def depot(self) -> str: ...


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
    print(f"boîte créée : {messagerie.emplacement}")
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
    poste_code = args.poste or _poste_code()
    adresse_slug, affichage = composer_identite(hote, args.task, poste_code)
    machine = args.machine or platform.node()
    messagerie = usine.ouvrir(_boite(args))
    comptes = {c.nom: c for c in messagerie.comptes(tous=True)}
    nom, existant = _slug_libre(adresse_slug, _projet(args), comptes, machine)
    if existant is not None and not args.update:
        compte, etat = existant, "déjà inscrit"
    else:
        compte, cree = messagerie.inscrire(
            nom, hote, args.role or f"{hote} — {args.task}",
            machine=machine, humain=args.human,
            releve=args.wake or "hooks (messenger.py check --hook)",
            affichage=affichage, mise_a_jour=existant is not None)
        etat = "compte créé" if cree else "compte mis à jour"
    if args.session:
        poste.memoriser_session(args.session, compte.nom)
    print(f"{etat} : {compte.affichage or compte.nom}  (adresse {compte.nom})")
    if args.session:
        print(f"session {args.session} rattachée à {compte.nom} : cette session te reconnaît sans variable")
    else:
        print("astuce : passe --session <id de session> pour être reconnu automatiquement à chaque tour")
    return 0


def _activate(args: argparse.Namespace, usine: Usine) -> int:
    """Activer ce dépôt : boîte du poste, projet du dépôt, hooks et skill installés dans .claude/."""
    if args.box is not None:
        messagerie = usine.ouvrir(args.box)
        messagerie.instantane()  # refuse une boîte illisible
        chemin = messagerie.emplacement
    else:
        chemin = poste.resoudre_boite(None)
        if not chemin:
            raise _Refus("aucune boîte sur ce poste : passe --box <chemin>, "
                         "ou fais d'abord `messenger.py setup --box <chemin>`")
    projet = valider_nom(args.project, "projet") if args.project else None
    try:
        resume = poste.activer_depot(os.getcwd(), projet, usine.depot(), box=chemin)
    except poste.ActivationRefusee as e:
        raise _Refus(str(e)) from None
    print(f"dépôt activé : {resume['dossier']}")
    print(f"  boîte (poste) : {resume['boite']}")
    print(f"  projet        : {resume['projet'] or '— (compte commun)'}")
    print(f"  hooks         : {resume['hooks']}")
    print(f"  skill         : {resume['skill']}")
    print("Chaque session ouverte ici sera invitée à s'enrôler (messenger.py enroll), puis relèvera seule.")
    return 0


def _start(args: argparse.Namespace, usine: Usine) -> int:
    """Le point d'entrée humain : ouvre l'interface web locale (et son API)."""
    args.api = False
    args.front = None
    args.exit_with_parent = False
    args.link = None
    return _ui(args, usine)


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
    print(envoi.message.id)
    return 0


def _check(args: argparse.Namespace, usine: Usine) -> int:
    """Silencieuse, en code 0, si la boîte est injoignable : une relève ne bloque jamais une session.

    Avec `--hook`, lit la charge JSON du hook Claude Code sur l'entrée standard : elle donne le
    `session_id` (qui rattache la session à son agent enrôlé) et le `cwd` (qui donne le projet).
    Une session encore sans identité, au démarrage, reçoit une invitation à s'enrôler.
    """
    session, dossier, evenement = getattr(args, "session", None), None, None
    if getattr(args, "hook", False):
        charge = _lire_hook()
        session = session or (charge.get("session_id") if isinstance(charge.get("session_id"), str) else None)
        dossier = charge.get("cwd") if isinstance(charge.get("cwd"), str) else None
        evenement = charge.get("hook_event_name")
    try:
        chemin = poste.resoudre_boite(args.box)
        nom = poste.resoudre_agent(args.agent, session)
        if not nom:
            if getattr(args, "hook", False) and evenement in (None, "SessionStart"):
                _annoncer_enrolement(chemin, _projet(args, dossier), session)
            return 0
        if not chemin:
            return 0
        messagerie = usine.ouvrir(chemin)
        agent = messagerie.adresse(nom, _projet(args, dossier))
        trouves = messagerie.releve(agent)
    except (ErreurMessenger, OSError):
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
            print(f"{m.statut:8} {_resume(m)}")
    return 0


def _watch(args: argparse.Namespace, usine: Usine) -> int:
    messagerie = usine.ouvrir(_boite(args))
    agent = _agent(args, messagerie)
    recus = messagerie.guetter(agent, args.interval, args.max_hours)
    if not recus:
        print(f"aucun message pour {agent} en {args.max_hours:g} h")
        return SORTIE_ECHEANCE
    print(f"COURRIER — {len(recus)} nouveau(x) message(s) pour {agent}.")
    for m in recus:
        print(_resume(m))
    return 0


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


def _poste_code() -> str:
    """Le code du poste pour l'identité : `win`, `mac`, `lnx`, ou trois lettres du système."""
    systeme = platform.system()
    return {"Windows": "win", "Darwin": "mac", "Linux": "lnx"}.get(systeme) or (slugifier(systeme)[:3] or "pc")


def _slug_libre(adresse_slug: str, projet: Optional[str], comptes: dict, machine: str):
    """Le premier slug libre pour cette machine : réutilise le tien, sinon suffixe -2, -3…"""
    n = 1
    while True:
        candidat = adresse_slug if n == 1 else f"{adresse_slug[:29]}-{n}"
        nom = qualifier(candidat, projet)
        existant = comptes.get(nom)
        if existant is None:
            return nom, None
        if (existant.machine or "") == (machine or ""):
            return nom, existant  # c'est le tien : on le réutilise
        n += 1


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


def _annoncer_enrolement(chemin: Optional[str], projet: Optional[str], session: Optional[str]) -> None:
    """Invite une session sans identité à s'enrôler dans un dépôt activé."""
    option_session = f" --session {session}" if session else ""
    boite = f" · Boîte : {chemin}" if chemin else (
        " · Boîte : non configurée sur ce poste (`messenger.py setup --box <chemin>`, ou demande à ton humain)")
    sys.stdout.write("\n".join([
        "📬 arkalabs-messenger — une boîte est active pour ce dépôt, mais tu n'y es pas encore enrôlé.",
        f"Projet : {projet or '— (compte commun)'}" + boite,
        "Pour recevoir et écrire du courrier, en une fois :",
        "1. Charge la skill « arkalabs-messenger » (lire, répondre, ignorer ce qui n'est pas pour toi).",
        "2. Choisis un intitulé de tâche court et durable, puis enregistre-toi :",
        f"   python messenger.py enroll --task \"<ta tâche>\"{option_session}",
        "   Ton adresse (cl-agent-<tâche>-win) et ton nom lisible (CL_Agent-<Tâche>_WIN) se déduisent",
        "   de ton hôte et de ton poste. Ensuite, ta relève se fait toute seule.",
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
    commande("activate", "active ce dépôt : boîte du poste, projet, hooks et skill dans .claude/", _activate,
             agent=False)

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

    x = commande("agents", "liste les comptes", _agents, agent=False)
    x.add_argument("--all", action="store_true", help="inclure les comptes désactivés")
    x.add_argument("--json", action="store_true", help="sortie JSON (le manifeste)")

    commande("deactivate", "désactive un compte (jamais supprimé)", _deactivate)

    x = commande("send", "poste un message", _send)
    x.add_argument("--to", required=True, help="destinataires, séparés par des virgules")
    x.add_argument("--subject", required=True)
    x.add_argument("--body", default="", help="deux lignes au plus")
    x.add_argument("--attach", help="fichier joint (copié dans le dossier de la boîte s'il n'y est pas)")
    x.add_argument("--reply-to", help="identifiant du message auquel tu réponds")

    x = commande("check", "relève le courrier « nouveau » (hooks)", _check)
    x.add_argument("--wake", action="store_true", help="résumé sur stderr et code 2 s'il y a du courrier")
    x.add_argument("--json", action="store_true", help="sortie JSON")
    x.add_argument("--hook", action="store_true",
                   help="lit la charge JSON du hook Claude Code (session_id, cwd) sur l'entrée standard")
    x.add_argument("--session", help="l'id de session (sinon lu du hook avec --hook)")

    x = commande("mark", "fait avancer le statut d'un message reçu", _mark)
    x.add_argument("--id", required=True)
    x.add_argument("--status", required=True, choices=STATUTS[1:])

    x = commande("list", "affiche les messages, du plus récent au plus ancien", _list)
    x.add_argument("--status", choices=STATUTS)
    x.add_argument("--limit", type=int, default=20)
    x.add_argument("--json", action="store_true", help="sortie JSON")

    x = commande("watch", "attend le prochain message pour un agent", _watch)
    x.add_argument("--interval", type=float, default=10.0, help="secondes entre deux relèves")
    x.add_argument("--max-hours", type=float, default=12.0)

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

    x = commande("notify", "notifie chaque message qui passe, sans interface", _notify, projet=False)
    x.add_argument("--interval", type=float, default=5.0, help="secondes entre deux relèves")
    return p
