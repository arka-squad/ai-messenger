"""L'horloge du système."""
from __future__ import annotations

import time
from datetime import datetime

from ...application.ports import Horloge


class HorlogeSysteme(Horloge):
    def maintenant(self) -> datetime:
        return datetime.now().astimezone()

    def monotone(self) -> float:
        return time.monotonic()

    def dormir(self, secondes: float) -> None:
        time.sleep(secondes)
