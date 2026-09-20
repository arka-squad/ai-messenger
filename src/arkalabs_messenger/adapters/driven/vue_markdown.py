"""La vue lisible de la boîte, régénérée à chaque écriture : `boite.md`."""
from __future__ import annotations

import os

from ...domain import Boite, Message
from .fichiers import ecrire_atomique


class VueMarkdown:
    """Publie la boîte en Markdown, du plus récent au plus ancien. Ne se lit jamais."""

    def __init__(self, chemin: str, nom_boite: str, nom_manifeste: str) -> None:
        self._chemin = chemin
        self._nom_boite = nom_boite
        self._nom_manifeste = nom_manifeste

    def __call__(self, boite: Boite) -> None:
        ecrire_atomique(self._chemin, rendre(boite, self._nom_boite, self._nom_manifeste))

    @staticmethod
    def pour(chemin_boite: str) -> "VueMarkdown":
        racine = os.path.splitext(chemin_boite)[0]
        return VueMarkdown(racine + ".md", os.path.basename(chemin_boite),
                           os.path.basename(racine + ".manifest.json"))


def rendre(boite: Boite, nom_boite: str, nom_manifeste: str) -> str:
    lignes = [
        "# Boîte aux lettres des agents — vue générée",
        "",
        f"> Vue lisible régénérée par `messenger.py` à chaque écriture. **Ne pas éditer** : "
        f"la source est `{nom_boite}`. Comptes : `{nom_manifeste}`.",
        "",
        "## Messages",
        "",
    ]
    for m in boite.recents():
        lignes.extend(_bloc(m))
    return "\n".join(lignes)


def _statut(m: Message) -> str:
    """La vue d'ensemble, puis qui a avancé — un statut appartient à chaque destinataire."""
    avances = [f"{d} {s}" for d, s in m.statuts.items() if s != m.statut]
    return m.statut + (f" (dont {', '.join(avances)})" if avances else "")


def _bloc(m: Message) -> list:
    pj = f"[{m.pj}]({m.pj})" if m.pj else "—"
    return [
        f"### {m.id} · {m.titre}",
        f"**De** {m.de} → **À** {', '.join(m.a)} · **Statut** {_statut(m)} · **PJ** {pj}",
        *m.corps,
        "",
    ]
