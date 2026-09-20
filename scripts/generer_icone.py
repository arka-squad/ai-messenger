"""Dessine l'icône de Messenger et l'écrit en PNG, ICO (Windows) et ICNS (macOS) — bibliothèque standard seulement.

À relancer seulement si le dessin change :

    python3 scripts/generer_icone.py

Les fichiers produits (`src/arkalabs_messenger/ressources/`) sont versionnés : le raccourci du bureau
(`messenger.py shortcut`) les utilise tels quels, sans rien avoir à installer.
"""
import math
import os
import struct
import zlib

ICI = os.path.dirname(os.path.abspath(__file__))
SORTIE = os.path.join(os.path.dirname(ICI), "src", "arkalabs_messenger", "ressources")

ROUGE = (199, 15, 67)      # --arka-red
BLANC = (255, 255, 255)
TAILLE, SUR = 512, 3        # 512 px, chaque pixel échantillonné 3 × 3 fois


def _rectangle_arrondi(x, y, x0, y0, x1, y1, r):
    """Distance signée au bord d'un rectangle arrondi : négative à l'intérieur."""
    dx = max(x0 + r - x, 0, x - (x1 - r))
    dy = max(y0 + r - y, 0, y - (y1 - r))
    return math.hypot(dx, dy) - r


def _segment(x, y, ax, ay, bx, by):
    px, py, vx, vy = x - ax, y - ay, bx - ax, by - ay
    t = max(0.0, min(1.0, (px * vx + py * vy) / (vx * vx + vy * vy)))
    return math.hypot(px - t * vx, py - t * vy)


def _couleur(x, y):
    """La couleur (r, v, b, alpha) du point (x, y), en coordonnées 0..1."""
    if _rectangle_arrondi(x, y, 0.04, 0.04, 0.96, 0.96, 0.21) > 0:
        return (0, 0, 0, 0)
    dans_l_enveloppe = _rectangle_arrondi(x, y, 0.20, 0.30, 0.80, 0.70, 0.05) <= 0
    rabat = min(_segment(x, y, 0.22, 0.33, 0.50, 0.54), _segment(x, y, 0.50, 0.54, 0.78, 0.33)) <= 0.022
    return (*(BLANC if dans_l_enveloppe and not rabat else ROUGE), 255)


def dessiner(taille=TAILLE, sur=SUR):
    lignes = []
    for j in range(taille):
        ligne = bytearray()
        for i in range(taille):
            r = v = b = a = 0
            for dj in range(sur):
                for di in range(sur):
                    cr, cv, cb, ca = _couleur((i + (di + 0.5) / sur) / taille, (j + (dj + 0.5) / sur) / taille)
                    r, v, b, a = r + cr * ca, v + cv * ca, b + cb * ca, a + ca
            n = sur * sur
            ligne += bytes((r // a, v // a, b // a, a // n) if a else (0, 0, 0, 0))
        lignes.append(bytes(ligne))
    return lignes


def reduire(lignes, facteur):
    """Divise la taille par `facteur` en moyennant les pixels (alpha pris en compte)."""
    taille = len(lignes) // facteur
    sortie = []
    for j in range(taille):
        ligne = bytearray()
        for i in range(taille):
            r = v = b = a = 0
            for dj in range(facteur):
                source = lignes[j * facteur + dj]
                for di in range(facteur):
                    k = (i * facteur + di) * 4
                    alpha = source[k + 3]
                    r, v, b, a = r + source[k] * alpha, v + source[k + 1] * alpha, b + source[k + 2] * alpha, a + alpha
            ligne += bytes((r // a, v // a, b // a, a // (facteur * facteur)) if a else (0, 0, 0, 0))
        sortie.append(bytes(ligne))
    return sortie


def png(lignes):
    def bloc(nom, donnees):
        return struct.pack(">I", len(donnees)) + nom + donnees + struct.pack(">I", zlib.crc32(nom + donnees) & 0xFFFFFFFF)

    taille = len(lignes)
    brut = b"".join(b"\x00" + ligne for ligne in lignes)
    return (b"\x89PNG\r\n\x1a\n" + bloc(b"IHDR", struct.pack(">IIBBBBB", taille, taille, 8, 6, 0, 0, 0))
            + bloc(b"IDAT", zlib.compress(brut, 9)) + bloc(b"IEND", b""))


def ico(images):
    """Un .ico dont chaque image est un PNG (accepté depuis Windows Vista). `images` : {taille: png}."""
    entete = struct.pack("<HHH", 0, 1, len(images))
    table, corps, position = b"", b"", 6 + 16 * len(images)
    for taille, donnees in sorted(images.items()):
        table += struct.pack("<BBBBHHII", taille % 256, taille % 256, 0, 0, 1, 32, len(donnees), position)
        corps += donnees
        position += len(donnees)
    return entete + table + corps


def icns(images):
    """Un .icns : des PNG sous les types `ic07` (128), `ic08` (256), `ic09` (512)."""
    types = {128: b"ic07", 256: b"ic08", 512: b"ic09"}
    corps = b"".join(types[t] + struct.pack(">I", len(d) + 8) + d for t, d in sorted(images.items()) if t in types)
    return b"icns" + struct.pack(">I", len(corps) + 8) + corps


def main():
    os.makedirs(SORTIE, exist_ok=True)
    grand = dessiner()
    images = {512: png(grand), 256: png(reduire(grand, 2)), 128: png(reduire(grand, 4)), 64: png(reduire(grand, 8)),
              32: png(reduire(grand, 16))}
    fichiers = {
        "messenger.png": images[256],
        "messenger.ico": ico({t: images[t] for t in (32, 64, 128, 256)}),
        "messenger.icns": icns(images),
    }
    for nom, donnees in fichiers.items():
        with open(os.path.join(SORTIE, nom), "wb") as f:
            f.write(donnees)
        print(f"{nom} : {len(donnees)} octets")


if __name__ == "__main__":
    main()
