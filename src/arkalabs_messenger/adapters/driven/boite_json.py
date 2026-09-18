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

Publication = Callable[[Boite], None]


class DepotBoiteJson(DepotBoite):
    """Lit et écrit `boite.json`, et publie une vue après chaque écriture."""

    def __init__(self, chemin: str, vue: Optional[Publication] = None) -> None:
        self._chemin = chemin
        self._vue = vue

    @property
    def emplacement(self) -> str:
        return self._chemin

    def existe(self) -> bool:
        return os.path.exists(self._chemin)

    def creer(self, boite: Optional[Boite] = None) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self._chemin)), exist_ok=True)
        with verrou(self._chemin):
            if self.existe():
                raise BoiteExistante(f"existe déjà, rien écrit : {self._chemin}")
            self._ecrire(boite or Boite())

    def lire(self) -> Boite:
        try:
            with open(self._chemin, encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            raise BoiteIndisponible(f"boîte introuvable : {self._chemin} (crée-la avec `init`)") from None
        except ValueError:
            raise BoiteIndisponible(f"boîte illisible, JSON invalide : {self._chemin}") from None
        except OSError as e:
            raise BoiteIndisponible(f"boîte injoignable : {self._chemin} ({e.strerror})") from None
        try:
            return boite_depuis_dict(data)
        except FormatInvalide as e:
            raise BoiteIndisponible(f"boîte non conforme ({e}) : {self._chemin}") from None

    @contextlib.contextmanager
    def transaction(self) -> Iterator[Boite]:
        with verrou(self._chemin):
            boite = self.lire()
            yield boite
            self._ecrire(boite)

    def version(self) -> str:
        return empreinte(self._chemin)

    def _ecrire(self, boite: Boite) -> None:
        ecrire_atomique(self._chemin, en_json(boite_vers_dict(boite)))
        if self._vue:
            self._vue(boite)
