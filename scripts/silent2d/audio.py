"""Audio: pistas provisionales sintetizadas y mezcla final con FFmpeg.

Las pistas sintetizadas (pasos en arena, ambiente de mar, colchon musical)
son PROVISIONALES: sirven para comprobar sincronia y niveles. La mezcla
real usa los WAV de audio/narration, audio/music y audio/sfx cuando existen.
"""

import json
import re
import subprocess
import wave

import numpy as np

SR = 48000


def write_wav(path, x):
    x = np.clip(x, -1, 1)
    if x.ndim == 1:
        x = np.stack([x, x], axis=1)
    data = (x * 32767).astype("<i2").tobytes()
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data)


def band(x, lo=None, hi=None, order=2):
    """Filtro paso-banda en frecuencia (respuesta tipo Butterworth)."""
    n = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    g = np.ones_like(f)
    if hi:
        g /= np.sqrt(1 + (f / hi) ** (2 * order))
    if lo:
        g /= np.sqrt(1 + (lo / np.maximum(f, 1e-3)) ** (2 * order))
    return np.fft.irfft(X * g, n)


def norm(x, peak=0.9):
    m = np.max(np.abs(x)) or 1.0
    return x / m * peak


# ---------------------------------------------------------------------------
def footsteps(events, total, seed=3, surface="sand"):
    """Pasos: crujido filtrado + golpe grave del talon (arena o roca)."""
    rock = surface == "rock"
    n = int(total * SR) + SR
    out = np.zeros((n, 2))
    rng = np.random.default_rng(seed)
    L = int(0.4 * SR)
    tt = np.arange(L) / SR
    for ev in events:
        g = ev["gain"] * (0.85 + 0.3 * rng.random())
        noise = band(rng.standard_normal(L), (900 if rock else 350) + 150 * rng.random(),
                     6500 if rock else 3200, order=2)
        env = (1 - np.exp(-tt / 0.002)) * np.exp(-tt / ((0.025 if rock else 0.05) +
                                                       0.02 * rng.random()))
        grains = np.zeros(L)
        idx = rng.integers(0, int(0.09 * SR), 40)
        grains[idx] = rng.standard_normal(40)
        grains = band(grains, 1500, 6000) * np.exp(-tt / 0.06)
        thump = np.sin(2 * np.pi * ((95 if rock else 70) + 20 * rng.random()) * tt) * \
            np.exp(-tt / (0.022 if rock else 0.035))
        s = norm(noise * env, 0.6) + norm(grains, 0.25) + 0.45 * thump
        i0 = int(ev["t"] * SR)
        if i0 >= n:
            continue
        seg = s[: n - i0] * g
        pan = max(-1, min(1, ev.get("pan", 0.0)))
        out[i0:i0 + len(seg), 0] += seg * np.sqrt((1 - pan) / 2) * 1.414
        out[i0:i0 + len(seg), 1] += seg * np.sqrt((1 + pan) / 2) * 1.414
    return out[: int(total * SR)]


def ocean(total, wash_fn, crash_times, seed=11):
    """Mar: rumor grave + espuma ligada a la lamina de orilla + rompientes."""
    n = int(total * SR)
    rng = np.random.default_rng(seed)
    t = np.arange(n) / SR
    wash = np.array([wash_fn(x) for x in np.linspace(0, total, int(total * 50) + 1)])
    wash = np.interp(t, np.linspace(0, total, len(wash)), wash)
    ch = []
    for c in range(2):
        rumble = band(rng.standard_normal(n), 30, 380, order=2)
        foam = band(rng.standard_normal(n), 500, 7000, order=1)
        crash = np.zeros(n)
        for tc in crash_times:
            k = (t - tc)
            env = np.where(k > 0, (1 - np.exp(-k / 0.18)) * np.exp(-k / 1.9), 0)
            crash += env
        crash_n = band(rng.standard_normal(n), 120, 4500, order=1) * crash
        sig = (norm(rumble, 0.5) * (0.75 + 0.25 * wash) +
               norm(foam, 0.18) * (0.25 + 0.9 * wash) + norm(crash_n, 0.45))
        ch.append(sig)
    return np.stack(ch, axis=1)


def cliff(total, wind_fn, seed=17):
    """Acantilado nocturno: viento (rafagas sincronizadas con la ropa), mar lejano
    y cascada distante."""
    n = int(total * SR)
    rng = np.random.default_rng(seed)
    t = np.arange(n) / SR
    w = np.array([wind_fn(x) for x in np.linspace(0, total, int(total * 50) + 1)])
    w = np.interp(t, np.linspace(0, total, len(w)), w)
    ch = []
    for c in range(2):
        low = band(rng.standard_normal(n), 60, 500, order=2)
        hiss = band(rng.standard_normal(n), 700, 4000, order=2)
        whistle = band(rng.standard_normal(n), 1100 + 300 * c, 1500 + 300 * c, order=4)
        sea = band(rng.standard_normal(n), 25, 220, order=2)
        falls = band(rng.standard_normal(n), 300, 2500, order=1)
        swell = 0.7 + 0.3 * np.sin(2 * np.pi * t / 9.0 + c)
        sig = (norm(low, 0.45) * (0.4 + 0.8 * w) + norm(hiss, 0.25) * (0.15 + 0.9 * w ** 1.5) +
               norm(whistle, 0.06) * np.clip(w - 0.5, 0, 1) +
               norm(sea, 0.35) * swell + norm(falls, 0.05))
        ch.append(sig)
    return np.stack(ch, axis=1)


def pad_music(total, seed=5):
    """Colchon musical PROVISIONAL (acordes lentos) para probar el ducking."""
    n = int(total * SR)
    t = np.arange(n) / SR
    chords = [(0.0, [73.42, 110.0, 174.61, 261.63, 329.63]),
              (total / 2, [58.27, 87.31, 146.83, 220.0, 293.66])]
    out = np.zeros((n, 2))
    for i, (t0, notes) in enumerate(chords):
        t1 = chords[i + 1][0] if i + 1 < len(chords) else total
        env = np.clip((t - t0) / 1.5, 0, 1) * np.clip((t1 + 1.5 - t) / 1.5, 0, 1)
        for j, f in enumerate(notes):
            for c in range(2):
                det = 1 + (0.0015 if c else -0.0015) * (j + 1)
                vib = 1 + 0.002 * np.sin(2 * np.pi * (0.2 + 0.05 * j) * t)
                out[:, c] += np.sin(2 * np.pi * f * det * vib * t + j) * env / (j + 1.5)
    fade = np.clip(t / 2.0, 0, 1) * np.clip((total - t) / 2.0, 0, 1)
    out *= fade[:, None]
    out = np.stack([band(out[:, 0], 40, 2500), band(out[:, 1], 40, 2500)], axis=1)
    return norm(out, 0.7)


# ---------------------------------------------------------------------------
def ffmpeg(args, capture=False):
    cmd = ["ffmpeg", "-hide_banner", "-y"] + args
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if r.returncode != 0:
        raise RuntimeError("FFmpeg fallo:\n" + " ".join(cmd) + "\n" + r.stderr[-3000:])
    return r.stderr if capture else None


def mix(stems, narration, total, out_wav, target):
    """Mezcla buses con FFmpeg y normaliza a LUFS objetivo (2 pasadas).

    stems: [(ruta, volumen_db, bus)] con bus en {"music","ambience","sfx"}
    narration: [(ruta, inicio_s, volumen_db)]
    """
    inputs, filt = [], []
    for i, (p, vol, bus) in enumerate(stems):
        inputs += ["-i", p]
        filt.append(f"[{i}:a]aresample={SR},volume={vol}dB,apad,atrim=0:{total:.3f}[s{i}]")
    base = len(stems)
    for j, (p, start, vol) in enumerate(narration):
        inputs += ["-i", p]
        ms = int(start * 1000)
        filt.append(f"[{base + j}:a]aresample={SR},aformat=channel_layouts=stereo,"
                    f"volume={vol}dB,adelay={ms}|{ms},apad,atrim=0:{total:.3f}[n{j}]")
    bed = [f"[s{i}]" for i, (_, _, b) in enumerate(stems) if b in ("music", "ambience")]
    sfx = [f"[s{i}]" for i, (_, _, b) in enumerate(stems) if b == "sfx"]
    parts = []
    if bed:
        filt.append("".join(bed) + f"amix=inputs={len(bed)}:normalize=0[bed]")
    if narration:
        nn = "".join(f"[n{j}]" for j in range(len(narration)))
        filt.append(nn + f"amix=inputs={len(narration)}:normalize=0,asplit=2[narr][key]")
        if bed:
            # ducking: musica y ambiente bajan cuando habla el narrador
            filt.append("[bed][key]sidechaincompress=threshold=0.02:ratio=8:attack=30:"
                        "release=500:makeup=1[bedd]")
            parts.append("[bedd]")
        parts.append("[narr]")
    elif bed:
        parts.append("[bed]")
    parts += sfx
    filt.append("".join(parts) + f"amix=inputs={len(parts)}:normalize=0[pre]")
    graph = ";".join(filt)
    I, TP, LRA = target["loudness_lufs"], target["true_peak"], target.get("lra", 11)
    # pasada 1: medir
    err = ffmpeg(inputs + ["-filter_complex", graph + f";[pre]loudnorm=I={I}:TP={TP}:"
                           f"LRA={LRA}:print_format=json[o]", "-map", "[o]", "-f", "null",
                           "-"], capture=True)
    m = json.loads(re.findall(r"\{[^{}]*\}", err)[-1])
    # pasada 2: aplicar normalizacion lineal con lo medido
    ln = (f"loudnorm=I={I}:TP={TP}:LRA={LRA}:measured_I={m['input_i']}:"
          f"measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:"
          f"measured_thresh={m['input_thresh']}:offset={m['target_offset']}:"
          f"linear=true:print_format=json")
    # limitador sobremuestreado x4 (aproxima pico real) DESPUES de normalizar,
    # con margen para el rebasamiento que introduce el codec AAC
    lim = 10 ** ((TP - target.get("tp_margin", 1.0)) / 20)
    post = (f"aresample={SR * 4},alimiter=limit={lim:.4f}:attack=1:release=50:"
            f"level=false,aresample={SR}")
    err = ffmpeg(inputs + ["-filter_complex", graph + f";[pre]{ln},{post}[o]",
                           "-map", "[o]", "-ar", str(SR), "-c:a", "pcm_s16le", out_wav],
                 capture=True)
    m2 = json.loads(re.findall(r"\{[^{}]*\}", err)[-1])
    return {"input": m, "output": m2}


def measure(path):
    """Mide loudness integrada y pico real de un archivo (EBU R128)."""
    err = ffmpeg(["-i", path, "-af", "ebur128=peak=true", "-f", "null", "-"], capture=True)
    I = re.findall(r"I:\s+(-?[\d.]+) LUFS", err)
    P = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", err)
    return {"integrated_lufs": float(I[-1]) if I else None,
            "true_peak_dbfs": float(P[-1]) if P else None}
