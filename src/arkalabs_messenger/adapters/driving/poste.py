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
import re
import subprocess
import threading
import time
from typing import Any, Dict, List, Optional

from . import hotes

CONFIG = os.path.join(os.path.expanduser("~"), ".arkalabs-messenger.json")
VEILLES = os.path.join(os.path.expanduser("~"), ".arkalabs-messenger.veilles")
"""Une petite trace par veille en cours (`watch`), rafraîchie en boucle : la relève de fin de tour
sait ainsi si la session est joignable, sans jamais interroger de processus."""

_VEILLE_FRAICHE = 30.0
"""Une trace plus vieille que ça est morte : la veille a été tuée sans pouvoir se retirer."""
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
    """Le dernier agent enrôlé par cet hôte dans ce dossier — ou dans le plus proche dossier qui le contient :
    un agent enrôlé à la racine de son dépôt est reconnu dans ses sous-dossiers."""
    if not hote or not dossier:
        return None
    courant = os.path.realpath(dossier)
    while True:
        agent = _memo("identites", _cle_identite(hote, courant))
        if agent:
            return agent
        parent = os.path.dirname(courant)
        if parent == courant:
            return None
        courant = parent


def _fichier_veille(session: str) -> str:
    propre = re.sub(r"[^A-Za-z0-9._-]", "_", session)[:80] or "sans-nom"
    return os.path.join(VEILLES, propre + ".json")


def armer_veille(session: str, agent: str) -> str:
    """Note qu'une veille couvre `session`. À rappeler en boucle : c'est la fraîcheur qui fait foi."""
    os.makedirs(VEILLES, exist_ok=True)
    chemin = _fichier_veille(session)
    with open(chemin, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"session": session, "agent": agent, "pid": os.getpid()}, f, ensure_ascii=False)
    return chemin


def desarmer_veille(session: str) -> None:
    try:
        os.remove(_fichier_veille(session))
    except OSError:
        pass
    _purger_veilles()


def veille_armee(session: Optional[str]) -> bool:
    """Une veille fraîche couvre-t-elle cette session ? Sans `session_id`, on ne sait pas : non."""
    if not session:
        return False
    try:
        return time.time() - os.path.getmtime(_fichier_veille(session)) < _VEILLE_FRAICHE
    except OSError:
        return False


def _purger_veilles() -> None:
    """Les traces d'avant-hier ne couvrent plus personne : on fait le ménage en passant."""
    try:
        for nom in os.listdir(VEILLES):
            chemin = os.path.join(VEILLES, nom)
            try:
                if time.time() - os.path.getmtime(chemin) > 48 * 3600:
                    os.remove(chemin)
            except OSError:
                pass
    except OSError:
        pass


def deja_annonce(session: Optional[str], adresses: List[str]) -> bool:
    """A-t-on déjà dit à cette session que du courrier attendait ces comptes ? Sans `session_id`, on ne sait pas."""
    if not session:
        return False
    vus = lire_config().get("annonces")
    connus = vus.get(session) if isinstance(vus, dict) else None
    return isinstance(connus, list) and set(adresses) <= set(connus)


def noter_annonce(session: str, adresses: List[str]) -> None:
    conf = lire_config()
    vus = conf.get("annonces") if isinstance(conf.get("annonces"), dict) else {}
    vus[session] = sorted(set(vus.get(session) or []) | set(adresses))
    conf["annonces"] = dict(list(vus.items())[-_MEMOIRE_MAX:])
    _ecrire_config(conf)


def oublier_annonce(session: Optional[str], adresse: str) -> None:
    """Rend une annonce à nouveau due pour cette session — quand ce qu'elle rappelait n'est plus vrai."""
    if not session:
        return
    conf = lire_config()
    vus = conf.get("annonces")
    if isinstance(vus, dict) and isinstance(vus.get(session), list) and adresse in vus[session]:
        vus[session] = [a for a in vus[session] if a != adresse]
        _ecrire_config(conf)


def memoriser_identite(hote: str, dossier: str, agent: str) -> str:
    """Retient qu'un agent de `hote` s'est enrôlé dans `dossier` : la relève le retrouvera."""
    return _memoriser("identites", _cle_identite(hote, dossier), agent)


def code_du_poste() -> str:
    """Le code du poste dans une identité lisible : `win`, `mac`, `lnx`, ou trois lettres du système."""
    systeme = platform.system()
    connu = {"Windows": "win", "Darwin": "mac", "Linux": "lnx"}.get(systeme)
    return connu or "".join(c for c in systeme.lower() if c.isalnum())[:3] or "pc"


def _cle_identite(hote: Optional[str], dossier: Optional[str]) -> str:
    # Le chemin réel : sous macOS, `/var/…` et `/private/var/…` sont le même dossier, et l'hôte n'annonce
    # pas forcément celui que `os.getcwd()` a rendu à l'enrôlement.
    return f"{hote}|{os.path.normcase(os.path.realpath(dossier or '.'))}"


def _memo(table: str, cle: str) -> Optional[str]:
    valeurs = lire_config().get(table)
    valeur = valeurs.get(cle) if isinstance(valeurs, dict) else None
    return valeur if isinstance(valeur, str) and valeur else None


_MEMOIRE_MAX = 300
"""Les sessions passent : on ne garde que les dernières, la config du poste ne grossit pas sans fin."""


def _memoriser(table: str, cle: str, valeur: str) -> str:
    conf = lire_config()
    valeurs = conf.get(table)
    if not isinstance(valeurs, dict):
        valeurs = {}
    valeurs.pop(cle, None)  # réinsérée en dernier : les plus anciennes partent d'abord
    valeurs[cle] = valeur
    conf[table] = dict(list(valeurs.items())[-_MEMOIRE_MAX:])
    _ecrire_config(conf)
    return CONFIG


def trouver_boite(chemin: str) -> Optional[str]:
    """La boîte que désigne `chemin`, s'il y en a une : un fichier `.json`/`.md`, un dossier à arbo
    `.aimessenger/`, ou un dossier qui contient un `boite.json` à plat. None s'il n'y a rien à ouvrir."""
    chemin = os.path.abspath(os.path.expanduser(chemin))
    if os.path.isfile(chemin):
        return chemin if os.path.splitext(chemin)[1].lower() in (".json", ".md") else None
    if not os.path.isdir(chemin):
        return None
    arbo = chemin if os.path.basename(chemin) == ".aimessenger" else os.path.join(chemin, ".aimessenger")
    if os.path.isfile(os.path.join(arbo, "mail", "boite.json")):
        return chemin
    plat = os.path.join(chemin, "boite.json")
    return plat if os.path.isfile(plat) else None


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
    """Le sélecteur de dossier natif ne peut pas servir : l'humain saisira le chemin à la main."""


_TITRE_SELECTEUR = "Choisir le dossier"
_DELAI_SELECTEUR = 600
"""Au-delà de dix minutes, la fenêtre est sans doute oubliée : on la ferme et on le dit."""

_selecteur_ouvert = threading.Lock()

# La fenêtre appartient à une fenêtre invisible « toujours au-dessus » : lancée par un serveur en
# arrière-plan, elle s'ouvrirait sinon derrière le navigateur, et l'interface semblerait figée.
# La sortie est en UTF-8 sans BOM : un chemin accentué arrive intact.
_SCRIPT_WINDOWS = "; ".join([
    "$ErrorActionPreference = 'Stop'",
    "[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false",
    "Add-Type -AssemblyName System.Windows.Forms",
    "Add-Type -AssemblyName System.Drawing",
    "$proprietaire = New-Object System.Windows.Forms.Form",
    "$proprietaire.TopMost = $true",
    "$proprietaire.ShowInTaskbar = $false",
    "$proprietaire.Opacity = 0",
    "$proprietaire.StartPosition = 'CenterScreen'",
    "$proprietaire.Size = New-Object System.Drawing.Size(1, 1)",
    "$proprietaire.Show()",
    "$proprietaire.Activate()",
    "$f = New-Object System.Windows.Forms.FolderBrowserDialog",
    f"$f.Description = '{_TITRE_SELECTEUR}'",
    "$f.ShowNewFolderButton = $true",
    "$r = $f.ShowDialog($proprietaire)",
    "$proprietaire.Close()",
    "if ($r -eq [System.Windows.Forms.DialogResult]::OK) { [Console]::Out.Write($f.SelectedPath) }",
])


def commandes_selecteur(systeme: str) -> List[List[str]]:
    """Les commandes à essayer, dans l'ordre, pour ouvrir le sélecteur natif de `systeme`."""
    if systeme == "Windows":
        return [["powershell", "-STA", "-NoProfile", "-NonInteractive", "-Command", _SCRIPT_WINDOWS]]
    if systeme == "Darwin":
        # `tell me to activate` : le panneau passe devant le navigateur au lieu de s'ouvrir derrière.
        return [["osascript", "-e", "tell me to activate",
                 "-e", f'POSIX path of (choose folder with prompt "{_TITRE_SELECTEUR}")']]
    return [["zenity", "--file-selection", "--directory", "--title", _TITRE_SELECTEUR],
            ["kdialog", "--title", _TITRE_SELECTEUR, "--getexistingdirectory", os.path.expanduser("~")]]


def lire_selecteur(systeme: str, code: int, sortie: bytes, erreurs: bytes) -> Optional[str]:
    """Le dossier choisi, ou None si l'humain a annulé. Lève `SelecteurIndisponible` si la fenêtre
    n'a pas pu s'ouvrir : une panne ne doit jamais passer pour une annulation."""
    chemin = sortie.decode("utf-8", "replace").lstrip("\ufeff").strip()
    if code == 0:
        return chemin or None
    detail = " ".join(erreurs.decode("utf-8", "replace").split())
    annule = (systeme == "Darwin" and "-128" in detail) or (systeme not in ("Windows", "Darwin") and code == 1)
    if annule:
        return None
    raise SelecteurIndisponible(
        f"the directory picker could not open (code {code}{': ' + detail[:200] if detail else ''}); "
        "enter the path manually")


def choisir_dossier() -> Optional[str]:
    """Ouvre le sélecteur de dossier natif de l'OS et rend le chemin choisi, ou None si annulé.

    L'app tourne sur la machine de l'humain : la fenêtre s'ouvre sur son bureau, au premier plan. Un
    sous-processus par OS (PowerShell / osascript / zenity, kdialog) évite toute dépendance et les soucis
    de thread. Une seule fenêtre à la fois : un second clic ne doit pas en empiler une autre.
    """
    if not _selecteur_ouvert.acquire(blocking=False):
        raise SelecteurIndisponible("a directory picker is already open; check behind the browser or enter the "
                                    "path manually")
    try:
        systeme = platform.system()
        manquants = []
        for commande in commandes_selecteur(systeme):
            try:
                resultat = subprocess.run(commande, capture_output=True, timeout=_DELAI_SELECTEUR,
                                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            except FileNotFoundError:
                manquants.append(commande[0])
                continue
            except subprocess.TimeoutExpired:
                raise SelecteurIndisponible("the directory picker remained open too long and was closed; open it "
                                            "again or enter the path manually") from None
            except (OSError, ValueError) as e:
                raise SelecteurIndisponible(f"the directory picker could not open ({e}); "
                                            "enter the path manually") from None
            return lire_selecteur(systeme, resultat.returncode, resultat.stdout, resultat.stderr)
        raise SelecteurIndisponible(f"no directory picker is available on this machine "
                                    f"({', '.join(manquants)} not found); enter the path manually")
    finally:
        _selecteur_ouvert.release()


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
        raise ActivationRefusee(f"directory not found: {dossier}")
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
