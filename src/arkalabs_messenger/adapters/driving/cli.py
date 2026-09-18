"""La ligne de commande — l'interface des agents.

Codes de sortie : 0 succès ; 1 erreur ; 2 courrier présent (`check --wake`) ;
3 rien reçu avant l'échéance (`watch`).
"""
from __future__ import annotations

import argparse
import os
import platform
import sys
import time
from typing import Optional, Protocol, Sequence

from ... import __version__
from ...application import Annonceur, Messagerie, Notificateur, SourceAncienne
from ...domain import STATUTS, Annuaire, ErreurMessenger, Message, qualifier, valider_adresse, valider_nom
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
    chemin = _boite(args)
    if not chemin.lower().endswith(".json"):
        raise _Refus(f"la boîte est un fichier .json : {chemin}")
    messagerie = usine.ouvrir(chemin)
    messagerie.initialiser()
    racine = os.path.splitext(messagerie.emplacement)[0]
    print(f"boîte créée     : {messagerie.emplacement}")
    print(f"comptes         : {racine}.manifest.json")
    print(f"vue (lecture)   : {racine}.md")
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


def _register(args: argparse.Namespace, usine: Usine) -> int:
    compte, cree = usine.ouvrir(_boite(args)).inscrire(
        qualifier(_nom_agent(args), _projet(args)), args.host, args.role,
        machine=args.machine or (None if args.update else platform.node()),
        modele=args.model, humain=args.human, releve=args.wake, mise_a_jour=args.update)
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
    """Silencieuse, en code 0, si la boîte est injoignable : une relève ne bloque jamais une session."""
    try:
        chemin, nom = poste.resoudre_boite(args.box), poste.resoudre_agent(args.agent)
        if not chemin or not nom:
            return 0
        messagerie = usine.ouvrir(chemin)
        agent = messagerie.adresse(nom, _projet(args))
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
    cible = _boite(args)
    if not cible.lower().endswith(".json"):
        raise _Refus(f"la boîte cible est un fichier .json : {cible}")
    resultat = usine.ouvrir(cible).importer(usine.ancienne_boite(args.source))
    print(f"{resultat.messages} messages importés dans {usine.ouvrir(cible).emplacement}")
    print(f"comptes importés, à compléter par chaque agent : {', '.join(resultat.comptes)}")
    return 0


def _ui(args: argparse.Namespace, usine: Usine) -> int:
    from .web import servir  # chargé à la demande : la CLI des agents n'en a pas besoin

    compte = valider_nom(poste.resoudre_agent(args.agent) or "owner")
    front = None if args.api else (args.front or usine.interface())
    # Sans boîte configurée, l'interface — et elle seule — ouvre la démonstration du dépôt.
    chemin = poste.resoudre_boite(args.box)
    demo = chemin is None
    if demo:
        chemin = usine.demonstration()
        print("aucune boîte configurée : ouverture de la boîte de démonstration "
              "(MESSENGER_BOX, ou `messenger.py setup --box <chemin>`, pour la tienne)", flush=True)
    messagerie = usine.ouvrir(chemin)
    adresse = args.link or (f"http://127.0.0.1:{args.port}/" if front else None)
    annonceur = None if args.no_notify else Annonceur(
        messagerie, usine.notificateur(), compte,
        lien=(lambda m: f"{adresse}?message={m.id}") if adresse else None)
    return servir(messagerie, compte, args.port, front, ouvrir_navigateur=not args.no_browser,
                  lie_au_parent=args.exit_with_parent, demonstration=demo, annonceur=annonceur)


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


def _projet(args: argparse.Namespace) -> Optional[str]:
    projet = poste.resoudre_projet(getattr(args, "project", None))
    return valider_nom(projet, "projet") if projet else None


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

    x = commande("register", "crée ou met à jour ton compte", _register)
    x.add_argument("--host", required=True, help="ton hôte : claude-code, kimi-code, codex, hermes, humain…")
    x.add_argument("--role", required=True, help="en une ligne : ce que tu fais, pour qu'on sache quand t'écrire")
    x.add_argument("--machine", help="où tu tournes (défaut : nom du poste)")
    x.add_argument("--model", help="ton modèle, si utile")
    x.add_argument("--human", help="l'humain responsable")
    x.add_argument("--wake", help="comment tu relèves ton courrier (hooks, watch…)")
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

    x = commande("notify", "notifie chaque message qui passe, sans interface", _notify, projet=False)
    x.add_argument("--interval", type=float, default=5.0, help="secondes entre deux relèves")
    return p
