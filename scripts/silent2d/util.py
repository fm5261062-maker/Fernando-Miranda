"""Utilidades matematicas: easing, interpolacion, matrices afines 2D y ruido."""

import math

import numpy as np


# --------------------------------------------------------------------------
# Easing
# --------------------------------------------------------------------------
def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def lerp(a, b, t):
    return a + (b - a) * t


def smoothstep(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


def smootherstep(t):
    t = clamp(t)
    return t * t * t * (t * (t * 6 - 15) + 10)


EASINGS = {
    "linear": lambda t: clamp(t),
    "in_out_sine": lambda t: 0.5 - 0.5 * math.cos(math.pi * clamp(t)),
    "in_sine": lambda t: 1 - math.cos(0.5 * math.pi * clamp(t)),
    "out_sine": lambda t: math.sin(0.5 * math.pi * clamp(t)),
    "in_out_cubic": lambda t: (4 * clamp(t) ** 3 if t < 0.5
                               else 1 - (-2 * clamp(t) + 2) ** 3 / 2),
    "smooth": smootherstep,
}


def ease(name, t):
    return EASINGS.get(name or "in_out_sine", EASINGS["in_out_sine"])(t)


def interp_keys(keys, t, field, default=0.0, easing="in_out_sine"):
    """Interpola un campo entre keyframes [{t:..., field:...}, ...].

    Los keys que no definen el campo se ignoran para ese campo.
    """
    pts = [(k["t"], k[field], k.get("ease", easing)) for k in keys if field in k]
    if not pts:
        return default
    if t <= pts[0][0]:
        return pts[0][1]
    for (t0, v0, _), (t1, v1, e1) in zip(pts, pts[1:]):
        if t <= t1:
            u = ease(e1, (t - t0) / max(t1 - t0, 1e-9))
            if isinstance(v0, (list, tuple)):
                return [lerp(a, b, u) for a, b in zip(v0, v1)]
            return lerp(v0, v1, u)
    return pts[-1][1]


# --------------------------------------------------------------------------
# Afines 2D (matrices 3x3, coordenadas de pantalla con y hacia abajo)
# --------------------------------------------------------------------------
def T(x, y):
    return np.array([[1, 0, x], [0, 1, y], [0, 0, 1]], dtype=float)


def R(deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], dtype=float)


def S(sx, sy=None):
    return np.array([[sx, 0, 0], [0, sx if sy is None else sy, 0], [0, 0, 1]],
                    dtype=float)


def apply(m, x, y):
    v = m @ np.array([x, y, 1.0])
    return float(v[0]), float(v[1])


# --------------------------------------------------------------------------
# Ruido periodico (para texturas procedurales provisionales)
# --------------------------------------------------------------------------
def value_noise(h, w, cell, rng, octaves=4, persistence=0.5, wrap_x=True):
    """Ruido fractal suave en [0,1], periodico en X si wrap_x."""
    from PIL import Image

    out = np.zeros((h, w), dtype=np.float32)
    amp, total = 1.0, 0.0
    for o in range(octaves):
        c = max(cell / (2 ** o), 2)
        gh, gw = int(math.ceil(h / c)) + 3, max(int(round(w / c)), 2)
        g = rng.random((gh, gw)).astype(np.float32)
        if wrap_x:
            g = np.concatenate([g, g, g], axis=1)
            im = Image.fromarray(g).resize((w * 3, int(gh * c)), Image.BICUBIC)
            arr = np.asarray(im)[:h, w:2 * w]
        else:
            im = Image.fromarray(g).resize((int(gw * c), int(gh * c)), Image.BICUBIC)
            arr = np.asarray(im)[:h, :w]
        out += amp * arr
        total += amp
        amp *= persistence
    out /= total
    lo, hi = np.percentile(out, 1), np.percentile(out, 99)
    return np.clip((out - lo) / max(hi - lo, 1e-6), 0, 1)
