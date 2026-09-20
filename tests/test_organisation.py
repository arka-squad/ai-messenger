"""Organiser sa boîte : ranger un compte dans un projet, reprendre son compte, inviter dans un projet,
et la relève qui prévient une session sans identité qu'un courrier attend un compte de son poste."""
import json
import os
import platform
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from arkalabs_messenger.adapters.driving import hotes, poste
from arkalabs_messenger.adapters.driving.web import OUTIL, creer_serveur
from arkalabs_messenger.bootstrap import Usine
from arkalabs_messenger.domain import Annuaire, Compte, CompteExistant, CompteInconnu, MessageInvalide

from .doublures import messagerie

DEPOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MESSENGER = os.path.join(DEPOT, "messenger.py")


class Rattachement(unittest.TestCase):
    def test_un_compte_commun_se_range_dans_un_projet_sans_changer_d_adresse(self):
        a = Annuaire()
        a.inscrire(Compte.ouvrir("windows", "claude-code", "releases"))
        a.inscrire(Compte.ouvrir("kimi@talos", "kimi-code", "plugins"))
        self.assertEqual(a.rattacher("windows", "cortex").projet, "cortex")
        self.assertEqual(a.compte("windows").nom, "windows")
        self.assertEqual(a.projets(), ["cortex", "talos"])
        self.assertEqual((a.projet_de("windows"), a.projet_de("kimi@talos"), a.projet_de("inconnu@x")),
                         ("cortex", "talos", "x"))
        self.assertIsNone(a.rattacher("windows", None).projet)
        with self.assertRaisesRegex(MessageInvalide, "porte déjà son projet"):
            a.rattacher("kimi@talos", "cortex")
        with self.assertRaises(CompteInconnu):
            a.rattacher("personne", "cortex")

    def test_mettre_a_jour_son_compte_garde_son_projet(self):
        a = Annuaire()
        a.inscrire(Compte.ouvrir("windows", "claude-code", "releases"))
        a.rattacher("windows", "cortex")
        a.inscrire(Compte.ouvrir("windows", "claude-code", "nouveau rôle"), mise_a_jour=True)
        self.assertEqual(a.compte("windows").projet, "cortex")

    def test_un_nom_court_se_resout_depuis_le_projet_de_rattachement(self):
        m, *_ = messagerie()
        for nom in ("windows", "mac@cortex", "owner"):
            m.inscrire(nom, "claude-code", "rôle")
        m.rattacher("windows", "cortex")
        self.assertEqual(m.envoyer("windows", ["mac"], "Objet").message.a, ("mac@cortex",))
        self.assertEqual([x.de for x in m.lister(projet="cortex")], ["windows"])
        m.envoyer("owner", ["windows"], "Pour un rangé")
        self.assertEqual(len(m.lister(projet="cortex")), 2)  # un message touche le projet par ses comptes rangés

    def test_l_agent_qui_revient_d_un_depot_connecte_garde_son_compte(self):
        """Sinon il créerait `…@cortex`, et le courrier envoyé à son adresse commune resterait orphelin."""
        m, *_ = messagerie()
        avant, _ = m.enroler("claude-code", "Addon", "mac", None, "mon-mac")
        apres, cree = m.enroler("claude-code", "Addon", "mac", "cortex", "mon-mac")
        self.assertEqual((apres.nom, cree, apres.projet), (avant.nom, False, "cortex"))
        autre, cree = m.enroler("claude-code", "Addon", "mac", "cortex", "un-autre-poste")
        self.assertEqual((autre.nom, cree), ("cl-agent-addon-mac@cortex", True))  # un homonyme d'ailleurs a son compte


class Reprendre(unittest.TestCase):
    def setUp(self):
        self.m, *_ = messagerie()
        self.m.inscrire("addon", "claude-code", "l'addon", machine="mon-mac")
        self.m.inscrire("mac", "inconnu", "compte importé — à compléter")

    def test_son_propre_compte(self):
        self.assertEqual(self.m.reprendre("addon", "claude-code", "mon-mac").nom, "addon")

    def test_pas_celui_d_un_autre_poste(self):
        with self.assertRaisesRegex(CompteExistant, "autre poste"):
            self.m.reprendre("addon", "claude-code", "un-autre-poste")
        with self.assertRaises(CompteInconnu):
            self.m.reprendre("personne", "claude-code", "mon-mac")

    def test_un_compte_importe_est_complete_au_passage(self):
        compte = self.m.reprendre("mac", "kimi-code", "mon-mac")
        self.assertEqual((compte.hote, compte.machine), ("kimi-code", "mon-mac"))

    def test_le_courrier_en_attente_sur_ce_poste(self):
        self.m.inscrire("owner", "humain", "arbitre")
        self.m.envoyer("owner", ["addon", "mac"], "Bonjour")
        attendus = self.m.en_attente_sur_ce_poste("claude-code", "mon-mac")
        self.assertEqual([(c.nom, n) for c, n in attendus], [("addon", 1)])
        self.assertEqual(self.m.en_attente_sur_ce_poste("claude-code", "ailleurs"), [])


class Releve(unittest.TestCase):
    """La ligne de commande, comme un hôte la lance : un agent enrôlé ailleurs est prévenu, une fois."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dossier = self._tmp.name
        self.boite = os.path.join(self.dossier, "partage")
        self.env = dict(os.environ, HOME=self.dossier, USERPROFILE=self.dossier, PYTHONIOENCODING="utf-8")
        for cle in ("MESSENGER_BOX", "MESSENGER_AGENT", "MESSENGER_PROJECT"):
            self.env.pop(cle, None)
        self.ici = os.path.join(self.dossier, "ici")
        self.travail = os.path.join(self.dossier, "travail", "sous-dossier")
        os.makedirs(self.ici)
        os.makedirs(self.travail)
        self.cmd("init", "--box", self.boite)
        self.cmd("setup", "--box", self.boite)
        self.cmd("register", "--agent", "owner", "--host", "humain", "--role", "arbitre")
        self.cmd("enroll", "--task", "Addon", "--host", "claude-code", cwd=self.ici)
        self.adresse = f"cl-agent-addon-{poste.code_du_poste()}"
        self.cmd("send", "--agent", "owner", "--to", self.adresse, "--subject", "Tu me reçois ?")

    def tearDown(self):
        self._tmp.cleanup()

    def cmd(self, *args, cwd=None, entree=None):
        r = subprocess.run([sys.executable, MESSENGER, *args], capture_output=True, text=True, encoding="utf-8",
                           env=self.env, cwd=cwd or self.dossier, input=entree)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def hook(self, dossier, session, evenement="UserPromptSubmit"):
        charge = json.dumps({"session_id": session, "cwd": dossier, "hook_event_name": evenement})
        return self.cmd("check", "--hook", "--host", "claude-code", "--event", evenement, entree=charge)

    def test_la_ou_il_s_est_enrole_il_recoit(self):
        self.assertIn(f"COURRIER — 1 message(s) au statut « nouveau » pour {self.adresse}", self.hook(self.ici, "s1"))

    def test_ailleurs_il_est_prevenu_une_fois_puis_il_reprend_son_compte(self):
        sortie = self.hook(self.travail, "s2")
        self.assertIn("du courrier attend un compte créé par claude-code sur ce poste", sortie)
        self.assertIn(f"- {self.adresse} (CL_Agent-Addon_{poste.code_du_poste().upper()}) — 1 message(s)", sortie)
        self.assertIn("identify --address", sortie)
        self.assertEqual(self.hook(self.travail, "s2"), "")  # pas à chaque message
        self.assertEqual(self.hook(self.travail, "s3", "SessionStart").count("📬"), 1)  # une autre session, si

        depot = os.path.dirname(self.travail)
        self.assertIn("c'est bien toi", self.cmd("identify", "--address", self.adresse, "--host", "claude-code",
                                                 cwd=depot))
        self.assertIn("COURRIER — 1 message(s)", self.hook(self.travail, "s4"))  # reconnu dans le sous-dossier

    def test_un_autre_hote_n_est_pas_derange(self):
        charge = json.dumps({"session_id": "k1", "cwd": self.travail})
        self.assertEqual(self.cmd("check", "--hook", "--host", "kimi-code", "--event", "UserPromptSubmit",
                                  entree=charge), "")

    def test_ranger_un_compte_depuis_la_ligne_de_commande(self):
        self.assertIn(f"{self.adresse} → projet cortex", self.cmd("attach", "--account", self.adresse, "--to", "cortex"))
        self.assertIn("sans projet", self.cmd("attach", "--account", self.adresse))


class Interface(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dossier = self._tmp.name
        self._config, self._contexte = poste.CONFIG, hotes.contexte
        poste.CONFIG = os.path.join(self.dossier, "poste.json")
        self.home = os.path.join(self.dossier, "home")
        os.makedirs(os.path.join(self.home, ".claude"))
        hotes.contexte = lambda depot: hotes.Contexte(depot, home=self.home, env={})
        self.messagerie = Usine().ouvrir(os.path.join(self.dossier, "partage"))
        self.messagerie.initialiser()
        for nom in ("owner", "windows", "mac"):
            self.messagerie.inscrire(nom, "claude-code", f"rôle de {nom}")
        self.lancer()

    def lancer(self, **options):
        self.serveur = creer_serveur(self.messagerie, "owner", port=0, depot=DEPOT, **options)
        self.base = f"http://127.0.0.1:{self.serveur.server_address[1]}"
        threading.Thread(target=self.serveur.serve_forever, daemon=True).start()

    def tearDown(self):
        poste.CONFIG, hotes.contexte = self._config, self._contexte
        self.serveur.shutdown()
        self.serveur.server_close()
        self._tmp.cleanup()

    def get(self, chemin):
        with urllib.request.urlopen(self.base + chemin) as r:
            return json.loads(r.read())

    def post(self, chemin, corps):
        req = urllib.request.Request(self.base + chemin, data=json.dumps(corps).encode(),
                                     headers={"Content-Type": "application/json", "Origin": self.base})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_l_invite_porte_le_projet_choisi_et_le_cree(self):
        code, rep = self.post("/api/invite", {"projet": "cortex"})
        self.assertEqual(code, 200)
        self.assertIn('enroll --task "<ta tâche>" --project cortex', rep["invite"])
        self.assertEqual(self.get("/api/boite")["projets"], ["cortex"])  # connu avant qu'un agent arrive
        self.assertIn('--project ""', self.post("/api/invite", {"projet": None})[1]["invite"])
        self.assertEqual(self.post("/api/invite", {"projet": "Pas Valide"})[0], 409)

    def test_l_invite_d_un_agent_qui_a_deja_son_compte(self):
        invite = self.post("/api/invite", {"compte": "windows"})[1]["invite"]
        self.assertIn("identify --address windows", invite)
        self.assertNotIn("enroll --task", invite)
        self.assertEqual(self.post("/api/invite", {"compte": "personne"})[0], 400)

    def test_ranger_un_agent_dans_un_projet(self):
        self.assertEqual(self.post("/api/rattacher", {"compte": "windows", "projet": "cortex"})[0], 200)
        comptes = {c["nom"]: c for c in self.get("/api/boite")["comptes"]}
        self.assertEqual((comptes["windows"]["projet"], comptes["mac"]["projet"]), ("cortex", None))
        self.assertEqual(self.post("/api/rattacher", {"compte": "windows", "projet": None})[0], 200)
        self.assertIsNone(self.messagerie.comptes()[2].projet)

    def test_tenir_le_carnet_d_un_agent(self):
        code, _ = self.post("/api/contact", {"compte": "windows", "alias": "equipe", "adresses": ["mac", "owner"],
                                             "note": "la chaîne de release"})
        self.assertEqual(code, 200)
        self.assertEqual([c.alias for c in self.messagerie.carnet("windows").contacts], ["equipe"])
        code, rep = self.post("/api/contact", {"compte": "windows", "alias": "mac", "adresses": ["owner"]})
        self.assertEqual(code, 409)
        self.assertIn("déjà l'adresse d'un compte", rep["erreur"])
        self.assertEqual(self.post("/api/contact-retirer", {"compte": "windows", "alias": "equipe"})[0], 200)
        self.assertEqual(self.messagerie.carnet("windows").contacts, ())
        self.assertEqual(self.post("/api/contact", {"compte": "windows", "alias": "x"})[0], 400)

    def test_fusionner_deux_comptes_depuis_l_interface(self):
        recu = self.messagerie.envoyer("owner", ["windows"], "Avant la fusion").message
        code, _ = self.post("/api/fusionner", {"compte": "windows", "dans": "mac"})
        self.assertEqual(code, 200)
        self.assertEqual([m.id for m in self.messagerie.releve("mac")], [recu.id])
        code, rep = self.post("/api/fusionner", {"compte": "windows", "dans": "owner"})
        self.assertEqual(code, 409)
        self.assertIn("déjà fusionné", rep["erreur"])

    def test_ce_poste_et_sa_preparation(self):
        avant = self.get("/api/poste")
        self.assertEqual([(h["id"], h["equipe"]) for h in avant["hotes"]], [("claude-code", False)])
        self.assertFalse(avant["eteignable"])
        code, apres = self.post("/api/preparer", {})
        self.assertEqual((code, [(h["id"], h["equipe"]) for h in apres["hotes"]]), (200, [("claude-code", True)]))

    def test_on_n_eteint_que_la_boite_qu_on_a_allumee(self):
        self.assertEqual(self.post("/api/eteindre", {})[0], 409)
        version = self.get("/api/version")
        self.assertEqual(version["outil"], OUTIL)
        self.serveur.shutdown()
        self.serveur.server_close()
        self.lancer(eteignable=True)
        self.assertEqual(self.post("/api/eteindre", {}), (200, {"eteinte": True}))


class Allumer(unittest.TestCase):
    """`start` : rouvrir la boîte déjà allumée plutôt que d'échouer sur un port pris."""

    def test_on_reconnait_sa_propre_boite_et_pas_celle_d_un_autre(self):
        from arkalabs_messenger.adapters.driving import cli

        with tempfile.TemporaryDirectory() as dossier:
            m = Usine().ouvrir(os.path.join(dossier, "partage"))
            m.initialiser()
            serveur = creer_serveur(m, "owner", port=0)
            threading.Thread(target=serveur.serve_forever, daemon=True).start()
            try:
                port = serveur.server_address[1]
                self.assertEqual(cli._qui_ecoute(port), OUTIL)
                self.assertFalse(cli._port_libre(port))
            finally:
                serveur.shutdown()
                serveur.server_close()
        self.assertIsNone(cli._qui_ecoute(port))
        self.assertEqual(platform.system() != "", True)


if __name__ == "__main__":
    unittest.main()
