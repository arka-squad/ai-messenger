"""Le carnet d'adresses d'un compte, et les projets connectés à la boîte."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

from arkalabs_messenger.adapters.codec import annuaire_depuis_dict, annuaire_vers_dict
from arkalabs_messenger.domain import Annuaire, Compte, CompteInconnu, Contact, ContactRefuse, NomInvalide

from .doublures import messagerie

DEPOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MESSENGER = os.path.join(DEPOT, "messenger.py")


def annuaire(*noms):
    a = Annuaire()
    for nom in noms:
        a.inscrire(Compte.ouvrir(nom, "claude-code", f"rôle de {nom}"))
    return a


class Domaine(unittest.TestCase):
    def test_un_contact_designe_une_adresse_ou_un_groupe(self):
        a = annuaire("windows@cortex", "mac@cortex", "owner")
        a.noter_contact("windows@cortex", "release", ["mac", "owner"], "  la chaîne de\nrelease  ", "2026-09-20")
        contact = a.compte("windows@cortex").contact("release")
        self.assertEqual(contact.adresses, ("mac@cortex", "owner"))  # enregistrées en entier
        self.assertEqual(contact.note, "la chaîne de release")
        self.assertEqual(a.developper("windows@cortex", ["release"]),
                         (["mac@cortex", "owner"], {"release": ("mac@cortex", "owner")}))

    def test_un_compte_l_emporte_toujours_sur_un_alias(self):
        a = annuaire("windows@cortex", "mac@cortex", "owner")
        with self.assertRaisesRegex(ContactRefuse, "déjà l'adresse d'un compte"):
            a.noter_contact("windows@cortex", "mac", ["owner"])       # compte du même projet
        with self.assertRaisesRegex(ContactRefuse, "déjà l'adresse d'un compte"):
            a.noter_contact("windows@cortex", "owner", ["mac"])       # compte commun
        a.noter_contact("windows@cortex", "kimi", ["owner"])
        a.inscrire(Compte.ouvrir("kimi@cortex", "kimi-code", "arrivé après"))
        self.assertEqual(a.developper("windows@cortex", ["kimi"]), (["kimi@cortex"], {}))
        self.assertEqual(a.masques("windows@cortex"), {"kimi": "kimi@cortex"})

    def test_le_carnet_est_personnel(self):
        a = annuaire("windows", "mac", "owner")
        a.noter_contact("windows", "chef", ["owner"])
        self.assertEqual(a.developper("mac", ["chef"]), (["chef"], {}))  # pour mac, « chef » n'est rien
        with self.assertRaisesRegex(CompteInconnu, "chef"):
            a.verifier("mac", ["chef"])

    def test_refus(self):
        a = annuaire("windows", "mac")
        with self.assertRaisesRegex(ContactRefuse, "sans compte actif : kimi"):
            a.noter_contact("windows", "k", ["kimi"])
        with self.assertRaises(NomInvalide):
            a.noter_contact("windows", "Pas Valide", ["mac"])
        with self.assertRaisesRegex(ContactRefuse, "sans adresse"):
            a.noter_contact("windows", "vide", [" "])
        with self.assertRaisesRegex(CompteInconnu, "appartient à un compte"):
            a.noter_contact("inconnu", "m", ["mac"])
        with self.assertRaisesRegex(ContactRefuse, "200 au plus"):
            a.noter_contact("windows", "bavard", ["mac"], "x" * 201)
        a.noter_contact("windows", "m", ["mac"])
        with self.assertRaisesRegex(ContactRefuse, "existe déjà"):
            a.noter_contact("windows", "m", ["mac"])
        with self.assertRaisesRegex(ContactRefuse, "introuvable.*ton carnet : m"):
            a.retirer_contact("windows", "autre")

    def test_remplacer_garde_la_date_et_retirer_rend_le_contact(self):
        a = annuaire("windows", "mac", "owner")
        a.noter_contact("windows", "m", ["mac"], date="2026-09-20")
        a.noter_contact("windows", "m", ["owner"], date="2026-09-21", remplacer=True)
        self.assertEqual(a.compte("windows").contact("m"), Contact("m", ("owner",), None, "2026-09-20"))
        self.assertEqual(a.retirer_contact("windows", "m").adresses, ("owner",))
        self.assertEqual(a.compte("windows").contacts, ())

    def test_mettre_a_jour_son_compte_garde_son_carnet(self):
        a = annuaire("windows", "mac")
        a.noter_contact("windows", "m", ["mac"])
        a.inscrire(Compte.ouvrir("windows", "claude-code", "nouveau rôle"), mise_a_jour=True)
        self.assertEqual([c.alias for c in a.compte("windows").contacts], ["m"])

    def test_un_destinataire_inconnu_rappelle_le_carnet(self):
        a = annuaire("windows", "mac")
        a.noter_contact("windows", "m", ["mac"])
        with self.assertRaisesRegex(CompteInconnu, "ton carnet : m"):
            a.verifier("windows", ["personne"])

    def test_projets_declares(self):
        a = annuaire("windows@cortex")
        self.assertTrue(a.declarer("talos", "2026-09-20"))
        self.assertFalse(a.declarer("talos"))
        self.assertEqual(a.projets(), ["cortex", "talos"])
        with self.assertRaises(NomInvalide):
            a.declarer("Pas Valide")


class Format(unittest.TestCase):
    def test_aller_retour(self):
        a = annuaire("windows", "mac")
        a.noter_contact("windows", "m", ["mac"], "le Mac", "2026-09-20")
        a.declarer("talos", "2026-09-20")
        d = annuaire_vers_dict(a, "boite.json")
        self.assertEqual(d["comptes"][0]["contacts"], [{"alias": "m", "adresses": ["mac"], "note": "le Mac",
                                                        "cree": "2026-09-20"}])
        self.assertNotIn("contacts", d["comptes"][1])  # un carnet vide ne s'écrit pas
        self.assertEqual(d["projets"], [{"nom": "talos", "cree": "2026-09-20"}])
        relu = annuaire_depuis_dict(json.loads(json.dumps(d)))
        self.assertEqual(relu.compte("windows").contacts, a.compte("windows").contacts)
        self.assertEqual(relu.projets(), ["talos"])
        self.assertEqual(annuaire_vers_dict(relu, "boite.json"), d)

    def test_les_champs_inconnus_d_un_contact_sont_gardes(self):
        d = {"comptes": [{"nom": "windows", "hote": "x", "role": "r",
                          "contacts": [{"alias": "m", "adresses": ["mac"], "favori": True}]}],
             "projets": [{"nom": "talos", "couleur": "bleu"}]}
        ecrit = annuaire_vers_dict(annuaire_depuis_dict(d), "b.json")
        self.assertTrue(ecrit["comptes"][0]["contacts"][0]["favori"])
        self.assertEqual(ecrit["projets"], [{"nom": "talos", "couleur": "bleu"}])


class CasDUsage(unittest.TestCase):
    def setUp(self):
        self.m, self.boite, *_ = messagerie()
        for nom in ("windows@cortex", "mac@cortex", "owner"):
            self.m.inscrire(nom, "claude-code", f"rôle de {nom}")

    def test_envoyer_a_un_alias_adresse_les_vraies_adresses(self):
        self.m.noter_contact("windows@cortex", "release", ["mac", "owner"])
        envoi = self.m.envoyer("windows@cortex", ["release", "owner"], "Build prêt")
        self.assertEqual(envoi.message.a, ("mac@cortex", "owner"))  # sans doublon
        self.assertEqual(envoi.alias_developpes, (("release", ("mac@cortex", "owner")),))
        self.assertEqual([m.id for m in self.m.releve("mac@cortex")], [envoi.message.id])

    def test_un_contact_devenu_inactif_est_refuse_a_l_envoi(self):
        self.m.noter_contact("windows@cortex", "m", ["mac"])
        self.m.desactiver("mac@cortex")
        with self.assertRaisesRegex(CompteInconnu, "mac@cortex"):
            self.m.envoyer("windows@cortex", ["m"], "Objet")

    def test_le_carnet(self):
        self.assertEqual(self.m.carnet("windows@cortex").contacts, ())
        self.m.noter_contact("windows@cortex", "m", ["mac"], "le Mac")
        carnet = self.m.carnet("windows@cortex")
        self.assertEqual([(c.alias, c.adresses, c.note) for c in carnet.contacts], [("m", ("mac@cortex",), "le Mac")])
        self.assertEqual(carnet.masques, {})
        self.m.retirer_contact("windows@cortex", "m")
        self.assertEqual(self.m.carnet("windows@cortex").contacts, ())

    def test_un_projet_connecte_est_connu_sans_agent(self):
        self.assertEqual(self.m.projets(), ["cortex"])
        self.assertTrue(self.m.declarer_projet("talos"))
        self.assertFalse(self.m.declarer_projet("talos"))
        self.assertEqual(self.m.projets(), ["cortex", "talos"])


class LigneDeCommande(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dossier = self._tmp.name
        self.boite = os.path.join(self.dossier, "partage")
        self.env = dict(os.environ, HOME=self.dossier, USERPROFILE=self.dossier, PYTHONIOENCODING="utf-8")
        for cle in ("MESSENGER_BOX", "MESSENGER_AGENT", "MESSENGER_PROJECT", "CLAUDE_CONFIG_DIR", "CODEX_HOME",
                    "KIMI_CODE_HOME"):
            self.env.pop(cle, None)
        self.assertEqual(self.cmd("init")[0], 0)
        for nom in ("windows", "mac", "owner"):
            self.assertEqual(self.cmd("register", "--agent", nom, "--host", "claude-code", "--role", "test")[0], 0)

    def tearDown(self):
        self._tmp.cleanup()

    def cmd(self, *args, cwd=None):
        r = subprocess.run([sys.executable, MESSENGER, *args, "--box", self.boite], capture_output=True, text=True,
                           encoding="utf-8", env=self.env, cwd=cwd or self.dossier)
        return r.returncode, r.stdout, r.stderr

    def test_noter_lister_envoyer_retirer(self):
        self.assertIn("carnet vide", self.cmd("contacts", "--agent", "windows")[1])
        code, out, _ = self.cmd("contact-add", "--agent", "windows", "--alias", "release", "--to", "mac,owner",
                                "--note", "la chaîne de release")
        self.assertEqual((code, out.strip()), (0, "contact noté : release → mac, owner"))
        self.assertIn("release              → mac, owner  — la chaîne de release",
                      self.cmd("contacts", "--agent", "windows")[1])
        carnet = json.loads(self.cmd("contacts", "--agent", "windows", "--json")[1])
        self.assertEqual(carnet["contacts"][0]["adresses"], ["mac", "owner"])

        code, mid, err = self.cmd("send", "--agent", "windows", "--to", "release", "--subject", "Build prêt")
        self.assertEqual(code, 0)
        self.assertIn("(carnet : release → mac, owner)", err)
        self.assertIn(mid.strip(), self.cmd("check", "--agent", "mac")[1])
        self.assertIn(mid.strip(), self.cmd("check", "--agent", "owner")[1])

        self.assertEqual(self.cmd("contact-add", "--agent", "windows", "--alias", "mac", "--to", "owner")[0], 1)
        self.assertEqual(self.cmd("contact-remove", "--agent", "windows", "--alias", "release")[0], 0)
        self.assertEqual(self.cmd("send", "--agent", "windows", "--to", "release", "--subject", "Encore")[0], 1)

    def test_activate_fait_connaitre_le_projet_a_la_boite(self):
        depot = os.path.join(self.dossier, "mon-depot")
        os.makedirs(depot)
        self.assertEqual(self.cmd("activate", "--project", "talos", cwd=depot)[0], 0)
        manifeste = os.path.join(self.boite, ".aimessenger", "manifest.json")
        with open(manifeste, encoding="utf-8") as f:
            self.assertEqual([p["nom"] for p in json.load(f)["projets"]], ["talos"])


if __name__ == "__main__":
    unittest.main()
