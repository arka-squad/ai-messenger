#!/usr/bin/env python3
"""arkalabs-messenger — point d'entrée, sans installation.

    python3 messenger.py --help

Python 3.8 ou plus, bibliothèque standard seulement. Le code est dans
`src/arkalabs_messenger` ; voir ARCHITECTURE.md.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from arkalabs_messenger.bootstrap import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
