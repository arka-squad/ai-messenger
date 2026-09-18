"""Le modèle : une boîte de messages, un annuaire de comptes, et leurs règles.

Tout ici est pur : aucune lecture de fichier, aucune horloge. Les dates sont
fournies par l'appelant, déjà formatées en ISO 8601.

Une adresse est `nom` ou `nom@projet`, comme un courriel : la même IA a une
adresse par projet (`claude-windows@cortex`, `claude-windows@talos`), et un
compte sans projet (`owner`) est commun à tous.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .erreurs import (
    CompteExistant,
    CompteInconnu,
    MessageIntrouvable,
    MessageInvalide,
    NomInvalide,
    TransitionRefusee,
)

STATUTS: Tuple[str, ...] = ("nouveau", "lu", "traité")
"""Les statuts d'un message, dans l'ordre où ils avancent."""

CORPS_MAX = 2
"""Nombre maximal de lignes de corps : le détail va en pièce jointe."""

_NOM = r"[a-z0-9][a-z0-9_.-]{0,31}"
_RE_NOM = re.compile(rf"^{_NOM}$")
_RE_ADRESSE = re.compile(rf"^{_NOM}(@{_NOM})?$")


def valider_nom(nom: Optional[str], quoi: str = "nom") -> str:
    """Rend le nom s'il est valide : minuscules, chiffres, `.`, `_`, `-`, 32 au plus."""
    if not nom or not _RE_NOM.match(nom):
        raise NomInvalide(f"{quoi} invalide « {nom} » : minuscules, chiffres, . _ - (32 max)")
    return nom


def valider_adresse(adresse: Optional[str], quoi: str = "adresse") -> str:
    """Rend l'adresse si elle est valide : `nom`, ou `nom@projet`."""
    if not adresse or not _RE_ADRESSE.match(adresse):
        raise NomInvalide(f"{quoi} invalide « {adresse} » : nom ou nom@projet — minuscules, chiffres, . _ - "
                          "(32 max de chaque côté)")
    return adresse


def projet_de(adresse: str) -> Optional[str]:
    """Le projet d'une adresse, ou None pour un compte commun à tous les projets."""
    return adresse.partition("@")[2] or None


def qualifier(nom: str, projet: Optional[str]) -> str:
    """`nom` rattaché à `projet`, sauf s'il porte déjà son projet."""
    return nom if "@" in nom or not projet else f"{nom}@{projet}"


def _une_ligne(texte: str) -> str:
    return " ".join((texte or "").split())


# --------------------------------------------------------------------------- #
# Messages
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Transition:
    """Un changement de statut : qui l'a fait, quand, vers quoi."""

    date: str
    par: str
    statut: str


@dataclass(frozen=True)
class Message:
    """Un message envoyé. Immuable : seul son statut avance, par `avancer`."""

    id: str
    date: str
    de: str
    a: Tuple[str, ...]
    objet: str
    corps: Tuple[str, ...] = ()
    pj: Optional[str] = None
    re: Optional[str] = None
    statut: str = "nouveau"
    historique: Tuple[Transition, ...] = ()
    importe: bool = False
    autres: Dict[str, Any] = field(default_factory=dict, compare=False, hash=False)
    """Champs inconnus de cette version, conservés tels quels à la réécriture."""

    @property
    def titre(self) -> str:
        """L'objet tel qu'on l'affiche : préfixé de `Re : <id> — ` pour une réponse."""
        return (f"Re : {self.re} — " if self.re else "") + self.objet

    def est_pour(self, compte: str) -> bool:
        return compte in self.a

    def concerne(self, compte: str) -> bool:
        return compte == self.de or compte in self.a

    def touche_le_projet(self, projet: str) -> bool:
        """Écrit ou reçu par un compte du projet : la discussion entre projets en fait partie."""
        return any(projet_de(x) == projet for x in (self.de, *self.a))

    def suite_pour(self, compte: str) -> Optional[str]:
        """Le statut que `compte` peut donner à ce message, ou None s'il ne peut rien."""
        if not self.est_pour(compte) or self.statut not in STATUTS[:-1]:
            return None
        return STATUTS[STATUTS.index(self.statut) + 1]

    def avancer(self, par: str, statut: str, date: str) -> "Message":
        """Fait avancer le statut. Seul un destinataire le peut, et jamais en arrière."""
        if statut not in STATUTS[1:]:
            raise TransitionRefusee(f"statut inconnu « {statut} » : lu ou traité")
        if not self.est_pour(par):
            raise TransitionRefusee(
                f"{par} n'est pas destinataire de {self.id} : seul un destinataire fait avancer le statut")
        actuel = STATUTS.index(self.statut) if self.statut in STATUTS else -1
        if STATUTS.index(statut) <= actuel:
            raise TransitionRefusee(f"{self.id} est déjà « {self.statut} » : un statut ne recule pas")
        return replace(self, statut=statut, historique=self.historique + (Transition(date, par, statut),))


@dataclass(frozen=True)
class Brouillon:
    """Un message validé, pas encore envoyé : il n'a ni identifiant ni date."""

    de: str
    a: Tuple[str, ...]
    objet: str
    corps: Tuple[str, ...]
    re: Optional[str] = None

    @classmethod
    def rediger(cls, de: str, a: Iterable[str], objet: str, corps: Iterable[str] = (),
                re: Optional[str] = None) -> "Brouillon":
        valider_adresse(de, "expéditeur")
        destinataires = tuple(dict.fromkeys(d.strip() for d in a if d and d.strip()))
        if not destinataires:
            raise MessageInvalide("aucun destinataire")
        for d in destinataires:
            valider_adresse(d, "destinataire")
        objet = _une_ligne(objet)
        if not objet:
            raise MessageInvalide("objet vide")
        lignes = tuple(l.rstrip() for l in corps if l and l.strip())
        if len(lignes) > CORPS_MAX:
            raise MessageInvalide("corps de plus de deux lignes : mets le détail dans une pièce jointe (--attach)")
        return cls(de, destinataires, objet, lignes, re or None)

    def emettre(self, id: str, date: str, pj: Optional[str] = None) -> Message:
        return Message(id=id, date=date, de=self.de, a=self.a, objet=self.objet,
                       corps=self.corps, pj=pj, re=self.re)


@dataclass
class Boite:
    """L'agrégat des messages, dans l'ordre d'envoi (le plus ancien en premier)."""

    messages: List[Message] = field(default_factory=list)
    autres: Dict[str, Any] = field(default_factory=dict)

    def message(self, mid: str) -> Message:
        for m in self.messages:
            if m.id == mid:
                return m
        raise MessageIntrouvable(f"message introuvable : {mid}")

    def recents(self) -> List[Message]:
        """Du plus récent au plus ancien."""
        return list(reversed(self.messages))

    def nouveaux_pour(self, compte: str) -> List[Message]:
        return [m for m in self.messages if m.est_pour(compte) and m.statut == "nouveau"]

    def identifiant_libre(self, de: str, instant: datetime) -> str:
        """`AAAAMMJJ-HHMM-<émetteur>`, suffixé `-2`, `-3`… s'il est déjà pris."""
        base = f"{instant.strftime('%Y%m%d-%H%M')}-{de}"
        pris = {m.id for m in self.messages}
        mid, n = base, 2
        while mid in pris:
            mid, n = f"{base}-{n}", n + 1
        return mid

    def controler(self, reponse_a: Optional[str] = None, nouvel_id: Optional[str] = None) -> None:
        """Refuse une réponse à un message absent, ou un identifiant déjà pris."""
        if reponse_a and not any(m.id == reponse_a for m in self.messages):
            raise MessageIntrouvable(f"le message auquel tu réponds est introuvable : {reponse_a}")
        if nouvel_id and any(m.id == nouvel_id for m in self.messages):
            raise MessageInvalide(f"identifiant déjà pris : {nouvel_id}")

    def ajouter(self, message: Message) -> None:
        self.controler(message.re, message.id)
        self.messages.append(message)

    def marquer(self, mid: str, par: str, statut: str, date: str) -> Message:
        for i, m in enumerate(self.messages):
            if m.id == mid:
                self.messages[i] = m.avancer(par, statut, date)
                return self.messages[i]
        raise MessageIntrouvable(f"message introuvable : {mid}")

    def participants(self) -> List[str]:
        """Les noms vus dans la boîte, dans l'ordre de première apparition."""
        vus: Dict[str, None] = {}
        for m in self.messages:
            vus.setdefault(m.de)
            for d in m.a:
                vus.setdefault(d)
        return list(vus)


# --------------------------------------------------------------------------- #
# Comptes
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Compte:
    """Le compte d'un agent : son adresse, son outil, son rôle."""

    nom: str
    hote: str
    role: str
    machine: Optional[str] = None
    modele: Optional[str] = None
    humain: Optional[str] = None
    releve: Optional[str] = None
    cree: Optional[str] = None
    actif: bool = True
    autres: Dict[str, Any] = field(default_factory=dict, compare=False, hash=False)

    @property
    def projet(self) -> Optional[str]:
        return projet_de(self.nom)

    @classmethod
    def ouvrir(cls, nom: str, hote: str, role: str, **infos: Optional[str]) -> "Compte":
        valider_adresse(nom)
        role = _une_ligne(role)
        if not role:
            raise MessageInvalide("rôle vide : dis en une ligne ce que fait cet agent")
        hote = _une_ligne(hote)
        if not hote:
            raise MessageInvalide("hôte vide : claude-code, kimi-code, codex, hermes, humain…")
        return cls(nom=nom, hote=hote, role=role, **infos)


@dataclass
class Annuaire:
    """L'agrégat des comptes. Un compte n'est jamais supprimé : il est désactivé."""

    comptes: List[Compte] = field(default_factory=list)
    autres: Dict[str, Any] = field(default_factory=dict)

    def compte(self, nom: str) -> Optional[Compte]:
        return next((c for c in self.comptes if c.nom == nom), None)

    def actifs(self) -> List[str]:
        return sorted(c.nom for c in self.comptes if c.actif)

    def projets(self) -> List[str]:
        return sorted({c.projet for c in self.comptes if c.projet})

    def resoudre(self, nom: str, projet: Optional[str]) -> str:
        """L'adresse désignée par `nom` depuis `projet`.

        `nom@projet` est pris tel quel. Un nom court désigne d'abord le compte du
        même projet, puis le compte commun du même nom (`owner`). S'il n'existe ni
        l'un ni l'autre, il est rattaché au projet : la vérification dira qu'il manque.
        """
        valider_adresse(nom)
        if "@" in nom or not projet:
            return nom
        local = qualifier(nom, projet)
        if self.compte(local) is None and self.compte(nom) is not None:
            return nom
        return local

    def inscrire(self, compte: Compte, mise_a_jour: bool = False) -> bool:
        """Ajoute le compte, ou met à jour le sien. Rend True s'il est créé."""
        existant = self.compte(compte.nom)
        if existant is None:
            self.comptes.append(compte)
            return True
        if not mise_a_jour:
            raise CompteExistant(
                f"le compte « {existant.nom} » existe déjà ({existant.hote}, {existant.machine}, "
                f"« {existant.role} ») : choisis un autre nom, ou --update si c'est bien toi")
        fusion = replace(
            compte,
            machine=compte.machine or existant.machine,
            modele=compte.modele or existant.modele,
            humain=compte.humain or existant.humain,
            releve=compte.releve or existant.releve,
            cree=existant.cree or compte.cree,
            actif=True,
            autres=existant.autres,
        )
        self.comptes[self.comptes.index(existant)] = fusion
        return False

    def desactiver(self, nom: str) -> None:
        existant = self.compte(nom)
        if existant is None:
            raise CompteInconnu(f"compte introuvable : {nom}")
        self.comptes[self.comptes.index(existant)] = replace(existant, actif=False)

    def verifier(self, de: str, destinataires: Iterable[str]) -> None:
        """Refuse un expéditeur ou un destinataire sans compte actif."""
        actifs = self.actifs()
        if de not in actifs:
            raise CompteInconnu(
                f"« {de} » n'a pas de compte actif : `messenger.py register --agent {de} --host … --role …`")
        inconnus = [d for d in destinataires if d not in actifs]
        if inconnus:
            raise CompteInconnu(f"destinataire(s) sans compte actif : {', '.join(inconnus)} — "
                                f"comptes actifs : {', '.join(actifs)}")
