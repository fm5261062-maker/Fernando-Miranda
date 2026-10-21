"""Metricas objetivas de control de calidad de una escena y su render.

    python scripts/qc_metrics.py scenes/test_ocean_walk.json renders/version_01.mp4 \
        --out renders/qc_version_01.json

Mide: duracion de planos frente a las reglas del proyecto, transiciones con
doble exposicion, recorte del IK de piernas (pie que no llega = salto),
recorrido en pantalla de manos y pies (legibilidad de la marcha), repeticion
de patron en la capa de rompiente, sonoridad y pico real del MP4 final.
"""

import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from silent2d import audio  # noqa: E402
from silent2d.render import ROOT, SceneRenderer  # noqa: E402


def walk_metrics(r):
    rig = r.rig
    J = rig.joints
    clamped = total = 0
    hand_px, foot_px = [], []
    for sh in r.shots:
        hx, fy, pp = [], [], []
        for fs in sh["frames"]:
            ch, d, st = fs["ch"], fs["d"], fs["cam"]
            ppa = st["zoom"] * st["f"] * (rig.height_m / d) / rig.units   # px(1080)/arte
            for side in "LR":
                hip_y = J[f"hip.{side}"][1] + ch["root_y"]
                v = np.hypot(ch[f"ankle_z.{side}"], ch[f"ankle_h.{side}"] + hip_y / rig.ppm)
                total += 1
                clamped += v > (rig.len[f"thigh.{side}"] + rig.len[f"shin.{side}"]) * 0.9995
            joints, _, _ = rig.solve(ch, d, st["height"])
            hx.append(joints["hand_tip.L"].tolist())
            fy.append(joints["ankle.L"].tolist())
            pp.append(ppa)
        # recorrido en unidades de arte (relativo al personaje) x escala media
        k = float(np.mean(pp))
        hx, fy = np.array(hx) * k, np.array(fy) * k
        hand_px.append({"shot": sh["id"], "x": round(float(np.ptp(hx[:, 0])), 1),
                        "y": round(float(np.ptp(hx[:, 1])), 1)})
        foot_px.append({"shot": sh["id"], "y": round(float(np.ptp(fy[:, 1])), 1)})
    return {"ik_clamped": f"{clamped}/{total}", "ik_clamped_pct": round(100 * clamped / total, 1),
            "hand_travel_px_1080": hand_px, "ankle_travel_px_1080": foot_px}


def tiling(set_dir, name="04_surf.png"):
    """Correlacion maxima de la capa consigo misma desplazada (1 = patron repetido)."""
    p = os.path.join(set_dir, name)
    if not os.path.exists(p):
        return None
    a = np.asarray(Image.open(p).getchannel("A"), np.float32)
    rows = a[a.sum(1) > 0]
    prof = rows.mean(0) - rows.mean()
    w = len(prof)
    best = 0.0
    for s in range(w // 12, w // 2):
        c = np.corrcoef(prof, np.roll(prof, s))[0, 1]
        best = max(best, c)
    return round(float(best), 3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scene")
    ap.add_argument("video")
    ap.add_argument("--out")
    a = ap.parse_args()
    r = SceneRenderer(a.scene, "final")
    rules = r.project.get("scene_rules", {})
    lo, hi = rules.get("shot_duration_s", [0, 1e9])
    shots = [{"id": s["id"], "duration": s["duration"],
              "transition": s["transition"].get("type", "cut"),
              "within_rule": lo <= s["duration"] <= hi} for s in r.shots]
    dbl = sum(int(round(s["transition_d"] * r.fps)) for s in r.shots[:-1]
              if s["transition"].get("type") == "dissolve")
    res = {"scene": a.scene, "video": a.video, "total_s": round(r.total, 3), "shots": shots,
           "double_exposure_frames": dbl, **walk_metrics(r),
           "surf_layer_self_correlation": tiling(r.set_dir),
           "audio_final": audio.measure(os.path.join(ROOT, a.video))}
    js = json.dumps(res, indent=2, ensure_ascii=False)
    print(js)
    if a.out:
        with open(os.path.join(ROOT, a.out), "w") as f:
            f.write(js)


if __name__ == "__main__":
    main()
