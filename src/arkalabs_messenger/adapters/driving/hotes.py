"""Équiper les hôtes IA de ce poste : le serveur MCP de la boîte, et la relève.

Un **hôte** est l'outil dans lequel tourne un agent : Claude Code, Codex, Kimi Code,
Antigravity, Cursor. Pour chacun, on pose deux choses dans **sa propre** configuration,
par machine (pas par dépôt) :

- le **serveur MCP** `arkalabs-messenger` (transport stdio : l'hôte lance
  `messenger.py mcp` quand l'agent travaille) — pour agir sur la boîte par des outils ;
- la **relève** — les hooks qui lancent `messenger.py check --hook` — là où l'hôte a un
  mécanisme de hooks dont la sortie entre dans le contexte (Claude Code, Codex, Kimi Code).

Règles de pose, les mêmes pour tous :

- **fusionner, jamais écraser** : on ne touche qu'à notre entrée, le reste du fichier est conservé ;
- **idempotent** : une entrée déjà conforme n'est pas réécrite ;
- **divergence détectée** : une entrée périmée (chemin ou interpréteur changés) est réparée ;
- **une autre installation est respectée** : une entrée qui pointe vers un autre
  `messenger.py` existant est laissée en place, sauf demande explicite (`forcer`) ;
- **un fichier illisible n'est jamais réécrit** : on le dit, l'humain tranche ;
- **écriture atomique** : à côté, puis remplacement.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

CLE = "arkalabs-messenger"
"""Le nom du serveur MCP, et de la skill, dans la configuration des hôtes."""

ABSENT = "absent"
VERIFIE = "vérifié"
DIVERGENT = "divergent"
AILLEURS = "ailleurs"
ILLISIBLE = "illisible"
SANS_OBJET = "sans objet"

EVENEMENTS: Tuple[str, ...] = ("SessionStart", "UserPromptSubmit")
"""Les deux moments de la relève : au début d'une session, et à chaque message de l'humain."""

_DELAI_HOOK = 20


class EquipementRefuse(Exception):
    """L'hôte ne peut pas être équipé sans risque : son fichier de configuration est illisible."""


@dataclass(frozen=True)
class Hote:
    """Un hôte IA, et où vit sa configuration."""

    id: str
    nom: str
    dossier: str
    """Son dossier, sous le dossier personnel."""
    variable: Optional[str]
    """La variable d'environnement qui déplace ce dossier, s'il y en a une."""
    mcp: str
    """Le fichier où il lit ses serveurs MCP, relatif à son dossier."""
    format_mcp: str
    """`json` (clé `mcpServers`) ou `toml` (tables `[mcp_servers.<nom>]`)."""
    type_stdio: bool = False
    """L'entrée doit-elle dire `"type": "stdio"` ?"""
    releve: Optional[str] = None
    """Son mécanisme de hooks : `json` (Claude Code, Codex), `toml` (Kimi Code), ou None."""
    hooks: Optional[str] = None
    """Le fichier de ses hooks, relatif à son dossier."""
    skills: Optional[str] = None
    """Le dossier où il charge ses skills, relatif à son dossier."""
    presence: Optional[str] = None
    """Ce qui prouve que l'hôte est installé, relatif à son dossier (défaut : le dossier lui-même)."""


HOTES: Tuple[Hote, ...] = (
    Hote("claude-code", "Claude Code", ".claude", "CLAUDE_CONFIG_DIR", mcp="../.claude.json", format_mcp="json",
         type_stdio=True, releve="json", hooks="settings.json", skills="skills"),
    Hote("codex", "Codex", ".codex", "CODEX_HOME", mcp="config.toml", format_mcp="toml",
         releve="json", hooks="hooks.json"),
    Hote("kimi-code", "Kimi Code", ".kimi-code", "KIMI_CODE_HOME", mcp="mcp.json", format_mcp="json",
         releve="toml", hooks="config.toml"),
    Hote("antigravity", "Antigravity", ".gemini", None, mcp="config/mcp_config.json", format_mcp="json",
         presence="config"),
    Hote("cursor", "Cursor", ".cursor", None, mcp="mcp.json", format_mcp="json"),
)


def hote(identifiant: str) -> Hote:
    for h in HOTES:
        if h.id == identifiant:
            return h
    raise EquipementRefuse(f"hôte inconnu « {identifiant} » : {', '.join(h.id for h in HOTES)}")


@dataclass(frozen=True)
class Contexte:
    """Le poste sur lequel on pose : où est l'outil, où est le dossier personnel."""

    depot: str
    """La racine d'arkalabs-messenger : là où vivent `messenger.py` et `skills/`."""
    home: str = field(default_factory=lambda: os.path.expanduser("~"))
    env: Mapping[str, str] = field(default_factory=lambda: os.environ)
    python: str = field(default_factory=lambda: sys.executable)

    def dossier(self, h: Hote) -> str:
        deplace = self.env.get(h.variable) if h.variable else None
        return os.path.abspath(deplace) if deplace else os.path.join(self.home, h.dossier)

    def fichier_mcp(self, h: Hote) -> str:
        dossier = self.dossier(h)
        # Claude Code range `.claude.json` à côté de `~/.claude`, mais dedans si le dossier est déplacé.
        if h.mcp.startswith("../"):
            deplace = bool(h.variable and self.env.get(h.variable))
            return os.path.join(dossier if deplace else os.path.dirname(dossier), h.mcp[3:])
        return os.path.join(dossier, *h.mcp.split("/"))

    def fichier_hooks(self, h: Hote) -> Optional[str]:
        return os.path.join(self.dossier(h), h.hooks) if h.hooks else None

    def dossier_skill(self, h: Hote) -> Optional[str]:
        return os.path.join(self.dossier(h), h.skills, CLE) if h.skills else None

    def present(self, h: Hote) -> bool:
        dossier = self.dossier(h)
        return os.path.isdir(os.path.join(dossier, h.presence) if h.presence else dossier)

    # -- Ce qu'on pose ----------------------------------------------------------
    @property
    def messenger(self) -> str:
        return _portable(os.path.join(self.depot, "messenger.py"))

    def entree_mcp(self, h: Hote) -> Dict[str, Any]:
        entree: Dict[str, Any] = {"type": "stdio"} if h.type_stdio else {}
        entree.update({"command": _portable(self.python), "args": [self.messenger, "mcp", "--host", h.id], "env": {}})
        return entree

    def commande_releve(self, h: Hote, evenement: str) -> str:
        return f'"{_portable(self.python)}" "{self.messenger}" check --hook --host {h.id} --event {evenement}'


def contexte(depot: str) -> Contexte:
    """Le contexte du poste réel. Le seul point d'entrée des appelants : les tests le remplacent
    pour ne jamais écrire dans la vraie configuration des hôtes."""
    return Contexte(depot)


@dataclass(frozen=True)
class EtatHote:
    """Où en est un hôte : présent ? serveur MCP, relève et skill posés ?"""

    id: str
    nom: str
    present: bool
    mcp: str
    releve: str
    skill: str
    fichiers: Tuple[str, ...] = ()
    """Les fichiers de configuration concernés, pour que l'humain sache où regarder."""
    note: Optional[str] = None

    @property
    def equipe(self) -> bool:
        return self.mcp == VERIFIE and self.releve in (VERIFIE, SANS_OBJET) and self.skill in (VERIFIE, SANS_OBJET)

    def vers_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["fichiers"] = list(self.fichiers)
        d["equipe"] = self.equipe
        return d


# --------------------------------------------------------------------------- #
# Lire l'état, équiper, retirer
# --------------------------------------------------------------------------- #
def presents(ctx: Contexte) -> List[Hote]:
    return [h for h in HOTES if ctx.present(h)]


def etat(h: Hote, ctx: Contexte) -> EtatHote:
    fichiers = tuple(f for f in (ctx.fichier_mcp(h), ctx.fichier_hooks(h)) if f)
    if not ctx.present(h):
        return EtatHote(h.id, h.nom, False, ABSENT, ABSENT if h.releve else SANS_OBJET,
                        ABSENT if h.skills else SANS_OBJET, fichiers, "hôte non installé sur ce poste")
    return EtatHote(h.id, h.nom, True, _etat_mcp(h, ctx), _etat_releve(h, ctx), _etat_skill(h, ctx), fichiers)


def etats(ctx: Contexte) -> List[EtatHote]:
    return [etat(h, ctx) for h in HOTES]


def equiper(h: Hote, ctx: Contexte, releve: bool = True, forcer: bool = False) -> EtatHote:
    """Pose le serveur MCP, la relève et la skill dans l'hôte. Rend l'état obtenu."""
    if not ctx.present(h):
        return etat(h, ctx)
    avant = etat(h, ctx)
    if ILLISIBLE in (avant.mcp, avant.releve):
        raise EquipementRefuse(
            f"{h.nom} : configuration illisible ({', '.join(avant.fichiers)}) — corrige-la à la main, "
            "je ne réécris pas un fichier que je ne sais pas lire")
    notes = []
    if avant.mcp in (ABSENT, DIVERGENT) or (avant.mcp == AILLEURS and forcer):
        _poser_mcp(h, ctx)
    elif avant.mcp == AILLEURS:
        notes.append("serveur MCP : une autre installation d'arkalabs-messenger est déjà déclarée (laissée en place)")
    if releve and h.releve:
        if avant.releve in (ABSENT, DIVERGENT) or (avant.releve == AILLEURS and forcer):
            _poser_releve(h, ctx)
        elif avant.releve == AILLEURS:
            notes.append("relève : une autre installation est déjà en place (laissée en place)")
    if h.skills and avant.skill in (ABSENT, DIVERGENT):
        _poser_skill(h, ctx)
    apres = etat(h, ctx)
    return EtatHote(apres.id, apres.nom, apres.present, apres.mcp, apres.releve, apres.skill, apres.fichiers,
                    " ; ".join(notes) or None)


def retirer(h: Hote, ctx: Contexte) -> EtatHote:
    """Retire ce qu'on a posé dans l'hôte — et rien d'autre. Idempotent."""
    if not ctx.present(h):
        return etat(h, ctx)
    avant = etat(h, ctx)
    if ILLISIBLE in (avant.mcp, avant.releve):
        raise EquipementRefuse(f"{h.nom} : configuration illisible ({', '.join(avant.fichiers)}) — rien retiré")
    if avant.mcp != ABSENT:
        _retirer_mcp(h, ctx)
    if h.releve and avant.releve != ABSENT:
        _retirer_releve(h, ctx)
    skill = ctx.dossier_skill(h)
    if skill and os.path.isdir(skill):
        shutil.rmtree(skill, ignore_errors=True)
    return etat(h, ctx)


def equiper_presents(ctx: Contexte, releve: bool = True, forcer: bool = False,
                     seulement: Optional[Sequence[str]] = None) -> List[EtatHote]:
    choisis = [hote(i) for i in seulement] if seulement else presents(ctx)
    return [equiper(h, ctx, releve, forcer) for h in choisis]


# --------------------------------------------------------------------------- #
# Le serveur MCP
# --------------------------------------------------------------------------- #
def _etat_mcp(h: Hote, ctx: Contexte) -> str:
    chemin = ctx.fichier_mcp(h)
    try:
        if h.format_mcp == "toml":
            texte = _lire_texte(chemin)
            if _toml_etranger(texte):
                return ILLISIBLE
            entree = _toml_lire_serveur(texte)
        else:
            serveurs = _lire_json(chemin).get("mcpServers")
            entree = serveurs.get(CLE) if isinstance(serveurs, dict) else None
    except _Illisible:
        return ILLISIBLE
    return _comparer(entree, ctx.entree_mcp(h))


def _comparer(entree: Any, attendu: Dict[str, Any]) -> str:
    if entree is None:
        return ABSENT
    if not isinstance(entree, dict):
        return DIVERGENT
    commande, args = entree.get("command"), entree.get("args")
    if (isinstance(commande, str) and isinstance(args, list) and args and all(isinstance(a, str) for a in args)
            and _meme_chemin(commande, attendu["command"]) and _meme_chemin(args[0], attendu["args"][0])
            and args[1:] == attendu["args"][1:] and entree.get("type") == attendu.get("type")):
        return VERIFIE
    autre = args[0] if isinstance(args, list) and args and isinstance(args[0], str) else None
    return AILLEURS if _autre_installation(autre, attendu["args"][0]) else DIVERGENT


def _poser_mcp(h: Hote, ctx: Contexte) -> None:
    chemin = ctx.fichier_mcp(h)
    if h.format_mcp == "toml":
        texte = _toml_sans_serveur(_lire_texte(chemin))
        entree = ctx.entree_mcp(h)
        bloc = [f"[mcp_servers.{CLE}]", f"command = {_toml(entree['command'])}", f"args = {_toml(entree['args'])}"]
        _ecrire(chemin, _joindre(texte, bloc))
        return
    data = _lire_json(chemin)
    serveurs = data.get("mcpServers")
    if not isinstance(serveurs, dict):
        serveurs = data["mcpServers"] = {}
    serveurs[CLE] = ctx.entree_mcp(h)
    _ecrire_json(chemin, data)


def _retirer_mcp(h: Hote, ctx: Contexte) -> None:
    chemin = ctx.fichier_mcp(h)
    if h.format_mcp == "toml":
        _ecrire(chemin, _toml_sans_serveur(_lire_texte(chemin)))
        return
    data = _lire_json(chemin)
    serveurs = data.get("mcpServers")
    if isinstance(serveurs, dict) and CLE in serveurs:
        del serveurs[CLE]
        _ecrire_json(chemin, data)


# --------------------------------------------------------------------------- #
# La relève
# --------------------------------------------------------------------------- #
def _etat_releve(h: Hote, ctx: Contexte) -> str:
    if not h.releve:
        return SANS_OBJET
    attendues = [ctx.commande_releve(h, e) for e in EVENEMENTS]
    try:
        trouvees = _releve_lire(h, ctx)
    except _Illisible:
        return ILLISIBLE
    if not trouvees:
        return ABSENT
    if sorted(trouvees) == sorted(zip(EVENEMENTS, attendues)):
        return VERIFIE
    for _, commande in trouvees:
        if _autre_installation(_messenger_dans(commande), ctx.messenger):
            return AILLEURS
    return DIVERGENT


def _releve_lire(h: Hote, ctx: Contexte) -> List[Tuple[str, str]]:
    """Nos hooks dans l'hôte : (événement, commande)."""
    chemin = ctx.fichier_hooks(h)
    assert chemin is not None
    if h.releve == "toml":
        return [(bloc.get("event", ""), bloc.get("command", ""))
                for bloc in _toml_blocs_hooks(_lire_texte(chemin))[0]]
    trouvees = []
    hooks = _lire_json(chemin).get("hooks")
    for evenement, groupes in (hooks.items() if isinstance(hooks, dict) else ()):
        for groupe in groupes if isinstance(groupes, list) else ():
            for crochet in (groupe.get("hooks") or []) if isinstance(groupe, dict) else ():
                if _est_notre_crochet(crochet):
                    trouvees.append((evenement, _commande_de(crochet)))
    return trouvees


def _poser_releve(h: Hote, ctx: Contexte) -> None:
    chemin = ctx.fichier_hooks(h)
    assert chemin is not None
    if h.releve == "toml":
        texte = _toml_blocs_hooks(_lire_texte(chemin))[1]
        for evenement in EVENEMENTS:
            # Kimi Code n'admet que quatre champs par règle : event, matcher, command, timeout.
            texte = _joindre(texte, ["[[hooks]]", f"event = {_toml(evenement)}",
                                     f"command = {_toml(ctx.commande_releve(h, evenement))}",
                                     f"timeout = {_DELAI_HOOK}"])
        _ecrire(chemin, texte)
        return
    data = _json_sans_releve(_lire_json(chemin))
    hooks = data.setdefault("hooks", {})
    for evenement in EVENEMENTS:
        crochet: Dict[str, Any] = {"type": "command", "command": ctx.commande_releve(h, evenement),
                                   "timeout": _DELAI_HOOK}
        if evenement == "SessionStart":
            crochet["statusMessage"] = "Relève du courrier"
        hooks.setdefault(evenement, []).append({"hooks": [crochet]})
    _ecrire_json(chemin, data)


def _retirer_releve(h: Hote, ctx: Contexte) -> None:
    chemin = ctx.fichier_hooks(h)
    assert chemin is not None
    if h.releve == "toml":
        _ecrire(chemin, _toml_blocs_hooks(_lire_texte(chemin))[1])
    else:
        _ecrire_json(chemin, _json_sans_releve(_lire_json(chemin)))


def retirer_releve_du_depot(dossier: str) -> bool:
    """Retire l'ancienne relève posée par dépôt (`.claude/settings.local.json`), remplacée par la pose par machine.

    Sans ce nettoyage, un dépôt activé avec une ancienne version relèverait deux fois.
    """
    chemin = os.path.join(dossier, ".claude", "settings.local.json")
    if not os.path.isfile(chemin):
        return False
    try:
        data = _lire_json(chemin)
    except _Illisible:
        return False
    avant = json.dumps(data, sort_keys=True)
    data = _json_sans_releve(data)
    if json.dumps(data, sort_keys=True) == avant:
        return False
    _ecrire_json(chemin, data)
    return True


def _json_sans_releve(data: Dict[str, Any]) -> Dict[str, Any]:
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return data
    for evenement in list(hooks):
        groupes = hooks[evenement]
        if not isinstance(groupes, list):
            continue
        gardes = []
        for groupe in groupes:
            crochets = groupe.get("hooks") if isinstance(groupe, dict) else None
            if not isinstance(crochets, list):
                gardes.append(groupe)
                continue
            restants = [c for c in crochets if not _est_notre_crochet(c)]
            if restants:
                gardes.append({**groupe, "hooks": restants})
        if gardes:
            hooks[evenement] = gardes
        else:
            del hooks[evenement]
    if not hooks:
        del data["hooks"]
    return data


def _est_notre_crochet(crochet: Any) -> bool:
    commande = _commande_de(crochet)
    return "messenger.py" in commande and "--hook" in commande


def _commande_de(crochet: Any) -> str:
    """La commande d'un hook, sous sa forme texte ou sous l'ancienne forme `command` + `args`."""
    if not isinstance(crochet, dict):
        return ""
    commande = crochet.get("command") if isinstance(crochet.get("command"), str) else ""
    args = crochet.get("args")
    if isinstance(args, list):
        commande = " ".join([commande, *(a for a in args if isinstance(a, str))])
    return commande


# --------------------------------------------------------------------------- #
# La skill
# --------------------------------------------------------------------------- #
def _etat_skill(h: Hote, ctx: Contexte) -> str:
    cible = ctx.dossier_skill(h)
    if not cible:
        return SANS_OBJET
    source = os.path.join(ctx.depot, "skills", CLE, "SKILL.md")
    pose = os.path.join(cible, "SKILL.md")
    if not os.path.isfile(pose):
        return ABSENT
    try:
        with open(source, "rb") as a, open(pose, "rb") as b:
            return VERIFIE if a.read() == b.read() else DIVERGENT
    except OSError:
        return DIVERGENT


def _poser_skill(h: Hote, ctx: Contexte) -> None:
    cible = ctx.dossier_skill(h)
    source = os.path.join(ctx.depot, "skills", CLE)
    if cible and os.path.isdir(source):
        shutil.copytree(source, cible, dirs_exist_ok=True)


# --------------------------------------------------------------------------- #
# TOML, édité comme du texte : on ne touche qu'à nos blocs, le reste est conservé tel quel
# --------------------------------------------------------------------------- #
_TABLE = re.compile(r"^\s*\[")
_NOTRE_TABLE = re.compile(r"""^\s*\[\s*mcp_servers\s*\.\s*(?:"%s"|'%s'|%s)\s*(?:\.[^\]]*)?\]\s*(?:#.*)?$"""
                          % (re.escape(CLE), re.escape(CLE), re.escape(CLE)))
_TABLE_PRINCIPALE = re.compile(r"""^\s*\[\s*mcp_servers\s*\.\s*(?:"%s"|'%s'|%s)\s*\]"""
                               % (re.escape(CLE), re.escape(CLE), re.escape(CLE)))
_REGLE_HOOK = re.compile(r"^\s*\[\[\s*hooks\s*\]\]\s*(?:#.*)?$")
_AFFECTATION = re.compile(r"^\s*([A-Za-z0-9_-]+)\s*=\s*(.+?)\s*$")


def _toml_lire_serveur(texte: str) -> Optional[Dict[str, Any]]:
    entree: Optional[Dict[str, Any]] = None
    dans = False
    for ligne in texte.splitlines():
        if _TABLE.match(ligne):
            dans = bool(_TABLE_PRINCIPALE.match(ligne))
            if dans and entree is None:
                entree = {}
            continue
        if dans and entree is not None:
            affectation = _AFFECTATION.match(ligne)
            if affectation:
                entree[affectation.group(1)] = _toml_valeur(affectation.group(2))
    return entree


def _toml_sans_serveur(texte: str) -> str:
    gardees, dans = [], False
    for ligne in texte.splitlines():
        if _TABLE.match(ligne):
            dans = bool(_NOTRE_TABLE.match(ligne))
        if not dans:
            gardees.append(ligne)
    return _terminer(gardees)


def _toml_etranger(texte: str) -> bool:
    """Notre serveur est-il déclaré sous une forme qu'on ne sait pas éditer (clé pointée, table en ligne) ?"""
    for ligne in _toml_sans_serveur(texte).splitlines():
        code = ligne.split("#", 1)[0]
        if CLE in code and "mcp_servers" in code:
            return True
    return False


def _toml_blocs_hooks(texte: str) -> Tuple[List[Dict[str, Any]], str]:
    """Nos règles `[[hooks]]`, et le texte sans elles."""
    blocs: List[List[str]] = [[]]
    for ligne in texte.splitlines():
        if _TABLE.match(ligne):
            blocs.append([])
        blocs[-1].append(ligne)
    notres, gardees = [], []
    for bloc in blocs:
        regle = {m.group(1): _toml_valeur(m.group(2)) for m in map(_AFFECTATION.match, bloc[1:]) if m}
        commande = regle.get("command")
        if (bloc and _REGLE_HOOK.match(bloc[0]) and isinstance(commande, str)
                and "messenger.py" in commande and "--hook" in commande):
            notres.append(regle)
        else:
            gardees.extend(bloc)
    return notres, _terminer(gardees)


def _toml_valeur(brut: str) -> Any:
    brut = brut.strip()
    if brut.startswith("'") and brut.endswith("'") and len(brut) >= 2:
        return brut[1:-1]
    try:
        return json.loads(brut)
    except ValueError:
        return brut.split("#", 1)[0].strip()


def _toml(valeur: Any) -> str:
    """Une chaîne ou une liste de chaînes, en TOML : les chaînes JSON sont des chaînes TOML valides."""
    if isinstance(valeur, list):
        return "[" + ", ".join(_toml(v) for v in valeur) + "]"
    return json.dumps(valeur, ensure_ascii=False)


def _joindre(texte: str, bloc: List[str]) -> str:
    corps = texte.rstrip("\n")
    return (corps + "\n\n" if corps else "") + "\n".join(bloc) + "\n"


def _terminer(lignes: List[str]) -> str:
    while lignes and not lignes[-1].strip():
        lignes.pop()
    return "\n".join(lignes) + "\n" if lignes else ""


# --------------------------------------------------------------------------- #
# Fichiers
# --------------------------------------------------------------------------- #
class _Illisible(Exception):
    pass


def _lire_texte(chemin: str) -> str:
    try:
        with open(chemin, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""
    except (OSError, UnicodeDecodeError):
        raise _Illisible(chemin) from None


def _lire_json(chemin: str) -> Dict[str, Any]:
    texte = _lire_texte(chemin)
    if not texte.strip():  # un fichier absent ou vide : aucune entrée, pas une erreur
        return {}
    try:
        data = json.loads(texte)
    except ValueError:
        raise _Illisible(chemin) from None
    if not isinstance(data, dict):
        raise _Illisible(chemin)
    return data


def _ecrire_json(chemin: str, data: Dict[str, Any]) -> None:
    _ecrire(chemin, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def _ecrire(chemin: str, texte: str) -> None:
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    tmp = f"{chemin}.{CLE}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(texte)
    os.replace(tmp, chemin)


def _portable(chemin: str) -> str:
    """Des barres obliques partout : lisible par cmd, PowerShell et bash, sans échappement."""
    return os.path.abspath(chemin).replace("\\", "/")


def _meme_chemin(a: str, b: str) -> bool:
    return os.path.normcase(os.path.normpath(a)) == os.path.normcase(os.path.normpath(b))


def _messenger_dans(commande: str) -> Optional[str]:
    trouve = re.search(r'"([^"]*messenger\.py)"|(\S*messenger\.py)', commande)
    return (trouve.group(1) or trouve.group(2)) if trouve else None


def _autre_installation(chemin: Optional[str], le_notre: str) -> bool:
    """`chemin` désigne-t-il un autre `messenger.py`, qui existe vraiment ?"""
    return bool(chemin and os.path.basename(chemin) == "messenger.py"
                and not _meme_chemin(chemin, le_notre) and os.path.isfile(chemin))
