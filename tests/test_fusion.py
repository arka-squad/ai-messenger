"""Fusionner deux comptes d'un même agent : le courrier en attente suit, l'adresse mène au compte gardé,
l'historique ne change pas."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

from arkalabs_messenger.domain import (
    Annuaire,
    Compte,
    CompteExistant,
    CompteInconnu,
    MessageInvalide,
    TransitionRefusee,
)

from .doublures import messagerie

DEPOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MESSENGER = os.path.join(DEPOT, "messenger.py")


def annuaire(*noms):
    a = Annuaire()
    for nom in noms:
        a.inscrire(Compte.ouvrir(nom, "claude-code", f"rôle de {nom}"))
    return a


class Domaine(unittest.TestCase):
    def test_fusionner_marque_desactive_et_fait_suivre(self):
        a = annuaire("cloud", "cl-agent-cloud-mac@cortex", "owner")
        marque = a.fusionner("cloud", "cl-agent-cloud-mac@cortex", "2026-09-20")
        self.assertEqual((marque.actif, marque.fusionne_dans), (False, "cl-agent-cloud-mac@cortex"))
        self.assertEqual(a.cible_de("cloud"), "cl-agent-cloud-mac@cortex")
        self.assertEqual(a.resoudre("cloud", None), "cl-agent-cloud-mac@cortex")
        self.assertEqual(a.resoudre("cloud", "talos"), "cl-agent-cloud-mac@cortex")  # depuis n'importe où
        self.assertEqual(a.identites("cl-agent-cloud-mac@cortex"), ["cl-agent-cloud-mac@cortex", "cloud"])
        self.assertNotIn("cloud", a.actifs())

    def test_les_refus(self):
        a = annuaire("cloud", "cible", "autre")
        with self.assertRaisesRegex(MessageInvalide, "itself"):
            a.fusionner("cloud", "cloud")
        with self.assertRaisesRegex(CompteInconnu, "personne"):
            a.fusionner("personne", "cible")
        with self.assertRaisesRegex(CompteInconnu, "personne"):
            a.fusionner("cloud", "personne")
        a.fusionner("cloud", "cible")
        with self.assertRaisesRegex(CompteExistant, "already merged into cible"):
            a.fusionner("cloud", "autre")
        with self.assertRaisesRegex(MessageInvalide, "merged into cible"):
            a.fusionner("autre", "cloud")  # une adresse fusionnée n'absorbe rien
        a.desactiver("autre")
        with self.assertRaisesRegex(MessageInvalide, "inactive"):
            a.fusionner("cible", "autre")

    def test_les_fusions_se_suivent_en_chaine(self):
        a = annuaire("premier", "deuxieme", "troisieme")
        a.fusionner("premier", "deuxieme")
        a.fusionner("deuxieme", "troisieme")
        self.assertEqual(a.cible_de("premier"), "troisieme")
        self.assertEqual(sorted(a.identites("troisieme")), ["deuxieme", "premier", "troisieme"])

    def test_le_carnet_rejoint_le_compte_garde_sans_ecraser(self):
        a = annuaire("cloud", "cible", "owner", "windows")
        a.noter_contact("cloud", "chef", ["owner"])
        a.noter_contact("cloud", "build", ["windows"])
        a.noter_contact("cible", "chef", ["windows"])  # déjà pris : celui de la cible reste
        a.fusionner("cloud", "cible")
        carnet = {c.alias: c.adresses for c in a.compte("cible").contacts}
        self.assertEqual(carnet, {"chef": ("windows",), "build": ("windows",)})

    def test_un_compte_fusionne_ne_se_range_pas_et_ne_se_met_pas_a_jour(self):
        a = annuaire("cloud", "cible")
        a.fusionner("cloud", "cible")
        with self.assertRaisesRegex(MessageInvalide, "merged into cible"):
            a.rattacher("cloud", "cortex")
        with self.assertRaisesRegex(CompteExistant, "merged into cible"):
            a.inscrire(Compte.ouvrir("cloud", "claude-code", "je reviens"), mise_a_jour=True)

    def test_enroll_ne_reutilise_pas_un_compte_fusionne(self):
        a = annuaire("cl-agent-cloud-mac", "cible")
        a.fusionner("cl-agent-cloud-mac", "cible")
        nom, existant = a.nom_libre("cl-agent-cloud-mac", None, None)
        self.assertEqual((nom, existant), ("cl-agent-cloud-mac-2", None))


class CasDUsage(unittest.TestCase):
    def setUp(self):
        self.m, self.boite, *_ = messagerie()
        for nom in ("cloud", "cl-agent-cloud-mac@cortex", "owner", "windows"):
            self.m.inscrire(nom, "claude-code", f"rôle de {nom}",
                            machine="mon-mac" if "cloud" in nom else "ailleurs")

    def test_le_courrier_en_attente_suit_et_se_marque(self):
        attendu = self.m.envoyer("windows", ["cloud"], "Coffre libéré").message
        self.m.fusionner("cloud", "cl-agent-cloud-mac@cortex")
        self.assertEqual([x.id for x in self.m.releve("cl-agent-cloud-mac@cortex")], [attendu.id])
        marque = self.m.marquer("cl-agent-cloud-mac@cortex", attendu.id, "lu")
        self.assertEqual(marque.historique[0].par, "cl-agent-cloud-mac@cortex")  # celui qui agit vraiment
        with self.assertRaises(TransitionRefusee):
            self.m.marquer("windows", attendu.id, "traité")  # personne d'autre
        self.assertEqual([x.id for x in self.m.lister("cl-agent-cloud-mac@cortex")], [attendu.id])

    def test_ecrire_a_l_ancienne_adresse_mene_au_compte_garde(self):
        self.m.fusionner("cloud", "cl-agent-cloud-mac@cortex")
        envoi = self.m.envoyer("windows", ["cloud"], "Tu es là ?")
        self.assertEqual(envoi.message.a, ("cl-agent-cloud-mac@cortex",))
        # …même depuis un carnet noté avant la fusion
        self.m.noter_contact("windows", "lecloud", ["cl-agent-cloud-mac@cortex"])
        self.assertEqual(self.m.envoyer("windows", ["lecloud"], "Encore").message.a, ("cl-agent-cloud-mac@cortex",))

    def test_la_releve_du_poste_compte_le_courrier_herite(self):
        self.m.envoyer("windows", ["cloud"], "En attente depuis avant la fusion")
        self.m.fusionner("cloud", "cl-agent-cloud-mac@cortex")
        attendus = self.m.en_attente_sur_ce_poste("claude-code", "mon-mac")
        self.assertEqual([(c.nom, n) for c, n in attendus], [("cl-agent-cloud-mac@cortex", 1)])

    def test_reprendre_un_compte_fusionne_renvoie_au_bon(self):
        self.m.fusionner("cloud", "cl-agent-cloud-mac@cortex")
        with self.assertRaisesRegex(CompteExistant, 'identify as "cl-agent-cloud-mac@cortex"'):
            self.m.reprendre("cloud", "claude-code", "mon-mac")


class LigneDeCommande(unittest.TestCase):
    def test_de_bout_en_bout(self):
        with tempfile.TemporaryDirectory() as dossier:
            env = dict(os.environ, HOME=dossier, USERPROFILE=dossier, PYTHONIOENCODING="utf-8")
            for cle in ("MESSENGER_BOX", "MESSENGER_AGENT", "MESSENGER_PROJECT"):
                env.pop(cle, None)
            boite = os.path.join(dossier, "partage")

            def cmd(*args, code=0):
                r = subprocess.run([sys.executable, MESSENGER, *args, "--box", boite], capture_output=True,
                                   text=True, encoding="utf-8", env=env, cwd=dossier)
                self.assertEqual(r.returncode, code, r.stderr)
                return r.stdout

            cmd("init")
            for nom in ("cloud", "garde", "windows"):
                cmd("register", "--agent", nom, "--host", "claude-code", "--role", "test")
            mid = cmd("send", "--agent", "windows", "--to", "cloud", "--subject", "Avant la fusion").strip()
            sortie = cmd("merge", "--account", "cloud", "--into", "garde")
            self.assertIn("cloud → merged into garde", sortie)
            self.assertIn("1 nouveau message(s) to check", sortie)
            self.assertIn(mid, cmd("check", "--agent", "garde"))
            cmd("mark", "--agent", "garde", "--id", mid, "--status", "lu")
            apres = cmd("send", "--agent", "windows", "--to", "cloud", "--subject", "Après").strip()
            dernier = json.loads(cmd("list", "--json", "--limit", "1"))[0]
            self.assertEqual((dernier["id"], dernier["a"]), (apres, ["garde"]))
            manifeste = json.load(open(os.path.join(boite, ".aimessenger", "manifest.json"), encoding="utf-8"))
            ancien = next(c for c in manifeste["comptes"] if c["nom"] == "cloud")
            self.assertEqual((ancien["actif"], ancien["fusionne_dans"]), (False, "garde"))
            cmd("merge", "--account", "cloud", "--into", "windows", code=1)  # déjà fusionné


if __name__ == "__main__":
    unittest.main()
