"""Les ports : ce dont les cas d'usage ont besoin, sans dire comment c'est fait.

Chaque port est implémenté par un adaptateur (`adapters/driven`). Les tests
les implémentent en mémoire (`tests/doublures.py`).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import ContextManager, List, Optional, Sequence

from ..domain import Annuaire, Boite, ErreurMessenger, Message


class BoiteIndisponible(ErreurMessenger):
    """La boîte est absente, illisible, non conforme ou verrouillée trop longtemps."""


class BoiteExistante(ErreurMessenger):
    """On demande de créer une boîte qui existe déjà."""


class LectureSeule(ErreurMessenger):
    """La boîte ne peut pas être modifiée (ancienne boîte Markdown)."""


class PieceJointeRefusee(ErreurMessenger):
    """La pièce jointe est introuvable, ou son nom est déjà pris dans la boîte."""


class DepotBoite(ABC):
    """Là où vivent les messages."""

    lecture_seule: bool = False

    @property
    @abstractmethod
    def emplacement(self) -> str:
        """Où est la boîte, pour les messages adressés à l'utilisateur."""

    @abstractmethod
    def existe(self) -> bool: ...

    @abstractmethod
    def creer(self, boite: Optional[Boite] = None) -> None:
        """Crée la boîte, vide ou avec un contenu initial. Refuse si elle existe."""

    @abstractmethod
    def lire(self) -> Boite:
        """Un instantané de la boîte."""

    @abstractmethod
    def transaction(self) -> ContextManager[Boite]:
        """Verrouille, relit, cède la boîte, puis l'écrit — sauf si une erreur survient."""

    @abstractmethod
    def version(self) -> str:
        """Une empreinte qui change à chaque écriture, pour détecter un changement à peu de frais."""


class DepotAnnuaire(ABC):
    """Là où vivent les comptes."""

    @abstractmethod
    def existe(self) -> bool: ...

    @abstractmethod
    def creer(self) -> None:
        """Crée un annuaire vide s'il n'existe pas ; ne touche pas à un annuaire existant."""

    @abstractmethod
    def lire(self) -> Annuaire:
        """Un instantané ; vide si l'annuaire n'existe pas."""

    @abstractmethod
    def transaction(self) -> ContextManager[Annuaire]: ...


class PiecesJointes(ABC):
    """Les fichiers joints, rangés à côté de la boîte."""

    @abstractmethod
    def deposer(self, source: str) -> str:
        """Range le fichier près de la boîte et rend son nom."""

    @abstractmethod
    def localiser(self, nom: str) -> Optional[str]:
        """Le chemin lisible d'une pièce jointe, ou None si elle est absente."""


class Horloge(ABC):
    @abstractmethod
    def maintenant(self) -> datetime:
        """L'instant présent, avec son fuseau."""

    @abstractmethod
    def monotone(self) -> float:
        """Un compteur de secondes qui ne recule jamais."""

    @abstractmethod
    def dormir(self, secondes: float) -> None: ...


class Notificateur(ABC):
    """Les notifications du système d'exploitation."""

    @abstractmethod
    def notifier(self, titre: str, lignes: Sequence[str], lien: Optional[str] = None) -> None:
        """Affiche une notification ; ne lève jamais : une notification ne bloque rien."""


class SourceAncienne(ABC):
    """Une boîte d'un format antérieur, à importer."""

    @property
    @abstractmethod
    def emplacement(self) -> str: ...

    @abstractmethod
    def messages(self) -> List[Message]:
        """Les messages, dans l'ordre d'envoi."""
