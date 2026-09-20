"""L'icône du bureau : de quoi allumer la boîte d'un double-clic, sur chaque système."""
import os
import platform
import plistlib
import struct
import subprocess
import sys
import tempfile
import unittest

from arkalabs_messenger.adapters.driving import raccourci

DEPOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESSOURCES = os.path.join(DEPOT, "src", "arkalabs_messenger", "ressources")


class Icones(unittest.TestCase):
    def test_les_trois_formats_sont_livres_et_bien_formes(self):
        with open(os.path.join(RESSOURCES, "messenger.png"), "rb") as f:
            self.assertEqual(f.read(8), b"\x89PNG\r\n\x1a\n")
        with open(os.path.join(RESSOURCES, "messenger.ico"), "rb") as f:
            reserve, genre, nombre = struct.unpack("<HHH", f.read(6))
        self.assertEqual((reserve, genre), (0, 1))
        self.assertGreaterEqual(nombre, 3)
        with open(os.path.join(RESSOURCES, "messenger.icns"), "rb") as f:
            donnees = f.read()
        self.assertEqual(donnees[:4], b"icns")
        self.assertEqual(struct.unpack(">I", donnees[4:8])[0], len(donnees))


class Bureau(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.bureau = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_macos_une_application_minimale(self):
        python = "/usr/local/bin/python3"
        cible = raccourci.poser("/Users/moi/l'outil", python, self.bureau, "Darwin")
        self.assertEqual(cible, os.path.join(self.bureau, "Messenger.app"))
        with open(os.path.join(cible, "Contents", "Info.plist"), "rb") as f:
            plist = plistlib.load(f)
        self.assertEqual((plist["CFBundleExecutable"], plist["CFBundleIconFile"], plist["LSUIElement"]),
                         ("Messenger", "messenger", True))
        self.assertTrue(os.path.isfile(os.path.join(cible, "Contents", "Resources", "messenger.icns")))
        lanceur = os.path.join(cible, "Contents", "MacOS", "Messenger")
        with open(lanceur, encoding="utf-8") as f:
            script = f.read()
        self.assertTrue(script.startswith("#!/bin/sh\n"))
        # l'interpréteur en entier (le Finder n'a pas de PATH), les apostrophes du chemin protégées, un journal
        self.assertIn("nohup '/usr/local/bin/python3' '/Users/moi/l'\\''outil/messenger.py' start --log "
                      "\"$HOME/.arkalabs-messenger.log\" >/dev/null 2>&1 &", script)
        self.assertNotIn("exec ", script)  # l'app rend la main : un second double-clic relance bien le script
        if os.name == "posix":
            self.assertTrue(os.access(lanceur, os.X_OK))

    def test_linux_une_entree_de_bureau(self):
        cible = raccourci.poser("/opt/outil", "/usr/bin/python3", self.bureau, "Linux")
        with open(cible, encoding="utf-8") as f:
            entree = f.read()
        self.assertIn("Exec='/usr/bin/python3' '/opt/outil/messenger.py' start --log", entree)
        self.assertIn("Terminal=false", entree)

    def test_refaire_remplace_et_retirer_retire(self):
        raccourci.poser("/ancien", "/usr/bin/python3", self.bureau, "Darwin")
        cible = raccourci.poser("/nouveau", "/usr/bin/python3", self.bureau, "Darwin")
        with open(os.path.join(cible, "Contents", "MacOS", "Messenger"), encoding="utf-8") as f:
            self.assertIn("/nouveau/messenger.py", f.read())
        self.assertTrue(raccourci.retirer(self.bureau, "Darwin"))
        self.assertFalse(os.path.exists(cible))
        self.assertFalse(raccourci.retirer(self.bureau, "Darwin"))

    @unittest.skipUnless(platform.system() == "Windows", "un .lnk ne se crée que sous Windows")
    def test_windows_un_raccourci_sans_console(self):
        cible = raccourci.poser(DEPOT, sys.executable, self.bureau, "Windows")
        self.assertTrue(os.path.isfile(cible))
        lu = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             "[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false; "
             "$r = (New-Object -ComObject WScript.Shell).CreateShortcut($env:AM_CIBLE); "
             "[Console]::Out.Write($r.TargetPath + '|' + $r.Arguments + '|' + $r.IconLocation)"],
            env=dict(os.environ, AM_CIBLE=cible), capture_output=True).stdout.decode("utf-8")
        executable, arguments, icone = lu.split("|")
        self.assertIn(os.path.basename(executable).lower(), ("pythonw.exe", "python.exe"))
        self.assertIn("messenger.py", arguments)
        self.assertIn("start --log", arguments)
        self.assertIn("messenger.ico", icone)


if __name__ == "__main__":
    unittest.main()
