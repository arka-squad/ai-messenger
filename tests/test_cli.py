"""La ligne de commande, de bout en bout, telle que les agents l'appellent."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

DEPOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MESSENGER = os.path.join(DEPOT, "messenger.py")
ANCIENNE = os.path.join(DEPOT, "tests", "donnees", "ancienne-boite.md")


class LigneDeCommande(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dossier = self._tmp.name
        self.boite = os.path.join(self.dossier, "partage", "boite.json")
        self.env = dict(os.environ, HOME=self.dossier, USERPROFILE=self.dossier, PYTHONIOENCODING="utf-8")
        for cle in ("MESSENGER_BOX", "MESSENGER_AGENT", "MESSENGER_PROJECT"):
            self.env.pop(cle, None)

    def tearDown(self):
        self._tmp.cleanup()

    def cmd(self, *args, box=True):
        argv = [sys.executable, MESSENGER, *args] + (["--box", self.boite] if box else [])
        r = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", env=self.env, cwd=self.dossier)
        return r.returncode, r.stdout, r.stderr

    def inscrire(self, *noms):
        for nom in noms:
            self.assertEqual(self.cmd("register", "--agent", nom, "--host", "claude-code", "--role", "test")[0], 0)

    def test_parcours_complet(self):
        code, out, _ = self.cmd("init")
        self.assertEqual(code, 0)
        self.assertIn("mailbox created", out)
        self.inscrire("windows", "kimi")

        code, mid, _ = self.cmd("send", "--agent", "windows", "--to", "kimi", "--subject", "Build prêt",
                                "--body", "Ligne 1\nLigne 2")
        mid = mid.strip()
        self.assertEqual(code, 0)

        code, out, _ = self.cmd("check", "--agent", "kimi")
        self.assertEqual(code, 0)
        self.assertIn(f"- {mid} · Build prêt", out)
        self.assertIn("If you are not kimi, this mail is not addressed to you: ignore it", out)
        self.assertEqual(self.cmd("check", "--agent", "kimi", "--wake")[0], 2)
        self.assertEqual(self.cmd("check", "--agent", "windows")[1], "")

        code, out, _ = self.cmd("check", "--agent", "kimi", "--json")
        self.assertEqual(json.loads(out)["nouveaux"][0]["id"], mid)

        self.assertEqual(self.cmd("mark", "--agent", "windows", "--id", mid, "--status", "lu")[0], 1)
        self.assertEqual(self.cmd("mark", "--agent", "kimi", "--id", mid, "--status", "lu")[0], 0)

        code, reponse, _ = self.cmd("send", "--agent", "kimi", "--to", "windows", "--subject", "Reçu",
                                    "--reply-to", mid)
        code, out, _ = self.cmd("list", "--json")
        liste = json.loads(out)
        self.assertEqual([m["id"] for m in liste], [reponse.strip(), mid])
        self.assertEqual(liste[0]["re"], mid)
        self.assertEqual(liste[1]["historique"][0]["par"], "kimi")

        with open(os.path.join(self.dossier, "partage", "boite.md"), encoding="utf-8") as f:
            self.assertIn(f"Re: {mid} — Reçu", f.read())

    def test_refus_en_code_1(self):
        self.cmd("init")
        self.inscrire("windows")
        cas = [
            ("send", "--agent", "windows", "--to", "kimi-mc", "--subject", "s"),
            ("send", "--agent", "windows", "--to", "windows", "--subject", "s", "--body", "a\nb\nc"),
            ("register", "--agent", "windows", "--host", "x", "--role", "doublon"),
            ("register", "--agent", "Kimi", "--host", "x", "--role", "y"),
            ("send", "--agent", "windows"),  # argument manquant : code 1, jamais 2
        ]
        for args in cas:
            with self.subTest(args=args):
                self.assertEqual(self.cmd(*args)[0], 1)

    def test_check_reste_muet_si_la_boite_est_injoignable(self):
        self.assertEqual(self.cmd("check", "--agent", "kimi"), (0, "", ""))

    def test_setup_memorise_la_boite(self):
        self.cmd("init")
        self.assertEqual(self.cmd("setup")[0], 0)
        self.assertEqual(self.cmd("list", box=False)[0], 0)

    def test_migrate_puis_utilisation(self):
        code, out, _ = self.cmd("migrate", "--from", ANCIENNE)
        self.assertEqual(code, 0)
        self.assertIn("3 messages imported", out)
        self.assertIn("mac", self.cmd("agents")[1])
        self.assertIn("20260917-2250-mac", self.cmd("check", "--agent", "windows")[1])

    def test_ancienne_boite_lisible_mais_pas_modifiable(self):
        argv = ("--box", ANCIENNE)
        code, out, _ = self.cmd("list", *argv, box=False)
        self.assertEqual(code, 0)
        self.assertIn("20260918-2300-windows", out)
        code, _, err = self.cmd("mark", "--agent", "windows", "--id", "20260917-2250-mac", "--status", "lu",
                                *argv, box=False)
        self.assertEqual(code, 1)
        self.assertIn("read-only", err)


if __name__ == "__main__":
    unittest.main()
