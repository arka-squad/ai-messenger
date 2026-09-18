"""Tests : `python -m unittest` depuis la racine du dépôt."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
