"""L'interface construite est livrée avec l'outil : elle ne doit jamais être en retard sur son code.

`ui/dist` est versionné pour qu'un humain ouvre sa boîte sans Node. Chaque `npm run build` y pose
l'empreinte des sources (`ui/vite/tampon.ts`) ; on la recalcule ici, de la même façon.
"""
import hashlib
import json
import os
import unittest

DEPOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI = os.path.join(DEPOT, "ui")


def empreinte_des_sources() -> str:
    fichiers = ["index.html"]
    for dossier, _, noms in os.walk(os.path.join(UI, "src")):
        fichiers += [os.path.relpath(os.path.join(dossier, n), UI).replace(os.sep, "/") for n in noms]
    hache = hashlib.sha256()
    for f in sorted(f for f in fichiers if not f.endswith(".test.ts")):
        with open(os.path.join(UI, *f.split("/")), encoding="utf-8", newline="") as source:
            contenu = source.read().replace("\r\n", "\n")
        hache.update(f.encode("utf-8") + b"\0" + contenu.encode("utf-8") + b"\0")
    return hache.hexdigest()


class InterfaceLivree(unittest.TestCase):
    def test_elle_est_la_et_complete(self):
        with open(os.path.join(UI, "dist", "index.html"), encoding="utf-8") as f:
            page = f.read()
        for ressource in (r.split('"')[0] for r in page.split('="/assets/')[1:]):
            self.assertTrue(os.path.isfile(os.path.join(UI, "dist", "assets", ressource)), ressource)

    def test_elle_est_a_jour(self):
        with open(os.path.join(UI, "dist", "build.json"), encoding="utf-8") as f:
            tampon = json.load(f)["sources"]
        self.assertEqual(tampon, empreinte_des_sources(),
                         "l'interface livrée (ui/dist) est en retard sur ui/src : lance `npm run build` et versionne ui/dist")


if __name__ == "__main__":
    unittest.main()
