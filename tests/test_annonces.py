"""Les annonces : une notification système par message qui passe."""
import os
import tempfile
import unittest

from arkalabs_messenger import demonstration
from arkalabs_messenger.adapters.driven.notifications_systeme import AUMID, commande
from arkalabs_messenger.application import Annonceur, Notificateur
from arkalabs_messenger.bootstrap import Usine

from .doublures import messagerie


class NotificateurMemoire(Notificateur):
    def __init__(self):
        self.recues = []

    def notifier(self, titre, lignes, lien=None):
        self.recues.append((titre, list(lignes), lien))


def installation():
    m, *_ = messagerie()
    for nom in ("owner", "kimi-mac", "claude-windows"):
        m.inscrire(nom, "claude-code", "test")
    notificateur = NotificateurMemoire()
    annonceur = Annonceur(m, notificateur, "owner", lien=lambda x: f"http://interface/?message={x.id}")
    return m, notificateur, annonceur


class Annonces(unittest.TestCase):
    def test_la_premiere_releve_memorise_sans_annoncer(self):
        m, notificateur, annonceur = installation()
        m.envoyer("kimi-mac", ["owner"], "Déjà là")
        self.assertEqual(annonceur.relever(), [])
        self.assertEqual(notificateur.recues, [])

    def test_annonce_chaque_message_qui_passe(self):
        m, notificateur, annonceur = installation()
        annonceur.relever()
        pour_moi = m.envoyer("kimi-mac", ["owner"], "On publie ce soir ?", "Le plugin est prêt.").message
        m.envoyer("claude-windows", ["kimi-mac"], "Build prêt")
        self.assertEqual(len(annonceur.relever()), 2)
        self.assertEqual(notificateur.recues, [
            ("kimi-mac wrote to you", ["On publie ce soir ?", "Le plugin est prêt."],
             f"http://interface/?message={pour_moi.id}"),
            ("claude-windows → kimi-mac", ["Build prêt"], notificateur.recues[1][2]),
        ])
        self.assertEqual(annonceur.relever(), [])

    def test_un_changement_de_statut_n_annonce_rien(self):
        m, notificateur, annonceur = installation()
        mid = m.envoyer("kimi-mac", ["owner"], "Objet").message.id
        annonceur.relever()
        m.marquer("owner", mid, "lu")
        annonceur.relever()
        self.assertEqual(notificateur.recues, [])

    def test_une_rafale_est_resumee(self):
        m, notificateur, annonceur = installation()
        annonceur.relever()
        for i in range(5):
            m.envoyer("kimi-mac", ["owner" if i < 2 else "claude-windows"], f"Message {i}")
        annonceur.relever()
        self.assertEqual(len(notificateur.recues), 1)
        self.assertEqual(notificateur.recues[0][:2], ("5 new messages in the mailbox", ["including 2 for owner"]))

    def test_coupe_n_annonce_pas_mais_suit_la_boite(self):
        m, notificateur, annonceur = installation()
        annonceur.relever()
        annonceur.actif = False
        m.envoyer("kimi-mac", ["owner"], "Pendant la coupure")
        annonceur.relever()
        annonceur.actif = True
        self.assertEqual(annonceur.relever(), [])
        self.assertEqual(notificateur.recues, [])


class CommandesSysteme(unittest.TestCase):
    def test_windows_passe_le_texte_par_l_environnement(self):
        argv, env = commande("win32", "kimi-mac t'écrit", ["Objet ; $(rm -rf /)", "corps"], "http://x/?message=1")
        self.assertEqual(argv[0], "powershell.exe")
        self.assertNotIn("rm -rf", " ".join(argv))
        self.assertEqual((env["MESSENGER_TITRE"], env["MESSENGER_TEXTE"]), ("kimi-mac t'écrit", "Objet ; $(rm -rf /)\ncorps"))
        self.assertEqual((env["MESSENGER_AUMID"], env["MESSENGER_LIEN"]), (AUMID, "http://x/?message=1"))
        self.assertTrue(env["MESSENGER_ICONE"].startswith("file:///"))

    def test_macos_passe_le_texte_en_arguments(self):
        argv, env = commande("darwin", "titre", ["ligne 1", "ligne 2"])
        self.assertEqual(argv[0], "osascript")
        self.assertEqual(argv[-2:], ["titre", "ligne 1 — ligne 2"])
        self.assertEqual(env, {})


class Demonstration(unittest.TestCase):
    def test_cree_une_boite_vivante_une_seule_fois(self):
        with tempfile.TemporaryDirectory() as dossier:
            chemin = demonstration.preparer(dossier)
            m = Usine().ouvrir(chemin)
            messages = m.instantane().messages
            self.assertEqual(len(messages), len(demonstration.SCENARIO))
            self.assertEqual({c.nom for c in m.comptes()}, {nom for nom, _, _ in demonstration.COMPTES})
            self.assertEqual(sorted(m.statut for m in messages).count("nouveau"), 3)
            self.assertTrue(all(m.piece_jointe(x.pj) for x in messages if x.pj))
            avant = os.path.getmtime(chemin)
            self.assertEqual(demonstration.preparer(dossier), chemin)
            self.assertEqual(os.path.getmtime(chemin), avant)


if __name__ == "__main__":
    unittest.main()
