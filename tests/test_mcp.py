"""Le serveur MCP : le protocole, les outils, l'identité — puis un vrai échange par l'entrée standard."""
import json
import os
import platform
import subprocess
import sys
import tempfile
import threading
import unittest

from arkalabs_messenger.adapters.driving import poste
from arkalabs_messenger.adapters.driving.mcp import (
    METHODE_INCONNUE,
    PARAMETRES_INVALIDES,
    REQUETE_INVALIDE,
    RESSOURCE_INTROUVABLE,
    VERSIONS,
    ServeurMcp,
)
from arkalabs_messenger.bootstrap import Usine

DEPOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MESSENGER = os.path.join(DEPOT, "messenger.py")


class Serveur(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dossier = self._tmp.name
        self._config = poste.CONFIG
        poste.CONFIG = os.path.join(self.dossier, "poste.json")  # ne pas toucher à la vraie config du poste
        self._env = {k: os.environ.pop(k) for k in ("MESSENGER_BOX", "MESSENGER_AGENT", "MESSENGER_PROJECT")
                     if k in os.environ}
        self.boite = os.path.join(self.dossier, "partage")
        self.messagerie = Usine().ouvrir(self.boite)
        self.messagerie.initialiser()
        self.messagerie.inscrire("owner", "humain", "arbitre")
        self.depot = os.path.join(self.dossier, "monrepo")
        os.makedirs(self.depot)
        self.serveur = self.nouveau()
        self._n = 0

    def tearDown(self):
        poste.CONFIG = self._config
        os.environ.update(self._env)
        self._tmp.cleanup()

    def nouveau(self, **options):
        return ServeurMcp(Usine(), boite=self.boite, hote="claude-code", dossier=self.depot, **options)

    def requete(self, methode, params=None, serveur=None):
        self._n += 1
        message = {"jsonrpc": "2.0", "id": self._n, "method": methode}
        if params is not None:
            message["params"] = params
        return (serveur or self.serveur).traiter(message)

    def outil(self, nom, serveur=None, **arguments):
        reponse = self.requete("tools/call", {"name": nom, "arguments": arguments}, serveur)
        self.assertIn("result", reponse, reponse)
        resultat = reponse["result"]
        return resultat.get("structuredContent"), resultat


class Protocole(Serveur):
    def test_initialize_negocie_la_version(self):
        for demandee, rendue in ((VERSIONS[-1], VERSIONS[-1]), ("1999-01-01", VERSIONS[0])):
            resultat = self.requete("initialize", {"protocolVersion": demandee, "capabilities": {},
                                                   "clientInfo": {"name": "test", "version": "0"}})["result"]
            self.assertEqual(resultat["protocolVersion"], rendue)
            self.assertEqual(resultat["serverInfo"]["name"], "arkalabs-messenger")
            self.assertIn("tools", resultat["capabilities"])
            self.assertIn("enroll", resultat["instructions"])

    def test_une_notification_ne_recoit_pas_de_reponse(self):
        self.assertIsNone(self.serveur.traiter({"jsonrpc": "2.0", "method": "notifications/initialized"}))
        self.assertEqual(self.requete("ping")["result"], {})

    def test_erreurs_de_protocole(self):
        self.assertEqual(self.requete("prompts/list")["error"]["code"], METHODE_INCONNUE)
        self.assertEqual(self.serveur.traiter({"id": 1, "method": "ping"})["error"]["code"], REQUETE_INVALIDE)
        self.assertEqual(self.requete("tools/call", {"name": "inexistant"})["error"]["code"], PARAMETRES_INVALIDES)
        for arguments in ({}, {"to": ["owner"], "subject": "s", "inconnu": 1}, {"to": "owner", "subject": "s"}):
            with self.subTest(arguments=arguments):
                erreur = self.requete("tools/call", {"name": "send", "arguments": arguments})["error"]
                self.assertEqual(erreur["code"], PARAMETRES_INVALIDES)
        self.assertEqual(self.requete("resources/read", {"uri": "messenger://rien"})["error"]["code"],
                         RESSOURCE_INTROUVABLE)

    def test_un_lot_rend_un_lot(self):
        reponses = self.serveur.traiter([{"jsonrpc": "2.0", "id": 1, "method": "ping"},
                                         {"jsonrpc": "2.0", "method": "notifications/initialized"},
                                         {"jsonrpc": "2.0", "id": 2, "method": "ping"}])
        self.assertEqual([r["id"] for r in reponses], [1, 2])

    def test_les_outils_decrivent_leurs_arguments(self):
        outils = {o["name"]: o for o in self.requete("tools/list")["result"]["tools"]}
        self.assertEqual(set(outils), {"whoami", "enroll", "identify", "check", "list", "read", "send", "reply",
                                       "mark", "agents", "contacts", "contact_add", "contact_remove", "wait"})
        self.assertEqual(outils["send"]["inputSchema"]["required"], ["to", "subject"])
        self.assertEqual(outils["mark"]["inputSchema"]["properties"]["status"]["enum"], ["lu", "traité"])


class Identite(Serveur):
    def test_sans_identite_les_outils_disent_quoi_faire(self):
        moi, _ = self.outil("whoami")
        self.assertIsNone(moi["address"])
        self.assertIn("enroll", moi["advice"])
        _, resultat = self.outil("check")
        self.assertTrue(resultat["isError"])
        self.assertIn("enroll", resultat["content"][0]["text"])

    def test_enroll_donne_une_identite_lisible_et_la_retient(self):
        compte, _ = self.outil("enroll", task="MessengerAI")
        self.assertEqual(compte["address"], f"cl-agent-messengerai-{poste.code_du_poste()}")
        self.assertEqual(compte["display"], f"CL_Agent-MessengerAI_{poste.code_du_poste().upper()}")
        self.assertTrue(compte["created"])
        self.assertEqual(self.outil("whoami")[0]["address"], compte["address"])
        # une autre session du même hôte dans ce dépôt : rien n'est adopté d'office, mais c'est proposé
        autre = self.nouveau()
        suggestion = self.outil("whoami", serveur=autre)[0]
        self.assertIsNone(suggestion["address"])
        self.assertIn(compte["address"], suggestion["advice"])
        self.assertEqual(self.outil("identify", serveur=autre, address=compte["address"])[0]["address"],
                         compte["address"])
        self.assertFalse(self.outil("enroll", serveur=autre, task="MessengerAI")[0]["created"])

    def test_on_ne_prend_pas_le_compte_d_un_autre_poste(self):
        self.messagerie.inscrire("kimi-mac", "kimi-code", "plugins", machine="un-autre-poste")
        _, resultat = self.outil("identify", address="kimi-mac")
        self.assertTrue(resultat["isError"])
        self.assertIn("autre poste", resultat["content"][0]["text"])

    def test_le_projet_vient_du_depot(self):
        poste.attacher_projet(self.depot, "talos")
        compte, _ = self.outil("enroll", task="Build")
        self.assertTrue(compte["address"].endswith("@talos"))
        self.assertEqual(self.outil("whoami")[0]["project"], "talos")


class Courrier(Serveur):
    def setUp(self):
        super().setUp()
        self.moi = self.outil("enroll", task="Build")[0]["address"]

    def test_envoyer_relever_lire_repondre_marquer(self):
        note = os.path.join(self.dossier, "detail.md")
        with open(note, "w", encoding="utf-8") as f:
            f.write("# Le détail\n")
        recu = self.messagerie.envoyer("owner", [self.moi], "Go ?", "Dis-moi.", note).message

        nouveaux = self.outil("check")[0]["new"]
        self.assertEqual([m["id"] for m in nouveaux], [recu.id])

        lu = self.outil("read", id=recu.id)[0]
        self.assertTrue(lu["addressed_to_me"])
        self.assertEqual(lu["next_status"], "lu")
        self.assertEqual(lu["attachment"]["text"], "# Le détail\n")

        reponse = self.outil("reply", id=recu.id, subject="Go", body="C'est parti.")[0]
        self.assertEqual((reponse["to"], reponse["reply_to"]), (["owner"], recu.id))
        self.assertEqual(self.outil("mark", id=recu.id, status="lu")[0]["status"], "lu")
        self.assertEqual(self.outil("mark", id=recu.id, status="traité")[0]["status"], "traité")
        self.assertEqual(self.outil("check")[0]["new"], [])
        self.assertEqual(self.outil("read", id=recu.id)[0]["thread"][0]["id"], reponse["id"])

    def test_les_refus_du_domaine_arrivent_en_clair(self):
        pas_pour_moi = self.messagerie.envoyer("owner", ["owner"], "Note à moi-même").message
        for nom, arguments, attendu in (
                ("mark", {"id": pas_pour_moi.id, "status": "lu"}, "n'est pas destinataire"),
                ("send", {"to": ["personne"], "subject": "s"}, "sans compte actif"),
                ("send", {"to": ["owner"], "subject": "s", "body": "a\nb\nc"}, "deux lignes"),
                ("read", {"id": "inexistant"}, "introuvable")):
            with self.subTest(outil=nom):
                _, resultat = self.outil(nom, **arguments)
                self.assertTrue(resultat["isError"])
                self.assertIn(attendu, resultat["content"][0]["text"])

    def test_lister_et_connaitre_les_comptes(self):
        self.outil("send", to=["owner"], subject="Un")
        self.outil("send", to=["owner"], subject="Deux")
        self.assertEqual([m["subject"] for m in self.outil("list", mine=True, limit=1)[0]["messages"]], ["Deux"])
        comptes = {c["nom"]: c for c in self.outil("agents")[0]["accounts"]}
        self.assertEqual(comptes[self.moi]["machine"], platform.node())

    def test_le_carnet_d_adresses(self):
        self.assertEqual(self.outil("contacts")[0], {"contacts": [], "shadowed": {}})
        note = self.outil("contact_add", alias="chef", addresses=["owner"], note="mon humain")[0]["contact"]
        self.assertEqual((note["alias"], note["adresses"], note["note"]), ("chef", ["owner"], "mon humain"))
        envoi = self.outil("send", to=["chef"], subject="Par le carnet")[0]
        self.assertEqual((envoi["to"], envoi["expanded"]), (["owner"], {"chef": ["owner"]}))
        _, refus = self.outil("contact_add", alias="owner", addresses=["owner"])
        self.assertTrue(refus["isError"])
        self.assertIn("déjà l'adresse d'un compte", refus["content"][0]["text"])
        self.assertEqual(self.outil("contact_remove", alias="chef")[0]["removed"]["alias"], "chef")
        self.assertEqual(self.outil("contacts")[0]["contacts"], [])

    def test_wait_rend_le_message_qui_arrive_et_s_arrete_a_l_echeance(self):
        self.assertEqual(self.outil("wait", timeout_seconds=1)[0]["received"], [])
        threading.Timer(0.5, lambda: self.messagerie.envoyer("owner", [self.moi], "Réveil")).start()
        recus = self.outil("wait", timeout_seconds=20)[0]["received"]
        self.assertEqual([m["subject"] for m in recus], ["Réveil"])

    def test_les_ressources(self):
        self.outil("send", to=["owner"], subject="Pour la vue")
        uris = [r["uri"] for r in self.requete("resources/list")["result"]["resources"]]
        self.assertEqual(uris, ["messenger://boite", "messenger://comptes", "messenger://accueil"])
        vue = self.requete("resources/read", {"uri": "messenger://boite"})["result"]["contents"][0]
        self.assertIn("Pour la vue", vue["text"])
        self.assertEqual(self.requete("resources/templates/list")["result"], {"resourceTemplates": []})


class ParLEntreeStandard(unittest.TestCase):
    """Le vrai serveur, lancé comme le lance un hôte."""

    def test_une_session_complete(self):
        with tempfile.TemporaryDirectory() as dossier:
            env = dict(os.environ, HOME=dossier, USERPROFILE=dossier, PYTHONIOENCODING="utf-8")
            for cle in ("MESSENGER_BOX", "MESSENGER_AGENT", "MESSENGER_PROJECT"):
                env.pop(cle, None)
            boite = os.path.join(dossier, "partage")
            subprocess.run([sys.executable, MESSENGER, "init", "--box", boite], check=True, capture_output=True, env=env)
            subprocess.run([sys.executable, MESSENGER, "setup", "--box", boite], check=True, capture_output=True,
                           env=env)
            messages = [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                 "params": {"protocolVersion": VERSIONS[0], "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "enroll", "arguments": {"task": "Éclaireur"}}},
            ]
            entree = "".join(json.dumps(m, ensure_ascii=False) + "\n" for m in messages) + "ceci n'est pas du JSON\n"
            r = subprocess.run([sys.executable, MESSENGER, "mcp", "--host", "codex"], input=entree.encode("utf-8"),
                               capture_output=True, env=env, cwd=dossier, timeout=60)
            self.assertEqual(r.returncode, 0, r.stderr.decode("utf-8", "replace"))
            self.assertNotIn(b"\r\n", r.stdout)  # un message par ligne, sans fin de ligne traduite
            reponses = {rep.get("id"): rep for rep in map(json.loads, r.stdout.decode("utf-8").splitlines())}
            self.assertEqual(reponses[1]["result"]["protocolVersion"], VERSIONS[0])
            self.assertEqual(reponses[2]["result"]["structuredContent"]["display"],
                             f"CD_Agent-Éclaireur_{poste.code_du_poste().upper()}")
            self.assertEqual(reponses[None]["error"]["code"], -32700)

    def test_un_hote_qui_part_en_pleine_reponse_n_est_pas_une_panne(self):
        with tempfile.TemporaryDirectory() as dossier:
            env = dict(os.environ, HOME=dossier, USERPROFILE=dossier, PYTHONIOENCODING="utf-8")
            for cle in ("MESSENGER_BOX", "MESSENGER_AGENT", "MESSENGER_PROJECT"):
                env.pop(cle, None)
            p = subprocess.Popen([sys.executable, MESSENGER, "mcp", "--host", "codex"], stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, cwd=dossier)
            p.stdout.close()  # l'hôte a disparu : plus personne ne lit
            for i in range(1, 4):
                p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": i, "method": "tools/call",
                                          "params": {"name": "whoami", "arguments": {}}}).encode("utf-8") + b"\n")
            p.stdin.close()
            self.assertEqual(p.wait(timeout=60), 0)
            erreurs = p.stderr.read().decode("utf-8", "replace")
            p.stderr.close()
            self.assertEqual(erreurs, "")  # ni trace, ni exception ignorée à la sortie de l'interpréteur


class SortieFermee(Serveur):
    def test_le_serveur_s_arrete_sans_lever(self):
        class Cassee:
            def write(self, _):
                raise OSError(22, "Invalid argument")

            def flush(self):
                pass

        import io
        serveur = self.nouveau()
        entree = io.BytesIO(b'{"jsonrpc":"2.0","id":1,"method":"ping"}\n{"jsonrpc":"2.0","id":2,"method":"ping"}\n')
        self.assertEqual(serveur.servir(entree, Cassee()), 0)
        self.assertTrue(serveur.sortie_fermee)
        self.assertNotEqual(entree.read(), b"")  # il n'a pas insisté : la seconde requête n'est pas lue


if __name__ == "__main__":
    unittest.main()
