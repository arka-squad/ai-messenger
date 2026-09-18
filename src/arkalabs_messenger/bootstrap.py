"""L'assemblage : le seul endroit qui choisit les adaptateurs.

Une boîte `.json` s'ouvre en lecture-écriture et publie sa vue `.md` ; une
ancienne boîte `.md` s'ouvre en lecture seule.
"""
from __future__ import annotations

import os
from typing import List, Optional

from .adapters.driven import (
    DepotAnnuaireJson,
    DepotBoiteJson,
    DepotBoiteMarkdown,
    HorlogeSysteme,
    NotificationsSysteme,
    PiecesDossier,
    SourceMarkdown,
    VueMarkdown,
)
from . import demonstration
from .adapters.driving.cli import executer
from .application import BoiteIndisponible, Messagerie, Notificateur, SourceAncienne

DEPOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INTERFACE = os.path.join(DEPOT, "ui", "dist")
DEMONSTRATION = os.path.join(DEPOT, ".demo")


class Usine:
    """Fabrique les objets dont les adaptateurs pilotes ont besoin."""

    def ouvrir(self, chemin: str) -> Messagerie:
        chemin = _absolu(chemin)
        racine, extension = os.path.splitext(chemin)
        extension = extension.lower()
        if extension == ".json":
            boite = DepotBoiteJson(chemin, vue=VueMarkdown.pour(chemin))
        elif extension == ".md":
            boite = DepotBoiteMarkdown(chemin)
        else:
            raise BoiteIndisponible(
                f"la boîte est un fichier .json (ou une ancienne boîte .md, en lecture seule) : {chemin}")
        annuaire = DepotAnnuaireJson(racine + ".manifest.json", os.path.basename(chemin))
        return Messagerie(boite, annuaire, PiecesDossier(os.path.dirname(chemin)), HorlogeSysteme())

    def ancienne_boite(self, chemin: str) -> SourceAncienne:
        return SourceMarkdown(_absolu(chemin))

    def demonstration(self) -> str:
        """La boîte de démonstration du dépôt, créée au premier appel."""
        return demonstration.preparer(DEMONSTRATION)

    def notificateur(self) -> Notificateur:
        return NotificationsSysteme()

    def interface(self) -> Optional[str]:
        """L'interface construite par `npm run build`, si elle existe."""
        return INTERFACE if os.path.isfile(os.path.join(INTERFACE, "index.html")) else None


def main(argv: Optional[List[str]] = None) -> int:
    return executer(argv, Usine())


def _absolu(chemin: str) -> str:
    return os.path.abspath(os.path.expanduser(chemin))
