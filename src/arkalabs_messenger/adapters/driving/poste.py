"""Ce que le poste et le dépôt savent, et ce qu'on fait sur le poste.

- La boîte est propre au **poste** (son chemin diffère d'une machine à l'autre) :
  `~/.arkalabs-messenger.json`, écrit par `setup --box`.
- Le projet est propre au **dépôt** (il est le même sur toutes les machines) :
  `.messenger.json` à la racine du dépôt, écrit par `setup --project`, versionnable.
- L'identité d'une **session** (`enroll --session`) est mémorisée dans la config du poste.
- Activer un dépôt (hooks et skill dans son `.claude/`) et ouvrir le sélecteur de dossier
  natif sont des gestes du poste : ils vivent ici, partagés par la CLI et l'API web.
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional

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


def resoudre_agent(explicite: Optional[str], session: Optional[str] = None) -> Optional[str]:
    """`--agent`, sinon MESSENGER_AGENT, sinon l'agent enrôlé dans cette session (`enroll --session`).

    L'identité d'une session est mémorisée par `session_id` : chaque session de l'hôte porte la
    sienne, sans variable au lancement.
    """
    return explicite or os.environ.get("MESSENGER_AGENT") or agent_de_session(session)


def agent_de_session(session: Optional[str]) -> Optional[str]:
    """L'agent enrôlé pour ce `session_id`, ou None."""
    if not session:
        return None
    valeur = lire_config().get("sessions", {}).get(session)
    return valeur if isinstance(valeur, str) and valeur else None


def memoriser_session(session: str, agent: str) -> str:
    """Rattache un `session_id` à un agent, dans la config du poste. Rend le chemin de la config."""
    conf = lire_config()
    sessions = conf.get("sessions")
    if not isinstance(sessions, dict):
        sessions = {}
    sessions[session] = agent
    conf["sessions"] = sessions
    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump(conf, f, ensure_ascii=False, indent=2)
    return CONFIG


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


# --------------------------------------------------------------------------- #
# Activer un dépôt : hooks et skill dans .claude/, pour que ses agents s'enrôlent
# --------------------------------------------------------------------------- #
class ActivationRefusee(Exception):
    """Une activation impossible (dossier absent, réglages illisibles, skill introuvable)."""


class SelecteurIndisponible(Exception):
    """Aucun sélecteur de dossier natif sur ce poste : l'humain saisira le chemin à la main."""


def choisir_dossier() -> Optional[str]:
    """Ouvre le sélecteur de dossier natif de l'OS et rend le chemin choisi, ou None si annulé.

    L'app tourne sur la machine de l'humain : la fenêtre s'ouvre sur son bureau. Un sous-processus
    par OS (PowerShell / osascript / zenity) évite toute dépendance et les soucis de thread.
    """
    systeme = platform.system()
    if systeme == "Windows":
        script = ("Add-Type -AssemblyName System.Windows.Forms | Out-Null;"
                  "$f = New-Object System.Windows.Forms.FolderBrowserDialog;"
                  "$f.Description = 'Choisir le dossier';"
                  "if ($f.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) "
                  "{ [Console]::Out.Write($f.SelectedPath) }")
        commande = ["powershell", "-STA", "-NoProfile", "-Command", script]
    elif systeme == "Darwin":
        commande = ["osascript", "-e", 'POSIX path of (choose folder with prompt "Choisir le dossier")']
    else:
        commande = ["zenity", "--file-selection", "--directory", "--title", "Choisir le dossier"]
    try:
        resultat = subprocess.run(commande, capture_output=True, text=True)
    except (OSError, ValueError) as e:
        raise SelecteurIndisponible(
            f"sélecteur de dossier natif indisponible ({e}) : saisis le chemin à la main") from None
    chemin = (resultat.stdout or "").strip()
    return chemin or None


def activer_depot(dossier: str, projet: Optional[str], depot: str, box: Optional[str] = None) -> Dict[str, Any]:
    """Rend un dépôt prêt : mémorise sa boîte pour le poste, l'attache au projet, pose hooks et skill.

    `depot` est la racine d'arkalabs-messenger (où vivent `messenger.py` et `skills/`).
    Rend un résumé des chemins écrits. Lève `ActivationRefusee` si le dossier n'existe pas.
    """
    dossier = os.path.abspath(os.path.expanduser(dossier))
    if not os.path.isdir(dossier):
        raise ActivationRefusee(f"dossier introuvable : {dossier}")
    if box:
        memoriser_boite(box)
    if projet:
        attacher_projet(dossier, projet)
    reglages = _installer_hooks(dossier, depot)
    skill = _copier_skill(dossier, depot)
    return {"dossier": dossier, "projet": resoudre_projet(None, dossier),
            "boite": box, "hooks": reglages, "skill": skill}


def _installer_hooks(dossier: str, depot: str) -> str:
    """Fusionne les hooks SessionStart et UserPromptSubmit dans `.claude/settings.local.json`."""
    chemin = os.path.join(dossier, ".claude", "settings.local.json")
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    reglages: Dict[str, Any] = {}
    if os.path.isfile(chemin):
        try:
            with open(chemin, encoding="utf-8") as f:
                reglages = json.load(f)
        except ValueError:
            raise ActivationRefusee(f"{chemin} n'est pas un JSON valide : corrige-le avant d'activer") from None
    if not isinstance(reglages, dict):
        reglages = {}
    hooks = reglages.setdefault("hooks", {})
    messenger_py = os.path.join(depot, "messenger.py")
    base = {"type": "command", "command": sys.executable, "args": [messenger_py, "check", "--hook"], "timeout": 20}
    for evenement, extra in (("SessionStart", {"statusMessage": "Relève du courrier"}), ("UserPromptSubmit", {})):
        liste = hooks.setdefault(evenement, [])
        if isinstance(liste, list) and not _hook_present(liste, messenger_py):
            liste.append({"hooks": [{**base, **extra}]})
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(reglages, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return chemin


def _hook_present(liste: List[Any], messenger_py: str) -> bool:
    for groupe in liste:
        for h in (groupe.get("hooks", []) if isinstance(groupe, dict) else []):
            args = h.get("args") if isinstance(h, dict) else None
            if isinstance(args, list) and messenger_py in args and "--hook" in args:
                return True
    return False


def _copier_skill(dossier: str, depot: str) -> str:
    """Copie la skill dans `.claude/skills/` du dépôt, pour que les agents la chargent d'eux-mêmes."""
    source = os.path.join(depot, "skills", "arkalabs-messenger")
    cible = os.path.join(dossier, ".claude", "skills", "arkalabs-messenger")
    if not os.path.isdir(source):
        raise ActivationRefusee(f"skill introuvable dans le dépôt de l'outil : {source}")
    if os.path.abspath(source) != os.path.abspath(cible):
        shutil.copytree(source, cible, dirs_exist_ok=True)
    return cible
