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
from .adapters.driven.disposition import poser_onboarding as _poser_onboarding
from .adapters.driven.disposition import resoudre as _disposition
from . import demonstration
from .adapters.driving.cli import executer
from .application import Messagerie, Notificateur, SourceAncienne

DEPOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INTERFACE = os.path.join(DEPOT, "ui", "dist")
DEMONSTRATION = os.path.join(DEPOT, ".demo")


class Usine:
    """Fabrique les objets dont les adaptateurs pilotes ont besoin."""

    def ouvrir(self, chemin: str) -> Messagerie:
        d = _disposition(_absolu(chemin))
        if d.markdown:
            boite = DepotBoiteMarkdown(d.boite)
        else:
            boite = DepotBoiteJson(d.boite, racine=d.racine,
                                   vue=VueMarkdown(d.vue, os.path.basename(d.boite), os.path.basename(d.manifeste)))
        annuaire = DepotAnnuaireJson(d.manifeste, os.path.basename(d.boite))
        return Messagerie(boite, annuaire, PiecesDossier(d.pieces), HorlogeSysteme())

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

    def depot(self) -> str:
        """La racine du dépôt arkalabs-messenger (où vivent `messenger.py` et `skills/`)."""
        return DEPOT

    def poser_onboarding(self, chemin: str) -> str:
        """Pose `onboarding.md` à la racine de la boîte (guide d'accueil des agents)."""
        return _poser_onboarding(_disposition(_absolu(chemin)).racine)


def main(argv: Optional[List[str]] = None) -> int:
    return executer(argv, Usine())


def _absolu(chemin: str) -> str:
    return os.path.abspath(os.path.expanduser(chemin))
