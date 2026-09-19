"""L'arbo imposée `.aimessenger/`, et la lecture des anciennes boîtes."""
import os
import subprocess
import sys
import tempfile
import unittest

from arkalabs_messenger.adapters.driven.disposition import resoudre

DEPOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MESSENGER = os.path.join(DEPOT, "messenger.py")


def _n(chemin: str) -> str:
    return chemin.replace("\\", "/")


class Resolveur(unittest.TestCase):
    def test_un_dossier_impose_aimessenger(self):
        d = resoudre(os.path.join("partage"))
        self.assertTrue(_n(d.boite).endswith("/partage/.aimessenger/mail/boite.json"))
        self.assertTrue(_n(d.manifeste).endswith("/partage/.aimessenger/manifest.json"))
        self.assertTrue(_n(d.vue).endswith("/partage/.aimessenger/boite.md"))
        self.assertTrue(_n(d.pieces).endswith("/partage/.aimessenger/pj"))
        self.assertFalse(d.markdown)

    def test_json_a_plat_reste_l_heritage(self):
        d = resoudre(os.path.join("dossier", "boite.json"))
        self.assertTrue(_n(d.boite).endswith("/dossier/boite.json"))
        self.assertTrue(_n(d.manifeste).endswith("/dossier/boite.manifest.json"))
        self.assertTrue(_n(d.pieces).endswith("/dossier"))
        self.assertFalse(d.markdown)

    def test_md_est_en_lecture_seule(self):
        d = resoudre(os.path.join("dossier", "vieux.md"))
        self.assertTrue(d.markdown)
        self.assertIsNone(d.vue)

    def test_un_chemin_dans_aimessenger_retrouve_sa_racine(self):
        d = resoudre(os.path.join("partage", ".aimessenger", "mail", "boite.json"))
        self.assertTrue(_n(d.racine).endswith("/partage/.aimessenger"))
        self.assertTrue(_n(d.pieces).endswith("/partage/.aimessenger/pj"))


class ArboBoutEnBout(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dossier = self._tmp.name
        self.env = dict(os.environ, HOME=self.dossier, USERPROFILE=self.dossier, PYTHONIOENCODING="utf-8")
        for cle in ("MESSENGER_BOX", "MESSENGER_AGENT", "MESSENGER_PROJECT"):
            self.env.pop(cle, None)

    def tearDown(self):
        self._tmp.cleanup()

    def cmd(self, *args):
        r = subprocess.run([sys.executable, MESSENGER, *args], capture_output=True, text=True,
                           encoding="utf-8", env=self.env, cwd=self.dossier)
        return r.returncode, r.stdout, r.stderr

    def test_init_cree_l_arbo_et_range_les_pieces_jointes(self):
        partage = os.path.join(self.dossier, "partage")
        os.makedirs(partage)
        code, out, err = self.cmd("init", "--box", partage)
        self.assertEqual(code, 0, err)
        base = os.path.join(partage, ".aimessenger")
        self.assertTrue(os.path.isfile(os.path.join(base, "mail", "boite.json")))
        self.assertTrue(os.path.isfile(os.path.join(base, "manifest.json")))
        self.assertTrue(os.path.isfile(os.path.join(base, "boite.md")))

        for nom in ("owner", "windows"):
            self.cmd("register", "--agent", nom, "--host", "claude-code", "--role", "test", "--box", partage)
        note = os.path.join(self.dossier, "note.md")
        with open(note, "w", encoding="utf-8") as f:
            f.write("# détail\n")
        code, mid, err = self.cmd("send", "--agent", "windows", "--to", "owner", "--subject", "Coucou",
                                  "--attach", note, "--box", partage)
        self.assertEqual(code, 0, err)
        self.assertTrue(os.path.isfile(os.path.join(base, "pj", "note.md")))


if __name__ == "__main__":
    unittest.main()
