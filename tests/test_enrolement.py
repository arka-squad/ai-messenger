"""L'enrôlement : identité lisible déduite, activation d'un dépôt, relève par session."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

from arkalabs_messenger.domain import composer_identite, initiales_hote, slugifier

DEPOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MESSENGER = os.path.join(DEPOT, "messenger.py")


class Identite(unittest.TestCase):
    def test_slug_sans_accent_ni_casse(self):
        self.assertEqual(slugifier("Refonte de l'Été !"), "refonte-de-l-ete")
        self.assertEqual(slugifier("A" * 40, 8), "aaaaaaaa")

    def test_initiales_du_fournisseur(self):
        self.assertEqual(initiales_hote("claude-code"), "cl")
        self.assertEqual(initiales_hote("codex"), "cd")
        self.assertEqual(initiales_hote("kimi-code"), "km")
        self.assertEqual(initiales_hote("hermes-x"), "he")  # inconnu : deux lettres

    def test_adresse_slug_et_affichage(self):
        adresse, affichage = composer_identite("claude-code", "MessengerAI", "win")
        self.assertEqual(adresse, "cl-agent-messengerai-win")
        self.assertEqual(affichage, "CL_Agent-MessengerAI_WIN")

    def test_adresse_toujours_valide_et_bornee(self):
        adresse, _ = composer_identite("codex", "une tâche vraiment très très longue à décrire", "mac")
        self.assertLessEqual(len(adresse), 32)
        self.assertTrue(adresse.startswith("cd-agent-") and adresse.endswith("-mac"))


class LigneDeCommande(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dossier = self._tmp.name
        self.boite = os.path.join(self.dossier, "partage", "boite.json")
        self.env = dict(os.environ, HOME=self.dossier, USERPROFILE=self.dossier, PYTHONIOENCODING="utf-8")
        # ni la vraie boîte, ni la vraie configuration des hôtes IA : tout vit dans le dossier temporaire
        for cle in ("MESSENGER_BOX", "MESSENGER_AGENT", "MESSENGER_PROJECT",
                    "CLAUDE_CONFIG_DIR", "CODEX_HOME", "KIMI_CODE_HOME"):
            self.env.pop(cle, None)

    def tearDown(self):
        self._tmp.cleanup()

    def cmd(self, *args, box=True, entree=None, cwd=None):
        argv = [sys.executable, MESSENGER, *args] + (["--box", self.boite] if box else [])
        r = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", env=self.env,
                           cwd=cwd or self.dossier, input=entree)
        return r.returncode, r.stdout, r.stderr

    def test_enroll_cree_une_identite_lisible_et_rattache_la_session(self):
        self.cmd("init")
        code, out, _ = self.cmd("enroll", "--task", "MessengerAI", "--host", "claude-code",
                                "--poste", "win", "--session", "S1")
        self.assertEqual(code, 0)
        self.assertIn("CL_Agent-MessengerAI_WIN", out)
        self.assertIn("cl-agent-messengerai-win", out)

        comptes = json.loads(self.cmd("agents", "--json")[1])["comptes"]
        moi = next(c for c in comptes if c["nom"] == "cl-agent-messengerai-win")
        self.assertEqual(moi["affichage"], "CL_Agent-MessengerAI_WIN")

    def test_enroll_reutilise_le_sien_et_suffixe_un_homonyme(self):
        self.cmd("init")
        self.cmd("enroll", "--task", "Build", "--host", "claude-code", "--poste", "win", "--machine", "PC-A")
        # même tâche/poste, autre machine → un homonyme reçoit un suffixe
        code, out, _ = self.cmd("enroll", "--task", "Build", "--host", "claude-code", "--poste", "win",
                                "--machine", "PC-B")
        self.assertIn("cl-agent-build-win-2", out)
        # ré-enrôlement de la même machine → on réutilise le même compte
        code, out, _ = self.cmd("enroll", "--task", "Build", "--host", "claude-code", "--poste", "win",
                                "--machine", "PC-A")
        self.assertIn("déjà inscrit", out)
        self.assertIn("(adresse cl-agent-build-win)", out)

    def test_check_hook_releve_par_session_sans_variable(self):
        self.cmd("init")
        self.cmd("register", "--agent", "owner", "--host", "humain", "--role", "arbitre")
        self.cmd("enroll", "--task", "Build", "--host", "claude-code", "--poste", "win", "--session", "S1")
        code, mid, _ = self.cmd("send", "--agent", "owner", "--to", "cl-agent-build-win", "--subject", "Go")
        mid = mid.strip()

        charge = json.dumps({"session_id": "S1", "cwd": self.dossier, "hook_event_name": "UserPromptSubmit"})
        code, out, _ = self.cmd("check", "--hook", entree=charge)
        self.assertEqual(code, 0)
        self.assertIn(mid, out)
        self.assertIn("cl-agent-build-win", out)

    def test_check_hook_invite_a_s_enroler_dans_un_depot_connecte(self):
        self.cmd("init")
        self.cmd("setup", "--project", "demo")
        charge = json.dumps({"session_id": "S9", "cwd": self.dossier, "hook_event_name": "SessionStart"})
        code, out, _ = self.cmd("check", "--hook", "--host", "codex", entree=charge)
        self.assertEqual(code, 0)
        self.assertIn("pas encore enrôlé", out)
        self.assertIn("outil `enroll`", out)
        self.assertIn("--host codex --session S9", out)

    def test_check_hook_muet_hors_d_un_depot_connecte(self):
        """La relève est posée par machine : elle tourne partout, et ne dit rien ailleurs."""
        self.cmd("init")
        charge = json.dumps({"session_id": "S9", "cwd": self.dossier, "hook_event_name": "SessionStart"})
        self.assertEqual(self.cmd("check", "--hook", entree=charge), (0, "", ""))

    def test_check_hook_muet_sur_un_simple_prompt_sans_identite(self):
        self.cmd("init")
        self.cmd("setup", "--project", "demo")
        self.assertEqual(self.cmd("check", "--hook", "--event", "UserPromptSubmit", entree="{}"), (0, "", ""))

    def test_releve_par_hote_et_dossier_quand_l_hote_ne_donne_pas_de_session(self):
        self.cmd("init")
        self.cmd("register", "--agent", "owner", "--host", "humain", "--role", "arbitre")
        self.cmd("enroll", "--task", "Plugins", "--host", "kimi-code", "--poste", "mac")
        mid = self.cmd("send", "--agent", "owner", "--to", "km-agent-plugins-mac", "--subject", "Go")[1].strip()
        code, out, _ = self.cmd("check", "--hook", "--host", "kimi-code", "--event", "UserPromptSubmit", entree="")
        self.assertIn(mid, out)
        self.assertEqual(self.cmd("check", "--hook", "--host", "codex", "--event", "UserPromptSubmit", entree="")[1], "")

    def test_activate_declare_le_depot_et_equipe_les_hotes_du_poste(self):
        self.cmd("init")
        os.makedirs(os.path.join(self.dossier, ".claude"))   # Claude Code est « installé » sur ce faux poste
        depot_projet = os.path.join(self.dossier, "monrepo")
        os.makedirs(depot_projet)
        code, out, err = self.cmd("activate", "--project", "demo", cwd=depot_projet)
        self.assertEqual(code, 0, err)
        self.assertIn("dépôt connecté", out)
        self.assertIn("Claude Code", out)
        self.assertTrue(os.path.isfile(os.path.join(depot_projet, ".messenger.json")))
        self.assertFalse(os.path.exists(os.path.join(depot_projet, ".claude")))

        with open(os.path.join(self.dossier, ".claude.json"), encoding="utf-8") as f:
            serveur = json.load(f)["mcpServers"]["arkalabs-messenger"]
        self.assertEqual(serveur["args"][1:], ["mcp", "--host", "claude-code"])
        with open(os.path.join(self.dossier, ".claude", "settings.json"), encoding="utf-8") as f:
            hooks = json.load(f)["hooks"]
        for evenement in ("SessionStart", "UserPromptSubmit"):
            self.assertIn(f"check --hook --host claude-code --event {evenement}",
                          hooks[evenement][0]["hooks"][0]["command"])
        self.assertTrue(os.path.isfile(
            os.path.join(self.dossier, ".claude", "skills", "arkalabs-messenger", "SKILL.md")))

    def test_activate_retire_l_ancienne_releve_posee_dans_le_depot(self):
        self.cmd("init")
        depot_projet = os.path.join(self.dossier, "monrepo")
        os.makedirs(os.path.join(depot_projet, ".claude"))
        ancien = {"permissions": {"allow": ["Bash(ls)"]}, "hooks": {"SessionStart": [{"hooks": [
            {"type": "command", "command": "python", "args": ["/vieux/messenger.py", "check", "--hook"]}]}]}}
        with open(os.path.join(depot_projet, ".claude", "settings.local.json"), "w", encoding="utf-8") as f:
            json.dump(ancien, f)
        self.assertEqual(self.cmd("activate", "--project", "demo", cwd=depot_projet)[0], 0)
        with open(os.path.join(depot_projet, ".claude", "settings.local.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"permissions": {"allow": ["Bash(ls)"]}})


if __name__ == "__main__":
    unittest.main()
