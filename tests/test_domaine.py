import unittest
from datetime import datetime

from arkalabs_messenger.domain import (
    Annuaire,
    Boite,
    Brouillon,
    Compte,
    CompteExistant,
    CompteInconnu,
    Message,
    MessageIntrouvable,
    MessageInvalide,
    NomInvalide,
    TransitionRefusee,
    valider_nom,
)


def message(mid="20260918-2250-windows", a=("kimi",), statut="nouveau", re=None):
    return Message(id=mid, date="2026-09-18T22:50:00+02:00", de="windows", a=tuple(a),
                   objet="Objet", statut=statut, re=re)


class Noms(unittest.TestCase):
    def test_accepte_la_convention(self):
        for nom in ("claude-windows", "kimi-mac", "claude-mac-2", "a", "x.y_z"):
            self.assertEqual(valider_nom(nom), nom)

    def test_refuse_le_reste(self):
        for nom in ("", "Kimi", "-kimi", "a b", "é", "x" * 33, None):
            with self.assertRaises(NomInvalide):
                valider_nom(nom)


class Redaction(unittest.TestCase):
    def test_normalise_objet_destinataires_et_corps(self):
        b = Brouillon.rediger("windows", [" kimi", "mac", "kimi"], "  Build   prêt ", ["ligne 1", "  ", "ligne 2  "])
        self.assertEqual(b.a, ("kimi", "mac"))
        self.assertEqual(b.objet, "Build prêt")
        self.assertEqual(b.corps, ("ligne 1", "ligne 2"))

    def test_refuse_un_corps_de_trois_lignes(self):
        with self.assertRaisesRegex(MessageInvalide, "deux lignes"):
            Brouillon.rediger("windows", ["kimi"], "Objet", ["a", "b", "c"])

    def test_refuse_objet_vide_et_sans_destinataire(self):
        with self.assertRaises(MessageInvalide):
            Brouillon.rediger("windows", ["kimi"], "   ")
        with self.assertRaises(MessageInvalide):
            Brouillon.rediger("windows", [" ", ""], "Objet")

    def test_refuse_un_destinataire_mal_nomme(self):
        with self.assertRaises(NomInvalide):
            Brouillon.rediger("windows", ["Kimi"], "Objet")


class Statuts(unittest.TestCase):
    def test_avance_et_trace_l_historique(self):
        m = message().avancer("kimi", "lu", "t1").avancer("kimi", "traité", "t2")
        self.assertEqual(m.statut, "traité")
        self.assertEqual([(t.par, t.statut, t.date) for t in m.historique], [("kimi", "lu", "t1"), ("kimi", "traité", "t2")])

    def test_seul_un_destinataire_fait_avancer(self):
        with self.assertRaisesRegex(TransitionRefusee, "n'est pas destinataire"):
            message().avancer("windows", "lu", "t")

    def test_un_statut_ne_recule_pas(self):
        with self.assertRaisesRegex(TransitionRefusee, "ne recule pas"):
            message(statut="traité").avancer("kimi", "lu", "t")
        with self.assertRaises(TransitionRefusee):
            message(statut="lu").avancer("kimi", "lu", "t")

    def test_suite_pour(self):
        self.assertEqual(message().suite_pour("kimi"), "lu")
        self.assertEqual(message(statut="lu").suite_pour("kimi"), "traité")
        self.assertIsNone(message(statut="traité").suite_pour("kimi"))
        self.assertIsNone(message().suite_pour("windows"))

    def test_titre_d_une_reponse(self):
        self.assertEqual(message(re="20260918-2248-kimi").titre, "Re : 20260918-2248-kimi — Objet")


class BoiteAgregat(unittest.TestCase):
    def test_identifiant_suffixe_en_cas_de_collision(self):
        b = Boite()
        instant = datetime(2026, 9, 18, 22, 50)
        ids = []
        for _ in range(3):
            mid = b.identifiant_libre("windows", instant)
            b.ajouter(message(mid))
            ids.append(mid)
        self.assertEqual(ids, ["20260918-2250-windows", "20260918-2250-windows-2", "20260918-2250-windows-3"])

    def test_refuse_une_reponse_a_un_message_absent(self):
        with self.assertRaises(MessageIntrouvable):
            Boite().ajouter(message(re="inexistant"))

    def test_marquer_un_message_absent(self):
        with self.assertRaises(MessageIntrouvable):
            Boite().marquer("x", "kimi", "lu", "t")

    def test_recents_et_participants(self):
        b = Boite([message("1", a=("kimi",)), message("2", a=("mac", "owner"))])
        self.assertEqual([m.id for m in b.recents()], ["2", "1"])
        self.assertEqual(b.participants(), ["windows", "kimi", "mac", "owner"])


class Comptes(unittest.TestCase):
    def test_inscrire_puis_refuser_le_doublon(self):
        a = Annuaire()
        self.assertTrue(a.inscrire(Compte.ouvrir("kimi-mac", "kimi-code", "dev", machine="Mac")))
        with self.assertRaisesRegex(CompteExistant, "existe déjà"):
            a.inscrire(Compte.ouvrir("kimi-mac", "kimi-code", "autre"))

    def test_mise_a_jour_garde_creation_et_champs_omis(self):
        a = Annuaire()
        a.inscrire(Compte.ouvrir("kimi-mac", "kimi-code", "dev", machine="Mac", cree="t0"))
        self.assertFalse(a.inscrire(Compte.ouvrir("kimi-mac", "kimi-code", "plugins", cree="t1"), mise_a_jour=True))
        c = a.compte("kimi-mac")
        self.assertEqual((c.role, c.machine, c.cree), ("plugins", "Mac", "t0"))

    def test_desactiver_puis_verifier(self):
        a = Annuaire()
        a.inscrire(Compte.ouvrir("windows", "claude-code", "build"))
        a.inscrire(Compte.ouvrir("kimi", "kimi-code", "dev"))
        a.desactiver("kimi")
        self.assertEqual(a.actifs(), ["windows"])
        with self.assertRaisesRegex(CompteInconnu, "comptes actifs : windows"):
            a.verifier("windows", ["kimi"])
        with self.assertRaisesRegex(CompteInconnu, "n'a pas de compte actif"):
            a.verifier("kimi", ["windows"])

    def test_role_obligatoire(self):
        with self.assertRaises(MessageInvalide):
            Compte.ouvrir("kimi", "kimi-code", "   ")


if __name__ == "__main__":
    unittest.main()
