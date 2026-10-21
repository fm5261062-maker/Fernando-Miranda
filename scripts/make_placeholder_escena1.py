"""ARTE PROVISIONAL para el Episodio 1, Escena 1 (prueba del plano 2).

    python scripts/make_placeholder_escena1.py

Genera:
  * assets/character/silent/back/   Silent de espaldas (chaqueta con capucha y
    cremallera, faldon largo, mochila tactica negra), segun las referencias
    assets/reference/escena1/plano_02/04/05/06.
  * assets/backgrounds/cliff_night/  acantilado nocturno con luna, mar abajo,
    isla con cascadas, niebla y primer termino.

Todo queda marcado con "placeholder": true. Sirve para validar la caminata,
la camara y el paralaje; NO sustituye a las capas ilustradas definitivas.
No sobrescribe una carpeta cuyo JSON tenga "placeholder": false.
"""

import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_placeholder_assets as base  # noqa: E402
from make_placeholder_assets import (LINE, Strokes, ellipse_pts, grad, mirror,  # noqa: E402
                                     rgba, streaks)
from silent2d.paint import Sheet  # noqa: E402
from silent2d.util import value_noise  # noqa: E402

ROOT = base.ROOT

# Paleta tomada de las referencias (chaqueta gris claro casi blanca, mochila negra)
JACKET = (206, 204, 200)
JACKET_FOLD = (120, 122, 132)
JACKET_DARK = (168, 166, 166)
PACK = (30, 30, 35)
PACK_HI = (78, 80, 90)
WEB = (52, 53, 60)
BUCKLE = (128, 130, 138)
PANTS = (38, 39, 47)
PANTS_FOLD = (20, 21, 27)
GLOVE = (18, 18, 22)
GLOVE_HI = (66, 68, 80)
BOOT = (30, 28, 31)
SOLE = (58, 56, 58)

# ---------------------------------------------------------------------------
# Rig de espaldas: mismas articulaciones que el frontal con X invertida
# (de espaldas, la izquierda del personaje queda a la izquierda de pantalla)
# ---------------------------------------------------------------------------
JOINTS = {}
for k, (x, y) in base.JOINTS.items():
    JOINTS[k] = (-x, y) if (k.endswith(".L") or k.endswith(".R")) else (x, y)
JOINTS.update({"pack_top": (0, -820), "pack_bottom": (0, -522),
               "hem_top": (0, -575), "hem_bottom": (0, -412)})
del JOINTS["string_top"], JOINTS["string_end"]

BONES = {"pelvis": ("pelvis", "crotch"), "torso": ("pelvis", "neck"),
         "coat_tail": ("hem_top", "hem_bottom"), "hood": ("neck", "head_top"),
         "backpack": ("pack_top", "pack_bottom")}
for side in ("L", "R"):
    BONES.update({
        f"upper_arm.{side}": (f"shoulder.{side}", f"elbow.{side}"),
        f"forearm.{side}": (f"elbow.{side}", f"wrist.{side}"),
        f"hand.{side}": (f"wrist.{side}", f"hand_tip.{side}"),
        f"thigh.{side}": (f"hip.{side}", f"knee.{side}"),
        f"shin.{side}": (f"knee.{side}", f"ankle.{side}"),
        f"foot.{side}": (f"ankle.{side}", f"toe.{side}"),
    })

DRAW_ORDER = ["foot.R", "foot.L", "shin.R", "shin.L", "thigh.R", "thigh.L", "pelvis",
              "coat_tail", "torso", "upper_arm.R", "upper_arm.L", "forearm.R", "forearm.L",
              "hand.R", "hand.L", "hood", "backpack"]


def draw_back(name, sh):
    side = name.split(".")[-1] if "." in name else None
    # de espaldas, +X es el lado DERECHO del personaje
    s = 1 if side == "R" else -1
    M = (lambda pts: pts) if s > 0 else mirror

    if name == "torso":
        half = [(0, -850), (36, -852), (72, -842), (98, -826), (116, -806), (124, -776),
                (122, -735), (118, -700), (116, -650), (113, -600), (112, -566), (0, -562)]
        pts = half + mirror(half[::-1])[1:-1]
        m = sh.fill(pts, JACKET, volume=0.32)
        sh.folds(m, [[(0, -846), (0, -566)],                      # costura central
                     [(-96, -826), (-50, -800), (0, -796), (50, -800), (96, -826)],
                     [(-110, -640), (-80, -620)], [(110, -640), (80, -620)],
                     [(-108, -720), (-88, -700)], [(108, -720), (88, -700)]],
                 JACKET_FOLD, lw=1.6)
    elif name == "coat_tail":
        half = [(0, -582), (113, -582), (117, -530), (121, -470), (124, -418),
                (60, -410), (0, -408)]
        pts = half + mirror(half[::-1])[1:-1]
        m = sh.fill(pts, JACKET, volume=0.30)
        sh.fill([(-123, -430), (0, -424), (123, -430), (124, -418), (60, -410), (0, -408),
                 (-60, -410), (-124, -418)], JACKET_DARK, lw=1.4, volume=0.2, smooth=False)
        sh.folds(m, [[(0, -580), (0, -450)], [(-70, -560), (-80, -470), (-86, -430)],
                     [(70, -560), (80, -470), (86, -430)], [(-30, -540), (-36, -440)],
                     [(30, -540), (36, -440)]], JACKET_FOLD, lw=1.5, alpha=95)
    elif name == "hood":
        half = [(0, -1030), (34, -1020), (64, -1000), (82, -964), (87, -922),
                (84, -882), (94, -854), (110, -830), (84, -816), (42, -810), (0, -806)]
        pts = half + mirror(half[::-1])[1:-1]
        m = sh.fill(pts, JACKET, volume=0.40, light_amt=0.16)
        sh.folds(m, [[(0, -1028), (2, -960), (0, -880)],
                     [(-62, -990), (-74, -930), (-70, -880)],
                     [(62, -990), (74, -930), (70, -880)],
                     [(-86, -860), (-60, -836), (-20, -828)],
                     [(86, -860), (60, -836), (20, -828)]], JACKET_FOLD, lw=1.7)
    elif name == "backpack":
        for x0 in (-1, 1):            # tirantes asomando sobre los hombros
            sh.fill([(x0 * 50, -812), (x0 * 60, -846), (x0 * 82, -842), (x0 * 80, -808)],
                    PACK, line=(10, 10, 12), volume=0.2)
        for x0 in (-1, 1):            # bolsillos laterales
            sh.fill([(x0 * 94, -720), (x0 * 114, -714), (x0 * 118, -630), (x0 * 114, -566),
                     (x0 * 94, -560)], PACK, line=(10, 10, 12), volume=0.3)
        half = [(0, -826), (70, -824), (94, -810), (102, -770), (103, -620), (100, -556),
                (86, -526), (0, -520)]
        pts = half + mirror(half[::-1])[1:-1]
        m = sh.fill(pts, PACK, line=(8, 8, 10), volume=0.35, light_amt=0.25)
        # panel central con cintas MOLLE
        sh.fill([(-62, -756), (62, -756), (64, -580), (-64, -580)], (36, 36, 42),
                line=(12, 12, 14), lw=1.4, volume=0.2, smooth=False)
        sh.folds(m, [[(-60, y), (60, y)] for y in range(-744, -586, 14)], WEB, lw=1.6,
                 alpha=230)
        sh.folds(m, [[(x, -756), (x, -580)] for x in (-42, -14, 14, 42)], (14, 14, 16),
                 lw=1.0, alpha=200)
        for y in (-778, -610):        # cinchas de compresion con hebillas
            sh.fill([(-103, y - 7), (103, y - 7), (103, y + 7), (-103, y + 7)], WEB,
                    line=(10, 10, 12), lw=1.0, volume=0.1, smooth=False)
            for x0 in (-1, 1):
                sh.fill([(x0 * 70, y - 10), (x0 * 84, y - 10), (x0 * 84, y + 10),
                         (x0 * 70, y + 10)], BUCKLE, line=(30, 30, 34), lw=1.0,
                        volume=0.25, smooth=False)
        sh.stroke([(-26, -826), (-14, -846), (14, -846), (26, -826)], PACK_HI, lw=3.2)
        sh.folds(m, [[(-84, -800), (-90, -700)], [(84, -800), (90, -700)]],
                 PACK_HI, lw=1.6, alpha=140)
    elif name == "pelvis":
        pts = [(-112, -540), (112, -540), (116, -470), (64, -428), (0, -404),
               (-64, -428), (-116, -470)]
        sh.fill(pts, PANTS, volume=0.25)
    elif name.startswith("upper_arm"):
        pts = [(90, -814), (110, -828), (128, -814), (136, -784), (137, -700),
               (135, -640), (131, -616), (102, -611), (98, -686), (94, -764)]
        m = sh.fill(M(pts), JACKET, volume=0.32)
        sh.folds(m, [M([(104, -642), (118, -630), (132, -638)]),
                     M([(100, -720), (118, -706)])], JACKET_FOLD, lw=1.5)
    elif name.startswith("forearm"):
        pts = [(101, -650), (136, -652), (141, -600), (139, -530), (138, -488),
               (113, -486), (107, -560), (101, -620)]
        m = sh.fill(M(pts), JACKET, volume=0.32)
        sh.folds(m, [M([(104, -600), (122, -590), (138, -598)]),
                     M([(110, -530), (126, -522)])], JACKET_FOLD, lw=1.4)
        sh.fill(M([(112, -500), (139, -500), (138, -480), (113, -480)]), JACKET_DARK,
                lw=1.4, volume=0.2)
    elif name.startswith("hand"):
        palm = [(110, -484), (142, -484), (149, -446), (147, -408), (141, -382),
                (126, -374), (112, -384), (107, -420), (107, -456)]
        m = sh.fill(M(palm), GLOVE, line=(8, 8, 10), volume=0.25, light_amt=0.2)
        sh.folds(m, [M([(116, -452), (140, -454)]), M([(122, -414), (122, -380)]),
                     M([(132, -416), (134, -380)])], GLOVE_HI, lw=1.4, alpha=150)
    elif name.startswith("thigh"):
        pts = [(4, -528), (112, -528), (110, -440), (100, -360), (92, -282),
               (18, -276), (12, -360), (6, -444)]
        m = sh.fill(M(pts), PANTS, volume=0.3)
        sh.folds(m, [M([(30, -300), (52, -290), (80, -298)]), M([(60, -470), (64, -400)])],
                 PANTS_FOLD, lw=1.8, alpha=160)
    elif name.startswith("shin"):
        pts = [(20, -304), (88, -304), (87, -200), (84, -110), (86, -66),
               (18, -64), (20, -110), (18, -200)]
        m = sh.fill(M(pts), PANTS, volume=0.3)
        sh.folds(m, [M([(24, -100), (52, -90), (82, -98)]), M([(50, -250), (54, -170)])],
                 PANTS_FOLD, lw=1.6, alpha=150)
    elif name.startswith("foot"):
        heel = [(20, -90), (82, -90), (88, -40), (90, -12), (84, -2), (18, -2), (12, -12),
                (14, -40)]
        sh.fill(M(heel), BOOT, line=(10, 10, 12), volume=0.3, light_amt=0.2)
        sh.fill(M([(10, -16), (92, -16), (90, 2), (14, 2)]), SOLE, line=(10, 10, 12),
                lw=1.2, volume=0.2)
        sh.stroke(M([(44, -88), (44, -62), (58, -62), (58, -88)]), (70, 68, 74), lw=1.6)
    else:
        raise ValueError(name)


def build_back(outdir, scale=1.5):
    os.makedirs(outdir, exist_ok=True)
    x0, y0, x1, y1 = -230, -1070, 230, 20
    parts = {}
    for name in DRAW_ORDER:
        sh = Sheet(x0, y0, x1, y1, scale=scale)
        draw_back(name, sh)
        img = sh.result()
        bb = img.getchannel("A").point(lambda a: 255 if a > 2 else 0).getbbox()
        pad = 4
        bb = (max(bb[0] - pad, 0), max(bb[1] - pad, 0),
              min(bb[2] + pad, img.width), min(bb[3] + pad, img.height))
        img.crop(bb).save(os.path.join(outdir, f"{name}.png"))
        parts[name] = {"image": f"{name}.png", "bone": list(BONES[name]),
                       "image_origin": [x0 + bb[0] / scale, y0 + bb[1] / scale],
                       "placeholder": True}
    rig = {
        "name": "Silent", "view": "back", "placeholder": True,
        "note": ("Capas PROVISIONALES de espaldas (chaqueta con capucha, faldon largo, "
                 "mochila tactica) segun las referencias de la escena 1. Sustituir por "
                 "las capas ilustradas definitivas."),
        "units": "1000 = altura total (1.78 m); origen en el suelo; y hacia abajo; "
                 "de espaldas .L queda a la izquierda de pantalla",
        "height_m": 1.78, "art_units_per_height": 1000, "image_scale": scale,
        "joints": {k: list(v) for k, v in JOINTS.items()},
        "parts": parts, "draw_order": DRAW_ORDER,
        "secondary": {"backpack": "pack_dy/pack_rot (muelle)",
                      "coat_tail": "coat_swing (muelle + viento)",
                      "hood": "hood_wind (viento)"},
    }
    with open(os.path.join(outdir, "rig.json"), "w") as f:
        json.dump(rig, f, indent=2)
    sheet = Image.new("RGBA", (int((x1 - x0) * scale), int((y1 - y0) * scale)),
                      (60, 64, 74, 255))
    for name in DRAW_ORDER:
        im = Image.open(os.path.join(outdir, f"{name}.png"))
        ox, oy = parts[name]["image_origin"]
        sheet.alpha_composite(im, (int(round((ox - x0) * scale)), int(round((oy - y0) * scale))))
    sheet.save(os.path.join(outdir, "_contact_sheet.png"))


# ---------------------------------------------------------------------------
# Escenario: acantilado nocturno
# ---------------------------------------------------------------------------
LW, LH = 2560, 1440
HZ = 470                      # fila del horizonte en la capa
F, H = 2015.0, 1.7            # focal (px a 1080) y altura de camara de referencia
DROP = 45.0                   # altura del acantilado sobre el mar (m)
EDGE = 17.0                   # distancia del borde del acantilado (m)


def row(D, height=0.0):
    return HZ + F * (H - height) / D


def build_cliff(outdir, seed=21):
    rng = np.random.default_rng(seed)
    os.makedirs(outdir, exist_ok=True)
    yy, xx = np.mgrid[0:LH, 0:LW].astype(np.float32)
    moon = (LW * 0.80, HZ - 330)
    moon_col = np.array([214, 228, 255], np.float32)

    # 00 cielo con luna y estrellas
    col = grad([(0, (6, 10, 26)), (0.18, (12, 22, 46)), (0.32, (30, 46, 80)),
                (0.33, (44, 62, 98)), (1, (44, 62, 98))], LH)
    sky = np.repeat(col[:, None, :], LW, axis=1)
    d = np.hypot(xx - moon[0], yy - moon[1])
    sky += np.exp(-(d / 420) ** 2)[..., None] * moon_col * 0.30
    sky += np.exp(-(d / 120) ** 2)[..., None] * moon_col * 0.35
    disk = np.clip((78 - d) / 2.0, 0, 1)
    crat = value_noise(LH, LW, 16, rng, octaves=3, wrap_x=False)
    disk_col = moon_col * (0.86 + 0.18 * crat[..., None])
    sky = sky * (1 - disk[..., None]) + disk_col * disk[..., None]
    stars = (rng.random((LH, LW)) > 0.9993) * (yy < HZ - 60) * rng.random((LH, LW))
    star_img = Image.fromarray((stars * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6))
    sky += np.asarray(star_img, np.float32)[..., None] * 2.2
    rgba(sky, np.ones((LH, LW))).save(os.path.join(outdir, "00_sky.png"))

    # 01 nubes nocturnas con borde iluminado por la luna (periodicas en X)
    n = value_noise(LH, LW, 380, rng, octaves=5, wrap_x=True)
    n2 = value_noise(LH, LW, 90, rng, octaves=3, wrap_x=True)
    band = (np.exp(-((yy - (HZ - 360)) / 210) ** 2) +
            0.7 * np.exp(-((yy - (HZ - 80)) / 60) ** 2))
    dens = np.clip((0.65 * n + 0.35 * n2 - 0.50) * 3.0, 0, 1) * band
    edge = np.clip(dens * (1 - dens) * 4, 0, 1)
    near = np.clip(1 - d / 900, 0, 1) ** 1.5
    cl = np.array([20, 28, 48]) + edge[..., None] * moon_col * (0.25 + 0.7 * near[..., None])
    rgba(cl, np.clip(dens * 0.95, 0, 1) * (yy < HZ - 2)).save(os.path.join(outdir, "01_clouds.png"))

    # 02 montanas lejanas (bruma azul)
    m = np.zeros(LW)
    for k, (a, wl) in enumerate(((60, 900), (35, 310), (14, 90))):
        m += a * np.sin(xx[0] / wl * 2 * math.pi / 6 + k * 2.1)
    ridge = HZ - 26 - np.clip(m, -40, 120) * (xx[0] < LW * 0.62)
    a = (yy > ridge[None, :]) & (yy < HZ + 2)
    rgba(np.broadcast_to(np.array([34, 46, 74]), (LH, LW, 3)), a.astype(np.float32)).save(
        os.path.join(outdir, "02_mountains.png"))

    # 03 mar 45 m mas abajo: base + pinceladas + camino de luna
    t = np.clip((yy - HZ) / (LH - HZ), 0, 1)
    sea = np.repeat(grad([(0, (52, 68, 104)), (0.03, (22, 34, 62)), (0.3, (10, 18, 36)),
                          (1, (6, 12, 26))], LH)[:, None, :], LW, axis=1)
    path = np.exp(-((xx - moon[0]) / (50 + 900 * t)) ** 2)
    sea += path[..., None] * moon_col * 0.28 * (1 - t[..., None]) ** 1.5
    st = Strokes()
    y = HZ + 1.0
    while y < HZ + 330:
        D = F * (H + DROP) / (y - HZ)
        k = 1.0 / D
        for _ in range(int(30 + 6000 * k)):
            x = rng.uniform(0, LW)
            inp = math.exp(-((x - moon[0]) / (50 + 900 * (y - HZ) / 970)) ** 2)
            if rng.random() < 0.12 + 0.75 * inp:
                c, al = (226, 236, 255), 0.35 + 0.6 * inp
            else:
                c, al = (4, 8, 18), 0.45
            st.dash(x, y, rng.uniform(8, 26) + 3000 * k, 0.6 + 140 * k, c, al)
        y += 0.7 + 2.2 * (y - HZ) / 330
    img = rgba(sea, (yy >= HZ).astype(np.float32))
    img.alpha_composite(st.result(0.3))
    img.save(os.path.join(outdir, "03_sea.png"))

    # 04 isla con cascadas (derecha), 05 agua de las cascadas (capa con flujo)
    D_isl = 700.0
    top = row(D_isl, DROP + 34)
    base_r = HZ + F * (H + DROP) / D_isl      # pie de la isla, al nivel del mar
    xi = xx[0]
    prof = np.where((xi > LW * 0.56) & (xi < LW * 0.98),
                    top + 14 * np.sin(xi / 37) + 9 * np.sin(xi / 13 + 1), LH)
    prof = np.where((xi > LW * 0.56) & (xi < LW * 0.60), prof + (LW * 0.60 - xi) * 1.4, prof)
    isl = (yy > prof[None, :]) & (yy < base_r + 3)
    rock = value_noise(LH, LW, 10, rng, octaves=3, wrap_x=False)
    icol = np.array([20, 26, 40]) * (0.75 + 0.5 * rock[..., None])
    rim = np.exp(-((yy - prof[None, :]) / 3) ** 2) * isl
    icol = icol + rim[..., None] * moon_col * 0.35
    a = isl.astype(np.float32)
    # arboles en lo alto
    timg = rgba(icol, a)
    dr = ImageDraw.Draw(timg)
    for x in range(int(LW * 0.6), int(LW * 0.97), 22):
        if rng.random() < 0.55:
            yb = float(prof[x]) + 2
            h_ = rng.uniform(14, 34)
            dr.polygon([(x - 6, yb), (x + 6, yb), (x, yb - h_)], fill=(10, 16, 26, 255))
    timg.save(os.path.join(outdir, "04_island.png"))
    falls = np.zeros((LH, LW), np.float32)
    for xc in np.linspace(LW * 0.66, LW * 0.92, 6):
        w = rng.uniform(6, 16)
        y0 = float(prof[int(xc)]) + 4
        falls += np.exp(-((xx - xc) / w) ** 2) * (yy > y0) * (yy < base_r)
    fl = streaks(rng, 1, 6, cell=4)
    falls_a = np.clip(falls * (0.45 + 0.7 * fl), 0, 1)
    rgba(np.broadcast_to(np.array([214, 226, 246]), (LH, LW, 3)), falls_a).save(
        os.path.join(outdir, "05_falls.png"))

    # 06 bancos de niebla sobre el mar (periodicos)
    fog = value_noise(LH, LW, 160, rng, octaves=4, wrap_x=True)
    fb = np.exp(-((yy - (base_r - 10)) / 26) ** 2) + 0.6 * np.exp(-((yy - (HZ + 40)) / 18) ** 2)
    rgba(np.broadcast_to(np.array([150, 166, 200]), (LH, LW, 3)),
         np.clip((fog - 0.4) * 1.3, 0, 1) * fb * 0.45).save(os.path.join(outdir, "06_fog.png"))

    # 07 suelo de roca del acantilado hasta el borde (con borde iluminado)
    er = row(EDGE)
    edge_line = er + 6 * np.sin(xi / 70) + 3 * np.sin(xi / 19 + 2)
    ground = yy > edge_line[None, :]
    tx = value_noise(LH, LW, 18, rng, octaves=4, wrap_x=True)
    tx2 = streaks(rng, 4, 1, cell=5)
    ty = np.clip((yy - er) / (LH - er), 0, 1)
    gcol = np.array([58, 62, 80]) * (0.55 + 0.6 * tx[..., None]) * (0.8 + 0.4 * tx2[..., None])
    gcol = gcol * (0.75 + 0.35 * ty[..., None])
    lip = np.exp(-((yy - edge_line[None, :]) / 3.5) ** 2) * ground
    gcol = gcol + lip[..., None] * moon_col * 0.45
    gimg = rgba(gcol, ground.astype(np.float32))
    st = Strokes()
    for _ in range(900):                       # grietas y matas de hierba
        yv = rng.uniform(er + 8, LH)
        D = F * H / (yv - HZ)
        if rng.random() < 0.6:
            st.dash(rng.uniform(0, LW), yv, rng.uniform(10, 50) * 9 / D, 0.8 + 9 / D,
                    (12, 12, 16), 0.55, curve=rng.uniform(-4, 4))
        else:
            x = rng.uniform(0, LW)
            for _ in range(5):
                st.d.line([(x * 2, yv * 2), ((x + rng.uniform(-6, 6) * 9 / D) * 2,
                                             (yv - rng.uniform(6, 16) * 9 / D) * 2)],
                          fill=(30, 44, 40, 220), width=2)
    gimg.alpha_composite(st.result(0.4))
    gimg.save(os.path.join(outdir, "07_ground.png"))

    # 08 rocas a los lados del camino (a ~9 m, con altura propia)
    rk = Image.new("RGBA", (LW, LH), (0, 0, 0, 0))
    dr = ImageDraw.Draw(rk)
    for cx, D, w_m, h_m in ((LW * 0.16, 9.0, 1.6, 0.9), (LW * 0.86, 8.0, 2.0, 1.2),
                            (LW * 0.30, 12.0, 0.9, 0.5), (LW * 0.70, 13.0, 1.1, 0.6)):
        yb = row(D)
        w = F * w_m / D
        h_ = F * h_m / D
        pts = [(cx + math.cos(a_) * w / 2 * (1 + 0.15 * math.sin(a_ * 5 + cx)),
                yb - max(0, math.sin(a_)) * h_ * (1 + 0.1 * math.sin(a_ * 3)))
               for a_ in np.linspace(0, math.pi, 14)]
        dr.polygon(pts, fill=(26, 28, 38, 255))
        dr.line(pts[:6], fill=(120, 140, 180, 255), width=3)    # borde lunar
    rk.filter(ImageFilter.GaussianBlur(0.8)).save(os.path.join(outdir, "08_rocks.png"))

    # 09 primer termino: rama seca a la izquierda y roca (desenfocadas)
    fg = Image.new("RGBA", (LW, LH), (0, 0, 0, 0))
    dr = ImageDraw.Draw(fg)
    dr.polygon([(0, LH), (0, LH - 420), (160, LH - 360), (330, LH - 250), (420, LH)],
               fill=(10, 11, 16, 255))
    bx, by = 60, LH - 330
    for k in range(9):
        L = 380 - k * 30
        ang = -0.35 + 0.09 * k
        ex, ey = bx + math.cos(ang) * L, by + math.sin(ang) * L * 0.5 - k * 14
        dr.line([(bx, by - k * 10), (ex, ey)], fill=(70, 74, 86, 255), width=max(3, 14 - k))
    dr.polygon([(LW, LH), (LW, LH - 300), (LW - 260, LH - 200), (LW - 420, LH)],
               fill=(10, 11, 16, 255))
    fg.filter(ImageFilter.GaussianBlur(7)).save(os.path.join(outdir, "09_foreground.png"))

    layers = [
        {"name": "sky", "image": "00_sky.png", "distance": "inf"},
        {"name": "clouds", "image": "01_clouds.png", "distance": 4000,
         "anim": {"type": "scroll", "speed_px_s": 7}},
        {"name": "mountains", "image": "02_mountains.png", "distance": 3000},
        {"name": "sea", "image": "03_sea.png", "distance": 900,
         "anim": {"type": "waves", "rows": [HZ, HZ + 340], "amp_px": 2.0,
                  "wavelength_rows": 4, "speed": 0.5}},
        {"name": "island", "image": "04_island.png", "distance": 700},
        {"name": "falls", "image": "05_falls.png", "distance": 700,
         "anim": {"type": "flow", "speed_px_s": 40}},
        {"name": "fog", "image": "06_fog.png", "distance": 500,
         "anim": {"type": "scroll", "speed_px_s": 14}},
        {"name": "ground", "image": "07_ground.png", "distance": EDGE, "ground": True},
        {"name": "rocks", "image": "08_rocks.png", "distance": 10},
        {"name": "foreground", "image": "09_foreground.png", "distance": 1.6,
         "follow_camera": True,
         "anim": {"type": "sway", "amp_px": 5, "speed": 0.35}},
    ]
    for L in layers:
        L["horizon_px"] = HZ
        L["placeholder"] = True
    spec = {
        "name": "cliff_night", "placeholder": True,
        "note": "Capas PROVISIONALES (referencia: assets/reference/escena1/plano_02).",
        "layer_size": [LW, LH], "reference_frame": [1920, 1080],
        "geometry": {"focal_px_1080": F, "camera_height_m": H, "cliff_drop_m": DROP,
                     "edge_distance_m": EDGE,
                     "rule": "fila = horizon_px + focal * (altura_camara - altura) / distancia"},
        "layers": layers,
        "particles": [
            {"name": "glints", "type": "glint", "distance": 900, "count": 110,
             "region": [moon[0] - 200, moon[0] + 200, HZ + 2, HZ + 150],
             "size": [1.2, 3.0], "color": [220, 232, 255], "alpha": 0.85},
            {"name": "falls_spray", "distance": 700, "count": 60,
             "region": [LW * 0.64, LW * 0.94, base_r - 30, base_r], "velocity": [6, -10],
             "life": [1.5, 3.5], "size": [2, 5], "color": [210, 222, 245], "alpha": 0.35},
            {"name": "wind_debris", "distance": 6, "count": 18, "region": [-200, LW, 300, LH],
             "velocity": [120, -14], "life": [2.0, 3.5], "size": [2, 4],
             "color": [150, 160, 180], "alpha": 0.5},
            {"name": "mist", "distance": 2.5, "count": 10, "region": [0, LW, 300, LH],
             "velocity": [40, -4], "life": [5, 9], "size": [20, 48],
             "color": [170, 190, 230], "alpha": 0.07, "blur": 1},
        ],
        "lighting": {
            "sun_dir": [0.62, -0.78], "ambient": [0.58, 0.64, 0.82],
            "rim_color": [200, 220, 255], "rim_strength": 1.15, "rim_width": 6,
            "shadow_strength": 0.45, "reflection": 0.0, "contact_shadow": 0.6,
        },
        "grade": {"lift": [0.006, 0.012, 0.03], "gain": [0.98, 1.0, 1.06],
                  "saturation": 0.95, "contrast": 1.08, "vignette": 0.36,
                  "grain": 0.014, "bloom": 0.35, "bloom_threshold": 0.72,
                  "haze": [0.20, 0.27, 0.42, 0.03]},
        "audio": {"ambience": "cliff"},
    }
    with open(os.path.join(outdir, "set.json"), "w") as f:
        json.dump(spec, f, indent=2)


def main():
    targets = ((os.path.join(ROOT, "assets/character/silent/back"), build_back, "rig.json"),
               (os.path.join(ROOT, "assets/backgrounds/cliff_night"), build_cliff, "set.json"))
    for d, fn, marker in targets:
        p = os.path.join(d, marker)
        if os.path.exists(p):
            with open(p) as f:
                if not json.load(f).get("placeholder", False):
                    print(f"[skip] {d} contiene arte definitivo")
                    continue
        fn(d)
        print(f"[ok] provisional -> {d}")


if __name__ == "__main__":
    main()
