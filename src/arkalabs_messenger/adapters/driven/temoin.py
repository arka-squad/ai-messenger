"""Le témoin d'une boîte : ce que ce poste a vu de plus complet, pour ne jamais écrire sur une lecture périmée.

**Pourquoi.** Une boîte ne rétrécit jamais : un message n'est jamais retiré, seul son statut avance.
Si une relecture en rend moins qu'avant, ce n'est pas la boîte qui a maigri — c'est la lecture qui
est fausse. Le cas est réel et observé : un partage réseau servi par la machine qui écrit dedans en
local (macOS) sert parfois à l'autre machine une copie périmée pendant plusieurs minutes. Écrire
par-dessus, c'est effacer les messages qu'on n'a pas vus.

Le témoin vit **sur le poste**, pas dans la boîte : c'est la mémoire de cette machine, pas une
donnée partagée. Il ne protège pas la boîte contre un autre poste — il protège la boîte contre
*cette* machine lorsqu'elle lit mal.
"""
from __future__ import annotations

import io
import json
import os
from typing import Dict, Optional, Tuple

NOM = ".arkalabs-messenger.temoins.json"
"""Un fichier par poste, à côté de sa configuration."""

FICHIER: Optional[str] = None
"""Détourne le témoin ailleurs — les tests s'en servent pour ne jamais toucher le poste réel."""


def fichier_du_poste() -> str:
    """Résolu à chaque appel, jamais à l'import : un poste déplacé (ou un test) est suivi."""
    return FICHIER or os.path.join(os.path.expanduser("~"), NOM)


_MAX = 50
"""On ne garde que les dernières boîtes vues : le fichier ne grossit pas sans fin."""


class LecturePerimee(Exception):
    """La boîte relue est plus courte que la dernière vue depuis ce poste : on n'écrit pas par-dessus."""


class Temoin:
    """Retient, par boîte, le nombre de messages le plus élevé que ce poste ait lu."""

    def __init__(self, fichier: Optional[str] = None) -> None:
        self._fichier = fichier or fichier_du_poste()

    def verifier(self, chemin: str, messages: int) -> None:
        """Lève `LecturePerimee` si la boîte a l'air d'avoir perdu des messages depuis la dernière fois."""
        vu = self.lu(chemin)
        if vu is not None and messages < vu:
            raise LecturePerimee(
                f"stale read; nothing was written: this mailbox contains {messages} message(s), "
                f"but this machine has already read {vu}. A mailbox never loses messages—the current "
                f"read is unreliable (network-share cache or a partially disconnected mount). "
                f"Try again; if the mailbox was intentionally replaced, delete its witness: {self._fichier}")

    def noter(self, chemin: str, messages: int) -> None:
        """Retient ce que ce poste vient de voir. Le témoin ne recule jamais."""
        table = self._lire()
        cle = _cle(chemin)
        if messages >= table.get(cle, 0):
            table[cle] = messages
            self._ecrire(table)

    def lu(self, chemin: str) -> Optional[int]:
        return self._lire().get(_cle(chemin))

    def oublier(self, chemin: str) -> None:
        """Le témoin d'une boîte délibérément remplacée (migration, réparation)."""
        table = self._lire()
        if table.pop(_cle(chemin), None) is not None:
            self._ecrire(table)

    # ---------------------------------------------------------------- #
    def _lire(self) -> Dict[str, int]:
        try:
            with io.open(self._fichier, encoding="utf-8") as f:
                table = json.load(f)
        except (OSError, ValueError):
            return {}
        return {k: v for k, v in table.items() if isinstance(k, str) and isinstance(v, int)} \
            if isinstance(table, dict) else {}

    def _ecrire(self, table: Dict[str, int]) -> None:
        garde = dict(list(table.items())[-_MAX:])
        tmp = self._fichier + ".tmp"
        try:
            with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
                json.dump(garde, f, ensure_ascii=False, indent=2)
                f.write("\n")
            os.replace(tmp, self._fichier)
        except OSError:
            pass  # un témoin qu'on ne peut pas écrire ne doit jamais empêcher d'écrire le courrier


def _cle(chemin: str) -> str:
    return os.path.normcase(os.path.abspath(chemin))


def etat(chemin: str, messages: int) -> Tuple[str, int]:
    """Le couple (clé, nombre) tel que le témoin le range — pour les tests et le diagnostic."""
    return _cle(chemin), messages
