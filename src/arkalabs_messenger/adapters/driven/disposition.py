"""Où vivent les fichiers d'une boîte : l'arbo imposée `.aimessenger/`, et l'héritage.

Une boîte moderne est un dossier `.aimessenger/` :

    .aimessenger/
    ├─ manifest.json   les comptes
    ├─ boite.md        la vue humaine (régénérée, ne pas éditer)
    ├─ mail/
    │  └─ boite.json   les messages — la source de vérité
    └─ pj/             les pièces jointes

On garde la lecture des anciennes boîtes : un fichier `.json` à plat, ou un `.md`
en lecture seule (première version), pour pouvoir les migrer.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

DOSSIER = ".aimessenger"


@dataclass(frozen=True)
class Disposition:
    """Les chemins concrets d'une boîte, quel que soit son emplacement."""

    boite: str
    manifeste: str
    vue: Optional[str]      # le `.md` à régénérer ; None si la boîte EST un `.md`
    pieces: str             # le dossier des pièces jointes
    markdown: bool          # une ancienne boîte `.md`, en lecture seule
    racine: str             # le dossier montré à l'humain (`.aimessenger/`, ou le dossier du fichier)


def resoudre(chemin: str) -> Disposition:
    """La disposition d'un chemin : un dossier impose `.aimessenger/`, un fichier reste tel quel."""
    chemin = os.path.abspath(os.path.expanduser(chemin))
    ext = os.path.splitext(chemin)[1].lower()
    if ext == ".md":
        radical = chemin[: -len(".md")]
        return Disposition(chemin, radical + ".manifest.json", None, os.path.dirname(chemin), True,
                           os.path.dirname(chemin))
    if ext == ".json":
        racine = _racine_aimessenger(chemin)
        if racine:
            return _arbo(racine)
        radical = chemin[: -len(".json")]
        return Disposition(chemin, radical + ".manifest.json", radical + ".md", os.path.dirname(chemin), False,
                           os.path.dirname(chemin))
    racine = chemin if os.path.basename(chemin) == DOSSIER else os.path.join(chemin, DOSSIER)
    return _arbo(racine)


def _arbo(racine: str) -> Disposition:
    return Disposition(
        boite=os.path.join(racine, "mail", "boite.json"),
        manifeste=os.path.join(racine, "manifest.json"),
        vue=os.path.join(racine, "boite.md"),
        pieces=os.path.join(racine, "pj"),
        markdown=False,
        racine=racine,
    )


def _racine_aimessenger(chemin: str) -> Optional[str]:
    """Le dossier `.aimessenger/` parent du chemin, s'il y en a un."""
    dossier = os.path.dirname(chemin)
    while True:
        if os.path.basename(dossier) == DOSSIER:
            return dossier
        parent = os.path.dirname(dossier)
        if parent == dossier:
            return None
        dossier = parent
