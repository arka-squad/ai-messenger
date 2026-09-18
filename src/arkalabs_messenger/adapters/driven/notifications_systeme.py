"""Les notifications du système : Windows (toast), macOS (Centre de notifications), Linux (notify-send).

Aucune dépendance : chaque système a son outil natif. Le texte passe par des
variables d'environnement ou des arguments, jamais dans une ligne de commande
interprétée : un objet de message ne peut rien exécuter.

Sous Windows, la notification porte la marque « arkalabs Messenger » et son
icône : l'application est déclarée pour l'utilisateur courant seulement
(`HKCU\\Software\\Classes\\AppUserModelId`), sans installation.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from ...application.ports import Notificateur

NOM = "arkalabs Messenger"
AUMID = "arkalabs.Messenger"
ICONE = Path(__file__).resolve().parent / "ressources" / "arkalabs-messenger.png"

_TOAST_WINDOWS = r"""
$ErrorActionPreference = 'Stop'
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom, ContentType = WindowsRuntime] | Out-Null
function Esc([string]$t) { [Security.SecurityElement]::Escape($t) }
$lignes = @($env:MESSENGER_TITRE) + @($env:MESSENGER_TEXTE -split "`n" | Where-Object { $_ })
$textes = ($lignes | Select-Object -First 3 | ForEach-Object { '<text>' + (Esc $_) + '</text>' }) -join ''
$logo = if ($env:MESSENGER_ICONE) { '<image placement="appLogoOverride" src="' + (Esc $env:MESSENGER_ICONE) + '"/>' } else { '' }
$lancement = if ($env:MESSENGER_LIEN) { ' activationType="protocol" launch="' + (Esc $env:MESSENGER_LIEN) + '"' } else { '' }
$doc = New-Object Windows.Data.Xml.Dom.XmlDocument
$doc.LoadXml('<toast' + $lancement + '><visual><binding template="ToastGeneric">' + $textes + $logo + '</binding></visual></toast>')
$toast = New-Object Windows.UI.Notifications.ToastNotification $doc
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($env:MESSENGER_AUMID).Show($toast)
"""

_AFFICHAGE_MACOS = [
    "-e", "on run argv",
    "-e", f"display notification (item 2 of argv) with title \"{NOM}\" subtitle (item 1 of argv)",
    "-e", "end run",
]

Commande = Tuple[List[str], Dict[str, str]]


def commande(plateforme: str, titre: str, lignes: Sequence[str], lien: Optional[str] = None) -> Optional[Commande]:
    """La commande qui affiche la notification sur `plateforme`, ou None si elle n'en a pas."""
    texte = "\n".join(l for l in lignes if l)
    if plateforme == "win32":
        env = {"MESSENGER_TITRE": titre, "MESSENGER_TEXTE": texte, "MESSENGER_LIEN": lien or "",
               "MESSENGER_AUMID": AUMID, "MESSENGER_ICONE": ICONE.as_uri() if ICONE.is_file() else ""}
        return (["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                 "-Command", _TOAST_WINDOWS], env)
    if plateforme == "darwin":
        return (["osascript", *_AFFICHAGE_MACOS, titre, texte.replace("\n", " — ")], {})
    if shutil.which("notify-send"):
        icone = [f"--icon={ICONE}"] if ICONE.is_file() else []
        return (["notify-send", f"--app-name={NOM}", *icone, titre, texte], {})
    return None


def declarer_application_windows() -> bool:
    """Déclare « arkalabs Messenger » et son icône pour l'utilisateur courant. Rend False en cas d'échec."""
    try:
        import winreg

        cle = winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\AppUserModelId\{AUMID}")
        with cle:
            winreg.SetValueEx(cle, "DisplayName", 0, winreg.REG_SZ, NOM)
            if ICONE.is_file():
                winreg.SetValueEx(cle, "IconUri", 0, winreg.REG_SZ, str(ICONE))
        return True
    except (ImportError, OSError):
        return False


class NotificationsSysteme(Notificateur):
    def __init__(self, plateforme: str = sys.platform) -> None:
        self._plateforme = plateforme
        self._declaree = False

    def notifier(self, titre: str, lignes: Sequence[str], lien: Optional[str] = None) -> None:
        prevue = commande(self._plateforme, titre, lignes, lien)
        if prevue is None:
            return
        if self._plateforme == "win32" and not self._declaree:
            self._declaree = declarer_application_windows()
        argv, env = prevue
        options = {"creationflags": subprocess.CREATE_NO_WINDOW} if self._plateforme == "win32" else {}
        try:
            subprocess.Popen(argv, env={**os.environ, **env}, stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **options)
        except OSError:
            pass  # pas d'outil de notification sur ce poste : la boîte fonctionne sans
