"""Écriture sûre sur un dossier partagé : verrou par fichier et remplacement atomique."""
from __future__ import annotations

import contextlib
import os
import time
from typing import Iterator

from ...application.ports import BoiteIndisponible

ATTENTE_MAX = 20.0
"""Secondes d'attente d'un verrou tenu par un autre processus."""

VERROU_PERIME = 60.0
"""Âge au-delà duquel un verrou est tenu pour abandonné par un processus mort."""


@contextlib.contextmanager
def verrou(chemin: str, attente: float = ATTENTE_MAX, perime: float = VERROU_PERIME) -> Iterator[None]:
    """Verrou `<chemin>.lock` par création exclusive — fiable sur un partage réseau."""
    lock = chemin + ".lock"
    debut = time.monotonic()
    while True:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                if time.time() - os.path.getmtime(lock) > perime:
                    os.remove(lock)
                    continue
            except OSError:
                continue  # le verrou vient d'être levé : on retente aussitôt
            if time.monotonic() - debut > attente:
                raise BoiteIndisponible(f"locked for more than {attente:.0f} seconds: {lock}") from None
            time.sleep(0.2)
        else:
            os.write(fd, f"{os.getpid()} {time.time()}".encode())
            os.close(fd)
            break
    try:
        yield
    finally:
        with contextlib.suppress(OSError):
            os.remove(lock)


def ecrire_atomique(chemin: str, texte: str) -> None:
    """Écrit à côté, puis remplace : un lecteur voit toujours un fichier complet."""
    tmp = chemin + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(texte)
    os.replace(tmp, chemin)


def empreinte(*chemins: str) -> str:
    """Date de modification et taille de chaque fichier : change à chaque écriture."""
    parts = []
    for c in chemins:
        try:
            st = os.stat(c)
            parts.append(f"{st.st_mtime_ns}:{st.st_size}")
        except OSError:
            parts.append("-")
    return "/".join(parts)
