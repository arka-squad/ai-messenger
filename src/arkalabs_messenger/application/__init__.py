"""L'application : les cas d'usage (`Messagerie`, `Annonceur`) et les ports qu'ils attendent."""

from .annonces import Annonceur
from .messagerie import Carnet, Envoi, Import, Messagerie
from .ports import (
    BoiteExistante,
    BoiteIndisponible,
    DepotAnnuaire,
    DepotBoite,
    Horloge,
    LectureSeule,
    Notificateur,
    PieceJointeRefusee,
    PiecesJointes,
    SourceAncienne,
)

__all__ = [
    "Messagerie", "Carnet", "Envoi", "Import", "Annonceur",
    "DepotBoite", "DepotAnnuaire", "PiecesJointes", "Horloge", "SourceAncienne", "Notificateur",
    "BoiteIndisponible", "BoiteExistante", "LectureSeule", "PieceJointeRefusee",
]
