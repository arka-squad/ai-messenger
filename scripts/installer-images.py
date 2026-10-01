"""Images NSIS de arkalabs Messenger au gabarit Cortex.

python scripts/installer-images.py <repo> [<dossier-apercus>]
Écrit src-tauri/icons/installer-header.bmp (150x57) et installer-sidebar.bmp (164x314), BMP 24 bits.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

REPO = Path(sys.argv[1])
PREVIEW = Path(sys.argv[2]) if len(sys.argv) > 2 else None
FONTS = REPO / "src/assets/fonts"
S = 4  # suréchantillonnage
RED = (199, 15, 67)  # --arka-red #c70f43
HALO = (235, 0, 45)  # halo plus saturé, comme Cortex


def font(weight, px):
    return ImageFont.truetype(str(FONTS / f"Poppins-{weight}.ttf"), round(px * S))


def lerp(a, b, t):
    return np.asarray(a, float) + (np.asarray(b, float) - np.asarray(a, float)) * t


# --- Marque officielle (arka-logo-mark.svg, carré 747.4) : rayon 138.8, hexagone pointe en haut,
# plats extérieurs à 245.6 du centre (arrondi 59.6), plats intérieurs à 196 (arrondi 47.5),
# centre de l'hexagone 10.1 sous celui du carré.
U = 747.4


def sd_box(x, y, half, r):
    qx, qy = np.abs(x) - (half - r), np.abs(y) - (half - r)
    return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r


def sd_hex(x, y, apothem, r):
    """Hexagone pointe en haut (plats verticaux) d'apothème `apothem`, coins arrondis de rayon r."""
    k = (-0.866025404, 0.5, 0.577350269)
    px, py = np.abs(y), np.abs(x)  # formule plats horizontaux, axes échangés
    a = apothem - r
    dot = np.minimum(k[0] * px + k[1] * py, 0)
    px, py = px - 2 * dot * k[0], py - 2 * dot * k[1]
    px, py = px - np.clip(px, -k[2] * a, k[2] * a), py - a
    return np.hypot(px, py) * np.sign(py) - r


def mark(size):
    """Marque brillante (RGBA, suréchantillonnée) de `size` px de côté final."""
    n = int(round(size * S))
    c = (np.arange(n) + 0.5) / n - 0.5  # centre en 0, côté 1
    X, Y = np.meshgrid(c, c)
    sq = sd_box(X, Y, 0.5, 138.8 / U)
    inside = sq <= 0
    hy = Y - 10.1 / U
    ring = (sd_hex(X, hy, 245.6 / U, 59.6 / U) <= 0) & (sd_hex(X, hy, 196.0 / U, 47.5 / U) > 0)
    t = (Y + 0.5)[..., None]
    # Dégradé vertical façon Cortex : rouge vif en haut, plus sombre en bas.
    col = lerp((244, 20, 78), (188, 8, 48), t)
    # Liseré clair sur le bord haut, qui s'éteint vers le milieu.
    rim = ((sq > -0.014) * np.clip(1 - (Y + 0.5) / 0.4, 0, 1))[..., None]
    col = lerp(col, (255, 130, 160), 0.6 * rim)
    col = np.where(ring[..., None], lerp((255, 255, 255), (224, 220, 224), t), col)
    rgba = np.dstack([col, inside * 255.0]).clip(0, 255).astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")


def glow(canvas, box, radius, strength, color=HALO):
    """Halo additif autour d'un rectangle arrondi (box en px finaux)."""
    w, h = canvas.size
    m = Image.new("L", (w, h), 0)
    x0, y0, x1, y1 = [v * S for v in box]
    ImageDraw.Draw(m).rounded_rectangle((x0, y0, x1, y1), radius=(x1 - x0) * 138.8 / U, fill=255)
    m = m.filter(ImageFilter.GaussianBlur(radius * S))
    a = np.asarray(m, float)[..., None] / 255 * strength
    base = np.asarray(canvas, float)
    out = base + (np.asarray(color, float) - base) * np.clip(a, 0, 1)
    return Image.fromarray(out.clip(0, 255).astype(np.uint8), "RGB")


def place_mark(canvas, size, x, y, reflect=0.32, reflect_len=0.5, gap=1.5):
    """Colle la marque et son reflet au sol (x, y en px finaux)."""
    mk = mark(size)
    n = mk.size[0]
    ref = mk.transpose(Image.FLIP_TOP_BOTTOM)
    fade = np.clip(1 - np.linspace(0, 1, n) / reflect_len, 0, 1) * reflect
    alpha = (np.asarray(ref.getchannel("A"), float) * fade[:, None]).astype(np.uint8)
    ref.putalpha(Image.fromarray(alpha, "L"))
    ref = ref.filter(ImageFilter.GaussianBlur(0.6 * S))
    rgba = canvas.convert("RGBA")
    rgba.alpha_composite(ref, (round(x * S), round((y + size + gap) * S)))
    rgba.alpha_composite(mk, (round(x * S), round(y * S)))
    return rgba.convert("RGB")


def text(img, x, baseline, parts, shear=0.0):
    """Écrit des segments (texte, police, couleur[, approche]) sur une ligne de base ; `shear` penche le tout."""
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for chunk, f, color, *extra in parts:
        tracking = extra[0] if extra else 0
        for ch in chunk:
            draw.text((x, baseline), ch, font=f, fill=color, anchor="ls")
            x += f.getlength(ch) + tracking * f.size
    if shear:  # italique synthétique autour de la ligne de base (Poppins n'est livrée qu'en romain)
        layer = layer.transform(layer.size, Image.AFFINE, (1, shear, -shear * baseline, 0, 1, 0), Image.BICUBIC)
    rgba = img.convert("RGBA")
    rgba.alpha_composite(layer)
    return rgba.convert("RGB"), x


def width(parts):
    return sum(f.getlength(ch) + (extra[0] if extra else 0) * f.size for chunk, f, _, *extra in parts for ch in chunk)


def wordmark(px):
    # Comme l'en-tête de l'app : « Messenger » Poppins 300, point Poppins 900 en arka-red.
    return [("Messenger", font("Light", px), (255, 255, 255), -0.01), (".", font("Black", px), RED)]


def background(w, h, stops_y, left_right=None):
    """Fond sombre : dégradé vertical, puis assombrissement horizontal optionnel."""
    W, H = w * S, h * S
    y = np.linspace(0, 1, H)[:, None, None]
    ys, cols = zip(*stops_y)
    col = np.stack([np.interp(y[:, 0, 0], ys, [c[i] for c in cols]) for i in range(3)], -1)[:, None, :]
    col = np.repeat(col, W, 1)
    if left_right:
        x = np.linspace(0, 1, W)[None, :, None]
        col = col * lerp(left_right[0], left_right[1], x)
    return Image.fromarray(col.clip(0, 255).astype(np.uint8), "RGB")


def finish(img, w, h, name):
    out = np.asarray(img.resize((w, h), Image.LANCZOS), float)
    out += np.random.default_rng(7).normal(0, 0.7, out.shape)  # grain léger contre les bandes du dégradé
    out = Image.fromarray(out.round().clip(0, 255).astype(np.uint8), "RGB")
    out.save(REPO / "src-tauri/icons" / name, format="BMP")
    if PREVIEW:
        out.save(PREVIEW / name.replace(".bmp", ".png"))
        zoom = 4 if w < 160 else 3
        out.resize((w * zoom, h * zoom), Image.NEAREST).save(PREVIEW / name.replace(".bmp", f"_x{zoom}.png"))
    return out


def header():
    w, h = 150, 57
    img = background(w, h, [(0, (44, 4, 9)), (1, (30, 3, 7))], left_right=(1.0, 0.55))
    m, mx, my = 21, 10, 17.5
    img = glow(img, (mx, my, mx + m, my + m), 5, 0.9)
    img = place_mark(img, m, mx, my, reflect=0.36, reflect_len=0.5, gap=1)
    px = 17.5
    baseline = my + m / 2 + 0.70 * px / 2  # hauteur de capitale centrée sur la marque
    img, _ = text(img, (mx + m + 9) * S, baseline * S, wordmark(px))
    return finish(img, w, h, "installer-header.bmp")


def sidebar():
    w, h = 164, 314
    img = background(w, h, [(0, (30, 4, 8)), (0.35, (24, 3, 6)), (0.75, (10, 2, 3)), (1, (3, 1, 1))])
    m = 96
    mx, my = (w - m) / 2, 95
    img = glow(img, (mx - 26, my - 22, mx + m + 26, my + m + 30), 26, 0.32)  # nappe large
    img = glow(img, (mx, my, mx + m, my + m), 9, 1.0)  # halo serré
    img = place_mark(img, m, mx, my, reflect=0.42, reflect_len=0.6, gap=2)
    parts = wordmark(22)
    img, _ = text(img, (w * S - width(parts)) / 2, 42 * S, parts)
    # Signature « by arkalabs » : by en italique léger, arka gras, labs léger.
    by = [("by", font("Light", 12.5), (236, 236, 236))]
    brand = [("arka", font("Bold", 12.5), (255, 255, 255)), ("labs", font("Light", 12.5), (236, 236, 236))]
    gap = 0.36 * 12.5 * S  # l'italique mange l'espace : on l'élargit un peu
    x0, base = (w * S - width(by + brand) - gap) / 2, 300 * S
    img, x = text(img, x0, base, by, shear=0.2)
    img, _ = text(img, x + gap, base, brand)
    return finish(img, w, h, "installer-sidebar.bmp")


if __name__ == "__main__":
    for out in (header(), sidebar()):
        print(out.size, out.mode)
