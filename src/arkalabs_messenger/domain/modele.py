"""Le modèle : une boîte de messages, un annuaire de comptes, et leurs règles.

Tout ici est pur : aucune lecture de fichier, aucune horloge. Les dates sont
fournies par l'appelant, déjà formatées en ISO 8601.

Une adresse est `nom` ou `nom@projet`, comme un courriel : la même IA a une
adresse par projet (`claude-windows@cortex`, `claude-windows@talos`), et un
compte sans projet (`owner`) est commun à tous.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .erreurs import (
    CompteExistant,
    CompteInconnu,
    ContactRefuse,
    MessageIntrouvable,
    MessageInvalide,
    NomInvalide,
    TransitionRefusee,
)

STATUTS: Tuple[str, ...] = ("nouveau", "lu", "traité")
"""Les statuts d'un message, dans l'ordre où ils avancent."""

CORPS_MAX = 2
"""Nombre maximal de lignes de corps : le détail va en pièce jointe."""

CONTACTS_MAX = 200
"""Nombre maximal de contacts dans le carnet d'un compte."""

ADRESSES_PAR_CONTACT_MAX = 20
"""Un contact désigne une adresse, ou un petit groupe : pas une liste de diffusion sans fin."""

NOTE_MAX = 200
"""Longueur maximale de la note d'un contact : une ligne, qui dit quand lui écrire."""

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


def _sans_accents(texte: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texte) if not unicodedata.combining(c))


INITIALES_HOTE: Dict[str, str] = {
    "claude-code": "cl", "codex": "cd", "kimi-code": "km", "hermes": "he", "humain": "hu",
}
"""Initiales du fournisseur pour l'adresse et le nom lisible ; sinon, deux lettres de l'hôte."""


def initiales_hote(hote: str) -> str:
    """`cl` pour claude-code, `cd` pour codex, `km` pour kimi-code… sinon deux lettres de l'hôte."""
    h = _une_ligne(hote).lower()
    if h in INITIALES_HOTE:
        return INITIALES_HOTE[h]
    lettres = re.sub(r"[^a-z0-9]", "", _sans_accents(h))
    return lettres[:2] or "ag"


def slugifier(texte: str, maximum: int = 32) -> str:
    """Un identifiant sûr : minuscules, sans accent, séparateurs réduits à `-`, tronqué à `maximum`."""
    slug = re.sub(r"[^a-z0-9]+", "-", _sans_accents(texte or "").lower()).strip("-")
    return slug[:maximum].strip("-")


def composer_identite(hote: str, tache: str, poste: str) -> Tuple[str, str]:
    """Rend `(adresse, affichage)` d'un agent : `cl-agent-<tâche>-win` et `CL_Agent-<Tâche>_WIN`.

    L'adresse est un identifiant sûr (≤ 32 caractères, minuscules) ; l'affichage garde la
    casse choisie par l'agent, pour un humain. `hote` donne le fournisseur, `poste` la machine.
    """
    prov = initiales_hote(hote)
    poste_slug = slugifier(poste) or "poste"
    tache_nette = _une_ligne(tache)
    if not tache_nette:
        raise MessageInvalide("tâche vide : donne un intitulé court et durable (ex. « MessengerAI »)")
    reserve = len(f"{prov}-agent--{poste_slug}")
    tache_slug = slugifier(tache_nette, max(4, 32 - reserve)) or "agent"
    adresse = f"{prov}-agent-{tache_slug}-{poste_slug}"
    affichage = f"{prov.upper()}_Agent-{tache_nette}_{poste_slug.upper()}"
    return valider_nom(adresse), affichage


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
class Contact:
    """Une entrée du carnet d'adresses d'un compte : un alias court pour une adresse, ou pour un groupe.

    Le carnet est personnel : `release` peut désigner `mac, owner` pour un agent, et autre chose pour
    un autre. Un message envoyé à un alias est adressé aux **adresses réelles** : la boîte ne connaît
    que des adresses, jamais des alias.
    """

    alias: str
    adresses: Tuple[str, ...]
    note: Optional[str] = None
    cree: Optional[str] = None
    autres: Dict[str, Any] = field(default_factory=dict, compare=False, hash=False)

    @classmethod
    def composer(cls, alias: str, adresses: Iterable[str], note: Optional[str] = None,
                 cree: Optional[str] = None) -> "Contact":
        valider_nom(alias, "alias")
        uniques = tuple(dict.fromkeys(a.strip() for a in adresses if a and a.strip()))
        if not uniques:
            raise ContactRefuse(f"contact « {alias} » sans adresse : donne au moins un destinataire")
        if len(uniques) > ADRESSES_PAR_CONTACT_MAX:
            raise ContactRefuse(f"contact « {alias} » : {ADRESSES_PAR_CONTACT_MAX} adresses au plus")
        for a in uniques:
            valider_adresse(a, "adresse du contact")
        note = _une_ligne(note or "") or None
        if note and len(note) > NOTE_MAX:
            raise ContactRefuse(f"note trop longue ({len(note)} caractères) : {NOTE_MAX} au plus, en une ligne")
        return cls(alias, uniques, note, cree)


@dataclass(frozen=True)
class ProjetDeclare:
    """Un projet connecté à la boîte, connu avant même qu'un agent s'y enrôle."""

    nom: str
    cree: Optional[str] = None
    autres: Dict[str, Any] = field(default_factory=dict, compare=False, hash=False)


@dataclass(frozen=True)
class Compte:
    """Le compte d'un agent : son adresse, son outil, son rôle, son carnet d'adresses."""

    nom: str
    hote: str
    role: str
    machine: Optional[str] = None
    modele: Optional[str] = None
    humain: Optional[str] = None
    releve: Optional[str] = None
    affichage: Optional[str] = None
    """Nom lisible pour un humain (`CL_Agent-MessengerAI_WIN`) ; l'adresse `nom` reste l'identifiant."""
    cree: Optional[str] = None
    actif: bool = True
    contacts: Tuple[Contact, ...] = ()
    """Son carnet d'adresses."""
    rattachement: Optional[str] = None
    """Le projet auquel on a rattaché ce compte **commun** : son adresse n'en porte pas, et ne change pas."""
    autres: Dict[str, Any] = field(default_factory=dict, compare=False, hash=False)

    @property
    def projet(self) -> Optional[str]:
        """Le projet du compte : celui de son adresse (`nom@projet`), sinon celui auquel on l'a rattaché."""
        return projet_de(self.nom) or self.rattachement

    def contact(self, alias: str) -> Optional[Contact]:
        return next((c for c in self.contacts if c.alias == alias), None)

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
    declares: List[ProjetDeclare] = field(default_factory=list)
    """Les projets connectés à la boîte (`activate`, « Connecter un projet »)."""
    autres: Dict[str, Any] = field(default_factory=dict)

    def compte(self, nom: str) -> Optional[Compte]:
        return next((c for c in self.comptes if c.nom == nom), None)

    def actifs(self) -> List[str]:
        return sorted(c.nom for c in self.comptes if c.actif)

    def projets(self) -> List[str]:
        """Les projets connus : ceux qu'on a connectés, et ceux des comptes."""
        return sorted({p.nom for p in self.declares} | {c.projet for c in self.comptes if c.projet})

    def projet_de(self, adresse: str) -> Optional[str]:
        """Le projet d'une adresse : celui de son compte s'il existe (rattachement compris), sinon celui qu'elle porte."""
        compte = self.compte(adresse)
        return compte.projet if compte else projet_de(adresse)

    def rattacher(self, nom: str, projet: Optional[str], date: Optional[str] = None) -> Compte:
        """Range un compte **commun** dans un projet (ou l'en sort, avec None). Son adresse ne change pas :
        ses messages, son carnet et ce que les autres ont noté de lui restent valables."""
        compte = self.compte(nom)
        if compte is None:
            raise CompteInconnu(f"compte introuvable : {nom}")
        if projet_de(nom):
            raise MessageInvalide(f"« {nom} » porte déjà son projet dans son adresse : il ne se range pas ailleurs")
        if projet:
            self.declarer(projet, date)
        nouveau = replace(compte, rattachement=projet or None)
        self._remplacer(compte, nouveau)
        return nouveau

    def declarer(self, projet: str, date: Optional[str] = None) -> bool:
        """Note qu'un projet est connecté à la boîte. Rend True s'il ne l'était pas."""
        valider_nom(projet, "projet")
        if any(p.nom == projet for p in self.declares):
            return False
        self.declares.append(ProjetDeclare(projet, date))
        return True

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

    def nom_libre(self, adresse: str, projet: Optional[str], machine: Optional[str]) -> Tuple[str, Optional[Compte]]:
        """Le premier nom disponible pour un agent de `machine`, à partir d'`adresse`.

        Rend `(nom, compte)` : le compte s'il existe déjà **et vient de la même machine** — c'est le
        même agent qui revient, on le réutilise. Un homonyme d'une autre machine reçoit `-2`, `-3`…
        """
        n = 1
        while True:
            candidat = adresse if n == 1 else f"{adresse[:29]}-{n}"
            nom = qualifier(candidat, projet)
            existant = self.compte(nom)
            if existant is not None and (existant.machine or "") == (machine or ""):
                return nom, existant
            if existant is None:
                # Le même agent, enrôlé avant que son dépôt ait un projet : on le retrouve sous son adresse
                # commune plutôt que de lui créer un second compte, qui laisserait son courrier orphelin.
                commun = self.compte(candidat) if projet else None
                if commun is not None and (commun.machine or "") == (machine or ""):
                    return candidat, commun
                return nom, None
            n += 1

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
            affichage=compte.affichage or existant.affichage,
            cree=existant.cree or compte.cree,
            actif=True,
            contacts=existant.contacts,
            rattachement=existant.rattachement,
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
            expediteur = self.compte(de)
            carnet = ", ".join(c.alias for c in expediteur.contacts) if expediteur else ""
            raise CompteInconnu(f"destinataire(s) sans compte actif : {', '.join(inconnus)} — "
                                f"comptes actifs : {', '.join(actifs)}"
                                + (f" — ton carnet : {carnet}" if carnet else ""))

    # -- Le carnet d'adresses --------------------------------------------------
    def developper(self, de: str, destinataires: Iterable[str]) -> Tuple[List[str], Dict[str, Tuple[str, ...]]]:
        """Les adresses réelles que désignent `destinataires`, écrits par `de`.

        Un compte l'emporte toujours sur un alias : ce que `resoudre` trouvait hier, il le trouve encore.
        Ce n'est que si aucun compte ne porte ce nom qu'on ouvre le carnet de l'expéditeur. Rend les
        adresses, et les alias développés (`{alias: adresses}`) pour le dire à celui qui envoie.
        """
        expediteur = self.compte(de)
        projet = expediteur.projet if expediteur else projet_de(de)
        adresses: List[str] = []
        developpes: Dict[str, Tuple[str, ...]] = {}
        for d in destinataires:
            resolue = self.resoudre(d, projet)
            contact = expediteur.contact(d) if expediteur and "@" not in d and self.compte(resolue) is None else None
            if contact:
                developpes[d] = contact.adresses
                adresses.extend(contact.adresses)
            else:
                adresses.append(resolue)
        return adresses, developpes

    def noter_contact(self, proprietaire: str, alias: str, adresses: Iterable[str], note: Optional[str] = None,
                      date: Optional[str] = None, remplacer: bool = False) -> Contact:
        """Ajoute un contact au carnet de `proprietaire`, ou le remplace. Rend le contact noté.

        Les adresses au nom court sont cherchées comme pour un envoi, depuis le projet du propriétaire,
        et enregistrées en entier : le carnet reste juste quel que soit l'endroit d'où l'on écrit.
        """
        compte = self._titulaire(proprietaire)
        valider_nom(alias, "alias")
        homonyme = self.compte(self.resoudre(alias, compte.projet))
        if homonyme is not None:
            raise ContactRefuse(f"« {alias} » est déjà l'adresse d'un compte ({homonyme.nom}) : écris-lui "
                                "directement, ou choisis un autre alias")
        resolues = [self.resoudre(valider_adresse(a.strip(), "adresse du contact"), compte.projet)
                    for a in adresses if a and a.strip()]
        contact = Contact.composer(alias, resolues, note, date)
        actifs = self.actifs()
        absents = [a for a in contact.adresses if a not in actifs]
        if absents:
            raise ContactRefuse(f"adresse(s) sans compte actif : {', '.join(absents)} — "
                                f"comptes actifs : {', '.join(actifs)}")
        existant = compte.contact(alias)
        if existant is not None and not remplacer:
            raise ContactRefuse(f"le contact « {alias} » existe déjà ({', '.join(existant.adresses)}) : "
                                "--replace pour le remplacer")
        if existant is None and len(compte.contacts) >= CONTACTS_MAX:
            raise ContactRefuse(f"carnet plein : {CONTACTS_MAX} contacts au plus")
        if existant is not None:
            contact = replace(contact, cree=existant.cree or contact.cree, autres=existant.autres)
        carnet = tuple(c for c in compte.contacts if c.alias != alias) + (contact,)
        self._remplacer(compte, replace(compte, contacts=tuple(sorted(carnet, key=lambda c: c.alias))))
        return contact

    def retirer_contact(self, proprietaire: str, alias: str) -> Contact:
        compte = self._titulaire(proprietaire)
        existant = compte.contact(alias)
        if existant is None:
            connus = ", ".join(c.alias for c in compte.contacts) or "aucun"
            raise ContactRefuse(f"contact introuvable : « {alias} » — ton carnet : {connus}")
        self._remplacer(compte, replace(compte, contacts=tuple(c for c in compte.contacts if c.alias != alias)))
        return existant

    def masques(self, proprietaire: str) -> Dict[str, str]:
        """Les alias du carnet qu'un compte créé depuis masque : `{alias: adresse du compte}`."""
        compte = self.compte(proprietaire)
        if compte is None:
            return {}
        trouves = ((c.alias, self.compte(self.resoudre(c.alias, compte.projet))) for c in compte.contacts)
        return {alias: homonyme.nom for alias, homonyme in trouves if homonyme is not None}

    def _titulaire(self, nom: str) -> Compte:
        compte = self.compte(nom)
        if compte is None or not compte.actif:
            raise CompteInconnu(f"« {nom} » n'a pas de compte actif : le carnet d'adresses appartient à un compte")
        return compte

    def _remplacer(self, ancien: Compte, nouveau: Compte) -> None:
        self.comptes[self.comptes.index(ancien)] = nouveau
