"""Le domaine : messages, comptes et leurs règles. Aucune entrée-sortie ici."""

from .erreurs import (
    CompteExistant,
    CompteInconnu,
    ErreurMessenger,
    MessageIntrouvable,
    MessageInvalide,
    NomInvalide,
    TransitionRefusee,
)
from .modele import (
    CORPS_MAX,
    STATUTS,
    Annuaire,
    Boite,
    Brouillon,
    Compte,
    Message,
    Transition,
    valider_nom,
)

__all__ = [
    "Annuaire", "Boite", "Brouillon", "Compte", "Message", "Transition",
    "CORPS_MAX", "STATUTS", "valider_nom",
    "ErreurMessenger", "CompteExistant", "CompteInconnu", "MessageIntrouvable",
    "MessageInvalide", "NomInvalide", "TransitionRefusee",
]
