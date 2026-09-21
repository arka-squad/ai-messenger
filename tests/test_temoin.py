"""Le témoin : une boîte ne rétrécit jamais, donc on n'écrit jamais sur une lecture qui a rétréci.

Le cas est réel : un partage réseau servi par la machine qui écrit dedans en local sert parfois à
l'autre machine une copie périmée. Écrire par-dessus efface les messages qu'on n'a pas vus — c'est
arrivé le 20/09/2026, six messages perdus (puis rattrapés). Ces tests verrouillent la protection.
"""
import io
import json
import os
import tempfile
import unittest

from arkalabs_messenger.adapters.driven.boite_json import DepotBoiteJson
from arkalabs_messenger.adapters.driven.temoin import LecturePerimee, Temoin
from arkalabs_messenger.application.ports import BoiteIndisponible
from arkalabs_messenger.domain import Boite, Message


def message(mid):
    return Message(id=mid, date="2026-09-20T18:00:00", de="windows", a=("mac",), objet=f"objet {mid}")


class LeTemoin(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.temoin = Temoin(os.path.join(self._tmp.name, "temoins.json"))
        self.boite = os.path.join(self._tmp.name, "boite.json")

    def tearDown(self):
        self._tmp.cleanup()

    def test_il_retient_le_plus_grand_nombre_vu(self):
        self.assertIsNone(self.temoin.lu(self.boite))
        self.temoin.noter(self.boite, 12)
        self.temoin.noter(self.boite, 30)
        self.temoin.noter(self.boite, 7)  # une lecture courte ne fait jamais reculer le témoin
        self.assertEqual(self.temoin.lu(self.boite), 30)

    def test_il_refuse_une_lecture_qui_a_retreci(self):
        self.temoin.noter(self.boite, 63)
        self.temoin.verifier(self.boite, 63)   # égal : la boîte n'a pas bougé
        self.temoin.verifier(self.boite, 64)   # plus longue : elle a grandi
        with self.assertRaises(LecturePerimee) as refus:
            self.temoin.verifier(self.boite, 57)
        self.assertIn("57", str(refus.exception))
        self.assertIn("63", str(refus.exception))
        self.assertIn("stale read", str(refus.exception))

    def test_une_boite_inconnue_ne_bloque_rien(self):
        self.temoin.verifier(self.boite, 0)

    def test_on_peut_oublier_une_boite_deliberement_remplacee(self):
        self.temoin.noter(self.boite, 63)
        self.temoin.oublier(self.boite)
        self.assertIsNone(self.temoin.lu(self.boite))
        self.temoin.verifier(self.boite, 1)

    def test_un_temoin_illisible_ne_bloque_pas_le_courrier(self):
        with io.open(self.temoin._fichier, "w", encoding="utf-8") as f:
            f.write("{ ceci n'est pas du JSON")
        self.temoin.verifier(self.boite, 3)  # aucun témoin exploitable : on laisse passer
        self.temoin.noter(self.boite, 3)

    def test_chaque_boite_a_son_temoin(self):
        autre = os.path.join(self._tmp.name, "autre.json")
        self.temoin.noter(self.boite, 63)
        self.temoin.verifier(autre, 1)


class LeDepotProtege(unittest.TestCase):
    """Le scénario du 20/09 : la boîte a grandi ailleurs, cette machine la relit périmée, et veut écrire."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.chemin = os.path.join(self._tmp.name, "boite.json")
        self.temoin = Temoin(os.path.join(self._tmp.name, "temoins.json"))
        self.depot = DepotBoiteJson(self.chemin, temoin=self.temoin)
        self.depot.creer(Boite(messages=[message(f"m{i}") for i in range(10)]))

    def tearDown(self):
        self._tmp.cleanup()

    def ecrire_dans_le_dos(self, combien):
        """Remplace le fichier sans passer par le dépôt : ce que voit une machine dont la lecture est périmée."""
        with io.open(self.chemin, "w", encoding="utf-8") as f:
            json.dump({"version": 1, "messages": [
                {"id": f"m{i}", "date": "2026-09-20T18:00:00", "de": "windows", "a": ["mac"],
                 "objet": f"objet m{i}", "corps": [], "pj": None, "re": None, "statut": "nouveau",
                 "historique": []} for i in range(combien)]}, f, ensure_ascii=False)

    def test_une_lecture_perimee_ne_peut_pas_ecraser(self):
        self.assertEqual(len(self.depot.lire().messages), 10)
        self.ecrire_dans_le_dos(6)  # la machine relit une copie plus courte
        with self.assertRaises(BoiteIndisponible) as refus:
            with self.depot.transaction() as boite:
                boite.ajouter(message("nouveau"))
        self.assertIn("stale read", str(refus.exception))
        # rien n'a été écrit : le fichier est resté tel que la lecture périmée l'a vu, pas amputé davantage
        self.assertEqual(len(self.depot.lire().messages), 6)

    def test_une_boite_qui_grandit_passe_toujours(self):
        self.ecrire_dans_le_dos(14)
        with self.depot.transaction() as boite:
            boite.ajouter(message("quinze"))
        self.assertEqual(len(self.depot.lire().messages), 15)
        self.assertEqual(self.temoin.lu(self.chemin), 15)

    def test_lire_nourrit_le_temoin_sans_ecrire(self):
        self.ecrire_dans_le_dos(20)
        self.depot.lire()
        self.assertEqual(self.temoin.lu(self.chemin), 20)

    def test_sans_temoin_injecte_le_depot_en_a_un_quand_meme(self):
        """Le garde-fou est actif par défaut : personne n'a à y penser."""
        depot = DepotBoiteJson(os.path.join(self._tmp.name, "autre.json"))
        self.assertIsNotNone(depot._temoin)


if __name__ == "__main__":
    unittest.main()
