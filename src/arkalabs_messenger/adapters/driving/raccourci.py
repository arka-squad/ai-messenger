"""L'icône « Messenger » sur le bureau : un double-clic allume la boîte.

Un humain n'ouvre pas de terminal. `messenger.py shortcut` pose, une fois par poste, de quoi lancer
`messenger.py start` d'un double-clic — sans console, avec un journal dans le dossier personnel :

- **Windows** : `Messenger.lnk` (vers `pythonw.exe`, qui n'ouvre pas de fenêtre noire) ;
- **macOS** : `Messenger.app`, une application minimale (un script et son icône), sans icône dans le Dock ;
- **Linux** : `messenger.desktop`.

Relancer la commande refait le raccourci (dépôt déplacé, autre Python) ; `--remove` le retire.
"""
from __future__ import annotations

import os
import platform
import shutil
import stat
import subprocess
import sys
from typing import List, Optional

NOM = "Messenger"
JOURNAL = ".arkalabs-messenger.log"
_RESSOURCES = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "ressources")


class RaccourciImpossible(Exception):
    """Le raccourci n'a pas pu être posé : le bureau est introuvable, ou l'écriture est refusée."""


def chemin(bureau: str, systeme: Optional[str] = None) -> str:
    """Où vit le raccourci, sur ce bureau."""
    systeme = systeme or platform.system()
    nom = {"Windows": f"{NOM}.lnk", "Darwin": f"{NOM}.app"}.get(systeme, "messenger.desktop")
    return os.path.join(bureau, nom)


def bureau_du_poste(systeme: Optional[str] = None) -> str:
    """Le dossier « Bureau » de l'humain — là où Windows ou Linux l'ont vraiment rangé (OneDrive, langue…)."""
    systeme = systeme or platform.system()
    trouve = None
    try:
        if systeme == "Windows":
            trouve = _sortie(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                              "[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false; "
                              "[Console]::Out.Write([Environment]::GetFolderPath('Desktop'))"])
        elif systeme != "Darwin":
            trouve = _sortie(["xdg-user-dir", "DESKTOP"])
    except (OSError, subprocess.SubprocessError):
        trouve = None
    bureau = trouve if trouve and os.path.isdir(trouve) else os.path.join(os.path.expanduser("~"), "Desktop")
    if not os.path.isdir(bureau):
        raise RaccourciImpossible(f"desktop directory not found ({bureau})")
    return bureau


def poser(depot: str, python: Optional[str] = None, bureau: Optional[str] = None, systeme: Optional[str] = None) -> str:
    """Pose le raccourci (ou le refait). Rend son chemin."""
    systeme = systeme or platform.system()
    python = python or sys.executable
    bureau = bureau or bureau_du_poste(systeme)
    # le séparateur du système visé, pas de celui qui exécute (les tests posent un raccourci macOS depuis Windows)
    messenger = depot.rstrip("/\\") + ("\\" if systeme == "Windows" else "/") + "messenger.py"
    cible = chemin(bureau, systeme)
    try:
        retirer(bureau, systeme)
        if systeme == "Windows":
            _poser_windows(cible, python, messenger, depot)
        elif systeme == "Darwin":
            _poser_macos(cible, python, messenger)
        else:
            _poser_linux(cible, python, messenger)
    except OSError as e:
        raise RaccourciImpossible(f"could not write shortcut ({cible}): {e.strerror or e}") from None
    return cible


def retirer(bureau: Optional[str] = None, systeme: Optional[str] = None) -> bool:
    """Retire le raccourci s'il est là. Rend True s'il y était."""
    systeme = systeme or platform.system()
    cible = chemin(bureau or bureau_du_poste(systeme), systeme)
    if os.path.isdir(cible):
        shutil.rmtree(cible)
        return True
    if os.path.lexists(cible):
        os.remove(cible)
        return True
    return False


def arguments(messenger: str) -> List[str]:
    """Ce que le raccourci lance : la boîte, avec son journal (sans console, une panne serait invisible)."""
    return [messenger, "start", "--log", os.path.join("~", JOURNAL)]


# --------------------------------------------------------------------------- #
def _poser_windows(cible: str, python: str, messenger: str, depot: str) -> None:
    sans_console = os.path.join(os.path.dirname(python), "pythonw.exe")
    executable = sans_console if os.path.isfile(sans_console) else python
    ligne = subprocess.list2cmdline(arguments(messenger))
    # Les valeurs passent par l'environnement : aucun guillemet à échapper dans le script.
    env = dict(os.environ, AM_CIBLE=cible, AM_EXE=executable, AM_ARGS=ligne, AM_DOSSIER=depot,
               AM_ICONE=os.path.join(_RESSOURCES, "messenger.ico"))
    script = "; ".join([
        "$ErrorActionPreference = 'Stop'",
        "$r = (New-Object -ComObject WScript.Shell).CreateShortcut($env:AM_CIBLE)",
        "$r.TargetPath = $env:AM_EXE",
        "$r.Arguments = $env:AM_ARGS",
        "$r.WorkingDirectory = $env:AM_DOSSIER",
        "$r.IconLocation = $env:AM_ICONE",
        "$r.Description = 'Open the agent mailbox'",
        "$r.WindowStyle = 7",
        "$r.Save()",
    ])
    resultat = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], env=env,
                              capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if resultat.returncode != 0 or not os.path.isfile(cible):
        detail = " ".join(resultat.stderr.decode("utf-8", "replace").split())[:200]
        raise RaccourciImpossible(f"Windows refused to create the shortcut "
                                  f"({detail or 'code ' + str(resultat.returncode)})")


def _poser_macos(cible: str, python: str, messenger: str) -> None:
    contenu = os.path.join(cible, "Contents")
    os.makedirs(os.path.join(contenu, "MacOS"))
    os.makedirs(os.path.join(contenu, "Resources"))
    shutil.copyfile(os.path.join(_RESSOURCES, "messenger.icns"), os.path.join(contenu, "Resources", "messenger.icns"))
    with open(os.path.join(contenu, "Info.plist"), "w", encoding="utf-8", newline="\n") as f:
        f.write(_PLIST)
    lanceur = os.path.join(contenu, "MacOS", NOM)
    with open(lanceur, "w", encoding="utf-8", newline="\n") as f:
        # Lancée par le Finder, une app n'a presque pas de PATH : l'interpréteur est donné en entier.
        # La boîte part en arrière-plan et l'app rend la main aussitôt : macOS ne relance pas une app déjà
        # ouverte, et un second double-clic — qui doit rouvrir la fenêtre de la boîte — ne ferait rien.
        f.write("#!/bin/sh\n"
                f"nohup {_sh(python)} {_sh(messenger)} start --log \"$HOME/{JOURNAL}\" >/dev/null 2>&1 &\n")
    os.chmod(lanceur, os.stat(lanceur).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _poser_linux(cible: str, python: str, messenger: str) -> None:
    with open(cible, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join([
            "[Desktop Entry]", "Type=Application", f"Name={NOM}",
            "Comment=Open the agent mailbox",
            f"Exec={_sh(python)} {_sh(messenger)} start --log {_sh(os.path.join(os.path.expanduser('~'), JOURNAL))}",
            f"Icon={os.path.join(_RESSOURCES, 'messenger.png')}", "Terminal=false", "Categories=Utility;", ""]))
    os.chmod(cible, os.stat(cible).st_mode | stat.S_IXUSR)


def _sh(texte: str) -> str:
    return "'" + texte.replace("'", "'\\''") + "'"


def _sortie(commande: List[str]) -> str:
    resultat = subprocess.run(commande, capture_output=True, timeout=20,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return resultat.stdout.decode("utf-8", "replace").strip() if resultat.returncode == 0 else ""


_PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Messenger</string>
  <key>CFBundleDisplayName</key><string>Messenger</string>
  <key>CFBundleIdentifier</key><string>app.arkalabs.messenger</string>
  <key>CFBundleExecutable</key><string>Messenger</string>
  <key>CFBundleIconFile</key><string>messenger</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleVersion</key><string>1</string>
  <key>CFBundleShortVersionString</key><string>1</string>
  <key>LSUIElement</key><true/>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
"""
