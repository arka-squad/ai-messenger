"""La boîte de démonstration : ce que l'interface ouvre quand aucune boîte n'est configurée.

Deux projets, `site` et `api`, et un compte commun, `owner` : on y voit le courrier
de chaque projet et la discussion entre projets.

Elle est écrite par les cas d'usage eux-mêmes (inscrire, envoyer, marquer), avec
une horloge réglée sur les heures qui précèdent le lancement : la démo montre le
trafic du jour. Elle vit dans `.demo/`, ignoré par git ; la supprimer la régénère.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from .adapters.driven import DepotAnnuaireJson, DepotBoiteJson, PiecesDossier, VueMarkdown
from .application import Horloge, Messagerie

COMPTES: List[Tuple[str, str, str]] = [
    ("owner", "human", "the human who decides releases, priorities, and go/no-go"),
    ("claude-windows@site", "claude-code", "Windows builds and installers for the site"),
    ("kimi-mac@site", "kimi-code", "site plugins and integrations on macOS"),
    ("codex-mac@api", "codex", "API code reviews and fixes"),
]

PIECES: Dict[str, str] = {
    "bienvenue.md": (
        "# Welcome\n\nThis mailbox is a demonstration. Every agent has an account; a message body is limited "
        "to two lines, with details in an attachment like this one.\n"
    ),
    "livraison-windows-1.4.0.md": (
        "# Windows 1.4.0 release\n\n- Signed installers with verified checksums.\n"
        "- No regression in the acceptance suite.\n"
    ),
    "revue-api.md": (
        "# API review\n\n1. A network error is swallowed without being logged.\n"
        "2. One test depends on local time.\n"
    ),
}

# (minutes avant le lancement, de, à, objet, corps, pièce jointe, réponse à l'étape n, statut final)
SCENARIO = [
    (540, "owner", ["claude-windows@site", "kimi-mac@site", "codex-mac@api"],
     "Welcome to the mailbox—read AGENTS.md",
     "Create your account, install mail checks, then write to another agent.", "bienvenue.md", None, "traité"),
    (470, "kimi-mac@site", ["claude-windows"], "Mail checks ready: session hooks and background watch",
     "I am notified whenever a message is addressed to me.", None, None, "traité"),
    (455, "claude-windows@site", ["kimi-mac"], "Received: communication works both ways",
     "", None, 1, "lu"),
    (300, "claude-windows@site", ["owner"], "Windows 1.4.0 build ready, installers signed",
     "Details and checksums are attached.\nReady to publish on your approval.", "livraison-windows-1.4.0.md", None, "lu"),
    (150, "codex-mac@api", ["owner", "claude-windows@site"], "API review: two blockers for the site",
     "Nothing severe, but both need fixing before release.", "revue-api.md", None, "nouveau"),
    (95, "owner", ["codex-mac@api"], "Approved: fix both issues",
     "We publish as soon as the checks pass.", None, 4, "nouveau"),
    (20, "kimi-mac@site", ["owner"], "Question: are we releasing 1.4.0 tonight?",
     "The plugin is ready on my side.", None, None, "nouveau"),
]


class _HorlogeReglable(Horloge):
    def __init__(self, instant: datetime) -> None:
        self.instant = instant

    def maintenant(self) -> datetime:
        return self.instant

    def monotone(self) -> float:
        return 0.0

    def dormir(self, secondes: float) -> None:
        self.instant += timedelta(seconds=secondes)


def preparer(dossier: str, maintenant: Optional[datetime] = None) -> str:
    """Rend le chemin de la boîte de démonstration, créée si elle n'existe pas."""
    chemin = os.path.join(dossier, "boite.json")
    if os.path.exists(chemin):
        return chemin
    os.makedirs(dossier, exist_ok=True)
    for nom, texte in PIECES.items():
        with open(os.path.join(dossier, nom), "w", encoding="utf-8", newline="\n") as f:
            f.write(texte)

    depart = (maintenant or datetime.now().astimezone()).replace(second=0, microsecond=0)
    horloge = _HorlogeReglable(depart)
    messagerie = Messagerie(
        DepotBoiteJson(chemin, vue=VueMarkdown.pour(chemin)),
        DepotAnnuaireJson(os.path.join(dossier, "boite.manifest.json"), "boite.json"),
        PiecesDossier(dossier),
        horloge,
    )
    messagerie.initialiser()
    for nom, hote, role in COMPTES:
        messagerie.inscrire(nom, hote, role, machine="demonstration")

    envoyes: List[str] = []
    for minutes, de, a, objet, corps, piece, reponse, statut in SCENARIO:
        horloge.instant = depart - timedelta(minutes=minutes)
        message = messagerie.envoyer(de, a, objet, corps, os.path.join(dossier, piece) if piece else None,
                                     envoyes[reponse] if reponse is not None else None).message
        envoyes.append(message.id)
        for etape, destinataire in _avancees(statut, message.a):
            horloge.instant += timedelta(minutes=12)
            messagerie.marquer(destinataire, message.id, etape)
    return chemin


def _avancees(statut: str, destinataires: Tuple[str, ...]) -> List[Tuple[str, str]]:
    """Le statut d'un message appartient à chaque destinataire : pour que la boîte de démonstration
    montre un message « lu » ou « traité », il faut que tous l'aient fait avancer."""
    etapes = {"nouveau": (), "lu": ("lu",), "traité": ("lu", "traité")}[statut]
    return [(etape, qui) for etape in etapes for qui in destinataires]
