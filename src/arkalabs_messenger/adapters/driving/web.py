"""L'API web locale, et l'interface construite si on la lui donne.

N'écoute que 127.0.0.1. Les écritures exigent une requête de même origine, en
JSON : une page tierce ouverte dans le navigateur ne peut pas agir sur la boîte.

    GET  /api/boite            la boîte, les comptes, l'invite, et ce que le compte courant peut faire
    GET  /api/version          une empreinte qui change à chaque écriture (veille à peu de frais)
    POST /api/statut           {"id", "statut"} : fait avancer un statut au nom du compte courant
    POST /api/notifications    {"actives"} : active ou coupe les notifications système
    POST /api/creer            {"dossier"} : crée une boîte (arbo .aimessenger/) et s'y branche
    POST /api/activer          {"dossier", "projet"?} : connecte un dépôt local à la boîte
    POST /api/choisir-dossier  ouvre le sélecteur de dossier natif du poste
    GET  /pj/<nom>             une pièce jointe référencée par un message

La boîte est résolue à chaque requête : créée depuis l'interface, elle s'ouvre sans redémarrage.
"""
from __future__ import annotations

import http.server
import json
import mimetypes
import os
import socketserver
import sys
import threading
import urllib.parse
import webbrowser
from typing import Any, Dict, Optional, Tuple

from ... import __version__
from ...application import Annonceur, BoiteExistante, BoiteIndisponible, Messagerie
from ...domain import Compte, ErreurMessenger, valider_nom
from ..codec import compte_vers_dict, message_vers_dict
from . import hotes, poste

OUTIL = "arkalabs-messenger"
"""Ce que `/api/version` répond à qui demande « qui écoute ici ? » — `start` s'y reconnaît."""

_TEXTE = {".md", ".txt", ".log", ".csv", ".yml", ".yaml", ".toml", ".py", ".ps1", ".sh",
          ".rs", ".ts", ".js", ".html", ".svg", ".xml"}
_IMAGES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp"}
_FRONT = {".html", ".js", ".css", ".svg", ".png", ".ico", ".woff2", ".json", ".map"}
_CSP_FRONT = ("default-src 'self'; script-src 'self'; connect-src 'self'; "
              "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; "
              "img-src 'self' data: https://arkalabs.app; frame-ancestors 'none'; base-uri 'none'")
_ENTREE_MAX = 4096
_RELEVE_ANNONCES = 3.0


def etat(messagerie: Messagerie, compte: str, demonstration: bool = False,
         notifications: Optional[bool] = None, depot: Optional[str] = None) -> Dict[str, Any]:
    """Tout ce que l'interface affiche, et ce que `compte` a le droit de faire."""
    version = messagerie.version()
    boite = messagerie.instantane()
    idents = messagerie.identites(compte)  # le compte de l'interface, plus ceux fusionnés dedans
    messages = []
    for m in boite.messages:
        d = message_vers_dict(m)
        d["suite"] = None if messagerie.lecture_seule else next(
            (m.suite_pour(i) for i in idents if m.suite_pour(i)), None)
        # `mien` : où en est CE message pour le compte de l'interface — c'est lui qu'elle affiche
        d["mien"] = m.statut_vu_par(idents)
        d["pj_presente"] = bool(m.pj) and messagerie.piece_jointe(m.pj) is not None
        messages.append(d)
    if messagerie.annuaire_present():
        # `projet` : celui que porte l'adresse, sinon celui auquel le compte a été rattaché — l'interface range par lui
        comptes = [{**compte_vers_dict(c), "projet": c.projet} for c in messagerie.comptes(tous=True)]
    else:
        comptes = [{"nom": nom, "actif": True} for nom in boite.participants()]
    return {
        "source": {
            "chemin": messagerie.emplacement,
            "nom": os.path.basename(messagerie.emplacement),
            "format": "markdown" if messagerie.lecture_seule else "json",
            "lecture_seule": messagerie.lecture_seule,
            "demonstration": demonstration,
            "activable": not messagerie.lecture_seule and not demonstration,
        },
        "compte": compte,
        "projets": messagerie.projets(),
        "notifications": notifications,
        "invite": _invite(messagerie, demonstration, depot),
        "version": version,
        "messages": messages,
        "comptes": comptes,
    }


_PROJET_DU_DEPOT = object()
"""L'humain n'a pas choisi de projet pour cette invite : l'agent prendra celui de son dépôt, s'il en a un."""


def _invite(messagerie: Messagerie, demonstration: bool, depot: Optional[str],
            projet: Any = _PROJET_DU_DEPOT, compte: Optional[Compte] = None) -> Optional[str]:
    """Le texte que l'humain copie et colle à son agent. None si pas de vraie boîte.

    `projet` : le projet que l'humain a choisi pour cet agent (`None` : sans projet, compte commun).
    `compte` : l'invite s'adresse à un agent qui a **déjà** un compte — il le reprend au lieu d'en créer un.
    """
    if demonstration or messagerie.lecture_seule:
        return None
    onboarding = os.path.join(messagerie.racine, "onboarding.md")
    outil = os.path.join(depot, "messenger.py") if depot else "messenger.py (dépôt arkalabs-messenger)"
    agents = os.path.join(depot, "AGENTS.md") if depot else "AGENTS.md du dépôt arkalabs-messenger"
    if compte is not None:
        return "\n".join([
            f"Tu es l'agent « {compte.affichage or compte.nom} » (adresse {compte.nom}) de la boîte aux lettres "
            "partagée des agents. Du courrier t'y attend peut-être, et ta relève ne te reconnaît pas encore ici.",
            f"Boîte : {messagerie.emplacement}",
            f"Outil : {outil} (lis {agents})",
            "Depuis ton dossier de travail, reprends ton compte — ta relève saura ensuite qui tu es :",
            f"- si ton hôte a le serveur MCP « arkalabs-messenger » : outil `identify` avec address \"{compte.nom}\" ;",
            f"- sinon : python3 \"{outil}\" identify --address {compte.nom} --host <ton hôte>",
            "Puis relève ton courrier (`check`), lis les pièces jointes, réponds, et marque « traité ».",
            f"Si la machine n'est pas encore équipée, suis d'abord l'étape 1 de {onboarding}.",
        ])
    if projet is _PROJET_DU_DEPOT:
        consigne = []
    elif projet:
        consigne = [f"Ton projet : {projet} — crée ton compte DANS ce projet : outil MCP `enroll` avec "
                    f"project \"{projet}\", ou `enroll --task \"<ta tâche>\" --project {projet}`."]
    else:
        consigne = ["Ton projet : aucun — crée un compte commun à tous les projets : outil MCP `enroll` avec "
                    "project \"\", ou `enroll --task \"<ta tâche>\" --project \"\"`."]
    return "\n".join([
        "Tu es un agent IA sur cette machine. Une boîte aux lettres partagée est active : "
        "présente-toi et relève ton courrier.",
        f"Boîte : {messagerie.emplacement}",
        f"Outil : {outil} (lis {agents})",
        *consigne,
        f"Lis {onboarding} et suis-le : équipe cette machine si personne ne l'a encore fait "
        "(étape 1), puis crée ton compte (étape 2), puis relève ton courrier.",
    ])


class _Serveur(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = False


def creer_serveur(messagerie: Messagerie, compte: str, port: int = 0, front: Optional[str] = None,
                  demonstration: bool = False, annonceur: Optional[Annonceur] = None,
                  depot: Optional[str] = None, resolveur=None, usine=None,
                  eteignable: bool = False) -> http.server.HTTPServer:
    """Un serveur prêt à `serve_forever()`. Port 0 : un port libre est choisi.

    `resolveur()` rend `(messagerie, demonstration)` à chaque requête : la boîte peut ainsi
    changer en cours de route (création depuis l'interface). Sans lui, la boîte donnée est fixe.
    `eteignable` : l'humain a allumé la boîte lui-même (`start`), il peut l'éteindre depuis l'interface.
    """
    resolveur = resolveur or (lambda: (messagerie, demonstration))
    serveur = _Serveur(("127.0.0.1", port),
                       _gestionnaire(resolveur, compte, front, depot, annonceur, usine, eteignable))
    return serveur


def servir(messagerie: Messagerie, compte: str, port: int, front: Optional[str],
           ouvrir_navigateur: bool = True, lie_au_parent: bool = False, demonstration: bool = False,
           annonceur: Optional[Annonceur] = None, depot: Optional[str] = None, resolveur=None, usine=None) -> int:
    """Sert jusqu'à Ctrl+C — ou, avec `lie_au_parent`, jusqu'à la fermeture de l'entrée standard.

    Lancée par `npm run dev`, l'API lit son entrée standard : si Vite s'arrête, même
    brutalement, le tube se ferme et l'API s'arrête avec lui au lieu de rester orpheline.
    """
    messagerie.instantane()  # échoue tôt si la boîte est illisible
    try:
        serveur = creer_serveur(messagerie, compte, port, front, demonstration, annonceur, depot, resolveur, usine,
                                eteignable=bool(front) and not lie_au_parent)
    except OSError:
        raise BoiteIndisponible(f"le port {port} est occupé : relance avec --port <autre>") from None
    url = f"http://127.0.0.1:{serveur.server_address[1]}/"
    mode = "lecture seule (ancienne boîte Markdown)" if messagerie.lecture_seule else f"au nom de {compte}"
    print(f"Messenger — {url}{'' if front else 'api/boite'}", flush=True)
    print(f"boîte : {messagerie.emplacement} · {mode}", flush=True)
    if not front and not lie_au_parent:  # lancée par `npm run dev`, l'interface est déjà là
        print("API seule : l'interface se lance avec `npm run dev`, ou se construit avec `npm run build`.",
              flush=True)
    elif ouvrir_navigateur:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    if lie_au_parent:
        threading.Thread(target=_attendre_la_fin_du_parent, args=(serveur,), daemon=True).start()
    arret = threading.Event()
    if annonceur:
        threading.Thread(target=_annoncer, args=(annonceur, arret), daemon=True).start()
    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        arret.set()
        serveur.server_close()
    return 0


def _annoncer(annonceur: Annonceur, arret: threading.Event) -> None:
    """Relève la boîte à intervalle et laisse l'annonceur notifier ce qui arrive."""
    while not arret.is_set():
        try:
            annonceur.relever()
        except (ErreurMessenger, OSError):
            pass  # boîte momentanément injoignable : on réessaie au tour suivant
        arret.wait(_RELEVE_ANNONCES)


def _attendre_la_fin_du_parent(serveur: http.server.HTTPServer) -> None:
    try:
        sys.stdin.read()
    finally:
        serveur.shutdown()


def _gestionnaire(resolveur, compte: str, front: Optional[str], depot: Optional[str] = None,
                  annonceur: Optional[Annonceur] = None, usine=None, eteignable: bool = False):
    class Gestionnaire(http.server.BaseHTTPRequestHandler):
        server_version = "arkalabs-messenger"

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 — silence
            pass

        def _courant(self):
            """La boîte du moment et si c'est la démonstration : résolue à chaque requête."""
            return resolveur()

        # -- Garde ------------------------------------------------------------
        def _hotes(self) -> Tuple[str, ...]:
            port = self.server.server_address[1]
            return (f"127.0.0.1:{port}", f"localhost:{port}")

        def _hote_admis(self) -> bool:
            return self.headers.get("Host", "") in self._hotes()

        def _meme_origine(self) -> bool:
            return self.headers.get("Origin", "") in {f"http://{h}" for h in self._hotes()}

        # -- Réponses ---------------------------------------------------------
        def _envoyer(self, code: int, corps: bytes, type_: str, entetes: Optional[Dict[str, str]] = None) -> None:
            self.send_response(code)
            self.send_header("Content-Type", type_)
            self.send_header("Content-Length", str(len(corps)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            for cle, valeur in (entetes or {}).items():
                self.send_header(cle, valeur)
            self.end_headers()
            self.wfile.write(corps)

        def _json(self, code: int, data: Any) -> None:
            self._envoyer(code, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def _erreur(self, code: int, message: str) -> None:
            self._json(code, {"erreur": message})

        def _fichier(self, chemin: str, type_: str, entetes: Optional[Dict[str, str]] = None) -> None:
            with open(chemin, "rb") as f:
                self._envoyer(200, f.read(), type_, entetes)

        # -- Routes -----------------------------------------------------------
        def do_GET(self) -> None:  # noqa: N802
            if not self._hote_admis():
                return self._erreur(403, "hôte refusé")
            chemin = urllib.parse.urlsplit(self.path).path
            try:
                if chemin == "/api/boite":
                    messagerie, demonstration = self._courant()
                    return self._json(200, etat(messagerie, compte, demonstration,
                                                 annonceur.actif if annonceur else None, depot))
                if chemin == "/api/version":
                    return self._json(200, {"version": self._courant()[0].version(), "outil": OUTIL,
                                            "logiciel": __version__})
                if chemin == "/api/poste":
                    return self._json(200, self._poste())
                if chemin.startswith("/pj/"):
                    return self._piece_jointe(urllib.parse.unquote(chemin[len("/pj/"):]))
                if front and not chemin.startswith("/api/"):
                    return self._front(chemin)
                return self._erreur(404, "introuvable")
            except ErreurMessenger as e:
                return self._erreur(503, str(e))
            except OSError as e:
                return self._erreur(503, f"boîte injoignable : {e.strerror or e}")

        def do_POST(self) -> None:  # noqa: N802
            if not self._hote_admis() or not self._meme_origine():
                return self._erreur(403, "requête refusée : origine inconnue")
            chemin = urllib.parse.urlsplit(self.path).path
            if chemin not in ("/api/statut", "/api/notifications", "/api/activer", "/api/creer",
                              "/api/choisir-dossier", "/api/preparer", "/api/eteindre", "/api/invite",
                              "/api/rattacher", "/api/contact", "/api/contact-retirer", "/api/fusionner",
                              "/api/boite-du-poste"):
                return self._erreur(404, "introuvable")
            if not self.headers.get("Content-Type", "").startswith("application/json"):
                return self._erreur(415, "JSON attendu")
            try:
                taille = int(self.headers.get("Content-Length") or 0)
                if taille > _ENTREE_MAX:
                    return self._erreur(413, "demande trop longue")
                demande = json.loads(self.rfile.read(taille) or b"{}")
                if chemin == "/api/notifications":
                    return self._notifications(demande)
                if chemin == "/api/activer":
                    return self._activer(demande)
                if chemin == "/api/creer":
                    return self._creer(demande)
                if chemin == "/api/boite-du-poste":
                    return self._boite_du_poste(demande)
                if chemin == "/api/choisir-dossier":
                    return self._choisir_dossier()
                if chemin in ("/api/invite", "/api/rattacher", "/api/contact", "/api/contact-retirer",
                              "/api/fusionner"):
                    return self._organiser(chemin, demande)
                if chemin == "/api/preparer":
                    return self._preparer()
                if chemin == "/api/eteindre":
                    return self._eteindre()
                messagerie = self._courant()[0]
                message = messagerie.marquer(compte, str(demande["id"]), str(demande["statut"]))
            except (ValueError, KeyError, TypeError):
                return self._erreur(400, "demande illisible : {\"id\", \"statut\"} attendus")
            except BoiteIndisponible as e:
                return self._erreur(503, str(e))
            except ErreurMessenger as e:
                return self._erreur(409, str(e))
            except OSError as e:
                return self._erreur(503, f"boîte injoignable : {e.strerror or e}")
            vu = {**message_vers_dict(message), "mien": message.statut_vu_par(messagerie.identites(compte))}
            return self._json(200, {"message": vu, "version": messagerie.version()})

        def _organiser(self, chemin: str, demande: Any) -> None:
            """Les gestes de l'humain qui organise sa boîte : inviter un agent dans un projet, ranger un compte
            dans un projet, tenir le carnet d'adresses d'un agent."""
            messagerie, demonstration = self._courant()
            if demonstration or messagerie.lecture_seule:
                return self._erreur(409, "aucune boîte inscriptible : crée d'abord la boîte")
            if not isinstance(demande, dict):
                return self._erreur(400, "demande illisible : un objet JSON est attendu")
            try:
                if chemin == "/api/invite":
                    return self._json(200, {"invite": self._inviter(messagerie, demande)})
                adresse = str(demande["compte"])
                if chemin == "/api/fusionner":
                    messagerie.fusionner(adresse, str(demande["dans"]))
                elif chemin == "/api/rattacher":
                    messagerie.rattacher(adresse, str(demande["projet"]) if demande.get("projet") else None)
                elif chemin == "/api/contact":
                    adresses = demande["adresses"]
                    if not isinstance(adresses, list) or not all(isinstance(a, str) for a in adresses):
                        return self._erreur(400, 'demande illisible : "adresses" est une liste d\'adresses')
                    note = demande.get("note")
                    messagerie.noter_contact(adresse, str(demande["alias"]), adresses,
                                             str(note) if note else None, remplacer=bool(demande.get("remplacer")))
                else:
                    messagerie.retirer_contact(adresse, str(demande["alias"]))
            except KeyError as e:
                return self._erreur(400, f"demande illisible : champ {e} attendu")
            except ErreurMessenger as e:
                return self._erreur(409, str(e))
            except OSError as e:
                return self._erreur(503, f"boîte injoignable : {e.strerror or e}")
            return self._json(200, {"version": messagerie.version()})

        def _inviter(self, messagerie: Messagerie, demande: Dict[str, Any]) -> Optional[str]:
            """L'invite à coller à un agent : pour un compte existant, ou pour un nouveau dans le projet choisi
            (créé au passage s'il est nouveau ; `null` : sans projet)."""
            if demande.get("compte"):
                compte = next((c for c in messagerie.comptes(tous=True) if c.nom == str(demande["compte"])), None)
                if compte is None:
                    raise KeyError("compte")
                return _invite(messagerie, False, depot, compte=compte)
            projet = valider_nom(str(demande["projet"]), "projet") if demande.get("projet") else None
            if projet:
                messagerie.declarer_projet(projet)
            return _invite(messagerie, False, depot, projet=projet)

        def _poste(self) -> Dict[str, Any]:
            """Où en est ce poste : ses outils d'IA sont-ils prêts, et peut-on éteindre la boîte d'ici ?"""
            etats = hotes.etats(hotes.contexte(depot)) if depot else []
            return {"hotes": [h.vers_dict() for h in etats if h.present], "eteignable": eteignable,
                    "logiciel": __version__}

        def _preparer(self) -> None:
            """Équipe les outils d'IA du poste (voir `hotes.py`) : le geste de `messenger.py install`."""
            if not depot:
                return self._erreur(409, "préparation indisponible : dépôt de l'outil introuvable")
            try:
                hotes.equiper_presents(hotes.contexte(depot))
            except hotes.EquipementRefuse as e:
                return self._erreur(409, str(e))
            except OSError as e:
                return self._erreur(500, f"préparation impossible : {e.strerror or e}")
            return self._json(200, self._poste())

        def _eteindre(self) -> None:
            """Arrête cette fenêtre sur la boîte. Les agents n'en dépendent pas : ils continuent de s'écrire."""
            if not eteignable:
                return self._erreur(409, "cette boîte n'a pas été allumée d'ici : ferme l'outil qui l'a lancée")
            self._json(200, {"eteinte": True})
            threading.Thread(target=self.server.shutdown, daemon=True).start()

        def _activer(self, demande: Any) -> None:
            """Connecte un projet : déclare le dépôt et équipe les hôtes IA du poste (voir `hotes.py`)."""
            messagerie, demonstration = self._courant()
            if demonstration or messagerie.lecture_seule:
                return self._erreur(409, "aucune boîte inscriptible : crée d'abord la boîte")
            if not depot:
                return self._erreur(409, "activation indisponible : dépôt de l'outil introuvable")
            if not isinstance(demande, dict) or not isinstance(demande.get("dossier"), str) \
                    or not demande["dossier"].strip():
                return self._erreur(400, 'demande illisible : {"dossier": "<chemin local>", "projet": "<nom?>"}')
            projet = None
            if demande.get("projet"):
                try:
                    projet = valider_nom(str(demande["projet"]), "projet")
                except ErreurMessenger as e:
                    return self._erreur(400, str(e))
            try:
                resume = poste.activer_depot(demande["dossier"], projet, depot, box=messagerie.emplacement)
            except poste.ActivationRefusee as e:
                return self._erreur(400, str(e))
            except OSError as e:
                return self._erreur(500, f"activation impossible : {e.strerror or e}")
            if resume["projet"]:
                try:  # le projet est connu de la boîte dès maintenant : l'interface le montre sans attendre un agent
                    messagerie.declarer_projet(resume["projet"])
                except (ErreurMessenger, BoiteIndisponible, OSError) as e:
                    return self._erreur(500, f"projet connecté, mais pas noté dans la boîte : {e}")
            return self._json(200, {**resume, "hotes": [h.vers_dict() for h in resume["hotes"]]})

        def _creer(self, demande: Any) -> None:
            """Crée une boîte (arbo .aimessenger/) dans un dossier et s'y branche pour ce poste."""
            if usine is None:
                return self._erreur(409, "création indisponible pour cette interface")
            if not isinstance(demande, dict) or not isinstance(demande.get("dossier"), str) \
                    or not demande["dossier"].strip():
                return self._erreur(400, 'demande illisible : {"dossier": "<dossier partagé>"}')
            try:
                messagerie = usine.ouvrir(demande["dossier"])
                if messagerie.lecture_seule:
                    return self._erreur(409, "ce dossier pointe une boîte Markdown en lecture seule")
                try:
                    messagerie.initialiser()
                except BoiteExistante:
                    pass  # une boîte est déjà là : on s'y branche simplement
                usine.poser_onboarding(demande["dossier"])
                poste.memoriser_boite(messagerie.emplacement)
            except ErreurMessenger as e:
                return self._erreur(409, str(e))
            except OSError as e:
                return self._erreur(500, f"création impossible : {e.strerror or e}")
            return self._json(200, {"cree": True, "boite": messagerie.emplacement})

        def _boite_du_poste(self, demande: Any) -> None:
            """Dit à ce poste où est la boîte : l'interface bascule dessus à la prochaine relève.

            C'est le geste de l'humain quand la boîte vit sur un dossier partagé (NAS) : chaque machine
            désigne le même endroit, vu par son propre chemin.
            """
            if not isinstance(demande, dict) or not isinstance(demande.get("dossier"), str) \
                    or not demande["dossier"].strip():
                return self._erreur(400, 'demande illisible : {"dossier": "<chemin local du dossier partagé>"}')
            boite = poste.trouver_boite(demande["dossier"].strip())
            if boite is None:
                return self._erreur(404, "aucune boîte dans ce dossier : vérifie le chemin, "
                                         "ou crée-la ici avec « Créer la boîte »")
            try:
                if usine is None:
                    return self._erreur(409, "changement de boîte indisponible pour cette interface")
                messagerie = usine.ouvrir(boite)
                messagerie.instantane()  # refuse une boîte illisible avant de la mémoriser
            except (ErreurMessenger, OSError) as e:
                return self._erreur(409, f"cette boîte ne s'ouvre pas : {e}")
            poste.memoriser_boite(messagerie.emplacement)
            return self._json(200, {"boite": messagerie.emplacement})

        def _choisir_dossier(self) -> None:
            """Ouvre le sélecteur de dossier natif du poste et rend le chemin choisi (ou null si annulé)."""
            try:
                return self._json(200, {"dossier": poste.choisir_dossier()})
            except poste.SelecteurIndisponible as e:
                return self._erreur(501, str(e))
            except OSError as e:
                return self._erreur(500, f"sélecteur indisponible : {e.strerror or e}")

        def _notifications(self, demande: Any) -> None:
            if annonceur is None:
                return self._erreur(409, "notifications système indisponibles pour cette interface")
            if not isinstance(demande, dict) or not isinstance(demande.get("actives"), bool):
                return self._erreur(400, 'demande illisible : {"actives": true|false} attendu')
            annonceur.actif = demande["actives"]
            return self._json(200, {"notifications": annonceur.actif})

        def _piece_jointe(self, nom: str) -> None:
            chemin = self._courant()[0].piece_jointe(nom)
            if not chemin:
                return self._erreur(404, f"pièce jointe introuvable : {nom}")
            extension = os.path.splitext(nom)[1].lower()
            isolee = {"Content-Security-Policy": "sandbox", "Content-Disposition": "inline"}
            if extension in _IMAGES:
                return self._fichier(chemin, _IMAGES[extension], isolee)
            if extension == ".pdf":
                return self._fichier(chemin, "application/pdf", {"Content-Disposition": "inline"})
            if extension == ".json":
                return self._fichier(chemin, "application/json; charset=utf-8", isolee)
            if extension in _TEXTE:  # jamais interprété : du texte, dans un bac à sable
                return self._fichier(chemin, "text/plain; charset=utf-8", isolee)
            return self._fichier(chemin, "application/octet-stream", {
                "Content-Disposition": f"attachment; filename*=UTF-8''{urllib.parse.quote(nom)}"})

        def _front(self, chemin: str) -> None:
            assert front is not None
            relatif = os.path.normpath(urllib.parse.unquote(chemin).lstrip("/")) if chemin != "/" else "index.html"
            cible = os.path.join(front, relatif)
            if (relatif.startswith("..") or os.path.isabs(relatif) or not os.path.isfile(cible)
                    or os.path.splitext(cible)[1].lower() not in _FRONT):
                cible = os.path.join(front, "index.html")
            type_ = mimetypes.guess_type(cible)[0] or "application/octet-stream"
            if type_.startswith("text/") or type_ in ("application/javascript", "application/json"):
                type_ += "; charset=utf-8"
            entetes = {"Content-Security-Policy": _CSP_FRONT} if cible.endswith(".html") else None
            return self._fichier(cible, type_, entetes)

    return Gestionnaire
