"""Camara virtual 2.5D: paneo, dolly, zoom, horizonte y temblor de mano.

Modelo: camara pinhole a `height` m sobre el suelo mirando al horizonte.
Cada capa esta a una distancia real (m), asi el dolly escala cada capa por
D/(D - z) alrededor del punto de fuga y el paneo la desplaza f*x/D: el
paralaje sale de la geometria, no de factores inventados por capa.
"""

import math
import zlib

from .util import interp_keys


class Camera:
    REF_W, REF_H = 1920, 1080

    def __init__(self, spec, defaults):
        self.keys = spec.get("keys", [{"t": 0}])
        self.shake = float(spec.get("shake", 0.0))
        self.easing = spec.get("ease", "in_out_sine")
        self.f = defaults["focal_px_1080"]
        self.h = defaults["height_m"]
        self.horizon = defaults["horizon"]
        self.seed = zlib.crc32(str(spec.get("seed", "cam")).encode()) % 1000

    def state(self, t, char_z=None):
        k = self.keys
        g = lambda name, d: interp_keys(k, t, name, d, self.easing)
        st = {
            "pan_x": g("pan_x", 0.0),
            "zoom": g("zoom", 1.0),
            "horizon": g("horizon", self.horizon) * self.REF_H,
            "height": g("height", self.h),
            "f": self.f,
        }
        if any("distance" in kk for kk in k) and char_z is not None:
            st["z"] = char_z - g("distance", 8.0)
        else:
            st["z"] = g("z", 0.0)
        # temblor de camara en mano: suma de senos inconmensurables (suave)
        a = self.shake
        s = self.seed
        st["shake_x"] = a * (math.sin(t * 1.31 + s) * 0.6 + math.sin(t * 2.73 + 2 * s) * 0.3 +
                             math.sin(t * 5.1 + s) * 0.1)
        st["shake_y"] = a * (math.sin(t * 1.07 + 3 * s) * 0.6 + math.sin(t * 3.19 + s) * 0.3 +
                             math.sin(t * 4.3 + 5 * s) * 0.1)
        return st

    # ------------------------------------------------------------------
    @staticmethod
    def layer_affine(st, D, layer_w, horizon_px, h_ref=None, ground_rows=False):
        """Afin (sx, sy, tx, ty) de px de capa a px de pantalla (ref 1920x1080).

        Las filas bajo el horizonte son proporcionales a la altura de camara
        (y - yh = f*h/D), asi que una camara mas baja comprime el suelo.
        """
        W2 = Camera.REF_W / 2
        yh = st["horizon"]
        if D == "inf" or D is None:
            k, shift = 1.0, 0.0
            # reflejos de objetos lejanos sobre el suelo: filas como suelo
            hf = st["height"] / h_ref if (h_ref and ground_rows) else 1.0
        else:
            dz = max(D - st["z"], 0.5)
            k = D / dz
            shift = -st["f"] * st["pan_x"] / dz
            hf = st["height"] / h_ref if h_ref else 1.0
        # p0 = (u - LW/2 + W/2, v - hpx + yh)
        # p1 = vp + k (p0 - vp) + (shift, 0), vp = (W/2, yh)
        # p2 = c + zoom (p1 - c) + shake
        z = st["zoom"]
        cx, cy = W2, Camera.REF_H / 2
        sx, sy = k * z, k * hf * z
        tx = cx + z * (W2 + k * (-layer_w / 2) + shift - cx) + st["shake_x"]
        ty = cy + z * (yh + k * hf * (-horizon_px) - cy) + st["shake_y"]
        return sx, sy, tx, ty

    @staticmethod
    def project_ground(st, X, d):
        """Punto del suelo a d m de la camara y X m lateral -> pantalla ref."""
        f, z = st["f"], st["zoom"]
        cx, cy = Camera.REF_W / 2, Camera.REF_H / 2
        x = cx + f * (X - st["pan_x"]) / d
        y = st["horizon"] + f * st["height"] / d
        return (cx + z * (x - cx) + st["shake_x"], cy + z * (y - cy) + st["shake_y"])
