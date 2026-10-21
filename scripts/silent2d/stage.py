"""Escenario multicapa con paralaje, particulas, iluminacion y composicion.

Orden de composicion de un frame:
  capas mas lejanas que el personaje (y capas de suelo) -> particulas lejanas
  -> sombra y reflejo del personaje -> personaje iluminado (+ brillo de ojos)
  -> capas y particulas mas cercanas -> post (bloom, etalonaje, vineta, grano)
"""

import json
import math
import os

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from .camera import Camera
from .character import MissingAsset
from .util import S, T


def surge_shape(u):
    """Ola que llega rapido (0.3 del ciclo) y se retira despacio."""
    if u < 0.3:
        return math.sin(0.5 * math.pi * u / 0.3)
    return math.cos(0.5 * math.pi * (u - 0.3) / 0.7) ** 1.4


class Stage:
    def __init__(self, folder, render_scale):
        path = os.path.join(folder, "set.json")
        if not os.path.exists(path):
            raise MissingAsset(f"Falta el escenario: {path}")
        with open(path) as f:
            self.spec = json.load(f)
        self.rs = render_scale
        self.placeholder = bool(self.spec.get("placeholder"))
        self.layers = []
        for L in self.spec["layers"]:
            fp = os.path.join(folder, L["image"])
            if not os.path.exists(fp):
                raise MissingAsset(f"Falta la capa de fondo '{L['name']}': {fp}")
            img = Image.open(fp).convert("RGBA")
            ow = img.width
            if render_scale != 1.0:
                img = img.resize((max(1, round(img.width * render_scale)),
                                  max(1, round(img.height * render_scale))), Image.LANCZOS)
            self.layers.append({**L, "arr": np.asarray(img).copy(), "orig_w": ow,
                                "D": L["distance"]})
            self.placeholder |= bool(L.get("placeholder"))
        self.h_ref = self.spec.get("geometry", {}).get("camera_height_m")
        self.light = self.spec.get("lighting", {})
        self.grade = self.spec.get("grade", {})
        self._sprites = {}
        self._frame_alpha = {}

    # ------------------------------------------------------------------
    def surge_value(self, name, t):
        for L in self.layers:
            if L["name"] == name and L.get("anim", {}).get("type") == "surge":
                a = L["anim"]
                return surge_shape((t / a["period_s"] + a.get("phase", 0.0)) % 1.0)
        return 0.0

    def _animated(self, L, t):
        """Devuelve (Image, dx, dy) con el desplazamiento extra en px de capa."""
        arr, a = L["arr"], L.get("anim")
        rs = self.rs
        dx = dy = 0.0
        if not a:
            return Image.fromarray(arr, "RGBA"), 0.0, 0.0
        typ = a["type"]
        drift = a.get("drift_px_s", a.get("speed_px_s", 0.0) if typ == "scroll" else 0.0)
        shift = drift * t * rs
        ish = math.floor(shift)
        dx = (shift - ish) / rs
        out = np.roll(arr, ish % arr.shape[1], axis=1) if ish else arr
        if typ == "waves":
            r0, r1 = (int(v * rs) for v in a["rows"])
            r1 = min(r1, arr.shape[0])
            rows = np.arange(r0, r1)
            ph = 2 * math.pi * (t * a.get("speed", 0.5))
            wl = a.get("wavelength_rows", 20) * rs
            # amplitud crece hacia el espectador (perspectiva del oleaje)
            depth = (rows - r0) / max(r1 - r0, 1)
            disp = a["amp_px"] * rs * (0.3 + 0.7 * depth) * np.sin(rows / wl * 2 * math.pi - ph)
            w = out.shape[1]
            base = np.arange(w)[None, :] + disp[:, None]
            i0 = np.floor(base).astype(np.int64)
            fr = (base - i0)[..., None]
            band = out[r0:r1]
            ri = np.arange(r1 - r0)[:, None]
            a0 = band[ri, i0 % w].astype(np.float32)
            a1 = band[ri, (i0 + 1) % w].astype(np.float32)
            out = out.copy() if out is arr else out
            out[r0:r1] = (a0 * (1 - fr) + a1 * fr).astype(np.uint8)
        elif typ == "flow":
            # agua que cae: la textura se desplaza en vertical dentro de su silueta
            if "mask" not in L:
                # silueta fija (la capa) x vetas verticales que caen (procedurales)
                L["mask"] = arr[..., 3].astype(np.float32) / 255.0
                h, w = arr.shape[:2]
                rng = np.random.default_rng(5)
                g = rng.random((max(h // 10, 4), max(w // 2, 4))).astype(np.float32)
                g = np.concatenate([g, g, g], axis=0)
                tex = np.asarray(Image.fromarray(g).resize((w, h * 3), Image.BICUBIC))
                L["tex"] = np.clip(tex[h:2 * h], 0, 1)
            sh = a["speed_px_s"] * t * rs
            tex = np.roll(L["tex"], int(math.floor(sh)) % arr.shape[0], axis=0)
            out = arr.copy()
            out[..., 3] = np.clip(L["mask"] * (0.35 + 0.9 * tex) * 255, 0, 255).astype(np.uint8)
        elif typ == "sway":
            # vegetacion/ramas: desplazamiento horizontal creciente hacia arriba
            h, w = out.shape[:2]
            rows = np.arange(h)
            k = ((h - rows) / h) ** 2
            disp = a["amp_px"] * rs * k * (math.sin(2 * math.pi * a.get("speed", 0.3) * t) +
                                           0.35 * math.sin(2 * math.pi * 1.7 * t + 1))
            base = np.arange(w)[None, :] - disp[:, None]
            i0 = np.clip(np.floor(base).astype(np.int64), 0, w - 2)
            fr = np.clip(base - i0, 0, 1)[..., None]
            ri = rows[:, None]
            out = (out[ri, i0].astype(np.float32) * (1 - fr) +
                   out[ri, i0 + 1].astype(np.float32) * fr).astype(np.uint8)
        elif typ == "surge":
            s = surge_shape((t / a["period_s"] + a.get("phase", 0.0)) % 1.0)
            dy = a["amp_px"] * s
            fade = a.get("fade", 0.0)
            if fade:
                out = out.copy()
                out[..., 3] = (out[..., 3] * (1 - fade * (1 - s))).astype(np.uint8)
        return Image.fromarray(out, "RGBA"), dx, dy

    def draw_layer(self, frame, L, st, t):
        img, ex, ey = self._animated(L, t)
        if L.get("follow_camera"):
            # elemento de primer termino que acompana a la camara en un seguimiento:
            # conserva el paralaje del paneo pero no se le "atraviesa" con el dolly
            st = dict(st, z=0.0)
        sx, sy, tx, ty = Camera.layer_affine(st, L["D"], L["orig_w"], L["horizon_px"],
                                             self.h_ref, L.get("ground_rows", False))
        rs = self.rs
        offx, offy = rs * (tx + sx * ex), rs * (ty + sy * ey)
        data = (1 / sx, 0, -offx / sx, 0, 1 / sy, -offy / sy)
        out = img.transform(frame.size, Image.AFFINE, data=data, resample=Image.BILINEAR)
        mask_name = L.get("mask_with")
        if mask_name and mask_name in self._frame_alpha:
            out.putalpha(ImageChops.multiply(out.getchannel("A"), self._frame_alpha[mask_name]))
        if any(M.get("mask_with") == L["name"] for M in self.layers):
            self._frame_alpha[L["name"]] = out.getchannel("A")
        frame.alpha_composite(out)

    # ------------------------------------------------------------------
    def _sprite(self, diam, color, soft):
        key = (diam, tuple(color), soft)
        if key not in self._sprites:
            n = max(diam, 2)
            yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
            r = np.hypot(xx - (n - 1) / 2, yy - (n - 1) / 2) / (n / 2)
            a = np.exp(-(r ** 2) * (3.0 if soft else 6.0)) * (r < 1)
            rgb = np.broadcast_to(np.array(color, np.float32), (n, n, 3))
            self._sprites[key] = (rgb, a)
        return self._sprites[key]

    def draw_particles(self, frame_arr, P, st, t, seed):
        """Particulas deterministas (dependen solo del tiempo)."""
        rs = self.rs
        H, W = frame_arr.shape[:2]
        sx, sy, tx, ty = Camera.layer_affine(st, P["distance"], self.spec["layer_size"][0],
                                             self.layers[0]["horizon_px"], self.h_ref)
        x0, x1, y0, y1 = P["region"]
        rng = np.random.default_rng(seed)
        n = P["count"]
        base = rng.random((n, 6))
        glint = P.get("type") == "glint"
        for i in range(n):
            r = base[i]
            if glint:
                px = x0 + r[0] * (x1 - x0) + 6 * math.sin(t * 0.7 + r[3] * 6)
                py = y0 + (r[1] ** 1.8) * (y1 - y0)
                fl = max(0.0, math.sin(t * (2 + 5 * r[2]) + r[4] * 40)) ** 6
                alpha = P["alpha"] * fl
                size = P["size"][0] + r[5] * (P["size"][1] - P["size"][0])
            else:
                life = P["life"][0] + r[2] * (P["life"][1] - P["life"][0])
                tt = t + r[3] * life
                cyc = math.floor(tt / life)
                age = tt - cyc * life
                rr = np.random.default_rng(seed * 7919 + i * 131 + cyc).random(2)
                px = x0 + rr[0] * (x1 - x0) + P["velocity"][0] * age
                py = y0 + rr[1] * (y1 - y0) + P["velocity"][1] * age + \
                    3 * math.sin(age * 2 + r[4] * 6)
                alpha = P["alpha"] * math.sin(math.pi * age / life) ** 1.5
                size = P["size"][0] + r[5] * (P["size"][1] - P["size"][0])
            if alpha < 0.01:
                continue
            X = rs * (sx * px + tx)
            Y = rs * (sy * py + ty)
            diam = int(max(2, size * sx * rs * (2.4 if P.get("blur") else 1.6)))
            xa, ya = int(X - diam / 2), int(Y - diam / 2)
            if xa >= W or ya >= H or xa + diam <= 0 or ya + diam <= 0:
                continue
            rgb, a = self._sprite(diam, P["color"], bool(P.get("blur")))
            cx0, cy0 = max(0, -xa), max(0, -ya)
            cx1, cy1 = min(diam, W - xa), min(diam, H - ya)
            sub = frame_arr[ya + cy0:ya + cy1, xa + cx0:xa + cx1, :3]
            aa = (a[cy0:cy1, cx0:cx1] * alpha)[..., None]
            sub[:] = sub * (1 - aa) + rgb[cy0:cy1, cx0:cx1] * aa  # mezcla normal
        return frame_arr


# ---------------------------------------------------------------------------
# Personaje en escena
# ---------------------------------------------------------------------------
def shifted(a, dx, dy):
    """Desplaza un array 2D (relleno con 0)."""
    h, w = a.shape
    out = np.zeros_like(a)
    xs, xd = (slice(0, w - dx), slice(dx, w)) if dx >= 0 else (slice(-dx, w), slice(0, w + dx))
    ys, yd = (slice(0, h - dy), slice(dy, h)) if dy >= 0 else (slice(-dy, h), slice(0, h + dy))
    out[yd, xd] = a[ys, xs]
    return out


def light_character(canvas, emissive, light, d, px_per_art, haze):
    """px_per_art: px de PANTALLA por unidad de arte (ya incluye la escala)."""
    rgba = np.asarray(canvas).astype(np.float32) / 255.0
    rgb, a = rgba[..., :3], rgba[..., 3]
    amb = np.array(light.get("ambient", [1, 1, 1]), np.float32)
    rgb = rgb * amb
    # luz de borde (contraluz): bordes orientados hacia el sol
    w = max(1, int(round(light.get("rim_width", 4) * px_per_art)))
    sd = light.get("sun_dir", [-0.5, -0.5])
    na = shifted(a, -int(round(sd[0] * w)), -int(round(sd[1] * w)))
    rim = np.clip(a - na, 0, 1)
    rim_img = Image.fromarray((rim * 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(max(0.6, w * 0.35)))
    rim = np.asarray(rim_img).astype(np.float32) / 255.0 * a
    rc = np.array(light.get("rim_color", [255, 200, 150]), np.float32) / 255.0
    rgb = rgb + rim[..., None] * rc * light.get("rim_strength", 0.8)
    # perspectiva aerea muy suave segun la distancia
    if haze:
        k = min(haze[3] * d / 10.0, 0.5)
        rgb = rgb * (1 - k) + np.array(haze[:3], np.float32) * k
    out = np.dstack([np.clip(rgb, 0, 1), a])
    img = Image.fromarray((out * 255).astype(np.uint8), "RGBA")
    # ojos emisivos + halo
    em = emissive
    if em.getbbox():
        glow = em.filter(ImageFilter.GaussianBlur(max(1.0, 22 * px_per_art)))
        g = np.asarray(glow).astype(np.float32)
        g[..., 3] = np.clip(g[..., 3] * 1.6, 0, 255)
        img.alpha_composite(Image.fromarray(g.astype(np.uint8), "RGBA"))
        img.alpha_composite(em)
    return img


def ground_effects(frame, canvas, origin, feet_y, light, rs):
    """Sombra proyectada hacia camara y reflejo en la arena humeda."""
    cx0, cy0 = origin
    a = canvas.getchannel("A")
    fy = int(round(feet_y - cy0))
    fy = max(1, min(fy, canvas.height))
    above_a = a.crop((0, 0, canvas.width, fy))
    above = canvas.crop((0, 0, canvas.width, fy))
    # oclusion de contacto bajo los pies (asienta al personaje en la arena)
    cs = light.get("contact_shadow", 0.0)
    if cs > 0:
        cols = np.where(np.asarray(a)[max(fy - 6, 0):fy].max(axis=0) > 40)[0]
        if len(cols):
            x0, x1 = cols.min(), cols.max()
            w = float(x1 - x0) * 1.5
            hgt = max(4, w * 0.16)
            pad = int(hgt * 2)
            sh_img = Image.new("L", (int(w) + 2 * pad, int(hgt) + 2 * pad), 0)
            ImageDraw.Draw(sh_img).ellipse((pad, pad, pad + w, pad + hgt), fill=int(255 * cs))
            sh_img = sh_img.filter(ImageFilter.GaussianBlur(hgt * 0.45))
            blk = Image.new("RGBA", sh_img.size, (6, 6, 10, 0))
            blk.putalpha(sh_img)
            paste_clipped(frame, blk, cx0 + (x0 + x1) / 2 - sh_img.width / 2,
                          cy0 + fy - sh_img.height / 2)
    # sombra
    q = 0.55
    sh = above_a.transpose(Image.FLIP_TOP_BOTTOM)
    sh = sh.resize((sh.width, max(1, int(sh.height * q))), Image.BILINEAR)
    sh = sh.filter(ImageFilter.GaussianBlur(max(1, 4 * rs)))
    st = light.get("shadow_strength", 0.4)
    shadow = Image.new("RGBA", sh.size, (8, 8, 14, 0))
    shadow.putalpha(sh.point(lambda v: int(v * st)))
    paste_clipped(frame, shadow, cx0, cy0 + fy)
    # reflejo
    rf = light.get("reflection", 0.0)
    if rf > 0:
        r = above.transpose(Image.FLIP_TOP_BOTTOM)
        arr = np.asarray(r).astype(np.float32)
        h = arr.shape[0]
        fade = np.clip(1 - np.arange(h) / (0.55 * h), 0, 1) ** 1.5
        arr[..., 3] *= rf * fade[:, None]
        arr[..., :3] *= 0.75
        r = Image.fromarray(arr.astype(np.uint8), "RGBA").filter(
            ImageFilter.GaussianBlur(max(1, 2.5 * rs)))
        paste_clipped(frame, r, cx0, cy0 + fy)


def paste_clipped(frame, img, x, y):
    """alpha_composite admitiendo que la imagen salga del cuadro."""
    x, y = int(x), int(y)
    sx0, sy0 = max(0, -x), max(0, -y)
    sx1, sy1 = min(img.width, frame.width - x), min(img.height, frame.height - y)
    if sx1 <= sx0 or sy1 <= sy0:
        return
    frame.alpha_composite(img.crop((sx0, sy0, sx1, sy1)), (x + sx0, y + sy0))


# ---------------------------------------------------------------------------
# Post-produccion
# ---------------------------------------------------------------------------
_VIG = {}


def post(frame, grade, t, frame_index, rs):
    x = np.asarray(frame.convert("RGB")).astype(np.float32) / 255.0
    H, W = x.shape[:2]
    b = grade.get("bloom", 0.0)
    if b:
        thr = grade.get("bloom_threshold", 0.8)
        lum = x.max(axis=2)
        m = np.clip((lum - thr) / (1 - thr), 0, 1)
        src = Image.fromarray((x * m[..., None] * 255).astype(np.uint8))
        small = src.resize((max(1, W // 8), max(1, H // 8)), Image.BILINEAR).filter(
            ImageFilter.GaussianBlur(3))
        up = np.asarray(small.resize((W, H), Image.BILINEAR)).astype(np.float32) / 255.0
        x = 1 - (1 - x) * (1 - up * b)                       # screen
    lift = np.array(grade.get("lift", [0, 0, 0]), np.float32)
    gain = np.array(grade.get("gain", [1, 1, 1]), np.float32)
    x = x * gain + lift * (1 - x)
    c = grade.get("contrast", 1.0)
    x = np.clip((x - 0.5) * c + 0.5, 0, 1)
    l = (x @ np.array([0.299, 0.587, 0.114], np.float32))[..., None]
    x = l + (x - l) * grade.get("saturation", 1.0)
    v = grade.get("vignette", 0.0)
    if v:
        key = (W, H, v)
        if key not in _VIG:
            yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
            r = np.hypot((xx - W / 2) / (W / 2), (yy - H / 2) / (H / 2)) / 1.414
            _VIG[key] = (1 - v * np.clip(r, 0, 1) ** 2.2)[..., None]
        x = x * _VIG[key]
    g = grade.get("grain", 0.0)
    if g:
        rng = np.random.default_rng(1000 + frame_index)
        n = rng.standard_normal((H, W, 1)).astype(np.float32)
        x = x + n * g
    return Image.fromarray((np.clip(x, 0, 1) * 255 + 0.5).astype(np.uint8), "RGB")


def stamp(img, text, rs):
    d = ImageDraw.Draw(img)
    size = max(10, int(17 * rs))
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except OSError:
        font = ImageFont.load_default()
    pad = int(10 * rs)
    bb = d.textbbox((0, 0), text, font=font)
    x, y = pad * 2, img.height - (bb[3] - bb[1]) - pad * 3
    d.rectangle((x - pad, y - pad, x + bb[2] - bb[0] + pad, y + bb[3] - bb[1] + pad + 2),
                fill=(0, 0, 0))
    d.text((x, y - bb[1]), text, fill=(255, 196, 64), font=font)
    return img


def char_screen_matrix(st, X, d, rig, rs):
    fx, fy = Camera.project_ground(st, X, d)
    px_per_art = st["zoom"] * st["f"] * (rig.height_m / d) / rig.units
    return T(fx * rs, fy * rs) @ S(px_per_art * rs), px_per_art * rs, fy * rs
