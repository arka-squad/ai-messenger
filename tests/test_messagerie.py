"""Les cas d'usage, contre des doublures en mémoire."""
import unittest

from arkalabs_messenger.application import BoiteExistante, PieceJointeRefusee
from arkalabs_messenger.domain import CompteInconnu, Message, MessageIntrouvable, TransitionRefusee

from .doublures import SourceMemoire, messagerie


def avec_comptes(*noms, **options):
    m, *reste = messagerie(**options)
    for nom in noms:
        m.inscrire(nom, "claude-code", f"rôle de {nom}")
    return (m, *reste)


class Envoyer(unittest.TestCase):
    def test_envoie_et_identifie(self):
        m, boite, *_ = avec_comptes("windows", "kimi")
        envoi = m.envoyer("windows", ["kimi"], "Build prêt", "Ligne 1\nLigne 2")
        self.assertTrue(envoi.adresses_verifiees)
        self.assertEqual(envoi.message.id, "20260918-2250-windows")
        self.assertEqual(envoi.message.date, "2026-09-18T22:50:00+02:00")
        self.assertEqual(boite.lire().message(envoi.message.id).corps, ("Ligne 1", "Ligne 2"))

    def test_refuse_un_destinataire_sans_compte(self):
        m, *_ = avec_comptes("windows", "kimi")
        with self.assertRaisesRegex(CompteInconnu, "kimi-mc"):
            m.envoyer("windows", ["kimi-mc"], "Objet")

    def test_sans_annuaire_les_adresses_ne_sont_pas_verifiees(self):
        m, *_ = messagerie(annuaire=False)
        self.assertFalse(m.envoyer("windows", ["qui-que-ce-soit"], "Objet").adresses_verifiees)

    def test_depose_la_piece_jointe(self):
        m, _, _, pieces, _ = avec_comptes("windows", "kimi", pieces={"/tmp/rapport.md": "détail"})
        envoi = m.envoyer("windows", ["kimi"], "Objet", piece="/tmp/rapport.md")
        self.assertEqual(envoi.message.pj, "rapport.md")
        self.assertIn("rapport.md", pieces.deposees)

    def test_pas_de_piece_orpheline_si_la_reponse_est_invalide(self):
        m, boite, _, pieces, _ = avec_comptes("windows", "kimi", pieces={"/tmp/rapport.md": "détail"})
        with self.assertRaises(MessageIntrouvable):
            m.envoyer("windows", ["kimi"], "Objet", piece="/tmp/rapport.md", re="inexistant")
        self.assertEqual(pieces.deposees, {})
        self.assertEqual(boite.lire().messages, [])

    def test_piece_introuvable(self):
        m, boite, *_ = avec_comptes("windows", "kimi")
        with self.assertRaises(PieceJointeRefusee):
            m.envoyer("windows", ["kimi"], "Objet", piece="/nulle/part.md")
        self.assertEqual(boite.lire().messages, [])

    def test_repondre(self):
        m, *_ = avec_comptes("windows", "kimi")
        premier = m.envoyer("windows", ["kimi"], "Question").message
        reponse = m.envoyer("kimi", ["windows"], "Réponse", re=premier.id).message
        self.assertEqual(reponse.re, premier.id)


class ReleverEtMarquer(unittest.TestCase):
    def test_releve_puis_marque(self):
        m, *_ = avec_comptes("windows", "kimi")
        mid = m.envoyer("windows", ["kimi"], "Objet").message.id
        self.assertEqual([x.id for x in m.releve("kimi")], [mid])
        self.assertEqual(m.releve("windows"), [])
        m.marquer("kimi", mid, "lu")
        self.assertEqual(m.releve("kimi"), [])
        with self.assertRaises(TransitionRefusee):
            m.marquer("windows", mid, "traité")

    def test_lister_filtre_et_ordonne(self):
        m, *_ = avec_comptes("windows", "kimi", "mac")
        a = m.envoyer("windows", ["kimi"], "A").message.id
        b = m.envoyer("mac", ["windows"], "B").message.id
        m.envoyer("mac", ["kimi"], "C")
        self.assertEqual([x.id for x in m.lister("windows")], [b, a])
        self.assertEqual(len(m.lister(limite=2)), 2)
        m.marquer("kimi", a, "lu")
        self.assertEqual([x.id for x in m.lister(statut="lu")], [a])


class Guetter(unittest.TestCase):
    def test_se_reveille_seulement_pour_un_nouveau_message_adresse(self):
        m, _, _, _, horloge = avec_comptes("windows", "kimi", "mac")
        attendu = []
        horloge.au_reveil = [
            lambda: m.envoyer("kimi", ["windows"], "Envoi de kimi : ne réveille pas"),
            lambda: m.envoyer("mac", ["windows"], "Pour un autre : ne réveille pas"),
            lambda: attendu.append(m.envoyer("mac", ["kimi"], "Pour kimi").message.id),
        ]
        recus = m.guetter("kimi", intervalle=10, heures=1)
        self.assertEqual([x.id for x in recus], attendu)

    def test_un_changement_de_statut_ne_reveille_pas(self):
        m, _, _, _, horloge = avec_comptes("windows", "kimi")
        mid = m.envoyer("windows", ["kimi"], "Déjà là").message.id
        horloge.au_reveil = [lambda: m.marquer("kimi", mid, "lu")]
        self.assertEqual(m.guetter("kimi", intervalle=60, heures=0.05), [])

    def test_echeance(self):
        m, _, _, _, horloge = avec_comptes("kimi")
        self.assertEqual(m.guetter("kimi", intervalle=600, heures=1), [])
        self.assertGreaterEqual(horloge.ecoule, 3600)


class Importer(unittest.TestCase):
    def test_importe_et_cree_les_comptes(self):
        m, boite, comptes, *_ = messagerie()
        boite.boite = None  # la cible n'existe pas encore
        anciens = [Message(id="20260917-2250-mac", date="2026-09-17T22:50:00", de="mac", a=("windows",),
                           objet="Demande", statut="traité", importe=True)]
        resultat = m.importer(SourceMemoire(anciens))
        self.assertEqual((resultat.messages, resultat.comptes), (1, ("mac", "windows")))
        self.assertEqual(comptes.lire().compte("mac").hote, "unknown")

    def test_refuse_d_ecraser_une_boite(self):
        m, *_ = messagerie()
        with self.assertRaises(BoiteExistante):
            m.importer(SourceMemoire([]))


if __name__ == "__main__":
    unittest.main()
