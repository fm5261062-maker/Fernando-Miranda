"""Pincel vectorial minimo para generar ARTE PROVISIONAL.

Solo lo usa `make_placeholder_assets.py`. El arte definitivo debe venir de un
ilustrador siguiendo la hoja de diseno de Silent; estas capas existen para
probar el rig, la camara y el montaje mientras tanto.
"""

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter


def catmull_rom(pts, closed=True, n=10):
    """Suaviza una polilinea con splines Catmull-Rom."""
    pts = [np.array(p, dtype=float) for p in pts]
    m = len(pts)
    out = []
    rng = range(m) if closed else range(m - 1)
    for i in rng:
        p0 = pts[(i - 1) % m] if closed or i > 0 else pts[0]
        p1, p2 = pts[i], pts[(i + 1) % m]
        p3 = pts[(i + 2) % m] if closed or i + 2 < m else pts[-1]
        for k in range(n):
            t = k / n
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * ((2 * p1) + (-p0 + p2) * t +
                                    (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 +
                                    (-p0 + 3 * p1 - 3 * p2 + p3) * t3)))
    if not closed:
        out.append(tuple(pts[-1]))
    return out


class Sheet:
    """Lienzo en coordenadas de arte (origen en el suelo, y hacia abajo)."""

    def __init__(self, x0, y0, x1, y1, scale=1.5, ss=3):
        self.x0, self.y0, self.scale, self.ss = x0, y0, scale, ss
        self.w = int((x1 - x0) * scale)
        self.h = int((y1 - y0) * scale)
        self.img = Image.new("RGBA", (self.w * ss, self.h * ss), (0, 0, 0, 0))

    def P(self, pts):
        k = self.scale * self.ss
        return [((x - self.x0) * k, (y - self.y0) * k) for x, y in pts]

    def mask(self, pts, smooth=True):
        poly = self.P(catmull_rom(pts) if smooth else pts)
        m = Image.new("L", self.img.size, 0)
        ImageDraw.Draw(m).polygon(poly, fill=255)
        return m, poly

    def fill(self, pts, color, line=(34, 36, 44), lw=2.2, smooth=True,
             volume=0.35, light=(-0.6, -0.8), light_amt=0.12, cut=None):
        """Rellena una forma con volumen suave (bordes mas oscuros) y luz."""
        m, poly = self.mask(pts, smooth)
        if cut is not None:
            m = ImageChops.subtract(m, cut)
        bb = m.getbbox()
        if not bb:
            return m
        k = self.scale * self.ss
        blur = m.filter(ImageFilter.GaussianBlur(14 * k))
        a = np.asarray(blur, dtype=np.float32) / 255.0
        shade = (1 - volume) + volume * np.clip(a * 1.6, 0, 1)
        h, w = a.shape
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        cx, cy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
        span = max(bb[2] - bb[0], bb[3] - bb[1], 1)
        d = ((xx - cx) * light[0] + (yy - cy) * light[1]) / span
        shade = shade * (1 + light_amt * np.clip(d * 2, -1, 1))
        rgb = np.clip(np.array(color, np.float32)[None, None, :] *
                      shade[..., None], 0, 255).astype(np.uint8)
        layer = Image.fromarray(rgb, "RGB").convert("RGBA")
        layer.putalpha(m)
        self.img.alpha_composite(layer)
        if line:
            ImageDraw.Draw(self.img).line(poly + [poly[0]], fill=(*line, 255),
                                          width=max(1, int(lw * k)), joint="curve")
        return m

    def stroke(self, pts, color, lw=1.6, alpha=255, smooth=True):
        k = self.scale * self.ss
        poly = self.P(catmull_rom(pts, closed=False, n=8) if smooth and len(pts) > 2
                      else pts)
        ImageDraw.Draw(self.img).line(poly, fill=(*color, alpha),
                                      width=max(1, int(lw * k)), joint="curve")

    def ellipse(self, cx, cy, rx, ry, color, line=None, lw=1.5):
        k = self.scale * self.ss
        (x0, y0), (x1, y1) = self.P([(cx - rx, cy - ry), (cx + rx, cy + ry)])
        ImageDraw.Draw(self.img).ellipse(
            (x0, y0, x1, y1), fill=(*color, 255),
            outline=(*line, 255) if line else None,
            width=max(1, int(lw * k)) if line else 0)

    def folds(self, m, lines, color, lw=1.4, alpha=110):
        """Pliegues de tela recortados a la mascara de la prenda."""
        k = self.scale * self.ss
        tmp = Image.new("RGBA", self.img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(tmp)
        for pts in lines:
            poly = self.P(catmull_rom(pts, closed=False, n=8) if len(pts) > 2 else pts)
            d.line(poly, fill=(*color, alpha), width=max(1, int(lw * k)), joint="curve")
        tmp = tmp.filter(ImageFilter.GaussianBlur(0.8 * k))
        tmp.putalpha(ImageChops.multiply(tmp.getchannel("A"), m))
        self.img.alpha_composite(tmp)

    def result(self):
        """Devuelve la imagen final (antialiasing por supermuestreo)."""
        return self.img.resize((self.w, self.h), Image.LANCZOS)
