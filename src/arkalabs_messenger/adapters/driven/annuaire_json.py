"""L'annuaire des comptes dans `<boîte>.manifest.json`."""
from __future__ import annotations

import contextlib
import json
import os
from typing import Iterator

from ...application.ports import BoiteIndisponible, DepotAnnuaire
from ...domain import Annuaire
from ..codec import FormatInvalide, annuaire_depuis_dict, annuaire_vers_dict, en_json
from .fichiers import ecrire_atomique, empreinte, verrou


class DepotAnnuaireJson(DepotAnnuaire):
    def __init__(self, chemin: str, nom_boite: str) -> None:
        self._chemin = chemin
        self._nom_boite = nom_boite

    def existe(self) -> bool:
        return os.path.exists(self._chemin)

    def creer(self) -> None:
        with verrou(self._chemin):
            if not self.existe():
                self._ecrire(Annuaire())

    def lire(self) -> Annuaire:
        try:
            with open(self._chemin, encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            return Annuaire()
        except ValueError:
            raise BoiteIndisponible(f"unreadable manifest, invalid JSON: {self._chemin}") from None
        except OSError as e:
            raise BoiteIndisponible(f"manifeste injoignable : {self._chemin} ({e.strerror})") from None
        try:
            return annuaire_depuis_dict(data)
        except FormatInvalide as e:
            raise BoiteIndisponible(f"manifeste non conforme ({e}) : {self._chemin}") from None

    @contextlib.contextmanager
    def transaction(self) -> Iterator[Annuaire]:
        with verrou(self._chemin):
            annuaire = self.lire()
            yield annuaire
            self._ecrire(annuaire)

    def version(self) -> str:
        return empreinte(self._chemin)

    def _ecrire(self, annuaire: Annuaire) -> None:
        ecrire_atomique(self._chemin, en_json(annuaire_vers_dict(annuaire, self._nom_boite)))
