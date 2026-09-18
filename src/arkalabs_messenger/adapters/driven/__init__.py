"""Les adaptateurs pilotés : ils implémentent les ports de `application.ports`."""

from .ancienne_boite import DepotBoiteMarkdown, SourceMarkdown
from .annuaire_json import DepotAnnuaireJson
from .boite_json import DepotBoiteJson
from .horloge import HorlogeSysteme
from .notifications_systeme import NotificationsSysteme
from .pieces_dossier import PiecesDossier
from .vue_markdown import VueMarkdown

__all__ = [
    "DepotBoiteJson", "DepotAnnuaireJson", "DepotBoiteMarkdown", "SourceMarkdown",
    "PiecesDossier", "HorlogeSysteme", "VueMarkdown", "NotificationsSysteme",
]
