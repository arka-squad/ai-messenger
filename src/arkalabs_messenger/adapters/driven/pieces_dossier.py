"""Les pièces jointes, rangées dans le dossier de la boîte."""
from __future__ import annotations

import os
import shutil
from typing import Optional

from ...application.ports import PieceJointeRefusee, PiecesJointes


class PiecesDossier(PiecesJointes):
    def __init__(self, dossier: str) -> None:
        self._dossier = os.path.abspath(dossier)

    def deposer(self, source: str) -> str:
        source = os.path.abspath(os.path.expanduser(source))
        if not os.path.isfile(source):
            raise PieceJointeRefusee(f"pièce jointe introuvable : {source}")
        nom = os.path.basename(source)
        cible = os.path.join(self._dossier, nom)
        if os.path.normcase(source) != os.path.normcase(cible):
            if os.path.exists(cible):
                raise PieceJointeRefusee(f"un fichier « {nom} » existe déjà dans la boîte : renomme ta pièce jointe")
            shutil.copy2(source, cible)
        return nom

    def localiser(self, nom: str) -> Optional[str]:
        if not nom or os.path.basename(nom) != nom or nom in (".", ".."):
            return None
        chemin = os.path.join(self._dossier, nom)
        return chemin if os.path.isfile(chemin) else None
