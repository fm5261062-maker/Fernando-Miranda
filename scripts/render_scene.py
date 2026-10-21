"""Renderiza una escena de Las Crónicas de Silent.

    python scripts/render_scene.py scenes/test_ocean_walk.json --quality preview
    python scripts/render_scene.py scenes/test_ocean_walk.json --quality final \
        --output renders/version_01.mp4
    python scripts/render_scene.py scenes/test_ocean_walk.json --still 4.0 --out frame.png
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from silent2d.render import SceneRenderer  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("scene")
    ap.add_argument("--quality", choices=["preview", "final"], default="preview")
    ap.add_argument("--output", help="ruta del MP4 final")
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--still", type=float, help="renderiza solo el frame en ese segundo")
    ap.add_argument("--out", default="still.png")
    a = ap.parse_args()
    r = SceneRenderer(a.scene, a.quality, a.workers)
    rep = r.asset_report()
    for m in rep["missing"]:
        print(f"[FALTA] {m}")
    for p in rep["provisional"]:
        print(f"[PROVISIONAL] {p}")
    for w in r.rule_warnings():
        print(f"[REGLA] {w}")
    if a.still is not None:
        print(r.still(a.still, a.out))
        return
    final, report = r.run(a.output)
    print(json.dumps({k: report[k] for k in ("output", "duration_s", "render_total_s")},
                     ensure_ascii=False))
    print("audio:", report["audio"]["measured_final"])


if __name__ == "__main__":
    main()
