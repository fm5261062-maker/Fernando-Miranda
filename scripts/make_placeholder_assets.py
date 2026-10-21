"""Genera ARTE PROVISIONAL para probar el pipeline de Las Cronicas de Silent.

    python scripts/make_placeholder_assets.py            # personaje + oceano
    python scripts/make_placeholder_assets.py --force    # sobrescribe

Todo lo generado se marca con "placeholder": true en su JSON y el render
muestra el sello "ARTE PROVISIONAL" mientras exista alguna capa provisional.
NO es el arte final: sustituye cada PNG por la ilustracion correspondiente
(misma convencion de articulaciones) y cambia "placeholder" a false.
"""

import argparse
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from silent2d.paint import Sheet  # noqa: E402
from silent2d.util import value_noise  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------
# Paleta (segun la descripcion del personaje; confirmar con la hoja de diseno)
# ---------------------------------------------------------------------------
HOOD = (200, 202, 208)        # gris claro de la sudadera/capucha
HOOD_DARK = (168, 172, 182)   # tono del acanalado y pliegues
LINE = (36, 38, 47)
FOLD = (110, 116, 132)
FACE = (4, 4, 7)
EYE = (246, 250, 255)
PANTS = (44, 46, 56)
PANTS_FOLD = (24, 25, 32)
GLOVE = (16, 16, 20)
GLOVE_HI = (70, 72, 84)
SHOE = (34, 35, 42)
SOLE = (214, 214, 208)
STRING = (232, 230, 222)

# ---------------------------------------------------------------------------
# Articulaciones en reposo (vista frontal, px de arte a escala 1000 = 1.78 m)
# Origen: suelo entre los pies. Y hacia abajo. Lado .L = izquierda del
# personaje = derecha de la pantalla (+X).
# ---------------------------------------------------------------------------
JOINTS = {
    "pelvis": (0, -505), "crotch": (0, -412), "neck": (0, -835),
    "head_top": (0, -1020), "string_top": (0, -858), "string_end": (0, -735),
}
for side, s in (("L", 1), ("R", -1)):
    JOINTS.update({
        f"shoulder.{side}": (107 * s, -798), f"elbow.{side}": (118 * s, -629),
        f"wrist.{side}": (126 * s, -477), f"hand_tip.{side}": (130 * s, -376),
        f"hip.{side}": (55 * s, -494), f"knee.{side}": (52 * s, -281),
        f"ankle.{side}": (51 * s, -45), f"toe.{side}": (51 * s, 0),
    })

# parte -> (articulacion origen, articulacion destino)
BONES = {
    "pelvis": ("pelvis", "crotch"), "torso": ("pelvis", "neck"),
    "drawstrings": ("string_top", "string_end"),
    "hood_back": ("neck", "head_top"), "face": ("neck", "head_top"),
    "eyes": ("neck", "head_top"), "hood_rim": ("neck", "head_top"),
}
for side in ("L", "R"):
    BONES.update({
        f"upper_arm.{side}": (f"shoulder.{side}", f"elbow.{side}"),
        f"forearm.{side}": (f"elbow.{side}", f"wrist.{side}"),
        f"hand.{side}": (f"wrist.{side}", f"hand_tip.{side}"),
        f"thigh.{side}": (f"hip.{side}", f"knee.{side}"),
        f"shin.{side}": (f"knee.{side}", f"ankle.{side}"),
        f"foot.{side}": (f"ankle.{side}", f"toe.{side}"),
    })

DRAW_ORDER = [
    "foot.R", "foot.L", "shin.R", "shin.L", "thigh.R", "thigh.L", "pelvis",
    "torso", "drawstrings", "upper_arm.R", "upper_arm.L", "forearm.R",
    "forearm.L", "hand.R", "hand.L", "hood_back", "face", "eyes", "hood_rim",
]


def mirror(pts):
    return [(-x, y) for x, y in pts]


def ellipse_pts(cx, cy, rx, ry, n=24, top_point=0.0):
    out = []
    for k in range(n):
        a = 2 * math.pi * k / n
        y = math.sin(a)
        r = ry * (1 + top_point * max(0, -y) ** 3)
        out.append((cx + rx * math.cos(a), cy + r * y))
    return out


# ---------------------------------------------------------------------------
# Dibujo de cada parte (lado L; el R es espejo)
# ---------------------------------------------------------------------------
def draw_part(name, sheet):
    side = name.split(".")[-1] if "." in name else None
    s = -1 if side == "R" else 1
    M = (lambda pts: mirror(pts)) if s < 0 else (lambda pts: pts)

    if name == "torso":
        half = [(0, -845), (36, -848), (72, -838), (98, -826), (116, -806),
                (124, -776), (122, -735), (118, -700), (116, -650), (110, -590),
                (108, -540), (112, -500), (114, -470), (60, -462), (0, -460)]
        pts = half + mirror(half[::-1])[1:-1]
        m = sheet.fill(pts, HOOD, volume=0.30)
        rib = [(-113, -492), (113, -492), (115, -462), (0, -458), (-115, -462)]
        sheet.fill(rib, HOOD_DARK, lw=1.6, volume=0.2)
        sheet.folds(m, [[(x, -490), (x + 1, -464)] for x in range(-104, 106, 13)],
                    FOLD, lw=0.9, alpha=90)
        pocket = [(-66, -602), (66, -602), (84, -540), (92, -500), (-92, -500),
                  (-84, -540)]
        sheet.fill(pocket, HOOD, lw=1.6, volume=0.18, light_amt=0.05)
        sheet.stroke([(66, -600), (80, -556), (90, -504)], LINE, lw=2.0)
        sheet.stroke([(-66, -600), (-80, -556), (-90, -504)], LINE, lw=2.0)
        sheet.folds(m, [
            [(-96, -700), (-60, -672), (-30, -664)], [(96, -700), (60, -672), (30, -664)],
            [(-100, -620), (-70, -606)], [(100, -620), (70, -606)],
            [(-40, -800), (-10, -770), (20, -790)], [(-106, -540), (-96, -515)],
            [(106, -540), (96, -515)]], FOLD, lw=1.6)
    elif name == "pelvis":
        pts = [(-112, -532), (112, -532), (116, -470), (64, -428), (0, -404),
               (-64, -428), (-116, -470)]
        sheet.fill(pts, PANTS, volume=0.25)
    elif name == "drawstrings":
        for x0 in (-16, 16):
            sheet.stroke([(x0, -858), (x0 * 1.1, -820), (x0 * 1.2, -780),
                          (x0 * 1.25, -748)], LINE, lw=5.2)
            sheet.stroke([(x0, -858), (x0 * 1.1, -820), (x0 * 1.2, -780),
                          (x0 * 1.25, -748)], STRING, lw=3.2)
            sheet.fill(ellipse_pts(x0 * 1.25, -738, 3.6, 11, 12), (190, 192, 198),
                       lw=1.4, volume=0.3)
    elif name == "hood_back":
        half = [(0, -1022), (42, -1016), (70, -994), (84, -958), (87, -918),
                (82, -880), (90, -852), (100, -830), (60, -818), (0, -812)]
        pts = half + mirror(half[::-1])[1:-1]
        m = sheet.fill(pts, HOOD, volume=0.35, light_amt=0.14)
        sheet.folds(m, [[(70, -990), (78, -950), (76, -900)],
                        [(-70, -990), (-78, -950), (-76, -900)],
                        [(30, -1012), (52, -1000)], [(84, -862), (96, -836)],
                        [(-84, -862), (-96, -836)]], FOLD, lw=1.6)
    elif name == "face":
        sheet.fill(ellipse_pts(0, -924, 47, 62, 32, top_point=0.18), FACE,
                   line=None, volume=0.15, light_amt=0.0)
    elif name == "eyes":
        for x in (-19, 19):
            sheet.fill(ellipse_pts(x, -930, 8.5, 27, 24), EYE, line=None,
                       volume=0.08, light_amt=0.0)
    elif name == "hood_rim":
        inner = ellipse_pts(0, -924, 47, 62, 32, top_point=0.18)
        outer = ellipse_pts(0, -922, 60, 76, 32, top_point=0.20)
        cut, _ = sheet.mask(inner)
        m = sheet.fill(outer, HOOD, volume=0.45, light_amt=0.1, cut=cut)
        sheet.stroke([(x, y) for x, y in inner] + [inner[0]], LINE, lw=2.0,
                     smooth=False)
        sheet.folds(m, [[(-52, -880), (-58, -920), (-50, -965)],
                        [(52, -880), (58, -920), (50, -965)]], FOLD, lw=1.4)
    elif name.startswith("upper_arm"):
        pts = [(90, -814), (110, -828), (128, -814), (136, -784), (137, -700),
               (135, -640), (131, -616), (102, -611), (98, -686), (94, -764)]
        m = sheet.fill(M(pts), HOOD, volume=0.32)
        sheet.folds(m, [M([(100, -640), (116, -628), (132, -636)]),
                        M([(98, -700), (110, -690)])], FOLD, lw=1.5)
    elif name.startswith("forearm"):
        pts = [(101, -650), (136, -652), (141, -600), (139, -530), (138, -496),
               (113, -494), (107, -560), (101, -620)]
        m = sheet.fill(M(pts), HOOD, volume=0.32)
        sheet.folds(m, [M([(104, -600), (122, -588), (138, -598)]),
                        M([(108, -540), (124, -532)])], FOLD, lw=1.4)
        cuff = [(112, -500), (139, -500), (137, -468), (114, -468)]
        m2 = sheet.fill(M(cuff), HOOD_DARK, lw=1.6, volume=0.2)
        sheet.folds(m2, [M([(x, -498), (x, -470)]) for x in range(117, 137, 5)],
                    FOLD, lw=0.8, alpha=100)
    elif name.startswith("hand"):
        palm = [(110, -486), (142, -486), (149, -446), (147, -408), (141, -380),
                (126, -372), (112, -382), (108, -420), (107, -458)]
        m = sheet.fill(M(palm), GLOVE, line=(8, 8, 10), volume=0.25, light_amt=0.2)
        sheet.folds(m, [M([(132, -418), (134, -380)]), M([(122, -416), (122, -376)]),
                        M([(141, -420), (143, -390)])], GLOVE_HI, lw=1.4, alpha=150)
        thumb = [(110, -470), (101, -452), (98, -426), (104, -414), (112, -424),
                 (114, -450)]
        sheet.fill(M(thumb), GLOVE, line=(8, 8, 10), volume=0.25, light_amt=0.2)
        sheet.stroke(M([(146, -476), (149, -440)]), GLOVE_HI, lw=1.6, alpha=170)
    elif name.startswith("thigh"):
        pts = [(4, -528), (112, -528), (110, -440), (100, -360), (92, -282),
               (18, -276), (12, -360), (6, -444)]
        m = sheet.fill(M(pts), PANTS, volume=0.3)
        sheet.folds(m, [M([(10, -470), (30, -440)]), M([(30, -300), (52, -292),
                                                         (80, -300)])],
                    PANTS_FOLD, lw=1.8, alpha=160)
    elif name.startswith("shin"):
        pts = [(20, -304), (88, -304), (87, -200), (82, -110), (88, -48),
               (16, -46), (20, -110), (18, -200)]
        m = sheet.fill(M(pts), PANTS, volume=0.3)
        sheet.folds(m, [M([(24, -90), (50, -78), (82, -88)]),
                        M([(28, -62), (52, -56), (84, -64)])], PANTS_FOLD,
                    lw=1.6, alpha=150)
    elif name.startswith("foot"):
        upper = [(22, -70), (80, -70), (92, -44), (97, -18), (88, -6), (14, -6),
                 (5, -18), (10, -44)]
        sheet.fill(M(upper), SHOE, volume=0.3, light_amt=0.18)
        sole = [(6, -18), (96, -18), (94, -2), (86, 3), (16, 3), (8, -2)]
        sheet.fill(M(sole), SOLE, lw=1.6, volume=0.15)
        for y in (-58, -48, -38):
            sheet.stroke(M([(38, y), (64, y)]), (120, 122, 132), lw=1.4)
    else:
        raise ValueError(name)


def build_character(outdir, scale=1.5):
    os.makedirs(outdir, exist_ok=True)
    x0, y0, x1, y1 = -230, -1070, 230, 20
    parts = {}
    for name in DRAW_ORDER:
        sh = Sheet(x0, y0, x1, y1, scale=scale)
        draw_part(name, sh)
        img = sh.result()
        bb = img.getchannel("A").point(lambda a: 255 if a > 2 else 0).getbbox()
        pad = 4
        bb = (max(bb[0] - pad, 0), max(bb[1] - pad, 0),
              min(bb[2] + pad, img.width), min(bb[3] + pad, img.height))
        img.crop(bb).save(os.path.join(outdir, f"{name}.png"))
        # origen de la imagen recortada en coordenadas de arte (escala 1000)
        parts[name] = {
            "image": f"{name}.png",
            "bone": list(BONES[name]),
            "image_origin": [x0 + bb[0] / scale, y0 + bb[1] / scale],
            "placeholder": True,
        }
    rig = {
        "name": "Silent", "view": "front", "placeholder": True,
        "note": ("Capas PROVISIONALES generadas por make_placeholder_assets.py. "
                 "Sustituir por la ilustracion de la hoja de diseno."),
        "units": "px de arte; 1000 px = altura total (1.78 m); origen en el "
                 "suelo entre los pies; y hacia abajo",
        "height_m": 1.78, "art_units_per_height": 1000, "image_scale": scale,
        "joints": {k: list(v) for k, v in JOINTS.items()},
        "parts": parts, "draw_order": DRAW_ORDER,
        "variants": {"hand.R": {"point": "hand_point.R.png"},
                     "hand.L": {"point": "hand_point.L.png"}},
    }
    with open(os.path.join(outdir, "rig.json"), "w") as f:
        json.dump(rig, f, indent=2)
    # hoja de control para revisar las capas montadas
    sheet = Image.new("RGBA", (int((x1 - x0) * scale), int((y1 - y0) * scale)),
                      (60, 64, 74, 255))
    for name in DRAW_ORDER:
        im = Image.open(os.path.join(outdir, f"{name}.png"))
        ox, oy = parts[name]["image_origin"]
        sheet.alpha_composite(im, (int(round((ox - x0) * scale)),
                                   int(round((oy - y0) * scale))))
    return sheet


# ---------------------------------------------------------------------------
# Escenario provisional: oceano al atardecer en capas
# ---------------------------------------------------------------------------
LW, LH = 2560, 1440       # tamano de capa (para 1920x1080 con margen)
HORIZON = 560             # fila del horizonte dentro de cada capa
F_REF, H_REF = 2015.0, 1.5  # focal (px a 1080) y altura de camara de referencia


def row(D, height=0.0):
    """Fila de la capa donde cae un punto a D m y `height` m sobre el suelo."""
    return HORIZON + F_REF * (H_REF - height) / D


def dist_of_row(y):
    return F_REF * H_REF / np.maximum(y - HORIZON, 1e-3)


def rgba(arr_rgb, alpha):
    a = np.clip(alpha * 255, 0, 255).astype(np.uint8)
    rgb = np.clip(arr_rgb, 0, 255).astype(np.uint8)
    return Image.fromarray(np.dstack([rgb, a]), "RGBA")


def grad(stops, n):
    """Interpola colores [(pos, (r,g,b)), ...] a lo largo de n filas."""
    pos = np.array([p for p, _ in stops])
    cols = np.array([c for _, c in stops], dtype=np.float32)
    x = np.linspace(0, 1, n)
    return np.stack([np.interp(x, pos, cols[:, i]) for i in range(3)], axis=1)


class Strokes:
    """Lienzo supermuestreado para pinceladas horizontales periodicas en X."""

    def __init__(self, ss=2):
        self.ss = ss
        self.img = Image.new("RGBA", (LW * ss, LH * ss), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)

    def dash(self, x, y, length, width, color, alpha, curve=0.0):
        s = self.ss
        for off in (-LW, 0, LW):          # periodico para el desplazamiento
            x0 = x + off
            if x0 + length < 0 or x0 - length > LW:
                continue
            n = 6
            pts = [((x0 + length * (k / n - 0.5)) * s,
                    (y - curve * math.sin(math.pi * k / n)) * s) for k in range(n + 1)]
            self.d.line(pts, fill=(*color, int(alpha * 255)), width=max(1, int(width * s)),
                        joint="curve")

    def result(self, blur=0.0):
        im = self.img.resize((LW, LH), Image.LANCZOS)
        return im.filter(ImageFilter.GaussianBlur(blur)) if blur else im


def streaks(rng, sx, sy, cell=6, octaves=3):
    """Ruido anisotropo: vetas alargadas sx veces en X y sy veces en Y."""
    small = value_noise(max(LH // sy, 8), max(LW // sx, 8), cell, rng, octaves=octaves,
                        wrap_x=True)
    return np.asarray(Image.fromarray(small).resize((LW, LH), Image.BICUBIC))


def build_ocean(outdir, seed=7):
    rng = np.random.default_rng(seed)
    os.makedirs(outdir, exist_ok=True)
    yy, xx = np.mgrid[0:LH, 0:LW].astype(np.float32)
    sun = (LW * 0.36, HORIZON - 46)
    sun_col = np.array([255, 178, 112], np.float32)

    # 00 cielo de atardecer con sol bajo
    col = grad([(0, (16, 26, 52)), (0.22, (40, 56, 92)), (0.34, (112, 100, 124)),
                (0.385, (236, 160, 112)), (0.40, (252, 196, 140)), (1, (252, 196, 140))], LH)
    sky = np.repeat(col[:, None, :], LW, axis=1)
    d = np.hypot((xx - sun[0]) / 1.5, yy - sun[1])
    glow = np.exp(-(d / 300) ** 2)[..., None] * sun_col * 0.55
    core_a = np.exp(-(d / 30) ** 4)[..., None]
    sky = sky * (1 - core_a) + core_a * np.array([255, 238, 206]) + glow
    rgba(sky, np.ones((LH, LW))).save(os.path.join(outdir, "00_sky.png"))

    # 01 nubes en bandas, iluminadas desde abajo (periodicas en X)
    n = value_noise(LH, LW, 480, rng, octaves=5, wrap_x=True)
    n2 = value_noise(LH, LW, 110, rng, octaves=3, wrap_x=True)
    stretch = np.asarray(Image.fromarray(value_noise(LH // 6, LW, 300, rng, octaves=4))
                         .resize((LW, LH), Image.BICUBIC))
    band = (np.exp(-((yy - (HORIZON - 300)) / 170) ** 2) +
            0.8 * np.exp(-((yy - (HORIZON - 95)) / 34) ** 2))
    dens = np.clip((0.55 * n + 0.25 * n2 + 0.35 * stretch - 0.55) * 3.2, 0, 1) * band
    under = np.clip((yy - (HORIZON - 420)) / 420, 0, 1)
    near_sun = np.clip(1 - d / 1100, 0, 1) ** 2
    cloud = (np.array([46, 50, 76]) * (1 - 0.4 * under[..., None]) +
             sun_col * (0.25 + 0.75 * near_sun[..., None]) * under[..., None] * 0.9)
    rgba(cloud, np.clip(dens * 0.9, 0, 1) * (yy < HORIZON - 3)).save(
        os.path.join(outdir, "01_clouds.png"))

    # 02 mar: base desde el horizonte hasta abajo + pinceladas y reflejo del sol
    t = np.clip((yy - HORIZON) / (LH - HORIZON), 0, 1)
    base = grad([(0, (132, 112, 122)), (0.012, (70, 76, 98)), (0.06, (36, 50, 72)),
                 (0.25, (20, 34, 52)), (1, (12, 22, 36))], LH)
    sea = np.repeat(base[:, None, :], LW, axis=1)
    path = np.exp(-((xx - sun[0]) / (40 + 1400 * t)) ** 2)
    sea = sea + path[..., None] * sun_col * 0.30 * (1 - t[..., None]) ** 2
    st = Strokes()
    for y in np.arange(HORIZON + 1, row(40), 0.9):
        D = float(dist_of_row(y))
        k = 1.0 / D
        for _ in range(int(40 + 2500 * k)):
            x = rng.uniform(0, LW)
            ln = rng.uniform(8, 30) + 1600 * k
            in_path = math.exp(-((x - sun[0]) / (40 + 1400 * (y - HORIZON) / 880)) ** 2)
            if rng.random() < 0.15 + 0.7 * in_path:
                c, a = (255, 208, 150), 0.35 + 0.6 * in_path
            elif rng.random() < 0.5:
                c, a = (150, 150, 172), 0.18
            else:
                c, a = (10, 18, 30), 0.35
            st.dash(x, y, ln, 0.6 + 60 * k, c, a)
    strokes = st.result(0.3)
    sea_img = rgba(sea, (yy >= HORIZON).astype(np.float32))
    sea_img.alpha_composite(strokes)
    sea_img.save(os.path.join(outdir, "02_sea_far.png"))

    # 03 mar de fondo: lineas de oleaje (cresta clara sobre seno oscuro)
    st = Strokes()
    y = row(260)
    while y < row(36):
        D = float(dist_of_row(y))
        k = 1.0 / D
        for _ in range(int(14 + 260 * k)):
            x = rng.uniform(0, LW)
            ln = rng.uniform(60, 220) * (0.4 + 24 * k)
            st.dash(x, y + 1.2 + 40 * k, ln, 0.8 + 70 * k, (8, 14, 26), 0.55, curve=2 + 60 * k)
            st.dash(x + rng.uniform(-6, 6), y, ln * 0.8, 0.5 + 35 * k, (170, 176, 196), 0.45,
                    curve=2 + 60 * k)
        y += 0.8 + 900 * k * k * 10
    st.result(0.4).save(os.path.join(outdir, "03_swells.png"))

    # 04 ola rompiente con altura (cara translucida + labio de espuma)
    D_surf = 34.0
    base_r, crest_h = row(D_surf), 1.15
    x = np.arange(LW)
    ph_ = 2 * math.pi * x / LW            # armonicos enteros: periodico en LW, sin repeticion visible
    sect = np.clip(0.5 + 0.32 * np.sin(2 * ph_ + 0.7) * np.sin(5 * ph_ + 1.3) +
                   0.22 * np.sin(11 * ph_ + 2.1) + 0.12 * np.sin(17 * ph_ + 0.4), 0, 1)
    crest = base_r - (base_r - row(D_surf, crest_h)) * (0.55 + 0.45 * sect)
    crest = crest + np.sin(x / 41) * 1.5
    foam_n = streaks(rng, 5, 1, cell=5)          # espuma en vetas horizontales
    drip = streaks(rng, 1, 4, cell=4)            # regueros verticales en la cara
    h_face = np.maximum(base_r - crest, 1)
    u = np.clip((yy - crest[None, :]) / h_face[None, :], 0, 1)          # 0 cresta, 1 base
    face = (yy >= crest[None, :]) & (yy <= base_r + 2)
    face_col = (np.array([34, 74, 82]) * (1 - u[..., None]) + np.array([12, 26, 40]) * u[..., None])
    # luz atravesando la ola (contraluz del sol)
    face_col = face_col + np.exp(-((xx - sun[0]) / 500) ** 2)[..., None] * \
        np.array([90, 120, 80]) * (1 - u[..., None]) ** 2
    broken = np.clip((sect - 0.45) * 3, 0, 1)[None, :]          # tramos ya rotos
    lip = np.exp(-((yy - crest[None, :]) / 2.2) ** 2) * (0.35 + 0.65 * broken)
    spray = np.exp(-((yy - crest[None, :] + 6) / 5.0) ** 2) * \
        np.clip((foam_n - 0.5) * 4, 0, 1) * broken
    white = np.exp(-((yy - base_r) / 4) ** 2) * np.clip((foam_n - 0.3) * 3, 0, 1)
    runs = np.clip((drip - 0.68) * 4, 0, 1) * face * (u > 0.25) * broken * 0.3
    foam = np.clip(lip + spray * 0.8 + white * 0.9 + runs, 0, 1)
    a = np.clip(face * (0.55 + 0.3 * u) + foam, 0, 1)
    wcol = face_col * (1 - foam[..., None]) + np.array([236, 232, 224]) * foam[..., None]
    Image.fromarray(np.dstack([np.clip(wcol, 0, 255).astype(np.uint8),
                               (np.clip(a, 0, 1) * 255).astype(np.uint8)]), "RGBA") \
        .filter(ImageFilter.GaussianBlur(0.6)).save(os.path.join(outdir, "04_surf.png"))

    # 05 espuma del rompiente que avanza (bore) a ~24 m
    r0 = row(24.0)
    top = r0 - 7 + np.sin(x / 63) * 3 + np.sin(x / 17 + 1) * 1.5
    lace = streaks(rng, 6, 1, cell=4)
    body = (yy >= top[None, :]) & (yy <= row(20.5))
    fade = np.clip(1 - (yy - top[None, :]) / (row(20.5) - top[None, :]), 0, 1) ** 1.5
    a = np.clip(np.exp(-((yy - top[None, :]) / 2.0) ** 2) * 0.9 +
                body * np.clip((lace - 0.45) * 3, 0, 1) * fade * 0.7, 0, 1)
    rgba(np.broadcast_to(np.array([236, 232, 224]), (LH, LW, 3)), a).filter(
        ImageFilter.GaussianBlur(0.7)).save(os.path.join(outdir, "05_whitewater.png"))

    # 06 lamina de agua sobre la arena (sube y baja con cada ola)
    e0 = row(17.0) + np.sin(x / 120 + 2) * 6 + np.sin(x / 33) * 2.5
    lace2 = streaks(rng, 8, 1, cell=4)
    sheet = (yy < e0[None, :]) & (yy > row(21))
    rim = np.exp(-((yy - e0[None, :]) / 1.8) ** 2)
    a = np.clip(sheet * (0.16 + 0.35 * np.clip((lace2 - 0.55) * 3, 0, 1)) + rim * 0.85, 0, 1)
    wash_col = np.array([200, 196, 196]) * (1 - rim[..., None]) + np.array([244, 240, 232]) * rim[..., None]
    rgba(wash_col, a).save(os.path.join(outdir, "06_shore_wash.png"))

    # 07 arena humeda (espejo del cielo) que se seca hacia el primer termino
    r_sand = row(20.0)
    ty = np.clip((yy - r_sand) / (LH - r_sand), 0, 1)
    refl = np.repeat(col[np.clip(2 * HORIZON - np.arange(LH), 0, LH - 1)][:, None, :],
                     LW, axis=1)
    dry = grad([(0, (120, 100, 92)), (0.5, (78, 66, 64)), (1, (40, 35, 38))], LH)
    dry = np.repeat(dry[:, None, :], LW, axis=1)
    wet = np.clip(1 - ty * 1.7, 0, 1) ** 1.2
    ripple = np.asarray(Image.fromarray(value_noise(LH // 4, LW, 40, rng, octaves=3))
                        .resize((LW, LH), Image.BICUBIC))
    grain_n = value_noise(LH, LW, 3, rng, octaves=2, wrap_x=True)
    sand = (refl * 0.55 * (0.85 + 0.3 * ripple[..., None]) * wet[..., None] +
            dry * (1 - wet[..., None] * 0.7)) * (0.94 + 0.1 * grain_n[..., None])
    a = np.clip((yy - r_sand) / 6, 0, 1)
    sand_img = rgba(sand, a)
    st = Strokes()
    for _ in range(2600):                     # pequenas ondulaciones y conchas
        yv = rng.uniform(r_sand + 10, LH)
        D = float(dist_of_row(yv))
        st.dash(rng.uniform(0, LW), yv, rng.uniform(6, 26) * 12 / D, 0.6 + 6 / D,
                (24, 20, 24) if rng.random() < 0.7 else (200, 180, 160), 0.25)
    sand_img.alpha_composite(st.result(0.5))
    sand_img.save(os.path.join(outdir, "07_sand.png"))

    # 07b reflejo del sol en la arena mojada: capa a distancia infinita para que
    # quede siempre bajo el sol aunque la camara panee o haga dolly
    tt = np.clip((yy - HORIZON) / (LH - HORIZON), 0, 1)
    glare = np.exp(-((xx - sun[0]) / (30 + 380 * tt)) ** 2) * (1 - tt) ** 0.9
    glare *= (0.75 + 0.5 * ripple) * np.clip((yy - HORIZON) / 60, 0, 1)
    rgba(np.broadcast_to(sun_col, (LH, LW, 3)), np.clip(glare * 0.55, 0, 1)).save(
        os.path.join(outdir, "07b_sun_glare.png"))

    # 08 primer termino: rocas y hierba desenfocadas en los bordes
    fg = Image.new("RGBA", (LW, LH), (0, 0, 0, 0))
    dr = ImageDraw.Draw(fg)
    for cx, w, h in ((-40, 560, 260), (330, 260, 120), (LW - 100, 640, 320),
                     (LW - 560, 260, 110)):
        pts = []
        for k in range(18):
            a_ = math.pi + math.pi * k / 17
            r = 1 + 0.12 * math.sin(k * 2.3 + cx)
            pts.append((cx + math.cos(a_) * w / 2 * r, LH + math.sin(a_) * h * r))
        dr.polygon(pts, fill=(14, 12, 15, 255))
    for k in range(70):
        xg = rng.choice([rng.uniform(0, 640), rng.uniform(LW - 820, LW)])
        hgt = rng.uniform(110, 300)
        dr.line([(xg, LH), (xg + rng.uniform(-70, 70), LH - hgt)], fill=(22, 19, 21, 255),
                width=int(rng.uniform(3, 7)))
    fg.filter(ImageFilter.GaussianBlur(10)).save(os.path.join(outdir, "08_foreground.png"))

    layers = [
        {"name": "sky", "image": "00_sky.png", "distance": "inf"},
        {"name": "clouds", "image": "01_clouds.png", "distance": 3000,
         "anim": {"type": "scroll", "speed_px_s": 5}},
        {"name": "sea_far", "image": "02_sea_far.png", "distance": 400,
         "anim": {"type": "waves", "rows": [HORIZON, int(row(40))], "amp_px": 1.5,
                  "wavelength_rows": 3, "speed": 0.7}},
        {"name": "swells", "image": "03_swells.png", "distance": 70,
         "anim": {"type": "waves", "rows": [HORIZON, int(row(30))], "amp_px": 3.0,
                  "wavelength_rows": 6, "speed": 0.25, "drift_px_s": 6}},
        {"name": "surf", "image": "04_surf.png", "distance": 34,
         "anim": {"type": "surge", "period_s": 7.0, "amp_px": 24, "phase": 0.0,
                  "drift_px_s": -3}},
        {"name": "whitewater", "image": "05_whitewater.png", "distance": 24,
         "anim": {"type": "surge", "period_s": 7.0, "amp_px": 34, "phase": 0.85,
                  "fade": 0.5}},
        {"name": "shore_wash", "image": "06_shore_wash.png", "distance": 18,
         "anim": {"type": "surge", "period_s": 7.0, "amp_px": 40, "phase": 0.7,
                  "fade": 0.75}},
        {"name": "sand", "image": "07_sand.png", "distance": 12, "ground": True},
        {"name": "sun_glare", "image": "07b_sun_glare.png", "distance": "inf",
         "ground_rows": True, "mask_with": "sand"},
        {"name": "foreground", "image": "08_foreground.png", "distance": 2.2},
    ]
    for L in layers:
        L["horizon_px"] = HORIZON
        L["placeholder"] = True
    spec = {
        "name": "ocean_dusk", "placeholder": True,
        "note": ("Capas PROVISIONALES procedurales. Sustituir por fondos pintados con el "
                 "mismo horizonte (horizon_px) y la misma distancia por capa."),
        "layer_size": [LW, LH], "reference_frame": [1920, 1080],
        "geometry": {"focal_px_1080": F_REF, "camera_height_m": H_REF,
                     "rule": "fila = horizon_px + focal * altura_camara / distancia"},
        "sun_px": [sun[0], sun[1]],
        "layers": layers,
        "particles": [
            {"name": "spray", "distance": 34, "count": 80,
             "region": [0, LW, row(34, 1.4), row(34, 0.5)],
             "velocity": [10, -6], "life": [1.2, 3.0], "size": [1.5, 4],
             "color": [240, 236, 230], "alpha": 0.35},
            {"name": "glints", "type": "glint", "distance": 400, "count": 120,
             "region": [sun[0] - 220, sun[0] + 220, HORIZON + 1, row(60)],
             "size": [1.2, 3.0], "color": [255, 230, 186], "alpha": 0.9},
            {"name": "mist", "distance": 3.0, "count": 12,
             "region": [0, LW, 200, LH], "velocity": [12, -2], "life": [6, 10],
             "size": [16, 40], "color": [255, 220, 190], "alpha": 0.08, "blur": 1},
        ],
        "lighting": {
            "sun_dir": [-0.55, -0.45], "ambient": [0.60, 0.63, 0.74],
            "rim_color": [255, 184, 128], "rim_strength": 1.1, "rim_width": 6,
            "shadow_strength": 0.42, "reflection": 0.25, "contact_shadow": 0.5,
        },
        "grade": {"lift": [0.012, 0.020, 0.034], "gain": [1.03, 1.0, 0.96],
                  "saturation": 0.94, "contrast": 1.05, "vignette": 0.30,
                  "grain": 0.016, "bloom": 0.30, "bloom_threshold": 0.80,
                  "haze": [0.85, 0.66, 0.55, 0.04]},
        "audio": {"ambience": "ocean", "surge_layer": "surf", "wash_layer": "shore_wash"},
    }
    with open(os.path.join(outdir, "set.json"), "w") as f:
        json.dump(spec, f, indent=2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    cdir = os.path.join(ROOT, "assets", "character", "silent", "front")
    bdir = os.path.join(ROOT, "assets", "backgrounds", "ocean_dusk")
    for d, fn in ((cdir, build_character), (bdir, build_ocean)):
        marker = os.path.join(d, "rig.json" if fn is build_character else "set.json")
        if os.path.exists(marker) and not args.force:
            with open(marker) as f:
                if not json.load(f).get("placeholder", False):
                    print(f"[skip] {d} contiene arte definitivo")
                    continue
        out = fn(d)
        if fn is build_character:
            out.save(os.path.join(d, "_contact_sheet.png"))
        print(f"[ok] provisional -> {d}")


if __name__ == "__main__":
    main()
