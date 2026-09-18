"""Plusieurs projets, une boîte : chaque dépôt a ses agents, et les projets se parlent."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

from arkalabs_messenger.domain import (
    Annuaire,
    Compte,
    Message,
    NomInvalide,
    projet_de,
    qualifier,
    valider_adresse,
)

from .doublures import messagerie

MESSENGER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "messenger.py")


class Adresses(unittest.TestCase):
    def test_nom_ou_nom_arobase_projet(self):
        for adresse in ("owner", "claude-windows@cortex", "kimi.mac@talos-2"):
            self.assertEqual(valider_adresse(adresse), adresse)
        for adresse in ("a@", "@b", "a@b@c", "Kimi@cortex", "a@B"):
            with self.assertRaises(NomInvalide):
                valider_adresse(adresse)

    def test_projet_et_qualification(self):
        self.assertEqual(projet_de("claude-windows@cortex"), "cortex")
        self.assertIsNone(projet_de("owner"))
        self.assertEqual(qualifier("kimi", "cortex"), "kimi@cortex")
        self.assertEqual(qualifier("kimi@talos", "cortex"), "kimi@talos")
        self.assertEqual(qualifier("kimi", None), "kimi")

    def test_un_nom_court_se_cherche_dans_le_projet_puis_parmi_les_comptes_communs(self):
        a = Annuaire()
        for nom in ("kimi@cortex", "kimi@talos", "owner"):
            a.inscrire(Compte.ouvrir(nom, "x", "rôle"))
        self.assertEqual(a.resoudre("kimi", "cortex"), "kimi@cortex")
        self.assertEqual(a.resoudre("kimi", "talos"), "kimi@talos")
        self.assertEqual(a.resoudre("owner", "cortex"), "owner")
        self.assertEqual(a.resoudre("kimi@talos", "cortex"), "kimi@talos")
        self.assertEqual(a.resoudre("inconnu", "cortex"), "inconnu@cortex")
        self.assertEqual(a.projets(), ["cortex", "talos"])

    def test_un_message_touche_les_projets_de_ses_adresses(self):
        m = Message(id="1", date="d", de="kimi@cortex", a=("codex@talos", "owner"), objet="o")
        self.assertTrue(m.touche_le_projet("cortex"))
        self.assertTrue(m.touche_le_projet("talos"))
        self.assertFalse(m.touche_le_projet("autre"))


class CasDUsage(unittest.TestCase):
    def setUp(self):
        self.m, *_ = messagerie()
        for nom in ("claude-windows@cortex", "kimi-mac@cortex", "claude-windows@talos", "owner"):
            self.m.inscrire(nom, "claude-code", "rôle")

    def test_la_meme_ia_a_une_boite_par_projet(self):
        self.m.envoyer("kimi-mac@cortex", ["claude-windows"], "Pour Claude sur Cortex")
        self.assertEqual(len(self.m.releve("claude-windows@cortex")), 1)
        self.assertEqual(self.m.releve("claude-windows@talos"), [])

    def test_les_projets_se_parlent(self):
        envoi = self.m.envoyer("kimi-mac@cortex", ["claude-windows@talos", "owner"], "Question inter-projet")
        self.assertEqual(envoi.message.a, ("claude-windows@talos", "owner"))
        self.assertEqual(len(self.m.releve("claude-windows@talos")), 1)
        self.assertEqual(len(self.m.releve("owner")), 1)
        self.assertEqual([x.id for x in self.m.lister(projet="talos")], [envoi.message.id])
        self.assertEqual(self.m.projets(), ["cortex", "talos"])


class DeuxDepots(unittest.TestCase):
    """Le parcours d'installation : une boîte sur le poste, un projet par dépôt."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        racine = self._tmp.name
        self.boite = os.path.join(racine, "partage", "boite.json")
        self.cortex = os.path.join(racine, "cortex")
        self.talos = os.path.join(racine, "talos")
        for dossier in (self.cortex, self.talos, os.path.join(self.cortex, "src", "profond")):
            os.makedirs(dossier)
        self.env = dict(os.environ, HOME=racine, USERPROFILE=racine, PYTHONIOENCODING="utf-8")
        for cle in ("MESSENGER_BOX", "MESSENGER_AGENT", "MESSENGER_PROJECT"):
            self.env.pop(cle, None)

    def tearDown(self):
        self._tmp.cleanup()

    def cmd(self, dossier, *args):
        r = subprocess.run([sys.executable, MESSENGER, *args], capture_output=True, text=True,
                           encoding="utf-8", env=self.env, cwd=dossier)
        return r.returncode, r.stdout.strip(), r.stderr.strip()

    def test_installation_sur_deux_depots(self):
        self.assertEqual(self.cmd(self.cortex, "init", "--box", self.boite)[0], 0)
        self.assertEqual(self.cmd(self.cortex, "setup", "--box", self.boite, "--project", "cortex")[0], 0)
        self.assertEqual(self.cmd(self.talos, "setup", "--project", "talos")[0], 0)
        with open(os.path.join(self.cortex, ".messenger.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"project": "cortex"})

        inscrire = ("register", "--host", "claude-code", "--role", "test", "--agent")
        self.assertTrue(self.cmd(self.cortex, *inscrire, "claude-windows")[1]
                        .startswith("compte créé : claude-windows@cortex "))
        self.cmd(self.cortex, *inscrire, "kimi-mac")
        self.cmd(self.talos, *inscrire, "claude-windows")
        self.cmd(self.talos, "register", "--host", "humain", "--role", "arbitre", "--agent", "owner", "--project", "")
        noms = [ligne.split()[0] for ligne in self.cmd(self.cortex, "agents")[1].splitlines()]
        self.assertEqual(sorted(noms), ["claude-windows@cortex", "claude-windows@talos", "kimi-mac@cortex", "owner"])

        # Dans le dépôt cortex (même depuis un sous-dossier), un nom court reste dans le projet.
        profond = os.path.join(self.cortex, "src", "profond")
        _, local, _ = self.cmd(profond, "send", "--agent", "kimi-mac", "--to", "claude-windows", "--subject", "Local")
        _, inter, _ = self.cmd(self.cortex, "send", "--agent", "kimi-mac", "--to", "claude-windows@talos,owner",
                               "--subject", "Inter-projet")
        def releve(dossier, *args):
            return [m["id"] for m in json.loads(self.cmd(dossier, "check", "--json", *args)[1])["nouveaux"]]

        self.assertEqual(releve(self.cortex, "--agent", "claude-windows"), [local])
        self.assertEqual(releve(self.talos, "--agent", "claude-windows"), [inter])
        self.assertEqual(releve(self.talos, "--agent", "owner", "--project", ""), [inter])

        liste = json.loads(self.cmd(self.cortex, "list", "--json", "--project", "talos")[1])
        self.assertEqual([m["id"] for m in liste], [inter])

        # Chaque agent ne fait avancer que son propre courrier.
        self.assertEqual(self.cmd(self.talos, "mark", "--agent", "claude-windows", "--id", local, "--status", "lu")[0], 1)
        self.assertEqual(self.cmd(self.cortex, "mark", "--agent", "claude-windows", "--id", local, "--status", "lu")[0], 0)


if __name__ == "__main__":
    unittest.main()
