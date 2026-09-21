"""Le statut appartient à chaque destinataire : qu'un seul lise n'éteint pas le réveil des autres.

Le cas est réel, observé le 20/09/2026 : une annonce adressée à dix comptes a été ouverte dans
l'interface par `owner` (l'humain). Le statut étant commun, elle est passée « lu » pour tout le
monde d'un coup — plus aucune relève, plus aucune veille ne l'a vue. C'était la vraie cause de
« mes agents ne se réveillent pas quand ils ont un message », puisque l'humain est en copie de
presque tout. Ces tests verrouillent la correction.
"""
import unittest

from arkalabs_messenger.adapters.codec import message_depuis_dict, message_vers_dict
from arkalabs_messenger.domain import Message, TransitionRefusee

from .doublures import messagerie


def message(a=("kimi", "owner", "codex"), statut="nouveau", **reste):
    return Message(id="20260920-2045-windows", date="2026-09-20T20:45:00+02:00", de="windows", a=tuple(a),
                   objet="La boîte a déménagé", statut=statut, **reste)


class ChacunSonStatut(unittest.TestCase):
    def test_lire_n_engage_que_celui_qui_lit(self):
        m = message().avancer("owner", "lu", "2026-09-20T20:46:00+02:00")
        self.assertEqual(m.statut_de("owner"), "lu")
        self.assertEqual(m.statut_de("kimi"), "nouveau")
        self.assertTrue(m.est_nouveau_pour("kimi"))
        self.assertFalse(m.est_nouveau_pour("owner"))

    def test_la_vue_d_ensemble_est_le_moins_avance(self):
        m = message().avancer("owner", "lu", "d1").avancer("kimi", "lu", "d2")
        self.assertEqual(m.statut, "nouveau")  # codex n'a rien vu
        m = m.avancer("codex", "lu", "d3")
        self.assertEqual(m.statut, "lu")
        for qui in ("owner", "kimi", "codex"):
            m = m.avancer(qui, "traité", f"d-{qui}")
        self.assertEqual(m.statut, "traité")

    def test_chacun_a_sa_prochaine_etape(self):
        m = message().avancer("owner", "lu", "d1")
        self.assertEqual(m.suite_pour("owner"), "traité")
        self.assertEqual(m.suite_pour("kimi"), "lu")
        self.assertIsNone(m.suite_pour("windows"))  # l'expéditeur ne marque rien

    def test_un_statut_ne_recule_pas_pour_qui_l_a_deja_donne(self):
        m = message().avancer("owner", "lu", "d1")
        with self.assertRaisesRegex(TransitionRefusee, "cannot move backward"):
            m.avancer("owner", "lu", "d2")
        self.assertEqual(m.avancer("kimi", "lu", "d3").statut_de("kimi"), "lu")  # un autre, lui, peut

    def test_seul_un_destinataire_avance(self):
        with self.assertRaisesRegex(TransitionRefusee, "not a recipient"):
            message().avancer("quelqu-un-dautre", "lu", "d1")

    def test_un_compte_fusionne_avance_sous_son_ancienne_adresse(self):
        m = message(a=("cloud", "kimi")).avancer("cl-agent-cloud@cortex", "lu", "d1", aussi=("cloud",))
        self.assertEqual(m.statut_de("cloud"), "lu")
        self.assertEqual(m.statut_de("kimi"), "nouveau")
        self.assertEqual(m.historique[-1].par, "cl-agent-cloud@cortex")  # qui a agi vraiment

    def test_le_statut_vu_par_celui_qui_releve(self):
        m = message().avancer("owner", "lu", "d1")
        self.assertEqual(m.statut_vu_par(["owner"]), "lu")
        self.assertEqual(m.statut_vu_par(["kimi"]), "nouveau")
        self.assertEqual(m.statut_vu_par(["windows"]), "nouveau")  # pas destinataire : la vue d'ensemble


class LaReleveEtLaVeille(unittest.TestCase):
    """Le scénario du 20/09, de bout en bout."""

    def messagerie_avec_annonce(self):
        m, *reste = messagerie()
        for nom in ("windows", "owner", "kimi", "codex"):
            m.inscrire(nom, "claude-code", f"rôle de {nom}", machine="arka")
        envoi = m.envoyer("windows", ["owner", "kimi", "codex"], "La boîte a déménagé")
        return m, envoi.message.id

    def test_l_humain_qui_lit_ne_prive_personne_de_son_courrier(self):
        m, mid = self.messagerie_avec_annonce()
        m.marquer("owner", mid, "lu")
        self.assertEqual([x.id for x in m.releve("kimi")], [mid])
        self.assertEqual([x.id for x in m.releve("codex")], [mid])
        self.assertEqual(m.releve("owner"), [])

    def test_l_annonce_de_la_releve_compte_le_courrier_qui_attend_encore(self):
        """Ce qui déclenche « un courrier attend un compte de ton hôte sur ce poste »."""
        m, mid = self.messagerie_avec_annonce()
        m.marquer("owner", mid, "traité")
        attentes = {c.nom: n for c, n in m.en_attente_sur_ce_poste("claude-code", "arka")}
        self.assertEqual(attentes, {"kimi": 1, "codex": 1})  # owner a fini, les deux autres attendent

    def test_lister_filtre_sur_le_statut_de_celui_qui_demande(self):
        m, mid = self.messagerie_avec_annonce()
        m.marquer("owner", mid, "lu")
        self.assertEqual([x.id for x in m.lister("kimi", statut="nouveau")], [mid])
        self.assertEqual(m.lister("owner", statut="nouveau"), [])
        self.assertEqual([x.id for x in m.lister("owner", statut="lu")], [mid])


class LeFormat(unittest.TestCase):
    def test_aller_retour(self):
        m = message().avancer("owner", "lu", "2026-09-20T20:46:00+02:00")
        d = message_vers_dict(m)
        self.assertEqual(d["statuts"], {"kimi": "nouveau", "owner": "lu", "codex": "nouveau"})
        self.assertEqual(d["statut"], "nouveau")
        self.assertEqual(message_depuis_dict(d), m)

    def test_un_message_d_avant_cette_version_donne_son_statut_a_tous(self):
        """Sans `statuts`, le fichier ne dit rien de qui a lu : on ne l'invente pas."""
        ancien = {"id": "20260901-1000-windows", "date": "2026-09-01T10:00:00+02:00", "de": "windows",
                  "a": ["kimi", "owner"], "objet": "Avant", "corps": [], "pj": None, "re": None,
                  "statut": "lu", "historique": []}
        m = message_depuis_dict(ancien)
        self.assertEqual(m.statuts, {"kimi": "lu", "owner": "lu"})
        self.assertEqual(m.statut, "lu")
        self.assertFalse(m.est_nouveau_pour("kimi"))

    def test_un_ancien_message_neuf_reste_du_courrier_pour_tous(self):
        ancien = {"id": "20260901-1000-windows", "date": "2026-09-01T10:00:00+02:00", "de": "windows",
                  "a": ["kimi", "owner"], "objet": "Avant", "corps": [], "pj": None, "re": None,
                  "statut": "nouveau", "historique": []}
        m = message_depuis_dict(ancien)
        self.assertTrue(m.est_nouveau_pour("kimi") and m.est_nouveau_pour("owner"))

    def test_un_statuts_mal_forme_est_refuse(self):
        from arkalabs_messenger.adapters.codec import FormatInvalide
        d = message_vers_dict(message())
        d["statuts"] = {"kimi": 3}
        with self.assertRaisesRegex(FormatInvalide, "statuts"):
            message_depuis_dict(d)

    def test_une_avancee_ecrite_par_une_version_anterieure_est_rattrapee(self):
        """Le Mac en 0.1.17 fait avancer `statut` sans toucher à `statuts` : l'historique dit qui a agi."""
        d = message_vers_dict(message(a=("kimi", "owner")))
        d["statut"] = "lu"  # ce qu'écrit l'ancienne version
        d["historique"] = [{"date": "2026-09-20T21:00:00+02:00", "par": "kimi", "statut": "lu"}]
        m = message_depuis_dict(d)
        self.assertEqual(m.statut_de("kimi"), "lu")          # rattrapé : il l'a vraiment lu
        self.assertEqual(m.statut_de("owner"), "nouveau")    # rien supposé pour les autres
        self.assertEqual(m.statut, "nouveau")

    def test_un_destinataire_absent_de_statuts_est_du_courrier_neuf(self):
        """Ajouté à la main dans le fichier : il n'a rien lu, on ne le déclare pas lu."""
        d = message_vers_dict(message().avancer("owner", "lu", "d1"))
        d["a"].append("nouveau-venu")
        m = message_depuis_dict(d)
        self.assertTrue(m.est_nouveau_pour("nouveau-venu"))
        self.assertEqual(m.statut, "nouveau")


if __name__ == "__main__":
    unittest.main()
