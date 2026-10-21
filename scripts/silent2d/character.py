"""Personaje 2D por capas: carga del rig, solver de pose y dibujo.

Cada capa es un "hueso" entre dos articulaciones del rig. El solver calcula
la posicion de las articulaciones (con brazos y piernas resueltos en 3D y
proyectados con perspectiva real) y cada imagen se deforma con una afin que
lleva el hueso de reposo al hueso resuelto.
"""

import json
import math
import os

import numpy as np
from PIL import Image

from .util import R, S, T


class MissingAsset(Exception):
    pass


def bone_angle(v):
    """Angulo que lleva +Y (abajo) a la direccion v (coordenadas y-abajo)."""
    return math.degrees(math.atan2(-v[0], v[1]))


def rot2(v, deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return np.array([c * v[0] - s * v[1], s * v[0] + c * v[1]])


class Rig:
    MIP_LEVELS = 4
    EMISSIVE = ("eyes",)

    def __init__(self, folder, render_scale=1.0):
        path = os.path.join(folder, "rig.json")
        if not os.path.exists(path):
            raise MissingAsset(f"Falta el rig del personaje: {path}")
        with open(path) as f:
            spec = json.load(f)
        self.folder = folder
        self.spec = spec
        self.view = spec.get("view", "front")
        # "back": el personaje mira hacia el fondo; avanzar = alejarse de camara
        self.zsign = -1.0 if self.view == "back" else 1.0
        self.units = spec["art_units_per_height"]
        self.height_m = spec["height_m"]
        self.ppm = self.units / self.height_m
        self.img_scale = spec["image_scale"]
        self.joints = {k: np.array(v, float) for k, v in spec["joints"].items()}
        self.parts = spec["parts"]
        self.order = spec["draw_order"]
        self.missing = []
        self.placeholder = bool(spec.get("placeholder")) or any(
            p.get("placeholder") for p in self.parts.values())
        self.images = {}
        for name, p in self.parts.items():
            fp = os.path.join(folder, p["image"])
            if not os.path.exists(fp):
                raise MissingAsset(f"Falta la capa '{name}': {fp}")
            self.images[(name, None)] = self._mips(Image.open(fp).convert("RGBA"))
        for part, vs in spec.get("variants", {}).items():
            for vname, fn in vs.items():
                fp = os.path.join(folder, fn)
                if os.path.exists(fp):
                    self.images[(part, vname)] = self._mips(Image.open(fp).convert("RGBA"))
                else:
                    self.missing.append(f"{os.path.relpath(fp)} (variante '{vname}' "
                                        f"de {part})")
        L = lambda a, b: np.linalg.norm(self.joints[a] - self.joints[b]) / self.ppm
        self.len = {}
        for side in ("L", "R"):
            self.len[f"thigh.{side}"] = L(f"hip.{side}", f"knee.{side}")
            self.len[f"shin.{side}"] = L(f"knee.{side}", f"ankle.{side}")
            self.len[f"upper_arm.{side}"] = L(f"shoulder.{side}", f"elbow.{side}")
            self.len[f"forearm.{side}"] = L(f"elbow.{side}", f"wrist.{side}")
            self.len[f"hand.{side}"] = L(f"wrist.{side}", f"hand_tip.{side}")
        self.rest_hip_h = -self.joints["hip.L"][1] / self.ppm
        self.rest_ankle_h = -self.joints["ankle.L"][1] / self.ppm

    @classmethod
    def _mips(cls, img):
        out = [(1.0, img)]
        for k in range(1, cls.MIP_LEVELS):
            s = 0.5 ** k
            w, h = max(int(img.width * s), 1), max(int(img.height * s), 1)
            out.append((s, img.resize((w, h), Image.LANCZOS)))
        return out

    # ------------------------------------------------------------------
    # Perspectiva: un punto a z metros hacia la camara respecto al plano
    # del personaje (que esta a d metros de una camara a h_cam de altura)
    # ------------------------------------------------------------------
    def persp(self, x, y, z, d, h_cam):
        ppm = self.ppm
        zp = max(d - z, 0.3)
        k = d / zp
        height = -y / ppm
        return np.array([x * k, -(h_cam - (h_cam - height) * k) * ppm]), k

    # ------------------------------------------------------------------
    def solve(self, c, d, h_cam):
        """Pose (canales) -> articulaciones resueltas + escalas por parte."""
        J = self.joints
        ppm = self.ppm
        out = {}
        width = {}
        extra = {}
        root = np.array([c["root_x"], c["root_y"]])
        pel = J["pelvis"] + root
        a_p = c["pelvis_rot"]
        a_t = a_p + c["torso_rot"]
        a_h = a_t + c["head_rot"]
        out["pelvis"] = pel
        out["crotch"] = pel + rot2(J["crotch"] - J["pelvis"], a_p)
        out["neck"] = pel + rot2(J["neck"] - J["pelvis"], a_t)
        if "string_top" in J:
            out["string_top"] = pel + rot2(J["string_top"] - J["pelvis"], a_t)
            out["string_end"] = out["string_top"] + rot2(
                J["string_end"] - J["string_top"], a_t + c["string_swing"])
        out["head_top"] = out["neck"] + rot2(J["head_top"] - J["neck"], a_h)
        zs = self.zsign
        # piezas con movimiento secundario (mochila, faldon de la chaqueta)
        if "pack_top" in J:
            out["pack_top"] = pel + rot2(J["pack_top"] - J["pelvis"], a_t) + \
                np.array([0.0, c.get("pack_dy", 0.0)])
            out["pack_bottom"] = out["pack_top"] + rot2(J["pack_bottom"] - J["pack_top"],
                                                        a_t + c.get("pack_rot", 0.0))
        if "hem_top" in J:
            out["hem_top"] = pel + rot2(J["hem_top"] - J["pelvis"], a_t)
            out["hem_bottom"] = out["hem_top"] + rot2(J["hem_bottom"] - J["hem_top"],
                                                      a_p + c.get("coat_swing", 0.0))

        for side in ("L", "R"):
            s = 1.0 if J[f"shoulder.{side}"][0] > 0 else -1.0   # lado de pantalla
            # ---------------- piernas: IK sagital + proyeccion ------------
            hip = pel + rot2(J[f"hip.{side}"] - J["pelvis"], a_p)
            out[f"hip.{side}"] = hip
            l1, l2 = self.len[f"thigh.{side}"], self.len[f"shin.{side}"]
            h_hip = -hip[1] / ppm
            za, ha = c[f"ankle_z.{side}"], c[f"ankle_h.{side}"]
            v = np.array([za, ha - h_hip])
            dist = float(np.linalg.norm(v))
            dist = min(max(dist, abs(l1 - l2) + 1e-3), (l1 + l2) * 0.9995)
            u = v / max(np.linalg.norm(v), 1e-6)
            cosa = (l1 * l1 + dist * dist - l2 * l2) / (2 * l1 * dist)
            alpha = math.acos(max(-1.0, min(1.0, cosa)))
            ca, sa = math.cos(alpha), math.sin(alpha)
            kdir = np.array([u[0] * ca - u[1] * sa, u[0] * sa + u[1] * ca])
            knee_zh = np.array([0.0, h_hip]) + l1 * kdir
            ankle_zh = np.array([0.0, h_hip]) + u * dist
            ax = c[f"ankle_x.{side}"]
            bend = sa
            kx = 0.5 * (hip[0] + ax) + s * 5 * bend
            knee, sk = self.persp(kx, -knee_zh[1] * ppm, zs * knee_zh[0], d, h_cam)
            ankle, sa_ = self.persp(ax, -ankle_zh[1] * ppm, zs * ankle_zh[0], d, h_cam)
            out[f"knee.{side}"] = knee
            out[f"ankle.{side}"] = ankle
            toe_len = (J[f"toe.{side}"][1] - J[f"ankle.{side}"][1]) * sa_
            pitch = math.radians(c[f"foot_pitch.{side}"])
            out[f"toe.{side}"] = ankle + np.array([0, toe_len * (1 + 0.35 * math.sin(pitch))])
            width[f"thigh.{side}"] = 0.5 * (1 + sk)
            width[f"shin.{side}"] = 0.5 * (sk + sa_)
            width[f"foot.{side}"] = sa_

            # ---------------- brazos: cadena 3D + proyeccion --------------
            sh = pel + rot2(J[f"shoulder.{side}"] - J["pelvis"], a_t)
            out[f"shoulder.{side}"] = sh
            pos = np.array([sh[0], sh[1], 0.0])     # x, y (arte), z (m)
            flex = c[f"arm_flex.{side}"]
            abd = c[f"arm_abd.{side}"]
            bends = (0.0, c[f"elbow.{side}"], c[f"elbow.{side}"] + c[f"wrist.{side}"])
            segs = ((f"shoulder.{side}", f"elbow.{side}"), (f"elbow.{side}", f"wrist.{side}"),
                    (f"wrist.{side}", f"hand_tip.{side}"))
            names = ("elbow", "wrist", "hand_tip")
            scales = []
            for (a, b), nm, bend_deg in zip(segs, names, bends):
                rest = J[b] - J[a]
                length = np.linalg.norm(rest)
                d0 = rest / length                               # en plano frontal
                d0 = rot2(d0, -abd * s)                          # abduccion
                phi = math.radians(flex + bend_deg)              # flexion sagital
                dv = np.array([d0[0], d0[1] * math.cos(phi), d0[1] * math.sin(phi)])
                xy = rot2(dv[:2], a_t)
                pos = pos + np.array([xy[0] * length, xy[1] * length,
                                      zs * dv[2] * length / ppm])
                p2, k = self.persp(pos[0], pos[1], pos[2], d, h_cam)
                out[f"{nm}.{side}"] = p2
                scales.append(k)
            sh_p, k0 = self.persp(sh[0], sh[1], 0.0, d, h_cam)
            out[f"shoulder.{side}"] = sh_p
            width[f"upper_arm.{side}"] = 0.5 * (k0 + scales[0])
            width[f"forearm.{side}"] = 0.5 * (scales[0] + scales[1])
            width[f"hand.{side}"] = scales[1]

        # Giro de cabeza (3/4 simulado) y parpadeo
        turn = c["head_turn"]
        eye_c = np.array([0.0, -930.0])
        extra["face"] = T(turn * 7, 0) @ T(*J["neck"]) @ S(1 - 0.06 * abs(turn), 1) @ \
            T(*-J["neck"])
        extra["eyes"] = T(turn * 14, 0) @ T(*eye_c) @ \
            S(1 - 0.18 * abs(turn), max(c["blink"], 0.06)) @ T(*-eye_c)
        extra["hood_rim"] = T(turn * 3, 0)
        hw = c.get("hood_wind", 0.0)
        if hw:
            extra["hood"] = T(*J["neck"]) @ R(hw) @ T(*-J["neck"])
        return out, width, extra

    # ------------------------------------------------------------------
    def matrices(self, joints, width, extra, variants=None):
        """Matriz imagen->arte de cada parte resuelta."""
        J = self.joints
        res = []
        for name in self.order:
            p = self.parts[name]
            a, b = p["bone"]
            ar, br = J[a], J[b]
            as_, bs = joints[a], joints[b]
            vr, vs = br - ar, bs - as_
            lr, ls = np.linalg.norm(vr), np.linalg.norm(vs)
            th_r, th_s = bone_angle(vr), bone_angle(vs)
            sl = ls / lr if lr > 1e-6 else 1.0
            sw = width.get(name, 1.0)
            m = T(*as_) @ R(th_s) @ S(sw, sl) @ R(-th_r) @ T(*-ar)
            if name in extra:
                m = m @ extra[name]
            ox, oy = p["image_origin"]
            img2art = T(ox, oy) @ S(1.0 / self.img_scale)
            var = (variants or {}).get(name)
            key = (name, var) if (name, var) in self.images else (name, None)
            res.append((name, key, m @ img2art))
        return res

    def draw(self, mats, art2screen, frame_size, pad=24):
        """Dibuja el personaje. Devuelve (rgba, emisivo, origen x0,y0)."""
        W, H = frame_size
        placed = []
        xs, ys = [], []
        for name, key, m in mats:
            A = art2screen @ m
            scale = math.sqrt(abs(np.linalg.det(A[:2, :2])))
            mips = self.images[key]
            lvl = 0
            for i, (k, _) in enumerate(mips):
                if scale / k >= 0.75:
                    lvl = i
            k, img = mips[lvl]
            A = A @ S(1.0 / k)
            corners = A @ np.array([[0, img.width, img.width, 0],
                                    [0, 0, img.height, img.height], [1, 1, 1, 1]])
            x0, y0 = math.floor(corners[0].min()), math.floor(corners[1].min())
            x1, y1 = math.ceil(corners[0].max()), math.ceil(corners[1].max())
            placed.append((name, img, A, x0, y0, x1, y1))
            xs += [x0, x1]
            ys += [y0, y1]
        cx0, cy0 = max(min(xs) - pad, -W), max(min(ys) - pad, -H)
        cx1, cy1 = min(max(xs) + pad, 2 * W), min(max(ys) + pad, 2 * H)
        cw, ch = max(cx1 - cx0, 1), max(cy1 - cy0, 1)
        canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        emissive = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        for name, img, A, x0, y0, x1, y1 in placed:
            w, h = x1 - x0, y1 - y0
            if w <= 0 or h <= 0 or w > 4 * W or h > 4 * H:
                continue
            local = T(-x0, -y0) @ A
            inv = np.linalg.inv(local)
            part = img.transform((w, h), Image.AFFINE, data=tuple(inv[:2].flatten()),
                                 resample=Image.BICUBIC)
            target = emissive if name in self.EMISSIVE else canvas
            target.alpha_composite(part, (x0 - cx0, y0 - cy0))
            if name in self.EMISSIVE:
                # el hueco del rostro tapa al ojo en el lienzo normal
                canvas.alpha_composite(part, (x0 - cx0, y0 - cy0))
        return canvas, emissive, (cx0, cy0)
