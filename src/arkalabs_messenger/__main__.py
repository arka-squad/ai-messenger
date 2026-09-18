"""`python -m arkalabs_messenger …` : la ligne de commande."""
import sys

from .bootstrap import main

if __name__ == "__main__":
    sys.exit(main())
