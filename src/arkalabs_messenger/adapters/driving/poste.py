"""Ce que le poste et le dépôt savent.

- La boîte est propre au **poste** (son chemin diffère d'une machine à l'autre) :
  `~/.arkalabs-messenger.json`, écrit par `setup --box`.
- Le projet est propre au **dépôt** (il est le même sur toutes les machines) :
  `.messenger.json` à la racine du dépôt, écrit par `setup --project`, versionnable.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

CONFIG = os.path.join(os.path.expanduser("~"), ".arkalabs-messenger.json")
FICHIER_PROJET = ".messenger.json"


def lire_config() -> Dict[str, Any]:
    try:
        with open(CONFIG, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def memoriser_boite(chemin: str) -> str:
    conf = lire_config()
    conf["box"] = chemin
    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump(conf, f, ensure_ascii=False, indent=2)
    return CONFIG


def resoudre_boite(explicite: Optional[str]) -> Optional[str]:
    """`--box`, sinon MESSENGER_BOX, sinon la boîte mémorisée par `setup`."""
    return explicite or os.environ.get("MESSENGER_BOX") or lire_config().get("box")


def resoudre_agent(explicite: Optional[str]) -> Optional[str]:
    """`--agent`, sinon MESSENGER_AGENT. Jamais mémorisé : un poste peut porter plusieurs agents."""
    return explicite or os.environ.get("MESSENGER_AGENT")


def resoudre_projet(explicite: Optional[str], dossier: Optional[str] = None) -> Optional[str]:
    """`--project`, sinon MESSENGER_PROJECT, sinon le `.messenger.json` du dépôt courant.

    Une valeur vide (`--project ""`) signifie : aucun projet, compte commun.
    """
    if explicite is not None:
        return explicite or None
    if "MESSENGER_PROJECT" in os.environ:
        return os.environ["MESSENGER_PROJECT"] or None
    fichier = trouver_fichier_projet(dossier or os.getcwd())
    if not fichier:
        return None
    try:
        with open(fichier, encoding="utf-8") as f:
            projet = json.load(f).get("project")
        return projet if isinstance(projet, str) and projet else None
    except (OSError, ValueError, AttributeError):
        return None


def trouver_fichier_projet(dossier: str) -> Optional[str]:
    """Le `.messenger.json` le plus proche, en remontant depuis `dossier`."""
    courant = os.path.abspath(dossier)
    while True:
        candidat = os.path.join(courant, FICHIER_PROJET)
        if os.path.isfile(candidat):
            return candidat
        parent = os.path.dirname(courant)
        if parent == courant:
            return None
        courant = parent


def attacher_projet(dossier: str, projet: str) -> str:
    """Écrit le `.messenger.json` du dépôt : ses agents appartiennent désormais à `projet`."""
    chemin = os.path.join(os.path.abspath(dossier), FICHIER_PROJET)
    with open(chemin, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"project": projet}, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return chemin
