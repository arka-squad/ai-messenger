"""System notifications for messages arriving in the mailbox."""
from __future__ import annotations

from typing import Callable, List, Optional, Set

from ..domain import Message
from .messagerie import Messagerie
from .ports import Notificateur

RAFALE = 3
"""Above this threshold, messages arriving together are grouped in one notification."""


class Annonceur:
    """Check the mailbox and announce messages received since the previous check.

    The first check records the mailbox without announcing anything. Messages for
    `compte` are identified as such; other messages include their recipient addresses.
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
        """Return messages received since the previous check and announce them when enabled."""
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
                f"{len(arrives)} new messages in the mailbox",
                [f"including {pour_moi} for {self._compte}" if pour_moi else "none are addressed to you"],
                self._lien(arrives[-1]) if self._lien else None)
            return
        for m in arrives:
            titre = f"{m.de} wrote to you" if m.est_pour(self._compte) else f"{m.de} → {', '.join(m.a)}"
            self._notificateur.notifier(titre, [m.titre, *m.corps[:1]], self._lien(m) if self._lien else None)
