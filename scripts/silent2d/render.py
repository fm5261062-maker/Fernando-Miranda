"""Orquestacion: escena JSON -> planos MP4 -> escena montada + audio mezclado."""

import json
import math
import multiprocessing as mp
import os
import shutil
import subprocess
import time

import numpy as np
from PIL import Image

from . import audio
from .actions import Timeline
from .camera import Camera
from .character import Rig
from .secondary import apply_secondary, wind_curve
from .stage import (Stage, char_screen_matrix, ground_effects, light_character,
                    paste_clipped, post, stamp)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
XFADE = {"dissolve": "fade", "fade_black": "fadeblack", "fade_white": "fadewhite",
         "wipe": "wipeleft", "slide": "slideleft", "circle": "circleopen",
         "smooth": "smoothleft"}
STAMP = "PRUEBA TECNICA - ARTE PROVISIONAL (ver assets/MISSING_ASSETS.md)"


def rel(p):
    return os.path.join(ROOT, p) if not os.path.isabs(p) else p


def load_json(p):
    with open(rel(p)) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Planificacion (proceso principal): estados por frame de cada plano
# ---------------------------------------------------------------------------
def plan_scene(scene, project, rig):
    fps = project["fps"]
    shots = []
    offset = 0.0
    prev = None
    for k, sh in enumerate(scene["shots"]):
        dur = float(sh["duration"])
        n = int(round(dur * fps))
        tr = sh.get("transition", {"type": "cut"})
        trd = 0.0 if tr.get("type", "cut") == "cut" else float(tr.get("duration", 0.5))
        cam = Camera(sh.get("camera", {}), project["camera"])
        cs = sh.get("character", {})
        z = float(cs.get("z", 10.0))
        X = float(cs.get("x", 0.0))
        actions = [dict(a, params=dict(a.get("params", {}))) for a in sh.get("actions", [])]
        if cs.get("continue") and prev is not None:
            # continuidad: arranca donde estaba el plano anterior al empezar la
            # transicion (mitad del fundido si lo hay)
            t_from = prev["duration"] - prev["transition_d"]
            i = min(int(math.floor(t_from * fps + 1e-6)), len(prev["frames"]) - 1)
            pf = prev["frames"][i]
            delta = t_from - pf["t"]          # avanza lo que falte hasta t_from exacto
            z = pf["z"] - pf["ch"]["speed"] * delta * cs.get("toward_camera", 1)
            X = pf["X"]
            for a in actions:
                if a["params"].get("phase") == "continue":
                    cyc = pf["meta"].get("_cycle", 1.1)
                    a["params"]["phase"] = (pf["meta"].get("_phase", 0.0) + delta / cyc) % 1.0
        tl = Timeline(actions, dur, rig, sh.get("eyes", {}).get("blinks", []))
        frames = []
        dt = 1.0 / fps
        for i in range(n):
            t = i * dt
            ch, meta = tl.evaluate(t)
            if i > 0:
                z -= ch["speed"] * dt * cs.get("toward_camera", 1)
                X += cs.get("drift_x", 0.0) * dt
            st = cam.state(t, z)
            d = z - st["z"]
            variants = {k[len("_variant."):]: v for k, v in meta.items()
                        if k.startswith("_variant.") and not k.endswith("@w")
                        and meta.get(k + "@w", 0) > 0.5}
            frames.append({"i": i, "t": t, "tg": offset + t, "cam": st, "ch": ch,
                           "meta": meta, "z": z, "X": X, "d": d, "variants": variants})
        apply_secondary(frames, fps, rig, wind_curve(scene.get("wind") or sh.get("wind")),
                        t_offset=offset)
        shot = {"id": sh.get("id", f"sh{k + 1:02d}"), "index": k, "duration": dur,
                "n": n, "offset": offset, "transition": tr, "transition_d": trd,
                "frames": frames, "spec": sh}
        shots.append(shot)
        prev = shot
        offset += dur - trd
    total = sum(s["duration"] for s in shots) - sum(s["transition_d"] for s in shots[:-1])
    return shots, total


def footstep_events(shots, fps, ref_w=1920):
    """Contactos de pie detectados en la pose -> eventos de sonido."""
    events = []
    for k, sh in enumerate(shots):
        lo = sh["offset"] + (shots[k - 1]["transition_d"] / 2 if k > 0 else -1)
        hi = (shots[k + 1]["offset"] + sh["transition_d"] / 2) if k + 1 < len(shots) else 1e9
        fr = sh["frames"]
        for side in ("L", "R"):
            key = f"_q.{side}"
            for a, b in zip(fr, fr[1:]):
                qa, qb = a["meta"].get(key), b["meta"].get(key)
                if qa is None or qb is None or qb >= qa - 0.5:
                    continue
                cyc = b["meta"].get("_cycle", 1.1)
                tg = b["tg"] - qb * cyc
                if not (lo <= tg < hi):
                    continue
                w = b["meta"].get(key + "@w", 1.0)
                fx, _ = Camera.project_ground(b["cam"], b["X"], b["d"])
                events.append({"t": tg, "side": side, "shot": sh["id"],
                               "gain": w * max(0.2, min(1.5, (5.0 / b["d"]) ** 0.9)),
                               "pan": 0.6 * (fx - ref_w / 2) / (ref_w / 2)})
    return sorted(events, key=lambda e: e["t"])


# ---------------------------------------------------------------------------
# Render de frames (procesos trabajadores)
# ---------------------------------------------------------------------------
_W = {}


def _init_worker(char_dir, set_dir, rs, size, stamp_on):
    _W["rig"] = Rig(char_dir, rs)
    _W["stage"] = Stage(set_dir, rs)
    _W["rs"], _W["size"], _W["stamp"] = rs, size, stamp_on


def render_frame(fs):
    rig, stage, rs, (W, H) = _W["rig"], _W["stage"], _W["rs"], _W["size"]
    st, t, d = fs["cam"], fs["tg"], fs["d"]
    frame = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    far = [L for L in stage.layers if L.get("ground") or L["D"] == "inf" or L["D"] > d]
    near = [L for L in stage.layers if L not in far]
    for L in far:
        stage.draw_layer(frame, L, st, t)
    parts = stage.spec.get("particles", [])
    arr = np.asarray(frame).astype(np.float32)
    for j, P in enumerate(parts):
        if P["distance"] > d:
            stage.draw_particles(arr, P, st, t, seed=17 + j)
    frame = Image.fromarray(arr.astype(np.uint8), "RGBA")
    # personaje
    joints, width, extra = rig.solve(fs["ch"], d, st["height"])
    mats = rig.matrices(joints, width, extra, fs.get("variants"))
    A, ppa, feet_y = char_screen_matrix(st, fs["X"], d, rig, rs)
    canvas, emissive, origin = rig.draw(mats, A, (W, H))
    ground_effects(frame, canvas, origin, feet_y, stage.light, rs)
    lit = light_character(canvas, emissive, stage.light, d, ppa,
                          stage.grade.get("haze"))
    paste_clipped(frame, lit, *origin)
    for L in near:
        stage.draw_layer(frame, L, st, t)
    if any(P["distance"] <= d for P in parts):
        arr = np.asarray(frame).astype(np.float32)
        for j, P in enumerate(parts):
            if P["distance"] <= d:
                stage.draw_particles(arr, P, st, t, seed=17 + j)
        frame = Image.fromarray(arr.astype(np.uint8), "RGBA")
    out = post(frame, stage.grade, t, int(round(t * 24)), rs)
    if _W["stamp"]:
        stamp(out, STAMP, rs)
    return out.tobytes()


# ---------------------------------------------------------------------------
class SceneRenderer:
    def __init__(self, scene_path, quality="preview", workers=0, out_root=None):
        self.project = load_json("project/project.json")
        self.scene = load_json(scene_path)
        self.quality = quality
        q = self.project[quality]
        self.size = tuple(q["resolution"])
        self.rs = self.size[0] / 1920.0
        self.q = q
        self.fps = self.project["fps"]
        self.char_dir = rel(os.path.join("assets/character", self.scene["character"],
                                         self.scene.get("character_view", "front")))
        self.set_dir = rel(os.path.join("assets/backgrounds", self.scene["background"]))
        self.rig = Rig(self.char_dir, self.rs)
        self.stage = Stage(self.set_dir, self.rs)
        self.workers = workers or max(1, (os.cpu_count() or 2))
        self.out_dir = rel(out_root or os.path.join("renders", self.scene["id"], quality))
        os.makedirs(os.path.join(self.out_dir, "shots"), exist_ok=True)
        self.shots, self.total = plan_scene(self.scene, self.project, self.rig)
        self.placeholder = self.rig.placeholder or self.stage.placeholder

    # -------------------------- comprobacion de recursos -------------------
    def rule_warnings(self):
        lo, hi = self.project.get("scene_rules", {}).get("shot_duration_s", [0, 1e9])
        return [f"Plano {s['id']} dura {s['duration']} s (regla: {lo}-{hi} s)"
                for s in self.shots if not lo <= s["duration"] <= hi]

    def asset_report(self):
        miss, prov = [], []
        if self.rig.placeholder:
            prov.append(f"Personaje: capas provisionales en {os.path.relpath(self.char_dir, ROOT)}")
        if self.stage.placeholder:
            prov.append(f"Fondo: capas provisionales en {os.path.relpath(self.set_dir, ROOT)}")
        miss += self.rig.missing
        for n in self.scene.get("narration", []):
            if not os.path.exists(rel(n["file"])):
                miss.append(f"{n['file']} (narracion: \"{n.get('text', '')[:60]}\")")
        mus = self.scene.get("music")
        if mus and not os.path.exists(rel(mus["file"])):
            miss.append(f"{mus['file']} (musica)")
            if mus.get("placeholder_if_missing"):
                prov.append("Musica: colchon sintetizado provisional")
        amb = self.scene.get("ambience", {})
        if amb.get("file") and not os.path.exists(rel(amb["file"])):
            miss.append(f"{amb['file']} (ambiente)")
        if not amb.get("file"):
            prov.append("Ambiente: mar sintetizado provisional")
        fs = self.scene.get("footsteps", {})
        if not fs.get("samples"):
            prov.append("Pasos: foley sintetizado provisional")
        return {"missing": miss, "provisional": prov}

    # -------------------------- video ------------------------------------
    def render_shot(self, shot, pool):
        W, H = self.size
        path = os.path.join(self.out_dir, "shots", f"{shot['index'] + 1:02d}_{shot['id']}.mp4")
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
               "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(self.fps), "-i", "-",
               "-c:v", "libx264", "-preset", self.q["preset"], "-crf", str(self.q["shot_crf"]),
               "-pix_fmt", "yuv420p", path]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        for buf in pool.imap(render_frame, shot["frames"], chunksize=2):
            p.stdin.write(buf)
        p.stdin.close()
        if p.wait() != 0:
            raise RuntimeError(f"FFmpeg fallo codificando {path}")
        return path

    def assemble_video(self, paths, out):
        inputs, filt = [], []
        for p in paths:
            inputs += ["-i", p]
        cur = "[0:v]"
        acc = self.shots[0]["duration"]
        for k in range(1, len(paths)):
            tr = self.shots[k - 1]["transition"]
            typ = tr.get("type", "cut")
            if typ == "cut":
                filt.append(f"{cur}[{k}:v]concat=n=2:v=1:a=0[v{k}]")
                acc += self.shots[k]["duration"]
            else:
                d = self.shots[k - 1]["transition_d"]
                filt.append(f"{cur}[{k}:v]xfade=transition={XFADE.get(typ, typ)}:"
                            f"duration={d:.3f}:offset={acc - d:.3f}[v{k}]")
                acc += self.shots[k]["duration"] - d
            cur = f"[v{k}]"
        fi, fo = self.scene.get("fade_in", 0.0), self.scene.get("fade_out", 0.0)
        tail = []
        if fi:
            tail.append(f"fade=t=in:st=0:d={fi}")
        if fo:
            tail.append(f"fade=t=out:st={self.total - fo:.3f}:d={fo}")
        tail.append("format=yuv420p")
        filt.append(f"{cur}{','.join(tail)}[vout]")
        audio.ffmpeg(inputs + ["-filter_complex", ";".join(filt), "-map", "[vout]",
                               "-c:v", "libx264", "-preset", self.q["preset"],
                               "-crf", str(self.q["crf"]), "-r", str(self.fps), out])

    # -------------------------- audio ------------------------------------
    def build_audio(self, out_wav):
        a_dir = os.path.join(self.out_dir, "audio")
        os.makedirs(a_dir, exist_ok=True)
        levels = self.project["audio"]["levels_db"]
        stems = []
        events = footstep_events(self.shots, self.fps)
        fs = self.scene.get("footsteps", {})
        if fs.get("enabled", True):
            p = os.path.join(a_dir, "footsteps.wav")
            audio.write_wav(p, audio.footsteps(events, self.total,
                                               surface=fs.get("surface", "sand")))
            stems.append((p, levels["sfx"] + fs.get("volume_db", 0), "sfx"))
        amb = self.scene.get("ambience", {})
        if amb:
            if amb.get("file") and os.path.exists(rel(amb["file"])):
                p = rel(amb["file"])
            elif amb.get("type") == "cliff":
                p = os.path.join(a_dir, "ambience.wav")
                audio.write_wav(p, audio.cliff(self.total, wind_curve(self.scene.get("wind"))))
            else:
                stage = self.stage
                wash_name = stage.spec.get("audio", {}).get("wash_layer", "shore_wash")
                surf = stage.spec.get("audio", {}).get("surge_layer", "surf")
                period = next((L["anim"]["period_s"] for L in stage.layers
                               if L["name"] == surf), 7.5)
                phase = next((L["anim"].get("phase", 0) for L in stage.layers
                              if L["name"] == surf), 0.0)
                # pico de la rompiente: u = 0.3 del ciclo de oleaje
                crashes = [(n - phase + 0.3) * period for n in range(-1, 20)]
                crashes = [c for c in crashes if -3 < c < self.total]
                p = os.path.join(a_dir, "ambience.wav")
                audio.write_wav(p, audio.ocean(self.total,
                                               lambda t: stage.surge_value(wash_name, t),
                                               crashes))
            stems.append((p, levels["ambience"] + amb.get("volume_db", 0), "ambience"))
        mus = self.scene.get("music")
        if mus:
            if os.path.exists(rel(mus["file"])):
                stems.append((rel(mus["file"]), levels["music"] + mus.get("volume_db", 0),
                              "music"))
            elif mus.get("placeholder_if_missing"):
                p = os.path.join(a_dir, "music_placeholder.wav")
                audio.write_wav(p, audio.pad_music(self.total))
                stems.append((p, levels["music"] + mus.get("volume_db", 0), "music"))
        narr = [(rel(n["file"]), n["start"], levels["narration"] + n.get("volume_db", 0))
                for n in self.scene.get("narration", []) if os.path.exists(rel(n["file"]))]
        target = dict(self.project["audio"])
        if "loudness_lufs" in self.scene:      # p. ej. dejar hueco para la voz futura
            target["loudness_lufs"] = self.scene["loudness_lufs"]
        stats = audio.mix(stems, narr, self.total, out_wav, target)
        return stats, events

    # -------------------------- todo -------------------------------------
    def run(self, output=None, keep_frames=False):
        t0 = time.time()
        report = {"scene": self.scene["id"], "quality": self.quality,
                  "resolution": self.size, "fps": self.fps,
                  "duration_s": round(self.total, 3), "assets": self.asset_report(),
                  "rule_warnings": self.rule_warnings(),
                  "shots": []}
        ctx = mp.get_context("fork")
        paths = []
        with ctx.Pool(self.workers, initializer=_init_worker,
                      initargs=(self.char_dir, self.set_dir, self.rs, self.size,
                                self.placeholder)) as pool:
            for sh in self.shots:
                ts = time.time()
                paths.append(self.render_shot(sh, pool))
                report["shots"].append({"id": sh["id"], "duration": sh["duration"],
                                        "frames": sh["n"], "file": os.path.relpath(paths[-1], ROOT),
                                        "render_s": round(time.time() - ts, 1),
                                        "transition": sh["transition"]})
                print(f"[plano] {sh['id']}: {sh['n']} frames en {time.time() - ts:.1f}s")
        video = os.path.join(self.out_dir, "video_only.mp4")
        self.assemble_video(paths, video)
        wav = os.path.join(self.out_dir, "mix.wav")
        stats, events = self.build_audio(wav)
        final = rel(output) if output else os.path.join(self.out_dir,
                                                         f"{self.scene['id']}_{self.quality}.mp4")
        os.makedirs(os.path.dirname(final), exist_ok=True)
        audio.ffmpeg(["-i", video, "-i", wav, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                      "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest",
                      "-movflags", "+faststart", final])
        report["audio"] = {"target_lufs": self.scene.get("loudness_lufs",
                                                         self.project["audio"]["loudness_lufs"]),
                           "stems": sorted(os.listdir(os.path.join(self.out_dir, "audio"))),
                           "measured_final": audio.measure(final),
                           "footsteps": [{"t": round(e["t"], 3), "side": e["side"],
                                          "shot": e["shot"]} for e in events]}
        report["output"] = os.path.relpath(final, ROOT)
        report["render_total_s"] = round(time.time() - t0, 1)
        with open(os.path.join(self.out_dir, "render_report.json"), "w") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        return final, report

    def still(self, tg, out_png):
        """Renderiza un frame suelto (tiempo global de la escena)."""
        for sh in reversed(self.shots):
            if tg >= sh["offset"]:
                i = min(int(round((tg - sh["offset"]) * self.fps)), sh["n"] - 1)
                _init_worker(self.char_dir, self.set_dir, self.rs, self.size, self.placeholder)
                buf = render_frame(sh["frames"][i])
                Image.frombytes("RGB", self.size, buf).save(out_png)
                return out_png
        raise ValueError(tg)
