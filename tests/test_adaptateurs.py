"""Les adaptateurs pilotés, sur de vrais fichiers dans un dossier temporaire."""
import json
import os
import tempfile
import time
import unittest

from arkalabs_messenger.adapters.driven import (
    DepotAnnuaireJson,
    DepotBoiteJson,
    DepotBoiteMarkdown,
    PiecesDossier,
    SourceMarkdown,
    VueMarkdown,
)
from arkalabs_messenger.adapters.driven.fichiers import verrou
from arkalabs_messenger.application import BoiteIndisponible, LectureSeule, PieceJointeRefusee
from arkalabs_messenger.bootstrap import Usine
from arkalabs_messenger.domain import Boite, Compte, Message

ANCIENNE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "donnees", "ancienne-boite.md")


class Dossier(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dossier = self._tmp.name
        self.boite = os.path.join(self.dossier, "boite.json")

    def tearDown(self):
        self._tmp.cleanup()


class BoiteJson(Dossier):
    def test_cree_ecrit_et_publie_la_vue(self):
        depot = DepotBoiteJson(self.boite, vue=VueMarkdown.pour(self.boite))
        depot.creer()
        with depot.transaction() as b:
            b.ajouter(Message(id="1", date="d", de="windows", a=("kimi",), objet="Objet", corps=("Ligne",),
                              pj="detail.md", re=None))
        with open(self.boite, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["messages"][0]["pj"], "detail.md")
        with open(os.path.join(self.dossier, "boite.md"), encoding="utf-8") as f:
            vue = f.read()
        self.assertIn("### 1 · Objet", vue)
        self.assertIn("**De** windows → **À** kimi · **Statut** nouveau · **PJ** [detail.md](detail.md)", vue)

    def test_conserve_les_champs_inconnus(self):
        with open(self.boite, "w", encoding="utf-8") as f:
            json.dump({"version": 1, "extension": {"x": 1}, "messages": [
                {"id": "1", "date": "d", "de": "windows", "a": ["kimi"], "objet": "o", "corps": [], "pj": None,
                 "re": None, "statut": "nouveau", "historique": [], "priorite": "haute"}]}, f)
        depot = DepotBoiteJson(self.boite)
        with depot.transaction() as b:
            b.marquer("1", "kimi", "lu", "t")
        with open(self.boite, encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["extension"], {"x": 1})
        self.assertEqual(data["messages"][0]["priorite"], "haute")
        self.assertEqual(data["messages"][0]["statut"], "lu")

    def test_une_erreur_n_ecrit_rien(self):
        depot = DepotBoiteJson(self.boite)
        depot.creer()
        avant = depot.version()
        with self.assertRaises(RuntimeError):
            with depot.transaction() as b:
                b.messages.append(Message(id="1", date="d", de="a", a=("b",), objet="o"))
                raise RuntimeError("interrompu")
        self.assertEqual(depot.lire().messages, [])
        self.assertEqual(depot.version(), avant)

    def test_boite_absente_illisible_ou_non_conforme(self):
        depot = DepotBoiteJson(self.boite)
        with self.assertRaisesRegex(BoiteIndisponible, "introuvable"):
            depot.lire()
        for contenu, motif in (("{pas du json", "JSON invalide"), ('{"version": 1}', "non conforme")):
            with open(self.boite, "w", encoding="utf-8") as f:
                f.write(contenu)
            with self.assertRaisesRegex(BoiteIndisponible, motif):
                depot.lire()


class Verrou(Dossier):
    def test_leve_un_verrou_abandonne(self):
        lock = self.boite + ".lock"
        open(lock, "w").close()
        ancien = time.time() - 120
        os.utime(lock, (ancien, ancien))
        with verrou(self.boite):
            self.assertTrue(os.path.exists(lock))
        self.assertFalse(os.path.exists(lock))

    def test_attend_puis_renonce(self):
        open(self.boite + ".lock", "w").close()
        with self.assertRaisesRegex(BoiteIndisponible, "verrouillé"):
            with verrou(self.boite, attente=0.3):
                pass


class Annuaire(Dossier):
    def test_absent_puis_cree(self):
        depot = DepotAnnuaireJson(os.path.join(self.dossier, "boite.manifest.json"), "boite.json")
        self.assertFalse(depot.existe())
        self.assertEqual(depot.lire().comptes, [])
        depot.creer()
        with depot.transaction() as a:
            a.inscrire(Compte.ouvrir("kimi-mac", "kimi-code", "dev"))
        with open(os.path.join(self.dossier, "boite.manifest.json"), encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual((data["boite"], data["comptes"][0]["nom"]), ("boite.json", "kimi-mac"))


class Pieces(Dossier):
    def test_depose_refuse_un_doublon_et_localise(self):
        source = os.path.join(self.dossier, "ailleurs")
        os.makedirs(source)
        fichier = os.path.join(source, "rapport.md")
        with open(fichier, "w", encoding="utf-8") as f:
            f.write("détail")
        pieces = PiecesDossier(self.dossier)
        self.assertEqual(pieces.deposer(fichier), "rapport.md")
        with self.assertRaisesRegex(PieceJointeRefusee, "existe déjà"):
            pieces.deposer(fichier)
        self.assertEqual(pieces.deposer(os.path.join(self.dossier, "rapport.md")), "rapport.md")
        self.assertIsNotNone(pieces.localiser("rapport.md"))
        for nom in ("../rapport.md", "..", "absent.md", ""):
            self.assertIsNone(pieces.localiser(nom))


class AncienneBoite(unittest.TestCase):
    def test_lit_l_ancien_format(self):
        messages = SourceMarkdown(ANCIENNE).messages()
        self.assertEqual([m.id for m in messages], ["20260917-2250-mac", "20260918-2248-kimi", "20260918-2300-windows"])
        kimi, windows = messages[1], messages[2]
        self.assertEqual((kimi.a, kimi.pj, kimi.statut, kimi.corps),
                         (("windows", "owner"), "note-kimi.md", "traité", ("Hooks posés.", "Guetteur de fond en place.")))
        self.assertEqual((windows.re, windows.objet), ("20260918-2248-kimi", "Liaison confirmée"))
        self.assertTrue(all(m.importe for m in messages))

    def test_s_ouvre_en_lecture_seule(self):
        depot = DepotBoiteMarkdown(ANCIENNE)
        self.assertEqual(len(depot.lire().messages), 3)
        with self.assertRaises(LectureSeule):
            with depot.transaction():
                pass

    def test_la_vue_generee_se_relit_a_l_identique(self):
        boite = Boite(SourceMarkdown(ANCIENNE).messages())
        with tempfile.TemporaryDirectory() as dossier:
            vue = os.path.join(dossier, "boite.md")
            VueMarkdown(vue, "boite.json", "boite.manifest.json")(boite)
            relus = SourceMarkdown(vue).messages()
        self.assertEqual(relus, boite.messages)


class Assemblage(Dossier):
    def test_choisit_l_adaptateur_selon_l_extension(self):
        usine = Usine()
        self.assertFalse(usine.ouvrir(self.boite).lecture_seule)
        self.assertTrue(usine.ouvrir(ANCIENNE).lecture_seule)
        with self.assertRaises(BoiteIndisponible):
            usine.ouvrir(os.path.join(self.dossier, "boite.txt"))


if __name__ == "__main__":
    unittest.main()
