"""Ce que le poste et le dépôt savent, et ce qu'on fait sur le poste.

- La boîte est propre au **poste** (son chemin diffère d'une machine à l'autre) :
  `~/.arkalabs-messenger.json`, écrit par `setup --box`.
- Le projet est propre au **dépôt** (il est le même sur toutes les machines) :
  `.messenger.json` à la racine du dépôt, écrit par `setup --project`, versionnable.
- L'identité d'une **session** (`enroll --session`) est mémorisée dans la config du poste.
- L'identité d'un agent est aussi retenue par **hôte et par dossier**, pour les hôtes qui ne
  donnent pas de `session_id`.
- Connecter un dépôt à la boîte et ouvrir le sélecteur de dossier natif sont des gestes du
  poste : ils vivent ici, partagés par la CLI, l'API web et le serveur MCP.
"""
from __future__ import annotations

import json
import os
import platform
import subprocess
from typing import Any, Dict, Optional

from . import hotes

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
    _ecrire_config(conf)
    return CONFIG


def _ecrire_config(conf: Dict[str, Any]) -> None:
    """Écrit à côté, puis remplace : plusieurs sessions partagent ce fichier."""
    tmp = CONFIG + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(conf, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CONFIG)


def resoudre_boite(explicite: Optional[str]) -> Optional[str]:
    """`--box`, sinon MESSENGER_BOX, sinon la boîte mémorisée par `setup`."""
    return explicite or os.environ.get("MESSENGER_BOX") or lire_config().get("box")


def resoudre_agent(explicite: Optional[str], session: Optional[str] = None, hote: Optional[str] = None,
                   dossier: Optional[str] = None) -> Optional[str]:
    """`--agent`, sinon MESSENGER_AGENT, sinon l'agent de cette session, sinon le dernier enrôlé ici.

    L'identité d'une session est mémorisée par `session_id` quand l'hôte en donne un ; à défaut,
    par hôte et par dossier. La relève annonce toujours son destinataire : une session qui n'est
    pas cet agent ignore ce courrier (c'est la règle de la skill).
    """
    return (explicite or os.environ.get("MESSENGER_AGENT") or agent_de_session(session)
            or (identite_memorisee(hote, dossier) if hote and dossier else None))


def agent_de_session(session: Optional[str]) -> Optional[str]:
    """L'agent enrôlé pour ce `session_id`, ou None."""
    return _memo("sessions", session) if session else None


def memoriser_session(session: str, agent: str) -> str:
    """Rattache un `session_id` à un agent, dans la config du poste. Rend le chemin de la config."""
    return _memoriser("sessions", session, agent)


def identite_memorisee(hote: Optional[str], dossier: Optional[str]) -> Optional[str]:
    """Le dernier agent enrôlé par cet hôte dans ce dossier, ou None."""
    return _memo("identites", _cle_identite(hote, dossier)) if hote and dossier else None


def memoriser_identite(hote: str, dossier: str, agent: str) -> str:
    """Retient qu'un agent de `hote` s'est enrôlé dans `dossier` : la relève le retrouvera."""
    return _memoriser("identites", _cle_identite(hote, dossier), agent)


def code_du_poste() -> str:
    """Le code du poste dans une identité lisible : `win`, `mac`, `lnx`, ou trois lettres du système."""
    systeme = platform.system()
    connu = {"Windows": "win", "Darwin": "mac", "Linux": "lnx"}.get(systeme)
    return connu or "".join(c for c in systeme.lower() if c.isalnum())[:3] or "pc"


def _cle_identite(hote: Optional[str], dossier: Optional[str]) -> str:
    return f"{hote}|{os.path.normcase(os.path.abspath(dossier or '.'))}"


def _memo(table: str, cle: str) -> Optional[str]:
    valeurs = lire_config().get(table)
    valeur = valeurs.get(cle) if isinstance(valeurs, dict) else None
    return valeur if isinstance(valeur, str) and valeur else None


def _memoriser(table: str, cle: str, valeur: str) -> str:
    conf = lire_config()
    valeurs = conf.get(table)
    if not isinstance(valeurs, dict):
        valeurs = {}
    valeurs[cle] = valeur
    conf[table] = valeurs
    _ecrire_config(conf)
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


def attacher_projet(dossier: str, projet: Optional[str]) -> str:
    """Écrit le `.messenger.json` du dépôt : ses agents appartiennent désormais à `projet`.

    Sans projet (`null`), le dépôt est déclaré quand même : ses agents y sont invités à s'enrôler,
    sous un compte commun à tous les projets.
    """
    chemin = os.path.join(os.path.abspath(dossier), FICHIER_PROJET)
    with open(chemin, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"project": projet}, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return chemin


# --------------------------------------------------------------------------- #
# Les gestes du poste : choisir un dossier, connecter un dépôt à la boîte
# --------------------------------------------------------------------------- #
class ActivationRefusee(Exception):
    """Une connexion impossible : dossier absent, ou configuration d'un hôte illisible."""


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


def activer_depot(dossier: str, projet: Optional[str], depot: str, box: Optional[str] = None,
                  releve: bool = True) -> Dict[str, Any]:
    """Connecte un dépôt à la boîte, quel que soit l'hôte des agents qui y travailleront.

    Deux gestes : **déclarer** le dépôt (`.messenger.json` — c'est lui qui déclenche l'invitation
    à s'enrôler), et **équiper les hôtes IA du poste** (serveur MCP et relève, voir `hotes.py`).
    Rien d'autre n'est écrit dans le dépôt. `depot` est la racine d'arkalabs-messenger.
    Lève `ActivationRefusee` si le dossier n'existe pas ou si un hôte a une configuration illisible.
    """
    dossier = os.path.abspath(os.path.expanduser(dossier))
    if not os.path.isdir(dossier):
        raise ActivationRefusee(f"dossier introuvable : {dossier}")
    if box:
        memoriser_boite(box)
    if projet:
        attacher_projet(dossier, projet)
    elif not trouver_fichier_projet(dossier):
        attacher_projet(dossier, None)
    hotes.retirer_releve_du_depot(dossier)  # l'ancienne pose par dépôt : sinon on relèverait deux fois
    try:
        equipes = hotes.equiper_presents(hotes.contexte(depot), releve=releve)
    except hotes.EquipementRefuse as e:
        raise ActivationRefusee(str(e)) from None
    return {"dossier": dossier, "projet": resoudre_projet(None, dossier), "boite": box,
            "hotes": equipes}
