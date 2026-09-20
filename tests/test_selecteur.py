"""Le sélecteur de dossier natif : une panne ne passe jamais pour une annulation."""
import subprocess
import threading
import unittest

from arkalabs_messenger.adapters.driving import poste


class Lecture(unittest.TestCase):
    def test_un_dossier_choisi(self):
        self.assertEqual(poste.lire_selecteur("Windows", 0, "C:\\Projets\\Été\r\n".encode("utf-8"), b""),
                         "C:\\Projets\\Été")
        self.assertEqual(poste.lire_selecteur("Windows", 0, b"\xef\xbb\xbfC:\\Projets", b""), "C:\\Projets")  # BOM
        self.assertEqual(poste.lire_selecteur("Darwin", 0, b"/Users/moi/depot/\n", b""), "/Users/moi/depot/")

    def test_une_annulation_rend_none(self):
        self.assertIsNone(poste.lire_selecteur("Windows", 0, b"", b""))
        self.assertIsNone(poste.lire_selecteur("Darwin", 1, b"", b"execution error: User canceled. (-128)"))
        self.assertIsNone(poste.lire_selecteur("Linux", 1, b"", b""))

    def test_une_panne_se_dit(self):
        for systeme, code, erreurs in (
                ("Windows", 1, b"Add-Type : Impossible de charger l'assembly"),
                ("Darwin", 1, b"execution error: No user interaction allowed. (-1713)"),
                ("Darwin", 143, b""),      # la fenêtre a été tuée
                ("Linux", 5, b""),         # zenity : délai dépassé
                ("Linux", 255, b"cannot open display")):
            with self.subTest(systeme=systeme, code=code):
                with self.assertRaisesRegex(poste.SelecteurIndisponible, f"code {code}"):
                    poste.lire_selecteur(systeme, code, b"", erreurs)


class Commandes(unittest.TestCase):
    def test_une_commande_par_systeme(self):
        windows = poste.commandes_selecteur("Windows")[0]
        self.assertEqual(windows[0], "powershell")
        self.assertIn("-STA", windows)  # les boîtes de dialogue Windows exigent un fil STA
        self.assertIn("TopMost = $true", windows[-1])  # sinon la fenêtre s'ouvre derrière le navigateur
        self.assertIn("UTF8Encoding", windows[-1])
        self.assertIn("tell me to activate", poste.commandes_selecteur("Darwin")[0])
        self.assertEqual([c[0] for c in poste.commandes_selecteur("Linux")], ["zenity", "kdialog"])


class Ouverture(unittest.TestCase):
    def setUp(self):
        self._run, self._systeme = subprocess.run, poste.platform.system
        poste.platform.system = lambda: "Linux"

    def tearDown(self):
        subprocess.run, poste.platform.system = self._run, self._systeme

    def test_on_essaie_le_selecteur_suivant_puis_on_dit_qu_il_n_y_en_a_pas(self):
        essais = []

        def absent(commande, **_):
            essais.append(commande[0])
            raise FileNotFoundError(commande[0])

        subprocess.run = absent
        with self.assertRaisesRegex(poste.SelecteurIndisponible, "zenity, kdialog introuvable"):
            poste.choisir_dossier()
        self.assertEqual(essais, ["zenity", "kdialog"])

    def test_le_second_selecteur_sert_si_le_premier_manque(self):
        def run(commande, **_):
            if commande[0] == "zenity":
                raise FileNotFoundError("zenity")
            return subprocess.CompletedProcess(commande, 0, b"/home/moi/depot\n", b"")

        subprocess.run = run
        self.assertEqual(poste.choisir_dossier(), "/home/moi/depot")

    def test_une_fenetre_oubliee_est_fermee_et_on_le_dit(self):
        def trop_long(commande, **options):
            raise subprocess.TimeoutExpired(commande, options["timeout"])

        subprocess.run = trop_long
        with self.assertRaisesRegex(poste.SelecteurIndisponible, "trop longtemps"):
            poste.choisir_dossier()

    def test_une_seule_fenetre_a_la_fois(self):
        ouverte, fermer = threading.Event(), threading.Event()

        def bloquant(commande, **_):
            ouverte.set()
            fermer.wait(10)
            return subprocess.CompletedProcess(commande, 0, b"/home/moi/depot", b"")

        subprocess.run = bloquant
        resultats = []
        fil = threading.Thread(target=lambda: resultats.append(poste.choisir_dossier()))
        fil.start()
        self.assertTrue(ouverte.wait(10))
        with self.assertRaisesRegex(poste.SelecteurIndisponible, "déjà ouverte"):
            poste.choisir_dossier()
        fermer.set()
        fil.join(10)
        self.assertEqual(resultats, ["/home/moi/depot"])
        self.assertEqual(poste.choisir_dossier(), "/home/moi/depot")  # le verrou est bien rendu


if __name__ == "__main__":
    unittest.main()
