"""La boîte dans un fichier JSON — la source de vérité."""
from __future__ import annotations

import contextlib
import json
import os
from typing import Callable, Iterator, Optional

from ...application.ports import BoiteExistante, BoiteIndisponible, DepotBoite
from ...domain import Boite
from ..codec import FormatInvalide, boite_depuis_dict, boite_vers_dict, en_json
from .fichiers import ecrire_atomique, empreinte, verrou
from .temoin import LecturePerimee, Temoin

Publication = Callable[[Boite], None]


class DepotBoiteJson(DepotBoite):
    """Lit et écrit `boite.json`, et publie une vue après chaque écriture."""

    def __init__(self, chemin: str, vue: Optional[Publication] = None, racine: Optional[str] = None,
                 temoin: Optional[Temoin] = None) -> None:
        self._chemin = chemin
        self._vue = vue
        self._racine = racine or os.path.dirname(os.path.abspath(chemin))
        # Le témoin refuse d'écrire sur une lecture périmée : une boîte ne perd jamais de message.
        self._temoin = temoin if temoin is not None else Temoin()

    @property
    def emplacement(self) -> str:
        return self._chemin

    @property
    def racine(self) -> str:
        return self._racine

    def existe(self) -> bool:
        return os.path.exists(self._chemin)

    def creer(self, boite: Optional[Boite] = None) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self._chemin)), exist_ok=True)
        with verrou(self._chemin):
            if self.existe():
                raise BoiteExistante(f"already exists; nothing was written: {self._chemin}")
            self._ecrire(boite or Boite())

    def lire(self) -> Boite:
        """Un instantané. Une lecture réussie nourrit le témoin : ce poste a vu cette boîte aussi longue."""
        try:
            with open(self._chemin, encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            raise BoiteIndisponible(f"mailbox not found: {self._chemin} (create it with `init`)") from None
        except ValueError:
            raise BoiteIndisponible(f"unreadable mailbox, invalid JSON: {self._chemin}") from None
        except OSError as e:
            raise BoiteIndisponible(f"mailbox unavailable: {self._chemin} ({e.strerror})") from None
        try:
            boite = boite_depuis_dict(data)
        except FormatInvalide as e:
            raise BoiteIndisponible(f"invalid mailbox format ({e}): {self._chemin}") from None
        self._temoin.noter(self._chemin, len(boite.messages))
        return boite

    @contextlib.contextmanager
    def transaction(self) -> Iterator[Boite]:
        with verrou(self._chemin):
            boite = self.lire()
            try:
                self._temoin.verifier(self._chemin, len(boite.messages))
            except LecturePerimee as e:
                raise BoiteIndisponible(str(e)) from None
            yield boite
            self._ecrire(boite)

    def version(self) -> str:
        return empreinte(self._chemin)

    def _ecrire(self, boite: Boite) -> None:
        ecrire_atomique(self._chemin, en_json(boite_vers_dict(boite)))
        self._temoin.noter(self._chemin, len(boite.messages))
        if self._vue:
            self._vue(boite)
