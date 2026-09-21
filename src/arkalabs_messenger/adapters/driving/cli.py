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
        raise _Refus("a Markdown mailbox cannot be initialized: provide a directory (.aimessenger/ layout) or a .json file")
    messagerie.initialiser()
    onboarding = usine.poser_onboarding(_boite(args))
    print(f"mailbox created: {messagerie.emplacement}")
    print(f"agent onboarding guide: {onboarding}")
    print("accounts, human-readable view, and attachments are stored alongside it (see PROTOCOLE.md).")
    return 0


def _setup(args: argparse.Namespace, usine: Usine) -> int:
    if args.box is None and args.project is None:
        raise _Refus("nothing to remember: pass --box (this machine's mailbox) and/or --project (this repository's project)")
    if args.box is not None:
        messagerie = usine.ouvrir(args.box)
        messagerie.instantane()  # refuse une boîte illisible
        config = poste.memoriser_boite(messagerie.emplacement)
        print(f"mailbox remembered for this machine in {config}: {messagerie.emplacement}")
    if args.project:
        fichier = poste.attacher_projet(os.getcwd(), valider_nom(args.project, "projet"))
        print(f"project “{args.project}” attached to this repository: {fichier} (commit this file)")
    return 0


def _enroll(args: argparse.Namespace, usine: Usine) -> int:
    """S'inscrire avec une identité lisible déduite de l'hôte, de la tâche et du poste."""
    hote = args.host or "claude-code"
    compte, cree = usine.ouvrir(_boite(args)).enroler(
        hote, args.task, args.poste or poste.code_du_poste(), _projet(args), args.machine or platform.node(),
        role=args.role, humain=args.human, releve=args.wake or "hooks (messenger.py check --hook)",
        mise_a_jour=args.update)
    etat = "account created" if cree else "account updated" if args.update else "already enrolled"
    poste.memoriser_identite(hote, os.getcwd(), compte.nom)
    if args.session:
        poste.memoriser_session(args.session, compte.nom)
    print(f"{etat}: {compte.affichage or compte.nom}  (address {compte.nom})")
    if args.session:
        print(f"session {args.session} linked to {compte.nom}: this session now recognizes you without an environment variable")
    return 0


def _identify(args: argparse.Namespace, usine: Usine) -> int:
    """Reprendre son compte depuis son dossier de travail : la relève de ce dossier saura qui tu es."""
    hote = args.host or "claude-code"
    messagerie = usine.ouvrir(_boite(args))
    compte = messagerie.reprendre(messagerie.adresse(args.address, _projet(args)), hote, platform.node())
    poste.memoriser_identite(hote, os.getcwd(), compte.nom)
    if args.session:
        poste.memoriser_session(args.session, compte.nom)
    print(f"identity confirmed: {compte.affichage or compte.nom}  (address {compte.nom})")
    print(f"mail checks now recognize you in {os.getcwd()} — check your mail: check --agent {compte.nom}")
    return 0


def _attach(args: argparse.Namespace, usine: Usine) -> int:
    """Ranger un compte commun dans un projet, ou l'en sortir : le geste de l'humain qui organise sa boîte."""
    compte = usine.ouvrir(_boite(args)).rattacher(args.account, args.to or None)
    print(f"{compte.nom} → {'project ' + compte.projet if compte.projet else 'no project (shared account)'}")
    return 0


def _merge(args: argparse.Namespace, usine: Usine) -> int:
    """Fusionner deux comptes d'un même agent : le geste de l'humain qui range sa boîte."""
    messagerie = usine.ouvrir(_boite(args))
    marque = messagerie.fusionner(args.account, args.into)
    herites = messagerie.releve(args.into)
    print(f"{marque.nom} → merged into {args.into}")
    print(f"  pending mail now reaches {args.into} ({len(herites)} nouveau message(s) to check);")
    print(f"  mail sent to {marque.nom} now reaches {args.into}; existing messages remain unchanged.")
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
            raise _Refus("no mailbox configured on this machine: pass --box <directory>, "
                         "or first run `messenger.py setup --box <directory>`")
    projet = valider_nom(args.project, "project") if args.project else None
    try:
        resume = poste.activer_depot(os.getcwd(), projet, usine.depot(), box=chemin, releve=not args.no_releve)
    except poste.ActivationRefusee as e:
        raise _Refus(str(e)) from None
    if resume["projet"]:
        _declarer_projet(usine, chemin, resume["projet"])
    print(f"repository connected: {resume['dossier']}")
    print(f"  mailbox (machine): {resume['boite']}")
    print(f"  project          : {resume['projet'] or '— (shared account)'}")
    _afficher_hotes(resume["hotes"])
    print("Every session opened here will be invited to enroll and will then check mail automatically.")
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
        print("no supported AI host found on this machine (Claude Code, Codex, Kimi Code, Antigravity, Cursor)")
        return 0
    _afficher_hotes(etats)
    print("Changes take effect in each host's next session (Codex may ask you to approve its hooks).")
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
        raise _Refus("the built interface is missing (ui/dist): obtain the complete repository or run `npm run build`")
    import webbrowser
    from .web import OUTIL

    port = args.port
    for port in range(args.port, args.port + 20):
        outil = _qui_ecoute(port)
        if outil == OUTIL:
            print(f"the mailbox is already running: http://127.0.0.1:{port}/", flush=True)
            if not args.no_browser:
                webbrowser.open(f"http://127.0.0.1:{port}/")
            return 0
        if outil is None and _port_libre(port):
            break
    else:
        raise _Refus(f"no free port between {args.port} and {args.port + 19}: close the process using those ports")
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
            print("desktop shortcut removed" if raccourci.retirer() else "no desktop shortcut found")
            return 0
        if not usine.interface():
            raise _Refus("the built interface is missing (ui/dist): obtain the complete repository or run `npm run build`")
        cible = raccourci.poser(usine.depot())
    except raccourci.RaccourciImpossible as e:
        raise _Refus(str(e)) from None
    print(f"desktop icon created: {cible}")
    print("Double-click it to start the mailbox and open it in your browser.")
    if not poste.resoudre_boite(None):
        print("(no mailbox configured on this machine yet; the interface will offer Create mailbox)")
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
    print(f"account {'created' if cree else 'updated'}: {compte.nom} ({compte.hote}, {compte.machine})")
    return 0


def _agents(args: argparse.Namespace, usine: Usine) -> int:
    messagerie = usine.ouvrir(_boite(args))
    racine = os.path.splitext(messagerie.emplacement)[0]
    if not messagerie.annuaire_present():
        print(f"this mailbox has no manifest ({racine}.manifest.json): no accounts")
        return 0
    comptes = messagerie.comptes(tous=True, projet=args.project or None)
    if args.json:
        print(en_json(annuaire_vers_dict(Annuaire(comptes), os.path.basename(messagerie.emplacement))), end="")
        return 0
    for c in comptes:
        if c.actif or args.all:
            etat = "" if c.actif else "  [disabled]"
            print(f"{c.nom:28} {c.hote:12} {c.machine or '?':22} {c.role}{etat}")
    return 0


def _deactivate(args: argparse.Namespace, usine: Usine) -> int:
    messagerie = usine.ouvrir(_boite(args))
    nom = _agent(args, messagerie)
    messagerie.desactiver(nom)
    print(f"account deactivated: {nom} (kept in the manifest; register --update can reactivate it)")
    return 0


class Cumul(argparse.Action):
    """Un `--to` répété s'ajoute au lieu d'écraser.

    Sans elle, `--to a --to b` n'envoie qu'à `b`, sans rien dire : une liste de destinataires se
    perdait en silence. Signalé par un agent le 21/09/2026.
    """

    def __call__(self, parser, namespace, values, option_string=None):  # type: ignore[override]
        ancien = getattr(namespace, self.dest, None)
        setattr(namespace, self.dest, f"{ancien},{values}" if ancien else values)


def _send(args: argparse.Namespace, usine: Usine) -> int:
    messagerie = usine.ouvrir(_boite(args))
    envoi = messagerie.envoyer(
        _agent(args, messagerie), args.to.split(","), args.subject, args.body or "", args.attach, args.reply_to)
    if not envoi.adresses_verifiees:
        sys.stderr.write("(mailbox without a manifest: recipients were not verified; create accounts with `register`)\n")
    for alias, adresses in envoi.alias_developpes:
        sys.stderr.write(f"(address book: {alias} → {', '.join(adresses)})\n")
    # les destinataires retenus, pour que personne n'en perde un sans s'en apercevoir ;
    # la sortie standard ne porte que l'identifiant : c'est un contrat lu par des agents
    sys.stderr.write(f"(sent to {len(envoi.message.a)}: {', '.join(envoi.message.a)})\n")
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
        print("empty address book: `contact-add --alias <alias> --to <address>[,<another>] --note \"when to write\"`")
        return 0
    for c in carnet.contacts:
        masque = f"  [shadowed by account {carnet.masques[c.alias]}; rename it]" if c.alias in carnet.masques else ""
        print(f"{c.alias:20} → {', '.join(c.adresses)}{('  — ' + c.note) if c.note else ''}{masque}")
    return 0


def _contact_add(args: argparse.Namespace, usine: Usine) -> int:
    messagerie = usine.ouvrir(_boite(args))
    contact = messagerie.noter_contact(_agent(args, messagerie), args.alias, args.to.split(","), args.note,
                                       remplacer=args.replace)
    print(f"contact saved: {contact.alias} → {', '.join(contact.adresses)}")
    return 0


def _contact_remove(args: argparse.Namespace, usine: Usine) -> int:
    messagerie = usine.ouvrir(_boite(args))
    contact = messagerie.retirer_contact(_agent(args, messagerie), args.alias)
    print(f"contact removed: {contact.alias} (was {', '.join(contact.adresses)})")
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
                f"MAIL — {len(trouves)} message(s) for {agent}, received while you were working. "
                "Before stopping:",
                *(_resume(m) for m in trouves),
                "Read every attachment, act, then mark lu or traité (MCP `mark`, or "
                f"`messenger.py mark --agent {agent} --id <id> --status lu|traité`). If a message "
                "requires no action, simply mark it.",
                *consigne_veille,
            ])}, ensure_ascii=False))
            return 0
        # Pas de courrier : on ne retient la session qu'une fois, pour qu'elle arme sa veille.
        if veille or not session or poste.deja_annonce(session, ["veille"]):
            return 0
        poste.noter_annonce(session, ["veille"])
        print(json.dumps({"decision": "block",
                          "reason": "Before stopping — " + _consigne_veille(agent, session, usine.depot())},
                         ensure_ascii=False))
        return 0
    if not trouves:
        return 0
    flux = sys.stderr if args.wake else sys.stdout
    if args.json:
        flux.write(en_json({"agent": agent, "nouveaux": [message_vers_dict(m) for m in trouves]}))
    else:
        flux.write("\n".join([
            f"MAIL — {len(trouves)} message(s) with status nouveau for {agent}.",
            # Un hook peut injecter ce courrier dans une session voisine : elle doit savoir l'ignorer.
            f"If you are not {agent}, this mail is not addressed to you: ignore it. Do not act, "
            "mark it, or reply on the recipient's behalf.",
            f"Mailbox: {messagerie.emplacement}",
            *(_resume(m) for m in trouves),
            f"Next: read every attachment, act, then run "
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
        raise _Refus("identify yourself with --agent <address>, or enroll first")
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
        print(f"no message for {agent} in {args.max_hours:g} h — restart the watch if you are still waiting")
        return SORTIE_ECHEANCE
    print(f"MAIL — {len(recus)} new message(s) for {agent}.")
    for m in recus:
        print(_resume(m))
    print("Next: read, act, mark (`mark`), then restart your watch.")
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
        raise _Refus("the target cannot be a Markdown mailbox: provide a directory or .json file")
    resultat = cible.importer(usine.ancienne_boite(args.source))
    print(f"{resultat.messages} messages imported into {cible.emplacement}")
    print(f"imported accounts, to be completed by their agents: {', '.join(resultat.comptes)}")
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
        print("no mailbox configured: opening the demo mailbox "
              "(create yours in the interface, or run `messenger.py setup --box <path>`)", flush=True)
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
    print(f"system notifications for {messagerie.emplacement} — Ctrl+C to stop", flush=True)
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
        raise _Refus("unknown mailbox: pass --box, set MESSENGER_BOX, or run `messenger.py setup --box <path>`")
    return chemin


def _nom_agent(args: argparse.Namespace) -> str:
    agent = poste.resoudre_agent(getattr(args, "agent", None))
    if not agent:
        raise _Refus("unknown agent: pass --agent <name> or set MESSENGER_AGENT")
    return valider_adresse(agent)


def _agent(args: argparse.Namespace, messagerie: Messagerie) -> str:
    """L'adresse de l'agent : son nom, rattaché au projet du dépôt s'il y en a un."""
    return messagerie.adresse(_nom_agent(args), _projet(args))


def _projet(args: argparse.Namespace, dossier: Optional[str] = None) -> Optional[str]:
    projet = poste.resoudre_projet(getattr(args, "project", None), dossier)
    return valider_nom(projet, "project") if projet else None


def _afficher_hotes(etats) -> None:
    for e in etats:
        if not e.present:
            print(f"  {e.nom:12} not installed on this machine")
            continue
        marque = "ready" if e.equipe else "set up"
        print(f"  {e.nom:12} {marque:10} MCP server: {e.mcp} · mail checks: {e.releve} · skill: {e.skill}")
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
    return ("ARM YOUR WATCH: run in the background (Bash tool, run_in_background) "
            f"`python \"{messenger}\" watch --agent {agent}{options}`. It wakes you as soon as mail "
            "arrives. When it returns: read, mark, and start it again.")


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
        f"📬 arkalabs-messenger — mail is waiting for an account created by {hote} on this machine, "
        "but this session has no identity here:",
        *(f"- {c.nom}{' (' + c.affichage + ')' if c.affichage else ''} — {n} message(s) · {c.role}"
          for c, n in attendus),
        "If one of these accounts is yours, identify it from this directory:",
        "- with the arkalabs-messenger MCP server: call `identify` with `address`, then `check`;",
        f"- otherwise: \"{sys.executable}\" \"{messenger}\" identify --address <address>{options}",
        "Otherwise ignore this notice: the mail is not for you. Do not act or mark it.",
    ]) + "\n")
    return True


def _annoncer_enrolement(chemin: Optional[str], projet: Optional[str], session: Optional[str],
                         depot: str, hote: Optional[str]) -> None:
    """Invite une session sans identité à s'enrôler, dans un dépôt connecté à la boîte."""
    messenger = os.path.join(depot, "messenger.py")
    options = (f" --host {hote}" if hote else "") + (f" --session {session}" if session else "")
    boite = f" · Mailbox: {chemin}" if chemin else (
        " · Mailbox: not configured on this machine (`messenger.py setup --box <directory>`, or ask your human)")
    sys.stdout.write("\n".join([
        "📬 arkalabs-messenger — this repository is connected to a mailbox, but you are not enrolled yet.",
        f"Project: {projet or '— (shared account)'}" + boite,
        "Choose a short, durable task title, then create your account:",
        "- with the arkalabs-messenger MCP server: call `enroll`;",
        f"- otherwise: \"{sys.executable}\" \"{messenger}\" enroll --task \"<your task>\"{options}",
        "Your address (cl-agent-<task>-win) and display name (CL_Agent-<Task>_WIN) are derived from",
        "your host and machine. Mail checks then run automatically.",
    ]) + "\n")


def _resume(m: Message) -> str:
    return f"- {m.id} · {m.titre}  (from {m.de} · attachment: {m.pj or '—'})"


class _Parseur(argparse.ArgumentParser):
    """Une erreur d'usage sort en code 1 : le code 2 signifie « courrier présent »."""

    def error(self, message: str) -> None:  # type: ignore[override]
        self.print_usage(sys.stderr)
        self.exit(SORTIE_ERREUR, f"{self.prog} : {message}\n")


def _parseur() -> argparse.ArgumentParser:
    p = _Parseur(prog="messenger.py", description="Shared JSON mailbox for AI agents.")
    p.add_argument("--version", action="version", version=__version__)
    s = p.add_subparsers(dest="nom", required=True, parser_class=_Parseur)

    def commande(nom: str, aide: str, fonction, agent: bool = True, projet: bool = True) -> argparse.ArgumentParser:
        sp = s.add_parser(nom, help=aide, description=aide)
        sp.add_argument("--box", help="mailbox .json path (otherwise MESSENGER_BOX, then setup)")
        if agent:
            sp.add_argument("--agent", help="your agent name (otherwise MESSENGER_AGENT)")
        if projet:
            sp.add_argument("--project", help="project (otherwise MESSENGER_PROJECT, then repository .messenger.json)")
        sp.set_defaults(commande=fonction)
        return sp

    commande("init", "create an empty mailbox, account manifest, and human view", _init, agent=False, projet=False)
    commande("setup", "remember this machine's mailbox (--box) and/or this repository's project (--project)", _setup,
             agent=False)
    x = commande("activate", "connect this repository: machine mailbox, project, and configured AI hosts", _activate,
                 agent=False)
    x.add_argument("--no-releve", action="store_true", help="install the MCP server without mail-check hooks")

    ids = ", ".join(h.id for h in hotes.HOTES)
    x = commande("install", "configure this machine's AI hosts: MCP server and mail-check hooks", _install,
                 agent=False, projet=False)
    x.add_argument("--host", action="append", help=f"specific repeatable host ({ids}); default: installed hosts")
    x.add_argument("--no-releve", action="store_true", help="install the MCP server without mail-check hooks")
    x.add_argument("--force", action="store_true",
                   help="replace an entry created by another arkalabs-messenger installation")
    x = commande("uninstall", "remove only what `install` added to AI hosts", _uninstall, agent=False, projet=False)
    x.add_argument("--host", action="append", help=f"specific repeatable host ({ids})")
    x = commande("hosts", "report AI-host setup on this machine", _hosts, agent=False, projet=False)
    x.add_argument("--json", action="store_true", help="JSON output")
    x = commande("mcp", "mailbox MCP server over standard input/output (started by the host)", _mcp)
    x.add_argument("--host", help=f"host starting this server ({ids})")

    x = commande("register", "create or update your account", _register)
    x.add_argument("--host", required=True, help="your host: claude-code, kimi-code, codex, hermes, human…")
    x.add_argument("--role", required=True, help="one line describing what you do and when to write to you")
    x.add_argument("--machine", help="where you run (default: machine name)")
    x.add_argument("--model", help="your model, when useful")
    x.add_argument("--human", help="responsible human")
    x.add_argument("--wake", help="how you check mail (hooks, watch…)")
    x.add_argument("--display", help="human-readable display name (otherwise derived by enroll)")
    x.add_argument("--update", action="store_true", help="update your existing account")

    x = commande("enroll", "enroll with a readable identity derived from host, task, and machine", _enroll, agent=False)
    x.add_argument("--task", required=True, help="short, durable task title (for example, MessengerAI)")
    x.add_argument("--host", help="your host: claude-code, codex, kimi-code… (default: claude-code)")
    x.add_argument("--poste", help="machine code: win, mac, lnx (default: detected)")
    x.add_argument("--machine", help="where you run (default: machine name)")
    x.add_argument("--role", help="one-line role (default: derived from host and task)")
    x.add_argument("--human", help="responsible human")
    x.add_argument("--wake", help="how you check mail (default: check --hook hooks)")
    x.add_argument("--session", help="session id to link to this agent")
    x.add_argument("--update", action="store_true", help="update your existing account")

    x = commande("identify", "identify your existing account from this working directory",
                 _identify, agent=False)
    x.add_argument("--address", required=True, help="your address: name or name@project")
    x.add_argument("--host", help="your host: claude-code, codex, kimi-code… (default: claude-code)")
    x.add_argument("--session", help="session id to link to this agent")

    x = commande("attach", "organize a shared account into or out of a project (human action)", _attach,
                 agent=False, projet=False)
    x.add_argument("--account", required=True, help="account address without @project")
    x.add_argument("--to", default="", help="project; empty removes it from every project")

    x = commande("merge", "merge two accounts owned by one agent; pending mail and addressing follow",
                 _merge, agent=False, projet=False)
    x.add_argument("--account", required=True, help="absorbed address (old full account)")
    x.add_argument("--into", required=True, help="surviving full account address")

    x = commande("agents", "list accounts", _agents, agent=False)
    x.add_argument("--all", action="store_true", help="include inactive accounts")
    x.add_argument("--json", action="store_true", help="JSON manifest output")

    commande("deactivate", "deactivate an account without deleting it", _deactivate)

    x = commande("send", "send a message", _send)
    x.add_argument("--to", required=True, action=Cumul,
                   help="comma-separated recipients: addresses, short names, or your address-book aliases; "
                        "repeating --to adds to the list")
    x.add_argument("--subject", required=True)
    x.add_argument("--body", default="", help="at most two lines")
    x.add_argument("--attach", help="attachment copied into the mailbox when needed")
    x.add_argument("--reply-to", help="identifier of the message being answered")

    x = commande("contacts", "your address book: aliases for one address or a group", _contacts)
    x.add_argument("--json", action="store_true", help="JSON output")

    x = commande("contact-add", "save a contact for use in `send --to`", _contact_add)
    x.add_argument("--alias", required=True, help="short alias: lowercase letters, digits, . _ - (32 max)")
    x.add_argument("--to", required=True, action=Cumul,
                   help="one address or a comma-separated group; repeating --to adds to the list")
    x.add_argument("--note", help="one line describing who it is and when to write")
    x.add_argument("--replace", action="store_true", help="replace an existing contact")

    x = commande("contact-remove", "remove a contact from your address book", _contact_remove)
    x.add_argument("--alias", required=True)

    x = commande("check", "check mail with status nouveau (used by hooks)", _check)
    x.add_argument("--wake", action="store_true", help="summary on stderr and exit code 2 when mail exists")
    x.add_argument("--json", action="store_true", help="JSON output")
    x.add_argument("--hook", action="store_true",
                   help="read hook JSON (session_id, cwd) from standard input")
    x.add_argument("--session", help="session id (otherwise read from --hook input)")
    x.add_argument("--host", help="host running this mail check (set by install)")
    x.add_argument("--event", help="hook event such as SessionStart or UserPromptSubmit")

    x = commande("mark", "advance the status of a received message", _mark)
    x.add_argument("--id", required=True)
    x.add_argument("--status", required=True, choices=STATUTS[1:])

    x = commande("list", "list messages from newest to oldest", _list)
    x.add_argument("--status", choices=STATUTS)
    x.add_argument("--limit", type=int, default=20)
    x.add_argument("--json", action="store_true", help="JSON output")

    x = commande("watch", "wait for an agent's next message and keep its session watch armed", _watch)
    x.add_argument("--interval", type=float, default=10.0, help="seconds between checks")
    x.add_argument("--max-hours", type=float, default=12.0)
    x.add_argument("--session", help="covered session id, so end-of-turn checks know a watch is active")
    x.add_argument("--host", help="your host, used to resolve remembered identity when --agent is absent")

    x = commande("migrate", "import a legacy Markdown mailbox", _migrate, agent=False, projet=False)
    x.add_argument("--from", dest="source", required=True, help="Markdown mailbox to import")

    x = commande("ui", "open the local web interface and API", _ui, projet=False)
    x.add_argument("--port", type=int, default=8765)
    x.add_argument("--api", action="store_true", help="API only, without the interface (used by `npm run dev`)")
    x.add_argument("--front", help="built interface directory (default: ui/dist)")
    x.add_argument("--no-browser", action="store_true", help="do not open the browser")
    x.add_argument("--exit-with-parent", action="store_true",
                   help="stop when standard input closes (used by `npm run dev`)")
    x.add_argument("--no-notify", action="store_true", help="disable system notifications")
    x.add_argument("--link", help="interface URL opened when clicking a notification")

    x = commande("start", "open the local web interface, the human entry point (ui shortcut)",
                 _start, projet=False)
    x.add_argument("--port", type=int, default=8765)
    x.add_argument("--no-browser", action="store_true", help="do not open the browser")
    x.add_argument("--no-notify", action="store_true", help="disable system notifications")
    x.add_argument("--log", help="write logs to this file (console-free desktop shortcut)")

    x = commande("shortcut", "create a Messenger desktop icon that starts the mailbox", _shortcut,
                 agent=False, projet=False)
    x.add_argument("--remove", action="store_true", help="remove the desktop icon")

    x = commande("notify", "notify every message without opening the interface", _notify, projet=False)
    x.add_argument("--interval", type=float, default=5.0, help="seconds between checks")
    return p
