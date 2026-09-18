"""Les annonces : une notification système pour chaque message qui passe dans la boîte."""
from __future__ import annotations

from typing import Callable, List, Optional, Set

from ..domain import Message
from .messagerie import Messagerie
from .ports import Notificateur

RAFALE = 3
"""Au-delà, les messages arrivés d'un coup sont résumés en une seule notification."""


class Annonceur:
    """Relève la boîte et annonce les messages arrivés depuis la relève précédente.

    La première relève mémorise la boîte sans rien annoncer. Un message adressé à
    `compte` est annoncé comme tel ; les autres le sont aussi, avec leurs adresses.
    """

    def __init__(self, messagerie: Messagerie, notificateur: Notificateur, compte: str,
                 lien: Optional[Callable[[Message], str]] = None) -> None:
        self._messagerie = messagerie
        self._notificateur = notificateur
        self._compte = compte
        self._lien = lien
        self._connus: Optional[Set[str]] = None
        self.actif = True

    def relever(self) -> List[Message]:
        """Les messages arrivés depuis la relève précédente, annoncés si l'annonceur est actif."""
        messages = self._messagerie.instantane().messages
        if self._connus is None:
            self._connus = {m.id for m in messages}
            return []
        arrives = [m for m in messages if m.id not in self._connus]
        self._connus.update(m.id for m in arrives)
        if self.actif and arrives:
            self._annoncer(arrives)
        return arrives

    def _annoncer(self, arrives: List[Message]) -> None:
        if len(arrives) > RAFALE:
            pour_moi = sum(1 for m in arrives if m.est_pour(self._compte))
            self._notificateur.notifier(
                f"{len(arrives)} nouveaux messages dans la boîte",
                [f"dont {pour_moi} pour {self._compte}" if pour_moi else "aucun ne t'est adressé"],
                self._lien(arrives[-1]) if self._lien else None)
            return
        for m in arrives:
            titre = f"{m.de} t'écrit" if m.est_pour(self._compte) else f"{m.de} → {', '.join(m.a)}"
            self._notificateur.notifier(titre, [m.titre, *m.corps[:1]], self._lien(m) if self._lien else None)
