"""Doublures en mémoire des ports : les cas d'usage se testent sans fichier."""
from __future__ import annotations

import contextlib
import copy
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, Iterator, List, Optional

from arkalabs_messenger.application import (
    BoiteExistante,
    DepotAnnuaire,
    DepotBoite,
    Horloge,
    Messagerie,
    PieceJointeRefusee,
    PiecesJointes,
    SourceAncienne,
)
from arkalabs_messenger.domain import Annuaire, Boite, Message


class BoiteMemoire(DepotBoite):
    def __init__(self) -> None:
        self.boite: Optional[Boite] = None
        self.ecritures = 0

    @property
    def emplacement(self) -> str:
        return "mémoire://boite"

    @property
    def racine(self) -> str:
        return "mémoire://"

    def existe(self) -> bool:
        return self.boite is not None

    def creer(self, boite: Optional[Boite] = None) -> None:
        if self.boite is not None:
            raise BoiteExistante("existe déjà")
        self.boite = boite or Boite()

    def lire(self) -> Boite:
        assert self.boite is not None
        return copy.deepcopy(self.boite)

    @contextlib.contextmanager
    def transaction(self) -> Iterator[Boite]:
        boite = self.lire()
        yield boite
        self.boite = boite
        self.ecritures += 1

    def version(self) -> str:
        return str(self.ecritures)


class AnnuaireMemoire(DepotAnnuaire):
    def __init__(self, present: bool = True) -> None:
        self.annuaire: Optional[Annuaire] = Annuaire() if present else None

    def existe(self) -> bool:
        return self.annuaire is not None

    def creer(self) -> None:
        if self.annuaire is None:
            self.annuaire = Annuaire()

    def lire(self) -> Annuaire:
        return copy.deepcopy(self.annuaire) if self.annuaire else Annuaire()

    @contextlib.contextmanager
    def transaction(self) -> Iterator[Annuaire]:
        annuaire = self.lire()
        yield annuaire
        self.annuaire = annuaire


class PiecesMemoire(PiecesJointes):
    def __init__(self, sources: Optional[Dict[str, str]] = None) -> None:
        self.sources = dict(sources or {})
        self.deposees: Dict[str, str] = {}

    def deposer(self, source: str) -> str:
        if source not in self.sources:
            raise PieceJointeRefusee(f"pièce jointe introuvable : {source}")
        nom = source.rsplit("/", 1)[-1]
        self.deposees[nom] = self.sources[source]
        return nom

    def localiser(self, nom: str) -> Optional[str]:
        return f"mémoire://{nom}" if nom in self.deposees else None


class HorlogeFigee(Horloge):
    """Avance seulement quand on dort ; peut déclencher un effet à chaque sommeil."""

    def __init__(self, depart: datetime = datetime(2026, 9, 18, 22, 50, tzinfo=timezone(timedelta(hours=2)))) -> None:
        self.instant = depart
        self.ecoule = 0.0
        self.au_reveil: List[Callable[[], None]] = []

    def maintenant(self) -> datetime:
        return self.instant

    def monotone(self) -> float:
        return self.ecoule

    def dormir(self, secondes: float) -> None:
        self.ecoule += secondes
        self.instant += timedelta(seconds=secondes)
        if self.au_reveil:
            self.au_reveil.pop(0)()


class SourceMemoire(SourceAncienne):
    def __init__(self, messages: List[Message]) -> None:
        self._messages = messages

    @property
    def emplacement(self) -> str:
        return "mémoire://ancienne"

    def messages(self) -> List[Message]:
        return list(self._messages)


def messagerie(annuaire: bool = True, pieces: Optional[Dict[str, str]] = None):
    """Une messagerie en mémoire, initialisée, et ses doublures."""
    boite, comptes, pj, horloge = BoiteMemoire(), AnnuaireMemoire(annuaire), PiecesMemoire(pieces), HorlogeFigee()
    m = Messagerie(boite, comptes, pj, horloge)
    boite.creer()
    return m, boite, comptes, pj, horloge
