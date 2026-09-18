"""L'API web locale, et l'interface construite si on la lui donne.

N'écoute que 127.0.0.1. Les écritures exigent une requête de même origine, en
JSON : une page tierce ouverte dans le navigateur ne peut pas agir sur la boîte.

    GET  /api/boite          la boîte, les comptes, et ce que le compte courant peut faire
    GET  /api/version        une empreinte qui change à chaque écriture (veille à peu de frais)
    POST /api/statut         {"id", "statut"} : fait avancer un statut au nom du compte courant
    POST /api/notifications  {"actives"} : active ou coupe les notifications système
    GET  /pj/<nom>           une pièce jointe référencée par un message
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

from ...application import Annonceur, BoiteIndisponible, Messagerie
from ...domain import ErreurMessenger
from ..codec import compte_vers_dict, message_vers_dict

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
         notifications: Optional[bool] = None) -> Dict[str, Any]:
    """Tout ce que l'interface affiche, et ce que `compte` a le droit de faire."""
    version = messagerie.version()
    boite = messagerie.instantane()
    messages = []
    for m in boite.messages:
        d = message_vers_dict(m)
        d["suite"] = None if messagerie.lecture_seule else m.suite_pour(compte)
        d["pj_presente"] = bool(m.pj) and messagerie.piece_jointe(m.pj) is not None
        messages.append(d)
    if messagerie.annuaire_present():
        comptes = [compte_vers_dict(c) for c in messagerie.comptes(tous=True)]
    else:
        comptes = [{"nom": nom, "actif": True} for nom in boite.participants()]
    return {
        "source": {
            "chemin": messagerie.emplacement,
            "nom": os.path.basename(messagerie.emplacement),
            "format": "markdown" if messagerie.lecture_seule else "json",
            "lecture_seule": messagerie.lecture_seule,
            "demonstration": demonstration,
        },
        "compte": compte,
        "projets": messagerie.projets(),
        "notifications": notifications,
        "version": version,
        "messages": messages,
        "comptes": comptes,
    }


class _Serveur(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = False


def creer_serveur(messagerie: Messagerie, compte: str, port: int = 0, front: Optional[str] = None,
                  demonstration: bool = False, annonceur: Optional[Annonceur] = None) -> http.server.HTTPServer:
    """Un serveur prêt à `serve_forever()`. Port 0 : un port libre est choisi."""
    serveur = _Serveur(("127.0.0.1", port), _gestionnaire(messagerie, compte, front, demonstration, annonceur))
    return serveur


def servir(messagerie: Messagerie, compte: str, port: int, front: Optional[str],
           ouvrir_navigateur: bool = True, lie_au_parent: bool = False, demonstration: bool = False,
           annonceur: Optional[Annonceur] = None) -> int:
    """Sert jusqu'à Ctrl+C — ou, avec `lie_au_parent`, jusqu'à la fermeture de l'entrée standard.

    Lancée par `npm run dev`, l'API lit son entrée standard : si Vite s'arrête, même
    brutalement, le tube se ferme et l'API s'arrête avec lui au lieu de rester orpheline.
    """
    messagerie.instantane()  # échoue tôt si la boîte est illisible
    try:
        serveur = creer_serveur(messagerie, compte, port, front, demonstration, annonceur)
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


def _gestionnaire(messagerie: Messagerie, compte: str, front: Optional[str], demonstration: bool,
                  annonceur: Optional[Annonceur]):
    class Gestionnaire(http.server.BaseHTTPRequestHandler):
        server_version = "arkalabs-messenger"

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 — silence
            pass

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
                    return self._json(200, etat(messagerie, compte, demonstration,
                                                 annonceur.actif if annonceur else None))
                if chemin == "/api/version":
                    return self._json(200, {"version": messagerie.version()})
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
            if chemin not in ("/api/statut", "/api/notifications"):
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
                message = messagerie.marquer(compte, str(demande["id"]), str(demande["statut"]))
            except (ValueError, KeyError, TypeError):
                return self._erreur(400, "demande illisible : {\"id\", \"statut\"} attendus")
            except BoiteIndisponible as e:
                return self._erreur(503, str(e))
            except ErreurMessenger as e:
                return self._erreur(409, str(e))
            except OSError as e:
                return self._erreur(503, f"boîte injoignable : {e.strerror or e}")
            return self._json(200, {"message": message_vers_dict(message), "version": messagerie.version()})

        def _notifications(self, demande: Any) -> None:
            if annonceur is None:
                return self._erreur(409, "notifications système indisponibles pour cette interface")
            if not isinstance(demande, dict) or not isinstance(demande.get("actives"), bool):
                return self._erreur(400, 'demande illisible : {"actives": true|false} attendu')
            annonceur.actif = demande["actives"]
            return self._json(200, {"notifications": annonceur.actif})

        def _piece_jointe(self, nom: str) -> None:
            chemin = messagerie.piece_jointe(nom)
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
