"""Tests : `python -m unittest` depuis la racine du dépôt.

Aucun test ne touche le poste réel. Le témoin des boîtes (`adapters/driven/temoin.py`) vit
normalement dans le dossier personnel : on le détourne ici, une fois pour toute la suite, vers un
dossier temporaire effacé à la fin. Les tests qui lancent `messenger.py` en sous-processus, eux,
déplacent déjà `HOME`.
"""
import atexit
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from arkalabs_messenger.adapters.driven import temoin  # noqa: E402 — après le chemin d'import

_DOSSIER = tempfile.mkdtemp(prefix="arkalabs-messenger-tests-")
temoin.FICHIER = os.path.join(_DOSSIER, "temoins.json")
atexit.register(shutil.rmtree, _DOSSIER, True)
