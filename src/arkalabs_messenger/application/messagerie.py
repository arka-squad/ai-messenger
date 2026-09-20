"""Les cas d'usage de la messagerie.

`Messagerie` orchestre le domaine et les ports ; elle ne sait rien des fichiers,
de la ligne de commande ni du web.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from ..domain import (
    Boite,
    Brouillon,
    Compte,
    Contact,
    Message,
    MessageInvalide,
    NomInvalide,
    composer_identite,
    projet_de,
    qualifier,
    valider_adresse,
    valider_nom,
)
from .ports import (
    BoiteExistante,
    BoiteIndisponible,
    DepotAnnuaire,
    DepotBoite,
    Horloge,
    PieceJointeRefusee,
    PiecesJointes,
    SourceAncienne,
)


@dataclass(frozen=True)
class Envoi:
    """Le résultat d'un envoi."""

    message: Message
    adresses_verifiees: bool
    """False si la boîte n'a pas d'annuaire : les adresses n'ont pas pu être vérifiées."""
    alias_developpes: Tuple[Tuple[str, Tuple[str, ...]], ...] = ()
    """Les alias du carnet de l'expéditeur qui ont été remplacés par leurs adresses."""


@dataclass(frozen=True)
class Carnet:
    """Le carnet d'adresses d'un compte, tel qu'on le lui montre."""

    contacts: Tuple[Contact, ...]
    masques: Dict[str, str]
    """Les alias qu'un compte créé depuis masque (`{alias: adresse}`) : à renommer."""


@dataclass(frozen=True)
class Import:
    """Le résultat d'une migration."""

    messages: int
    comptes: Tuple[str, ...]


class Messagerie:
    def __init__(self, boite: DepotBoite, annuaire: DepotAnnuaire,
                 pieces: PiecesJointes, horloge: Horloge) -> None:
        self._boite = boite
        self._annuaire = annuaire
        self._pieces = pieces
        self._horloge = horloge

    # -- La boîte -------------------------------------------------------------
    @property
    def emplacement(self) -> str:
        return self._boite.emplacement

    @property
    def racine(self) -> str:
        """Le dossier de la boîte : là où vit le guide d'accueil des agents (`onboarding.md`)."""
        return self._boite.racine

    @property
    def lecture_seule(self) -> bool:
        return self._boite.lecture_seule

    def initialiser(self) -> None:
        if self._boite.existe():
            raise BoiteExistante(f"existe déjà, rien écrit : {self._boite.emplacement}")
        self._boite.creer()
        self._annuaire.creer()

    def instantane(self) -> Boite:
        return self._boite.lire()

    def version(self) -> str:
        return self._boite.version()

    # -- Les comptes ----------------------------------------------------------
    def annuaire_present(self) -> bool:
        return self._annuaire.existe()

    def comptes(self, tous: bool = False, projet: Optional[str] = None) -> List[Compte]:
        return [c for c in self._annuaire.lire().comptes
                if (tous or c.actif) and (projet is None or c.projet == projet)]

    def adresse(self, nom: str, projet: Optional[str]) -> str:
        """L'adresse que désigne `nom` depuis `projet` (voir `Annuaire.resoudre`)."""
        if self._annuaire.existe():
            return self._annuaire.lire().resoudre(nom, projet)
        return qualifier(valider_adresse(nom), projet)

    def projets(self) -> List[str]:
        """Les projets connus : ceux qu'on a connectés, ceux des comptes, et ceux vus dans la boîte."""
        vus = set(self._annuaire.lire().projets())
        vus.update(p for p in (projet_de(x) for x in self._boite.lire().participants()) if p)
        return sorted(vus)

    def declarer_projet(self, projet: str) -> bool:
        """Note qu'un projet est connecté à la boîte : il est connu avant qu'un agent s'y enrôle.
        Rend True s'il ne l'était pas."""
        valider_nom(projet, "projet")
        with self._annuaire.transaction() as annuaire:
            return annuaire.declarer(projet, self._horodatage())

    def inscrire(self, nom: str, hote: str, role: str, *, machine: Optional[str] = None,
                 modele: Optional[str] = None, humain: Optional[str] = None,
                 releve: Optional[str] = None, affichage: Optional[str] = None,
                 mise_a_jour: bool = False) -> Tuple[Compte, bool]:
        """Crée le compte, ou met à jour le sien. Rend le compte et s'il vient d'être créé."""
        compte = Compte.ouvrir(nom, hote, role, machine=machine, modele=modele, humain=humain,
                               releve=releve, affichage=affichage, cree=self._horodatage())
        with self._annuaire.transaction() as annuaire:
            cree = annuaire.inscrire(compte, mise_a_jour)
            return annuaire.compte(nom), cree

    def enroler(self, hote: str, tache: str, poste: str, projet: Optional[str], machine: Optional[str], *,
                role: Optional[str] = None, humain: Optional[str] = None, releve: Optional[str] = None,
                mise_a_jour: bool = False) -> Tuple[Compte, bool]:
        """Inscrit un agent sous une identité lisible déduite de son hôte, de sa tâche et de son poste.

        Le même agent qui revient (même machine) retrouve son compte ; un homonyme d'une autre
        machine reçoit un suffixe. Rend le compte, et s'il vient d'être créé.
        """
        adresse, affichage = composer_identite(hote, tache, poste)
        with self._annuaire.transaction() as annuaire:
            nom, existant = annuaire.nom_libre(adresse, projet, machine)
            if existant is not None and not mise_a_jour:
                return existant, False
            compte = Compte.ouvrir(nom, hote, role or f"{hote} — {tache}", machine=machine, humain=humain,
                                   releve=releve, affichage=affichage, cree=self._horodatage())
            cree = annuaire.inscrire(compte, mise_a_jour=existant is not None)
            return annuaire.compte(nom), cree

    def desactiver(self, nom: str) -> None:
        with self._annuaire.transaction() as annuaire:
            annuaire.desactiver(valider_adresse(nom))

    # -- Le carnet d'adresses -------------------------------------------------
    def carnet(self, compte: str) -> Carnet:
        """Le carnet de `compte` (une adresse complète)."""
        annuaire = self._annuaire.lire()
        titulaire = annuaire.compte(valider_adresse(compte))
        return Carnet(titulaire.contacts if titulaire else (), annuaire.masques(compte))

    def noter_contact(self, compte: str, alias: str, adresses: Sequence[str], note: Optional[str] = None,
                      remplacer: bool = False) -> Contact:
        """Ajoute un contact au carnet de `compte`, ou le remplace. Un alias désigne une adresse, ou un groupe."""
        with self._annuaire.transaction() as annuaire:
            return annuaire.noter_contact(valider_adresse(compte), alias, adresses, note, self._horodatage(), remplacer)

    def retirer_contact(self, compte: str, alias: str) -> Contact:
        with self._annuaire.transaction() as annuaire:
            return annuaire.retirer_contact(valider_adresse(compte), alias)

    # -- Les messages ---------------------------------------------------------
    def envoyer(self, de: str, a: Sequence[str], objet: str, corps: str = "",
                piece: Optional[str] = None, re: Optional[str] = None) -> Envoi:
        """`de` est une adresse complète ; un destinataire au nom court est cherché dans le projet de `de`,
        puis parmi les comptes communs, puis dans le carnet d'adresses de `de`."""
        projet = projet_de(valider_adresse(de, "expéditeur"))
        demandes = [d.strip() for d in a if d and d.strip()]
        verifiees = self._annuaire.existe()
        developpes: Dict[str, Tuple[str, ...]] = {}
        if verifiees:
            annuaire = self._annuaire.lire()
            destinataires, developpes = annuaire.developper(de, demandes)
        else:
            destinataires = [qualifier(valider_adresse(d), projet) for d in demandes]
        brouillon = Brouillon.rediger(de, destinataires, objet, corps.splitlines(), re)
        if verifiees:
            annuaire.verifier(brouillon.de, brouillon.a)
        with self._boite.transaction() as boite:
            mid = boite.identifiant_libre(brouillon.de, self._horloge.maintenant())
            boite.controler(brouillon.re, mid)  # avant de déposer : pas de pièce orpheline
            pj = self._pieces.deposer(piece) if piece else None
            message = brouillon.emettre(mid, self._horodatage(), pj)
            boite.ajouter(message)
        return Envoi(message, verifiees, tuple(developpes.items()))

    def releve(self, compte: str) -> List[Message]:
        """Les messages au statut « nouveau » adressés à `compte`."""
        return self._boite.lire().nouveaux_pour(valider_adresse(compte))

    def marquer(self, compte: str, mid: str, statut: str) -> Message:
        with self._boite.transaction() as boite:
            return boite.marquer(mid, valider_adresse(compte), statut, self._horodatage())

    def lister(self, compte: Optional[str] = None, statut: Optional[str] = None,
               limite: Optional[int] = None, projet: Optional[str] = None) -> List[Message]:
        """Du plus récent au plus ancien, filtré par compte (émis ou reçu), statut et projet."""
        messages = [m for m in self._boite.lire().recents()
                    if (compte is None or m.concerne(compte)) and (statut is None or m.statut == statut)
                    and (projet is None or m.touche_le_projet(projet))]
        return messages if limite is None else messages[:limite]

    def guetter(self, compte: str, intervalle: float, heures: float) -> List[Message]:
        """Attend un message nouveau adressé à `compte`, arrivé après le début de l'attente.

        Rend la liste des messages reçus, ou une liste vide à l'échéance. Ni les
        envois de `compte`, ni les messages des autres, ni les changements de
        statut ne réveillent.
        """
        deja = {m.id for m in self.releve(compte)}
        fin = self._horloge.monotone() + heures * 3600
        while self._horloge.monotone() < fin:
            self._horloge.dormir(intervalle)
            try:
                recus = [m for m in self.releve(compte) if m.id not in deja]
            except BoiteIndisponible:
                continue  # boîte momentanément injoignable : on réessaie au tour suivant
            if recus:
                return recus
        return []

    def piece_jointe(self, nom: str) -> Optional[str]:
        """Le chemin d'une pièce jointe, seulement si un message la référence."""
        if not nom or nom not in {m.pj for m in self._boite.lire().messages}:
            return None
        return self._pieces.localiser(nom)

    # -- La migration ---------------------------------------------------------
    def importer(self, source: SourceAncienne) -> Import:
        """Crée la boîte à partir d'une ancienne ; crée les comptes rencontrés, à compléter."""
        if self._boite.existe():
            raise BoiteExistante(f"la boîte existe déjà, rien écrit : {self._boite.emplacement}")
        messages = source.messages()
        if not messages:
            raise MessageInvalide(f"aucun message reconnu dans {source.emplacement}")
        boite = Boite(messages=list(messages))
        self._boite.creer(boite)
        self._annuaire.creer()
        dossier_source = os.path.dirname(source.emplacement)
        for m in messages:  # rapatrie les pièces jointes trouvées à côté de l'ancienne boîte
            if m.pj:
                try:
                    self._pieces.deposer(os.path.join(dossier_source, m.pj))
                except PieceJointeRefusee:
                    pass
        noms = tuple(sorted(boite.participants()))
        with self._annuaire.transaction() as annuaire:
            for nom in noms:
                if annuaire.compte(nom) is None and _nom_valide(nom):
                    annuaire.inscrire(Compte.ouvrir(
                        nom, "inconnu", "compte importé — à compléter par son agent (register --update)",
                        cree=self._horodatage()))
        return Import(len(messages), noms)

    # -------------------------------------------------------------------------
    def _horodatage(self) -> str:
        return self._horloge.maintenant().isoformat(timespec="seconds")


def _nom_valide(nom: str) -> bool:
    try:
        valider_adresse(nom)
    except NomInvalide:
        return False
    return True
