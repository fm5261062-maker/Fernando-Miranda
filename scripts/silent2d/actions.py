"""Acciones del personaje y mezcla en una linea de tiempo.

Cada accion es una funcion f(t_local, params, rig) -> dict de canales.
Los canales que una accion no define conservan el valor neutro, y las
acciones solapadas se mezclan por peso (fundidos de entrada/salida).

Acciones: walk_front, walk_side, idle, head_turn, point, observe.
"""

import math

from .util import clamp, ease, lerp, smoothstep

SIDES = (("L", 1), ("R", -1))


def neutral(rig):
    c = {"root_x": 0.0, "root_y": 0.0, "pelvis_rot": 0.0, "torso_rot": 0.0,
         "head_rot": 0.0, "head_turn": 0.0, "blink": 1.0, "string_swing": 0.0,
         "speed": 0.0}
    for side, s in SIDES:
        c[f"ankle_x.{side}"] = float(rig.joints[f"ankle.{side}"][0])
        c[f"ankle_h.{side}"] = rig.rest_ankle_h
        c[f"ankle_z.{side}"] = 0.0
        c[f"foot_pitch.{side}"] = 0.0
        c[f"arm_flex.{side}"] = 0.0
        c[f"arm_abd.{side}"] = -2.0
        c[f"elbow.{side}"] = 8.0
        c[f"wrist.{side}"] = 0.0
    return c


# ---------------------------------------------------------------------------
# Caminar
# ---------------------------------------------------------------------------
def gait(t, p, rig):
    """Ciclo de marcha comun (frontal y lateral). Devuelve canales + fase."""
    cycle = p.get("cycle", 1.1)             # s por ciclo (2 pasos)
    speed = p.get("speed", 0.82)            # m/s
    stance = p.get("stance", 0.62)          # fraccion de apoyo
    lift = p.get("lift", 0.10)              # m de despeje del pie
    ppm = rig.ppm
    zr = speed * stance * cycle / 2         # recorrido relativo del pie en apoyo
    ph = (t / cycle + p.get("phase", 0.0)) % 1.0
    c = {"speed": speed, "_phase": ph, "_cycle": cycle}
    w2 = 2 * math.pi * ph

    # cadera: baja en el contacto y sube en el apoyo medio
    c["root_y"] = (p.get("drop", 0.034) + p.get("bob", 0.016) * math.cos(2 * w2)) * ppm
    c["root_x"] = p.get("sway", 6.0) * math.sin(w2 - 0.35)
    c["pelvis_rot"] = -p.get("hip_tilt", 2.2) * math.sin(w2 - 0.2)
    c["torso_rot"] = p.get("shoulder_tilt", 3.2) * math.sin(w2 - 0.3)
    c["head_rot"] = -1.1 * math.sin(w2 - 0.45)
    c["string_swing"] = 4.0 * math.sin(2 * w2 - 1.2) + 2.0 * math.sin(w2 - 0.9)

    for side, s in SIDES:
        q = (ph - (0.0 if side == "L" else 0.5)) % 1.0
        c[f"_q.{side}"] = q
        rest_x = float(rig.joints[f"ankle.{side}"][0])
        if q < stance:                                   # apoyo
            u = q / stance
            z = zr * (1 - 2 * u)
            h = rig.rest_ankle_h
            pitch = lerp(-8.0, 22.0, u ** 2.2)
            x = rest_x
        else:                                            # balanceo
            u = (q - stance) / (1 - stance)
            e = 0.5 - 0.5 * math.cos(math.pi * u)
            z = -zr + 2 * zr * e
            h = rig.rest_ankle_h + lift * math.sin(math.pi * u) ** 1.3
            pitch = lerp(22.0, -8.0, smoothstep(u))
            x = rest_x - s * 5.0 * math.sin(math.pi * u)
        c[f"ankle_x.{side}"] = x
        c[f"ankle_z.{side}"] = z
        c[f"ankle_h.{side}"] = h
        c[f"foot_pitch.{side}"] = pitch

    amp = p.get("arm_swing", 14.0)
    elbow_fwd = p.get("elbow_forward", 10.0)     # flexion extra del codo al adelantar
    inward = p.get("hand_inward", 0.0)           # la mano cruza hacia la linea media
    for side, s in SIDES:
        sw = amp * (-math.cos(w2 - 0.25) if side == "L" else math.cos(w2 - 0.25))
        fwd = max(sw, 0) / amp
        c[f"arm_flex.{side}"] = sw
        c[f"elbow.{side}"] = 10.0 + elbow_fwd * fwd
        c[f"arm_abd.{side}"] = 3.0 - inward * fwd
        c[f"wrist.{side}"] = 4.0 * fwd
    return c


def walk_front(t, p, rig):
    return gait(t, p, rig)


def walk_side(t, p, rig):
    """Marcha lateral: mismos canales; requiere un rig con "view": "side"."""
    c = gait(t, p, rig)
    c["_view"] = "side"
    return c


# ---------------------------------------------------------------------------
# Quieto, girar cabeza, observar, senalar
# ---------------------------------------------------------------------------
def idle(t, p, rig):
    br = 2 * math.pi * t / p.get("breath", 4.2)
    sh = 2 * math.pi * t / p.get("shift", 7.0)
    c = {"root_y": (0.004 * math.sin(br)) * rig.ppm + 4.0 * (0.5 - 0.5 * math.cos(sh)),
         "root_x": 4.0 * math.sin(sh), "pelvis_rot": -0.9 * math.sin(sh),
         "torso_rot": 0.5 * math.sin(sh) + 0.25 * math.sin(br),
         "head_rot": -0.3 * math.sin(sh), "string_swing": 0.8 * math.sin(sh + 1)}
    for side, s in SIDES:
        c[f"arm_flex.{side}"] = 1.5 * math.sin(br + (0 if side == "L" else 1.3))
        c[f"elbow.{side}"] = 9.0 + 1.0 * math.sin(br)
    return c


def head_turn(t, p, rig):
    dur = p.get("duration", 0.8)
    u = ease(p.get("ease", "in_out_sine"), t / dur)
    turn = lerp(p.get("from", 0.0), p.get("to", 0.6), u)
    return {"head_turn": turn, "head_rot": 2.5 * turn, "torso_rot": 0.6 * turn}


def observe(t, p, rig):
    span = p.get("span", 0.45)
    period = p.get("period", 6.0)
    ramp = smoothstep(t / 1.2)
    turn = span * math.sin(2 * math.pi * t / period) * ramp
    return {"head_turn": turn, "head_rot": p.get("tilt", 4.0) * ramp + 2.0 * turn,
            "torso_rot": 0.8 * turn, "root_y": 3.0 * ramp}


def point(t, p, rig):
    side = p.get("side", "R")
    s = 1 if side == "L" else -1
    u = ease("in_out_cubic", t / p.get("raise", 0.7))
    c = {f"arm_abd.{side}": lerp(-2, p.get("abduction", 62), u),
         f"arm_flex.{side}": lerp(0, p.get("flex", 28), u),
         f"elbow.{side}": lerp(8, 6, u), f"wrist.{side}": lerp(0, -6, u),
         "torso_rot": -2.0 * s * u, "head_turn": p.get("look", 0.55) * s * u,
         "head_rot": 1.5 * s * u, "_variant." + f"hand.{side}": "point"}
    return c


ACTIONS = {"walk_front": walk_front, "walk_side": walk_side, "idle": idle,
           "head_turn": head_turn, "observe": observe, "point": point}


# ---------------------------------------------------------------------------
# Linea de tiempo con mezcla
# ---------------------------------------------------------------------------
class Timeline:
    def __init__(self, actions, shot_duration, rig, blinks=()):
        self.rig = rig
        self.items = []
        for a in actions:
            if a["type"] not in ACTIONS:
                raise ValueError(f"Accion desconocida: {a['type']}")
            self.items.append({
                "fn": ACTIONS[a["type"]], "type": a["type"],
                "start": float(a.get("start", 0.0)),
                "end": float(a["end"]) if a.get("end") is not None else shot_duration + 99,
                "blend": float(a.get("blend", 0.35)),
                "params": a.get("params", {}),
                "layer": a.get("layer", "base"),
            })
        self.blinks = list(blinks)

    def weight(self, it, t):
        if t < it["start"] or t > it["end"]:
            return 0.0
        b = max(it["blend"], 1e-3)
        w_in = 1.0 if it["start"] <= 0 else smoothstep((t - it["start"]) / b)
        w_out = smoothstep((it["end"] - t) / b)
        return w_in * w_out

    def evaluate(self, t):
        base = neutral(self.rig)
        out = dict(base)
        meta = {}
        # capa base (cuerpo) y capa "overlay" (p. ej. cabeza o brazo encima)
        for layer in ("base", "overlay"):
            acc, wsum = {}, {}
            for it in self.items:
                if it["layer"] != layer:
                    continue
                w = self.weight(it, t)
                if w <= 0:
                    continue
                vals = it["fn"](t - it["start"], it["params"], self.rig)
                for k, v in vals.items():
                    if k.startswith("_"):
                        meta[k] = v
                        meta[k + "@w"] = max(meta.get(k + "@w", 0), w)
                        continue
                    acc[k] = acc.get(k, 0.0) + w * v
                    wsum[k] = wsum.get(k, 0.0) + w
            for k, v in acc.items():
                ws = wsum[k]
                if layer == "base":
                    out[k] = (v + max(0.0, 1 - ws) * base[k]) / max(ws, 1.0)
                else:  # overlay: sustituye esos canales sobre la base
                    out[k] = lerp(out[k], v / max(ws, 1e-6), min(ws, 1.0))
        for tb in self.blinks:
            dt = t - tb
            if -0.06 <= dt <= 0.12:
                out["blink"] = min(out["blink"], 0.08 + 0.92 * clamp(abs(dt) / 0.09))
        return out, meta
