"""Le format d'échange JSON, tel que le décrit PROTOCOLE.md.

Utilisé pour écrire la boîte et l'annuaire, et pour les sorties `--json` et
l'API web. Les champs inconnus sont conservés : une version plus récente de
l'outil peut en ajouter sans qu'une plus ancienne les efface.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from ..domain import Annuaire, Boite, Compte, Contact, Message, ProjetDeclare, Transition

FORMAT = 1

_CHAMPS_MESSAGE = ("id", "date", "de", "a", "objet", "corps", "pj", "re", "statut", "historique", "importe")
_CHAMPS_COMPTE = ("nom", "hote", "modele", "machine", "role", "affichage", "humain", "releve", "cree", "actif")
_CHAMPS_CONTACT = ("alias", "adresses", "note", "cree")
_CHAMPS_PROJET = ("nom", "cree")


def en_json(data: Any) -> str:
    """Le texte JSON tel que l'outil l'écrit : UTF-8 lisible, indenté, fin de ligne finale."""
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


class FormatInvalide(ValueError):
    """Le document ne respecte pas le format attendu."""


# --------------------------------------------------------------------------- #
# Messages
# --------------------------------------------------------------------------- #
def message_vers_dict(m: Message) -> Dict[str, Any]:
    d: Dict[str, Any] = {
        "id": m.id,
        "date": m.date,
        "de": m.de,
        "a": list(m.a),
        "objet": m.objet,
        "corps": list(m.corps),
        "pj": m.pj,
        "re": m.re,
        "statut": m.statut,
        "historique": [{"date": t.date, "par": t.par, "statut": t.statut} for t in m.historique],
    }
    if m.importe:
        d["importe"] = True
    d.update((k, v) for k, v in m.autres.items() if k not in d)
    return d


def message_depuis_dict(d: Any) -> Message:
    if not isinstance(d, dict):
        raise FormatInvalide("un message n'est pas un objet")
    try:
        return Message(
            id=_texte(d, "id"),
            date=_texte(d, "date"),
            de=_texte(d, "de"),
            a=tuple(_liste_textes(d, "a")),
            objet=_texte(d, "objet"),
            corps=tuple(_liste_textes(d, "corps", facultatif=True)),
            pj=_texte_ou_nul(d, "pj"),
            re=_texte_ou_nul(d, "re"),
            statut=_texte(d, "statut"),
            historique=tuple(Transition(date=_texte(t, "date"), par=_texte(t, "par"), statut=_texte(t, "statut"))
                             for t in d.get("historique") or []),
            importe=bool(d.get("importe", False)),
            autres={k: v for k, v in d.items() if k not in _CHAMPS_MESSAGE},
        )
    except (TypeError, AttributeError) as e:
        raise FormatInvalide(f"message {d.get('id', '?')} mal formé : {e}") from None


def boite_vers_dict(b: Boite) -> Dict[str, Any]:
    d: Dict[str, Any] = {"version": FORMAT, "messages": [message_vers_dict(m) for m in b.messages]}
    d.update((k, v) for k, v in b.autres.items() if k not in d)
    return d


def boite_depuis_dict(d: Any) -> Boite:
    if not isinstance(d, dict) or not isinstance(d.get("messages"), list):
        raise FormatInvalide("clé « messages » absente")
    return Boite(messages=[message_depuis_dict(m) for m in d["messages"]],
                 autres={k: v for k, v in d.items() if k not in ("version", "messages")})


# --------------------------------------------------------------------------- #
# Comptes
# --------------------------------------------------------------------------- #
def contact_vers_dict(c: Contact) -> Dict[str, Any]:
    d: Dict[str, Any] = {"alias": c.alias, "adresses": list(c.adresses)}
    if c.note:
        d["note"] = c.note
    if c.cree:
        d["cree"] = c.cree
    d.update((k, v) for k, v in c.autres.items() if k not in d)
    return d


def contact_depuis_dict(d: Any) -> Contact:
    if not isinstance(d, dict):
        raise FormatInvalide("un contact n'est pas un objet")
    return Contact(alias=_texte(d, "alias"), adresses=tuple(_liste_textes(d, "adresses")),
                   note=_texte_ou_nul(d, "note"), cree=_texte_ou_nul(d, "cree"),
                   autres={k: v for k, v in d.items() if k not in _CHAMPS_CONTACT})


def compte_vers_dict(c: Compte) -> Dict[str, Any]:
    d = {k: getattr(c, k) for k in _CHAMPS_COMPTE}
    d = {k: v for k, v in d.items() if v is not None}
    if c.contacts:
        d["contacts"] = [contact_vers_dict(x) for x in c.contacts]
    if c.rattachement:
        d["projet"] = c.rattachement
    d.update((k, v) for k, v in c.autres.items() if k not in d)
    return d


def compte_depuis_dict(d: Any) -> Compte:
    if not isinstance(d, dict):
        raise FormatInvalide("un compte n'est pas un objet")
    return Compte(
        nom=_texte(d, "nom"),
        hote=d.get("hote") or "inconnu",
        role=d.get("role") or "",
        machine=d.get("machine"),
        modele=d.get("modele"),
        humain=d.get("humain"),
        releve=d.get("releve"),
        affichage=d.get("affichage"),
        cree=d.get("cree"),
        actif=bool(d.get("actif", True)),
        contacts=tuple(contact_depuis_dict(x) for x in _liste(d, "contacts")),
        # un rattachement n'a de sens que pour une adresse sans projet ; ailleurs, l'adresse fait foi
        rattachement=(_texte_ou_nul(d, "projet") if "@" not in str(d.get("nom", "")) else None),
        autres={k: v for k, v in d.items() if k not in _CHAMPS_COMPTE + ("contacts", "projet")},
    )


def annuaire_vers_dict(a: Annuaire, nom_boite: str) -> Dict[str, Any]:
    d: Dict[str, Any] = {"version": FORMAT, "boite": nom_boite, "comptes": [compte_vers_dict(c) for c in a.comptes]}
    if a.declares:
        d["projets"] = [{**{k: v for k, v in (("nom", p.nom), ("cree", p.cree)) if v is not None},
                         **{k: v for k, v in p.autres.items() if k not in _CHAMPS_PROJET}} for p in a.declares]
    d.update((k, v) for k, v in a.autres.items() if k not in d)
    return d


def annuaire_depuis_dict(d: Any) -> Annuaire:
    if not isinstance(d, dict) or not isinstance(d.get("comptes", []), list):
        raise FormatInvalide("clé « comptes » absente ou mal formée")
    return Annuaire(comptes=[compte_depuis_dict(c) for c in d.get("comptes", [])],
                    declares=[_projet_depuis_dict(p) for p in _liste(d, "projets")],
                    autres={k: v for k, v in d.items() if k not in ("version", "boite", "comptes", "projets")})


def _projet_depuis_dict(d: Any) -> ProjetDeclare:
    if not isinstance(d, dict):
        raise FormatInvalide("un projet n'est pas un objet")
    return ProjetDeclare(nom=_texte(d, "nom"), cree=_texte_ou_nul(d, "cree"),
                         autres={k: v for k, v in d.items() if k not in _CHAMPS_PROJET})


# --------------------------------------------------------------------------- #
def _texte(d: Dict[str, Any], cle: str) -> str:
    v = d[cle] if cle in d else None
    if not isinstance(v, str):
        raise FormatInvalide(f"champ « {cle} » absent ou non textuel")
    return v


def _texte_ou_nul(d: Dict[str, Any], cle: str) -> Optional[str]:
    v = d.get(cle)
    if v is not None and not isinstance(v, str):
        raise FormatInvalide(f"champ « {cle} » non textuel")
    return v or None


def _liste(d: Dict[str, Any], cle: str) -> List[Any]:
    """Une liste facultative : absente ou nulle, elle est vide."""
    v = d.get(cle)
    if v is None:
        return []
    if not isinstance(v, list):
        raise FormatInvalide(f"champ « {cle} » : liste attendue")
    return v


def _liste_textes(d: Dict[str, Any], cle: str, facultatif: bool = False) -> List[str]:
    v = d.get(cle, [] if facultatif else None)
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        raise FormatInvalide(f"champ « {cle} » : liste de textes attendue")
    return v
