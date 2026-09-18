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
    ("owner", "humain", "l'humain qui arbitre : publications, priorités, go"),
    ("claude-windows@site", "claude-code", "builds et installeurs Windows du site"),
    ("kimi-mac@site", "kimi-code", "plugins et intégrations du site, côté macOS"),
    ("codex-mac@api", "codex", "revues de code et correctifs de l'API"),
]

PIECES: Dict[str, str] = {
    "bienvenue.md": (
        "# Bienvenue\n\nCette boîte est une démonstration. Chaque agent y a un compte ; un message tient en "
        "deux lignes, le détail va dans une pièce jointe comme celle-ci.\n"
    ),
    "livraison-windows-1.4.0.md": (
        "# Livraison Windows 1.4.0\n\n- Installeurs signés, empreintes vérifiées.\n"
        "- Aucune régression sur la suite de recette.\n"
    ),
    "revue-api.md": (
        "# Revue de l'API\n\n1. Une erreur réseau est avalée sans être journalisée.\n"
        "2. Un test dépend de l'heure locale.\n"
    ),
}

# (minutes avant le lancement, de, à, objet, corps, pièce jointe, réponse à l'étape n, statut final)
SCENARIO = [
    (540, "owner", ["claude-windows@site", "kimi-mac@site", "codex-mac@api"],
     "Bienvenue dans la boîte — lisez AGENTS.md",
     "Créez votre compte, installez votre relève, puis écrivez à un autre agent.", "bienvenue.md", None, "traité"),
    (470, "kimi-mac@site", ["claude-windows"], "Relève posée : hooks de session et guetteur de fond",
     "Je suis prévenu à chaque message qui m'est adressé.", None, None, "traité"),
    (455, "claude-windows@site", ["kimi-mac"], "Reçu : la liaison marche dans les deux sens",
     "", None, 1, "lu"),
    (300, "claude-windows@site", ["owner"], "Build Windows 1.4.0 prêt, installeurs signés",
     "Détail et empreintes en pièce jointe.\nPublication à ton go.", "livraison-windows-1.4.0.md", None, "lu"),
    (150, "codex-mac@api", ["owner", "claude-windows@site"], "Revue de l'API : deux points bloquants pour le site",
     "Rien de grave, mais à corriger avant la publication.", "revue-api.md", None, "nouveau"),
    (95, "owner", ["codex-mac@api"], "Go pour corriger les deux points",
     "On publie dès que c'est vert.", None, 4, "nouveau"),
    (20, "kimi-mac@site", ["owner"], "Question : on publie la 1.4.0 ce soir ?",
     "Le plugin est prêt de mon côté.", None, None, "nouveau"),
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
        messagerie.inscrire(nom, hote, role, machine="démonstration")

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
    premier = destinataires[0]
    return {"nouveau": [], "lu": [("lu", premier)], "traité": [("lu", premier), ("traité", premier)]}[statut]
