"""Équiper les hôtes IA : fusionner sans écraser, réparer ce qui a divergé, respecter le reste.

Tout se passe dans un faux dossier personnel : la vraie configuration des hôtes n'est jamais touchée.
"""
import json
import os
import tempfile
import unittest

from arkalabs_messenger.adapters.driving import hotes
from arkalabs_messenger.adapters.driving.hotes import ABSENT, AILLEURS, DIVERGENT, ILLISIBLE, SANS_OBJET, VERIFIE

DEPOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Poste(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = self._tmp.name
        self.ctx = hotes.Contexte(DEPOT, home=self.home, env={}, python="/usr/bin/python3")

    def tearDown(self):
        self._tmp.cleanup()

    def installer(self, *dossiers):
        for d in dossiers:
            os.makedirs(os.path.join(self.home, *d.split("/")), exist_ok=True)

    def ecrire(self, relatif, texte):
        chemin = os.path.join(self.home, *relatif.split("/"))
        os.makedirs(os.path.dirname(chemin), exist_ok=True)
        with open(chemin, "w", encoding="utf-8") as f:
            f.write(texte)
        return chemin

    def lire(self, relatif):
        with open(os.path.join(self.home, *relatif.split("/")), encoding="utf-8") as f:
            return f.read()

    def json(self, relatif):
        return json.loads(self.lire(relatif))


class Detection(Poste):
    def test_seuls_les_hotes_installes_sont_equipes(self):
        self.installer(".claude", ".cursor")
        self.assertEqual([h.id for h in hotes.presents(self.ctx)], ["claude-code", "cursor"])
        etats = hotes.equiper_presents(self.ctx)
        self.assertEqual([(e.id, e.equipe) for e in etats], [("claude-code", True), ("cursor", True)])
        self.assertFalse(os.path.exists(os.path.join(self.home, ".codex")))

    def test_un_hote_absent_n_est_jamais_cree(self):
        etat = hotes.equiper(hotes.hote("kimi-code"), self.ctx)
        self.assertFalse(etat.present)
        self.assertEqual(os.listdir(self.home), [])

    def test_le_dossier_d_un_hote_peut_etre_deplace(self):
        ailleurs = os.path.join(self.home, "conf-claude")
        os.makedirs(ailleurs)
        ctx = hotes.Contexte(DEPOT, home=self.home, env={"CLAUDE_CONFIG_DIR": ailleurs}, python="/usr/bin/python3")
        self.assertTrue(hotes.equiper(hotes.hote("claude-code"), ctx).equipe)
        self.assertTrue(os.path.isfile(os.path.join(ailleurs, ".claude.json")))
        self.assertTrue(os.path.isfile(os.path.join(ailleurs, "settings.json")))


class ClaudeCode(Poste):
    def setUp(self):
        super().setUp()
        self.installer(".claude")
        self.hote = hotes.hote("claude-code")

    def test_fusionne_sans_ecraser_et_reste_idempotent(self):
        self.ecrire(".claude.json", json.dumps({"numStartups": 7, "mcpServers": {"autre": {"type": "http", "url": "x"}}}))
        self.ecrire(".claude/settings.json", json.dumps({
            "permissions": {"deny": ["Bash(rm *)"]},
            "hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": "garde"}]}]}}))

        etat = hotes.equiper(self.hote, self.ctx)
        self.assertEqual((etat.mcp, etat.releve, etat.skill), (VERIFIE, VERIFIE, VERIFIE))

        config = self.json(".claude.json")
        self.assertEqual(config["numStartups"], 7)
        self.assertEqual(config["mcpServers"]["autre"], {"type": "http", "url": "x"})
        serveur = config["mcpServers"]["arkalabs-messenger"]
        self.assertEqual(serveur["type"], "stdio")
        self.assertEqual(serveur["args"][1:], ["mcp", "--host", "claude-code"])

        reglages = self.json(".claude/settings.json")
        self.assertEqual(reglages["permissions"], {"deny": ["Bash(rm *)"]})
        self.assertEqual(reglages["hooks"]["PreToolUse"][0]["hooks"][0]["command"], "garde")
        self.assertIn("--event SessionStart", reglages["hooks"]["SessionStart"][0]["hooks"][0]["command"])

        avant = (self.lire(".claude.json"), self.lire(".claude/settings.json"))
        hotes.equiper(self.hote, self.ctx)
        self.assertEqual((self.lire(".claude.json"), self.lire(".claude/settings.json")), avant)
        self.assertEqual(len(self.json(".claude/settings.json")["hooks"]["SessionStart"]), 1)

    def test_repare_une_entree_qui_a_diverge(self):
        hotes.equiper(self.hote, self.ctx)
        config = self.json(".claude.json")
        config["mcpServers"]["arkalabs-messenger"]["args"][0] = "/ancien/chemin/disparu/messenger.py"
        self.ecrire(".claude.json", json.dumps(config))
        self.assertEqual(hotes.etat(self.hote, self.ctx).mcp, DIVERGENT)
        self.assertEqual(hotes.equiper(self.hote, self.ctx).mcp, VERIFIE)

    def test_respecte_une_autre_installation(self):
        autre = self.ecrire("outils/messenger.py", "# une autre installation\n")
        self.ecrire(".claude.json", json.dumps({"mcpServers": {"arkalabs-messenger": {
            "type": "stdio", "command": "python3", "args": [autre, "mcp", "--host", "claude-code"]}}}))
        etat = hotes.equiper(self.hote, self.ctx)
        self.assertEqual(etat.mcp, AILLEURS)
        self.assertIn("autre installation", etat.note)
        self.assertEqual(self.json(".claude.json")["mcpServers"]["arkalabs-messenger"]["args"][0], autre)
        self.assertEqual(hotes.equiper(self.hote, self.ctx, forcer=True).mcp, VERIFIE)

    def test_ne_reecrit_jamais_un_fichier_illisible(self):
        casse = "{ ceci n'est pas du JSON"
        self.ecrire(".claude.json", casse)
        self.assertEqual(hotes.etat(self.hote, self.ctx).mcp, ILLISIBLE)
        with self.assertRaises(hotes.EquipementRefuse):
            hotes.equiper(self.hote, self.ctx)
        self.assertEqual(self.lire(".claude.json"), casse)

    def test_un_fichier_vide_vaut_aucune_entree(self):
        self.ecrire(".claude.json", "")
        self.assertEqual(hotes.etat(self.hote, self.ctx).mcp, ABSENT)
        self.assertEqual(hotes.equiper(self.hote, self.ctx).mcp, VERIFIE)

    def test_retirer_ne_retire_que_le_notre(self):
        self.ecrire(".claude/settings.json", json.dumps({
            "hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "garde"}]}]}}))
        hotes.equiper(self.hote, self.ctx)
        etat = hotes.retirer(self.hote, self.ctx)
        self.assertEqual((etat.mcp, etat.releve, etat.skill), (ABSENT, ABSENT, ABSENT))
        self.assertEqual(self.json(".claude/settings.json"),
                         {"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "garde"}]}]}})
        self.assertNotIn("arkalabs-messenger", self.json(".claude.json").get("mcpServers", {}))
        hotes.retirer(self.hote, self.ctx)  # idempotent


class Codex(Poste):
    CONFIG = '''# ma config Codex
model = "gpt-5.5"

[mcp_servers.node_repl]
command = "node"
args = ["repl.js"]

[mcp_servers.node_repl.env]
NODE_ENV = "production"
'''

    def setUp(self):
        super().setUp()
        self.installer(".codex")
        self.hote = hotes.hote("codex")

    def test_ajoute_sa_table_en_gardant_le_reste_tel_quel(self):
        self.ecrire(".codex/config.toml", self.CONFIG)
        etat = hotes.equiper(self.hote, self.ctx)
        self.assertEqual((etat.mcp, etat.releve, etat.skill), (VERIFIE, VERIFIE, SANS_OBJET))
        texte = self.lire(".codex/config.toml")
        self.assertTrue(texte.startswith(self.CONFIG.rstrip("\n")))
        self.assertIn("[mcp_servers.arkalabs-messenger]", texte)
        self.assertIn('"mcp", "--host", "codex"]', texte)
        self.assertIn("--host codex --event UserPromptSubmit",
                      self.json(".codex/hooks.json")["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"])
        hotes.equiper(self.hote, self.ctx)
        self.assertEqual(self.lire(".codex/config.toml"), texte)

    def test_repare_puis_retire_sa_table(self):
        self.ecrire(".codex/config.toml", self.CONFIG + '\n[mcp_servers.arkalabs-messenger]\ncommand = "vieux"\n'
                    'args = ["/disparu/messenger.py", "mcp"]\n\n[mcp_servers.arkalabs-messenger.env]\nX = "1"\n')
        self.assertEqual(hotes.etat(self.hote, self.ctx).mcp, DIVERGENT)
        self.assertEqual(hotes.equiper(self.hote, self.ctx).mcp, VERIFIE)
        self.assertNotIn('X = "1"', self.lire(".codex/config.toml"))
        hotes.retirer(self.hote, self.ctx)
        self.assertEqual(self.lire(".codex/config.toml"), self.CONFIG)

    def test_refuse_une_forme_qu_il_ne_sait_pas_editer(self):
        etrange = 'mcp_servers.arkalabs-messenger = { command = "x" }\n'
        self.ecrire(".codex/config.toml", etrange)
        self.assertEqual(hotes.etat(self.hote, self.ctx).mcp, ILLISIBLE)
        with self.assertRaises(hotes.EquipementRefuse):
            hotes.equiper(self.hote, self.ctx)
        self.assertEqual(self.lire(".codex/config.toml"), etrange)


class KimiCode(Poste):
    CONFIG = '''default_model = "kimi-k2"

[[hooks]]
event = "PreToolUse"
command = "echo garde"
timeout = 5
'''

    def setUp(self):
        super().setUp()
        self.installer(".kimi-code")
        self.hote = hotes.hote("kimi-code")

    def test_pose_deux_regles_de_quatre_champs_au_plus(self):
        self.ecrire(".kimi-code/config.toml", self.CONFIG)
        etat = hotes.equiper(self.hote, self.ctx)
        self.assertEqual((etat.mcp, etat.releve), (VERIFIE, VERIFIE))
        texte = self.lire(".kimi-code/config.toml")
        self.assertTrue(texte.startswith(self.CONFIG.rstrip("\n")))
        nos_regles = texte[len(self.CONFIG):].strip().split("[[hooks]]")[1:]
        self.assertEqual(len(nos_regles), 2)
        for regle in nos_regles:  # un champ de plus ferait échouer le chargement de la config de Kimi Code
            self.assertEqual(sorted(l.split("=")[0].strip() for l in regle.strip().splitlines()),
                             ["command", "event", "timeout"])
        self.assertEqual(self.json(".kimi-code/mcp.json")["mcpServers"]["arkalabs-messenger"]["args"][1:],
                         ["mcp", "--host", "kimi-code"])
        hotes.equiper(self.hote, self.ctx)
        self.assertEqual(self.lire(".kimi-code/config.toml"), texte)

    def test_retirer_garde_les_regles_des_autres(self):
        self.ecrire(".kimi-code/config.toml", self.CONFIG)
        hotes.equiper(self.hote, self.ctx)
        hotes.retirer(self.hote, self.ctx)
        self.assertEqual(self.lire(".kimi-code/config.toml"), self.CONFIG)


class SansHooks(Poste):
    def test_antigravity_et_cursor_n_ont_que_le_serveur_mcp(self):
        self.installer(".gemini/config", ".cursor")
        self.ecrire(".gemini/config/mcp_config.json", "")  # Antigravity laisse parfois ce fichier vide
        for identifiant, fichier in (("antigravity", ".gemini/config/mcp_config.json"), ("cursor", ".cursor/mcp.json")):
            etat = hotes.equiper(hotes.hote(identifiant), self.ctx)
            self.assertEqual((etat.mcp, etat.releve, etat.skill, etat.equipe), (VERIFIE, SANS_OBJET, SANS_OBJET, True))
            serveur = self.json(fichier)["mcpServers"]["arkalabs-messenger"]
            self.assertNotIn("type", serveur)
            self.assertEqual(serveur["args"][1:], ["mcp", "--host", identifiant])


if __name__ == "__main__":
    unittest.main()
