"""L'API web : ce que l'interface lit, ce qu'elle peut faire, ce qui est refusé."""
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from arkalabs_messenger.adapters.driving import hotes, poste
from arkalabs_messenger.adapters.driving.web import creer_serveur
from arkalabs_messenger.application import Annonceur
from arkalabs_messenger.bootstrap import Usine

from .test_annonces import NotificateurMemoire

ANCIENNE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "donnees", "ancienne-boite.md")


class Api(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        dossier = self._tmp.name
        with open(os.path.join(dossier, "note.md"), "w", encoding="utf-8") as f:
            f.write("# Détail\n<script>alert(1)</script>\n")
        self.messagerie = Usine().ouvrir(os.path.join(dossier, "boite.json"))
        self.messagerie.initialiser()
        for nom in ("windows", "owner"):
            self.messagerie.inscrire(nom, "claude-code", "test")
        self.pour_owner = self.messagerie.envoyer("windows", ["owner"], "À toi", piece=os.path.join(dossier, "note.md"))
        self.pour_windows = self.messagerie.envoyer("owner", ["windows"], "Pas à toi")
        self.demarrer(self.messagerie)

    def demarrer(self, messagerie):
        self.annonceur = Annonceur(messagerie, NotificateurMemoire(), "owner")
        self.serveur = creer_serveur(messagerie, "owner", port=0, annonceur=self.annonceur)
        self.base = f"http://127.0.0.1:{self.serveur.server_address[1]}"
        threading.Thread(target=self.serveur.serve_forever, daemon=True).start()

    def tearDown(self):
        self.serveur.shutdown()
        self.serveur.server_close()
        self._tmp.cleanup()

    def get(self, chemin):
        with urllib.request.urlopen(self.base + chemin) as r:
            return r.status, r.headers, r.read()

    def post(self, corps, origine=True, type_="application/json", chemin="/api/statut"):
        entetes = {"Content-Type": type_}
        if origine:
            entetes["Origin"] = self.base
        req = urllib.request.Request(self.base + chemin, data=json.dumps(corps).encode(), headers=entetes)
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_la_boite_dit_ce_que_le_compte_peut_faire(self):
        _, _, corps = self.get("/api/boite")
        etat = json.loads(corps)
        suites = {m["id"]: m["suite"] for m in etat["messages"]}
        self.assertEqual(suites[self.pour_owner.message.id], "lu")
        self.assertIsNone(suites[self.pour_windows.message.id])
        self.assertEqual(etat["compte"], "owner")
        self.assertFalse(etat["source"]["lecture_seule"])
        self.assertEqual({c["nom"] for c in etat["comptes"]}, {"windows", "owner"})

    def test_faire_avancer_un_statut(self):
        code, reponse = self.post({"id": self.pour_owner.message.id, "statut": "lu"})
        self.assertEqual((code, reponse["message"]["statut"]), (200, "lu"))
        self.assertEqual(self.messagerie.instantane().message(self.pour_owner.message.id).statut, "lu")

    def test_refus_du_domaine(self):
        code, reponse = self.post({"id": self.pour_windows.message.id, "statut": "lu"})
        self.assertEqual(code, 409)
        self.assertIn("n'est pas destinataire", reponse["erreur"])

    def test_refus_d_une_autre_origine_ou_d_un_autre_format(self):
        self.assertEqual(self.post({"id": "x", "statut": "lu"}, origine=False)[0], 403)
        self.assertEqual(self.post({"id": "x", "statut": "lu"}, type_="text/plain")[0], 415)

    def test_la_piece_jointe_est_servie_comme_texte_isole(self):
        _, entetes, corps = self.get("/pj/note.md")
        self.assertTrue(entetes["Content-Type"].startswith("text/plain"))
        self.assertEqual(entetes["Content-Security-Policy"], "sandbox")
        self.assertIn("Détail", corps.decode("utf-8"))

    def test_seules_les_pieces_referencees_sont_servies(self):
        for chemin in ("/pj/boite.json", "/pj/..%2Fboite.json", "/pj/absent.md"):
            with self.subTest(chemin=chemin):
                with self.assertRaises(urllib.error.HTTPError) as e:
                    self.get(chemin)
                self.assertEqual(e.exception.code, 404)

    def test_couper_et_retablir_les_notifications(self):
        self.assertTrue(json.loads(self.get("/api/boite")[2])["notifications"])
        self.assertEqual(self.post({"actives": False}, chemin="/api/notifications"), (200, {"notifications": False}))
        self.assertFalse(self.annonceur.actif)
        self.assertFalse(json.loads(self.get("/api/boite")[2])["notifications"])
        self.assertEqual(self.post({"actives": "oui"}, chemin="/api/notifications")[0], 400)
        self.assertEqual(self.post({"actives": True}, origine=False, chemin="/api/notifications")[0], 403)

    def test_choisir_dossier_relaye_le_selecteur_natif(self):
        original = poste.choisir_dossier
        poste.choisir_dossier = lambda: "/chemin/choisi"
        try:
            self.assertEqual(self.post({}, chemin="/api/choisir-dossier"), (200, {"dossier": "/chemin/choisi"}))
        finally:
            poste.choisir_dossier = original

    def test_choisir_dossier_indisponible_rend_501(self):
        original = poste.choisir_dossier

        def indispo():
            raise poste.SelecteurIndisponible("pas de sélecteur")

        poste.choisir_dossier = indispo
        try:
            self.assertEqual(self.post({}, chemin="/api/choisir-dossier")[0], 501)
        finally:
            poste.choisir_dossier = original

    def test_la_version_change_a_chaque_ecriture(self):
        avant = json.loads(self.get("/api/version")[2])["version"]
        self.post({"id": self.pour_owner.message.id, "statut": "lu"})
        self.assertNotEqual(json.loads(self.get("/api/version")[2])["version"], avant)


class Activation(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dossier = self._tmp.name
        self._config, self._contexte = poste.CONFIG, hotes.contexte
        poste.CONFIG = os.path.join(self.dossier, "poste.json")  # ne pas toucher au vrai config du poste
        # …ni à la vraie configuration des hôtes IA : un faux dossier personnel, où seul Claude Code existe
        self.home = os.path.join(self.dossier, "home")
        os.makedirs(os.path.join(self.home, ".claude"))
        hotes.contexte = lambda depot: hotes.Contexte(depot, home=self.home, env={})
        os.makedirs(os.path.join(self.dossier, "partage"))
        self.messagerie = Usine().ouvrir(os.path.join(self.dossier, "partage", "boite.json"))
        self.messagerie.initialiser()
        self.serveur = creer_serveur(self.messagerie, "owner", port=0, depot=Usine().depot())
        self.base = f"http://127.0.0.1:{self.serveur.server_address[1]}"
        threading.Thread(target=self.serveur.serve_forever, daemon=True).start()

    def tearDown(self):
        poste.CONFIG, hotes.contexte = self._config, self._contexte
        self.serveur.shutdown()
        self.serveur.server_close()
        self._tmp.cleanup()

    def post(self, corps):
        req = urllib.request.Request(self.base + "/api/activer", data=json.dumps(corps).encode(),
                                     headers={"Content-Type": "application/json", "Origin": self.base})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_activer_un_depot_depuis_l_interface(self):
        repo = os.path.join(self.dossier, "repo")
        os.makedirs(repo)
        code, rep = self.post({"dossier": repo, "projet": "demo"})
        self.assertEqual(code, 200)
        self.assertEqual(rep["projet"], "demo")
        # le projet est connu de la boîte tout de suite, avant qu'un agent s'y enrôle
        self.assertEqual(self.messagerie.projets(), ["demo"])
        with urllib.request.urlopen(self.base + "/api/boite") as r:
            self.assertEqual(json.loads(r.read())["projets"], ["demo"])
        # le dépôt n'est que déclaré : rien de propre à un hôte n'y est écrit
        self.assertTrue(os.path.isfile(os.path.join(repo, ".messenger.json")))
        self.assertFalse(os.path.exists(os.path.join(repo, ".claude")))
        # l'hôte présent sur le poste est équipé, dans sa propre configuration
        self.assertEqual([(h["id"], h["equipe"]) for h in rep["hotes"]], [("claude-code", True)])
        self.assertTrue(os.path.isfile(os.path.join(self.home, ".claude.json")))
        self.assertTrue(os.path.isfile(os.path.join(self.home, ".claude", "settings.json")))

    def test_activer_refuse_un_dossier_absent(self):
        code, rep = self.post({"dossier": os.path.join(self.dossier, "absent"), "projet": "demo"})
        self.assertEqual(code, 400)
        self.assertIn("introuvable", rep["erreur"])


class CreationDepuisLInterface(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dossier = self._tmp.name
        self._config = poste.CONFIG
        poste.CONFIG = os.path.join(self.dossier, "poste.json")  # ne pas toucher au vrai config du poste
        self.usine = Usine()
        repli = os.path.join(self.dossier, "repli")  # tient lieu de démonstration
        self.usine.ouvrir(repli).initialiser()

        def resolveur():
            chemin = poste.resoudre_boite(None)
            if chemin:
                return self.usine.ouvrir(chemin), False
            return self.usine.ouvrir(repli), True

        self.serveur = creer_serveur(None, "owner", port=0, depot=self.usine.depot(),
                                     resolveur=resolveur, usine=self.usine)
        self.base = f"http://127.0.0.1:{self.serveur.server_address[1]}"
        threading.Thread(target=self.serveur.serve_forever, daemon=True).start()

    def tearDown(self):
        poste.CONFIG = self._config
        self.serveur.shutdown()
        self.serveur.server_close()
        self._tmp.cleanup()

    def get_boite(self):
        with urllib.request.urlopen(self.base + "/api/boite") as r:
            return json.loads(r.read())

    def post_creer(self, dossier):
        req = urllib.request.Request(self.base + "/api/creer", data=json.dumps({"dossier": dossier}).encode(),
                                     headers={"Content-Type": "application/json", "Origin": self.base})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_creer_une_boite_puis_basculer_dessus(self):
        avant = self.get_boite()["source"]
        self.assertTrue(avant["demonstration"])
        self.assertFalse(avant["activable"])

        cible = os.path.join(self.dossier, "partage")
        code, rep = self.post_creer(cible)
        self.assertEqual(code, 200)
        self.assertTrue(rep["cree"])
        self.assertTrue(os.path.isfile(os.path.join(cible, ".aimessenger", "mail", "boite.json")))

        apres = self.get_boite()["source"]
        self.assertFalse(apres["demonstration"])
        self.assertTrue(apres["activable"])


class AncienneBoite(unittest.TestCase):
    def test_lecture_seule(self):
        serveur = creer_serveur(Usine().ouvrir(ANCIENNE), "windows", port=0)
        base = f"http://127.0.0.1:{serveur.server_address[1]}"
        threading.Thread(target=serveur.serve_forever, daemon=True).start()
        try:
            with urllib.request.urlopen(base + "/api/boite") as r:
                etat = json.loads(r.read())
            self.assertTrue(etat["source"]["lecture_seule"])
            self.assertIsNone(etat["notifications"])
            self.assertTrue(all(m["suite"] is None for m in etat["messages"]))
            req = urllib.request.Request(base + "/api/statut", method="POST",
                                         data=b'{"id": "20260917-2250-mac", "statut": "lu"}',
                                         headers={"Content-Type": "application/json", "Origin": base})
            with self.assertRaises(urllib.error.HTTPError) as e:
                urllib.request.urlopen(req)
            self.assertEqual(e.exception.code, 409)
        finally:
            serveur.shutdown()
            serveur.server_close()


if __name__ == "__main__":
    unittest.main()
