"""Movimiento secundario y viento.

La curva de viento es determinista (depende solo del tiempo global y de la
semilla) y la comparten la animacion de la ropa y la pista de audio del
viento, para que cada rafaga se vea y se oiga a la vez.
"""

import math


def wind_curve(spec):
    """Devuelve f(t) -> intensidad del viento en [0, ~1.3]."""
    if not spec:
        return lambda t: 0.0
    base = spec.get("base", 0.3)
    gust = spec.get("gust", 0.5)
    period = spec.get("gust_period_s", 4.5)
    seed = spec.get("seed", 3)

    def f(t):
        g = 0.0
        for k, (a, m) in enumerate(((1.0, 1.0), (0.55, 1.73), (0.3, 3.1))):
            g += a * math.sin(2 * math.pi * t * m / period + seed * (k + 1) * 1.7)
        g = max(0.0, g / 1.85) ** 1.6
        return base + gust * g
    return f


class Spring:
    """Muelle amortiguado (integrado a paso fijo)."""

    def __init__(self, freq, damping, x0=0.0):
        self.w = 2 * math.pi * freq
        self.z = damping
        self.x = x0
        self.v = 0.0

    def step(self, target, dt):
        n = 4
        h = dt / n
        for _ in range(n):
            a = self.w * self.w * (target - self.x) - 2 * self.z * self.w * self.v
            self.v += a * h
            self.x += self.v * h
        return self.x


def apply_secondary(frames, fps, rig, wind_fn, t_offset=0.0):
    """Anade canales pack_dy, pack_rot, coat_swing, hood_wind a cada frame."""
    dt = 1.0 / fps
    pack_y = Spring(2.6, 0.32)
    pack_r = Spring(1.8, 0.4)
    coat = Spring(1.6, 0.28)
    hood = Spring(2.2, 0.35)
    prev_rx = None
    first = True
    for fs in frames:
        ch = fs["ch"]
        tg = fs["t"] + t_offset
        w = wind_fn(tg)
        ry = ch["root_y"]
        if first:
            pack_y.x = ry
            first = False
        y = pack_y.step(ry, dt)
        ch["pack_dy"] = (y - ry) * 1.4                       # retraso al rebotar
        vx = 0.0 if prev_rx is None else (ch["root_x"] - prev_rx) / dt
        prev_rx = ch["root_x"]
        ch["pack_rot"] = pack_r.step(-0.12 * vx + 1.2 * ch["torso_rot"], dt)
        flutter = 1.6 * w * math.sin(tg * 9.0) + 0.8 * w * math.sin(tg * 15.3 + 1)
        ch["coat_swing"] = coat.step(-0.10 * vx + 7.0 * w, dt) + flutter
        ch["hood_wind"] = hood.step(2.5 * w, dt) + 0.6 * w * math.sin(tg * 11.0)
    return frames
