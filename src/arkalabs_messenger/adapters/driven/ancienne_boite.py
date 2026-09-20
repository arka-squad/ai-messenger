"""L'ancienne boîte Markdown (première version de l'outil) : lecture seule.

Format lu : sous la ligne `## Messages`, un bloc par message, du plus récent au
plus ancien :

    ### 20260918-2250-windows · Re : 20260918-2248-kimi — Objet
    **De** windows → **À** kimi, mac · **Statut** nouveau · **PJ** [detail.md](detail.md)
    Première ligne de corps.
"""
from __future__ import annotations

import contextlib
import os
import re
from datetime import datetime
from typing import Iterator, List, Optional

from ...application.ports import BoiteIndisponible, DepotBoite, LectureSeule, SourceAncienne
from ...domain import Boite, Message
from .fichiers import empreinte

_BLOC = re.compile(r"(?m)^### ")
_ID = re.compile(r"^(\d{8}-\d{4}-[A-Za-z0-9_.-]+?(?:-\d+)?)\s")
_DE = re.compile(r"\*\*De\*\*\s*([^\s→]+)")
_A = re.compile(r"\*\*À\*\*\s*(.+?)\s*·")
_STATUT = re.compile(r"\*\*Statut\*\*\s*(\S+)")
_PJ = re.compile(r"\*\*PJ\*\*\s*(.+)$")
_LIEN = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
_RE = re.compile(r"^Re\s*:\s*(\S+)\s*[—-]\s*(.*)$")


def lire_markdown(texte: str) -> List[Message]:
    """Les messages d'une ancienne boîte, dans l'ordre d'envoi."""
    _, _, corps_boite = texte.partition("## Messages")
    messages = [m for m in (_message(bloc) for bloc in _BLOC.split(corps_boite)[1:]) if m]
    return list(reversed(messages))


def _message(bloc: str) -> Optional[Message]:
    lignes = bloc.splitlines()
    entete = lignes[0].strip() if lignes else ""
    ident = _ID.match(entete + " ")
    adresse = next((l for l in lignes[1:] if _STATUT.search(l)), None)
    if not ident or adresse is None:
        return None
    mid = ident.group(1)
    objet, reponse_a = entete[len(mid):].lstrip(" ·").strip(), None
    reponse = _RE.match(objet)
    if reponse:
        reponse_a, objet = reponse.group(1), reponse.group(2).strip()
    pj_brute = _PJ.search(adresse)
    lien = _LIEN.search(pj_brute.group(1)) if pj_brute else None
    de = _DE.search(adresse)
    a = _A.search(adresse)
    return Message(
        id=mid,
        date=datetime.strptime(mid[:13], "%Y%m%d-%H%M").isoformat(timespec="seconds"),
        de=de.group(1) if de else "?",
        a=tuple(x.strip() for x in (a.group(1) if a else "").split(",") if x.strip()),
        objet=objet,
        corps=tuple(l.rstrip() for l in lignes[1:] if l.strip() and l is not adresse),
        pj=lien.group(1) if lien else None,
        re=reponse_a,
        statut=_STATUT.search(adresse).group(1),
        importe=True,
    )


def _lire_fichier(chemin: str) -> str:
    try:
        with open(chemin, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise BoiteIndisponible(f"boîte introuvable : {chemin}") from None
    except OSError as e:
        raise BoiteIndisponible(f"boîte injoignable : {chemin} ({e.strerror})") from None


class SourceMarkdown(SourceAncienne):
    """Une ancienne boîte à importer par `migrate`."""

    def __init__(self, chemin: str) -> None:
        self._chemin = chemin

    @property
    def emplacement(self) -> str:
        return self._chemin

    def messages(self) -> List[Message]:
        return lire_markdown(_lire_fichier(self._chemin))


class DepotBoiteMarkdown(DepotBoite):
    """Ouvre une ancienne boîte en lecture seule, convertie à la volée."""

    lecture_seule = True
    _REFUS = "boîte Markdown : lecture seule — migre-la en JSON pour agir (`messenger.py migrate`)"

    def __init__(self, chemin: str) -> None:
        self._chemin = chemin

    @property
    def emplacement(self) -> str:
        return self._chemin

    @property
    def racine(self) -> str:
        return os.path.dirname(os.path.abspath(self._chemin))

    def existe(self) -> bool:
        return os.path.exists(self._chemin)

    def creer(self, boite: Optional[Boite] = None) -> None:
        raise LectureSeule(self._REFUS)

    def lire(self) -> Boite:
        return Boite(messages=lire_markdown(_lire_fichier(self._chemin)))

    @contextlib.contextmanager
    def transaction(self) -> Iterator[Boite]:
        raise LectureSeule(self._REFUS)
        yield  # pragma: no cover — rend la fonction génératrice

    def version(self) -> str:
        return empreinte(self._chemin)
