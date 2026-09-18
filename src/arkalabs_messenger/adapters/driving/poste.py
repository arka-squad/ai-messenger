"""Ce que le poste sait : la boîte mémorisée par `setup`, et l'environnement."""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

CONFIG = os.path.join(os.path.expanduser("~"), ".arkalabs-messenger.json")


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
