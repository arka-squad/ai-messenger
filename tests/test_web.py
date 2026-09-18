"""L'API web : ce que l'interface lit, ce qu'elle peut faire, ce qui est refusé."""
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

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

    def test_la_version_change_a_chaque_ecriture(self):
        avant = json.loads(self.get("/api/version")[2])["version"]
        self.post({"id": self.pour_owner.message.id, "statut": "lu"})
        self.assertNotEqual(json.loads(self.get("/api/version")[2])["version"], avant)


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
