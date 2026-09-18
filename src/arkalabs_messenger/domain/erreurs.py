"""Les refus du domaine.

Chaque erreur porte un message destiné à l'utilisateur — humain ou agent — qui
dit ce qui est refusé et, quand c'est utile, quoi faire.
"""


class ErreurMessenger(Exception):
    """Racine de tous les refus explicables de l'outil."""


class NomInvalide(ErreurMessenger):
    """Un nom de compte ne respecte pas la forme imposée."""


class MessageInvalide(ErreurMessenger):
    """Un message, ou un compte, est mal formé (objet vide, corps trop long…)."""


class CompteInconnu(ErreurMessenger):
    """Un expéditeur ou un destinataire n'a pas de compte actif."""


class CompteExistant(ErreurMessenger):
    """Le nom demandé appartient déjà à un compte."""


class MessageIntrouvable(ErreurMessenger):
    """Aucun message ne porte cet identifiant."""


class TransitionRefusee(ErreurMessenger):
    """Le statut demandé n'est pas permis pour ce compte ou pour ce message."""
