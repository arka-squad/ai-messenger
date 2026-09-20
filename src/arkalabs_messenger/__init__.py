"""arkalabs-messenger — une boîte aux lettres partagée entre agents IA.

Architecture hexagonale (voir ARCHITECTURE.md) :

    domain/        le modèle et ses règles, sans aucune entrée-sortie
    application/   les cas d'usage et les ports qu'ils attendent
    adapters/      les implémentations : fichiers, horloge, CLI, web
    bootstrap.py   l'assemblage des adaptateurs autour des cas d'usage
"""

__version__ = "0.1.6"
