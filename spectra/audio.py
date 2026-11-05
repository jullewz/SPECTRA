"""Procedural audio: every sound effect and both music loops are synthesized from math.

Sounds are rendered into in-memory WAV files, so pygame converts them to whatever
format the sound card wants. Music takes a few seconds to compose, so it is built in a
background thread and cached on disk for the next launch.

created by jullewz
"""

import io
import math
import os
import random
import threading
import time
import wave

import pygame

from .config import VERSION

RATE = 22050
TAU = math.tau


def _wav_bytes(samples):
    """Float samples (-1..1) → an in-memory 16-bit mono WAV file."""
    frames = bytearray()
    for v in samples:
        if v > 1.0:
            v = 1.0
        elif v < -1.0:
            v = -1.0
        frames += int(v * 32767).to_bytes(2, "little", signed=True)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(bytes(frames))
    return buf.getvalue()


def tone(dur, f0, f1=None, shape="sine", vol=0.4, attack=0.003, curve=2.0, noise=0.0, cutoff=None, rng=None):
    """One synthesized note with a pitch sweep from f0 to f1 and a decaying envelope."""
    rng = rng or random.Random(int(f0 * 1000 + dur * 77))
    n = max(1, int(dur * RATE))
    f1 = f0 if f1 is None else f1
    out = [0.0] * n
    phase = 0.0
    lp = 0.0
    a = 1 - math.exp(-TAU * cutoff / RATE) if cutoff else 1.0
    att = max(1.0, attack * RATE)
    ratio = f1 / f0 if f0 > 0 else 1.0
    for i in range(n):
        t = i / n
        f = f0 * ratio ** t
        phase += f / RATE
        p = phase - int(phase)
        if shape == "sine":
            v = math.sin(TAU * p)
        elif shape == "square":
            v = 1.0 if p < 0.5 else -1.0
        elif shape == "saw":
            v = 2.0 * p - 1.0
        elif shape == "tri":
            v = 4.0 * abs(p - 0.5) - 1.0
        else:
            v = rng.random() * 2 - 1
        if noise:
            v = v * (1 - noise) + (rng.random() * 2 - 1) * noise
        if cutoff:
            lp += a * (v - lp)
            v = lp
        env = min(1.0, i / att) * (1.0 - t) ** curve
        out[i] = v * env * vol
    return out


def mix_into(dst, src, offset=0, gain=1.0):
    end = min(len(dst), offset + len(src))
    for i in range(max(0, offset), end):
        dst[i] += src[i - offset] * gain
    return dst


def silence(dur):
    return [0.0] * int(dur * RATE)


def concat(*parts):
    out = []
    for p in parts:
        out.extend(p)
    return out


def note_hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


# --------------------------------------------------------------------------- sound effects


def build_sfx():
    s = {}
    s["shoot"] = tone(0.07, 900, 380, "square", 0.13, curve=1.6, cutoff=3200)
    s["hit"] = tone(0.045, 300, 120, "noise", 0.22, curve=2.5, cutoff=2600)
    s["kill"] = mix_into(tone(0.11, 420, 110, "tri", 0.28, curve=1.8), tone(0.08, 1, 1, "noise", 0.14, cutoff=4000))
    s["explode"] = mix_into(tone(0.5, 1, 1, "noise", 0.55, curve=2.2, cutoff=900), tone(0.35, 110, 40, "sine", 0.5))
    s["bomb"] = mix_into(tone(1.1, 1, 1, "noise", 0.7, curve=1.6, cutoff=600), tone(0.9, 80, 30, "sine", 0.7, curve=1.2))
    for k, semi in enumerate((0, 3, 7, 12)):
        f = 1046 * 2 ** (semi / 12)
        s[f"gem{k}"] = tone(0.07, f, f * 1.12, "sine", 0.16, curve=1.5)
    s["levelup"] = concat(*[tone(0.085, note_hz(m), None, "square", 0.14, curve=0.8, cutoff=4200)
                            for m in (72, 76, 79, 84)], tone(0.3, note_hz(88), None, "tri", 0.22, curve=2))
    s["hurt"] = mix_into(tone(0.22, 260, 70, "saw", 0.32, curve=1.5, cutoff=1800), tone(0.12, 1, 1, "noise", 0.2))
    chest = silence(0.75)
    for k in range(9):
        mix_into(chest, tone(0.18, note_hz(76 + k * 2), None, "sine", 0.16, curve=2), int(k * 0.065 * RATE))
    s["chest"] = chest
    s["boss"] = mix_into(tone(1.5, 75, 42, "saw", 0.45, attack=0.15, curve=1.0, cutoff=500),
                         tone(1.5, 1, 1, "noise", 0.2, attack=0.2, curve=1.3, cutoff=300))
    s["ui_move"] = tone(0.035, 760, 760, "sine", 0.14, curve=1.2)
    s["ui_select"] = tone(0.1, 520, 1040, "square", 0.12, curve=1.5, cutoff=3000)
    s["ui_back"] = tone(0.1, 620, 310, "square", 0.11, curve=1.5, cutoff=2500)
    s["laser"] = tone(0.28, 1600, 180, "saw", 0.2, curve=1.4, cutoff=3500)
    s["zap"] = mix_into(tone(0.14, 1, 1, "noise", 0.25, curve=1.2, cutoff=5000), tone(0.14, 1800, 600, "square", 0.08))
    s["whoosh"] = tone(0.16, 1, 1, "noise", 0.2, attack=0.04, curve=1.5, cutoff=1400)
    s["warn"] = concat(tone(0.14, 880, None, "square", 0.12, curve=0.3, cutoff=2400), silence(0.06),
                       tone(0.14, 660, None, "square", 0.12, curve=0.3, cutoff=2400))
    s["pickup"] = tone(0.13, 520, 1100, "sine", 0.22, curve=1.2)
    s["heal"] = concat(tone(0.08, 660, None, "sine", 0.18), tone(0.12, 990, None, "sine", 0.18))
    s["evolve"] = concat(*[tone(0.1, note_hz(m), None, "tri", 0.2, curve=0.6) for m in (60, 64, 67, 72, 76, 79)],
                         tone(0.6, note_hz(84), None, "sine", 0.25, curve=1.5))
    s["revive"] = concat(*[tone(0.12, note_hz(m), None, "sine", 0.2, curve=0.5) for m in (67, 71, 74, 79)])
    s["victory"] = concat(*[tone(0.16, note_hz(m), None, "square", 0.12, curve=0.7, cutoff=3000)
                            for m in (72, 74, 76, 79, 81, 84)], tone(0.9, note_hz(88), None, "tri", 0.2, curve=1.2))
    s["defeat"] = concat(*[tone(0.25, note_hz(m), None, "tri", 0.2, curve=1.0) for m in (64, 60, 57, 52)])
    return s


# --------------------------------------------------------------------------- music


def compose(name):
    """Compose one of the two music loops. Returns float samples."""
    rng = random.Random(42 if name == "run" else 7)
    if name == "run":
        bpm, prog, root = 118, [(57, "m"), (53, ""), (48, ""), (55, "")], 33
    else:
        bpm, prog, root = 84, [(50, "m"), (46, ""), (53, ""), (48, "")], 38
    beat = 60.0 / bpm
    bar = beat * 4
    bars = 8
    out = [0.0] * int(bars * bar * RATE)

    def chord(base, quality):
        return [base, base + (3 if quality == "m" else 4), base + 7]

    for b in range(bars):
        base, q = prog[b % 4]
        notes = chord(base, q)
        start = int(b * bar * RATE)
        # pad: three detuned triangle voices with slow attack
        for m in notes:
            for det in (-0.06, 0.06):
                mix_into(out, tone(bar * 1.05, note_hz(m + det) / 2, None, "tri", 0.05, attack=0.35, curve=0.6), start)
        # bass
        bass_note = note_hz(base - 24 if base - 24 > root else base - 12)
        steps = 8 if name == "run" else 2
        for k in range(steps):
            length = bar / steps
            mix_into(out, tone(length * 0.9, bass_note, None, "saw", 0.16 if name == "run" else 0.12,
                               attack=0.005, curve=1.2, cutoff=600), start + int(k * length * RATE))
        # arpeggio
        arp = notes + [notes[0] + 12, notes[1] + 12]
        div = 16 if name == "run" else 8
        for k in range(div):
            if name == "title" and rng.random() < 0.25:
                continue
            m = arp[(k * 3 + b) % len(arp)] + 12
            length = bar / div
            mix_into(out, tone(length * 1.4, note_hz(m), None, "square" if name == "run" else "sine",
                               0.045 if name == "run" else 0.07, curve=2.5, cutoff=2400),
                     start + int(k * length * RATE))
        # drums
        if name == "run":
            for k in range(4):
                mix_into(out, tone(0.22, 120, 40, "sine", 0.55, curve=2.2), start + int(k * beat * RATE))
                mix_into(out, tone(0.05, 1, 1, "noise", 0.08, curve=3, cutoff=7000),
                         start + int((k + 0.5) * beat * RATE))
            for k in (1, 3):
                mix_into(out, tone(0.16, 1, 1, "noise", 0.16, curve=2.5, cutoff=3500), start + int(k * beat * RATE))
    peak = max(1e-6, max(abs(v) for v in out))
    g = 0.85 / peak
    return [v * g for v in out]


# --------------------------------------------------------------------------- engine


class Audio:
    MIN_GAP = {"hit": 0.035, "shoot": 0.05, "gem0": 0.03, "gem1": 0.03, "gem2": 0.03, "gem3": 0.03,
               "kill": 0.04, "zap": 0.06, "whoosh": 0.08, "explode": 0.06, "laser": 0.08}

    def __init__(self, settings, cache_dir, enabled=True):
        self.ok = False
        self.sounds = {}
        self.music = {}
        self.last = {}
        self.want = None
        self.playing = None
        self.channel = None
        self.settings = settings
        self.cache_dir = cache_dir
        if not enabled:
            return
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.set_num_channels(32)
            pygame.mixer.set_reserved(1)
            self.channel = pygame.mixer.Channel(0)
            for name, samples in build_sfx().items():
                self.sounds[name] = pygame.mixer.Sound(file=io.BytesIO(_wav_bytes(samples)))
            self.ok = True
        except (pygame.error, OSError, ValueError):
            self.ok = False
            return
        threading.Thread(target=self._load_music, daemon=True).start()

    # ---------------------------------------------------------------- music

    def _load_music(self):
        for name in ("title", "run"):
            path = os.path.join(self.cache_dir, f"music_{name}_{VERSION}.wav")
            try:
                if os.path.exists(path):
                    snd = pygame.mixer.Sound(path)
                else:
                    data = _wav_bytes(compose(name))
                    try:
                        os.makedirs(self.cache_dir, exist_ok=True)
                        with open(path, "wb") as f:
                            f.write(data)
                    except OSError:
                        pass
                    snd = pygame.mixer.Sound(file=io.BytesIO(data))
                self.music[name] = snd
            except (pygame.error, OSError, ValueError):
                pass

    def play_music(self, name):
        self.want = name

    def update(self):
        if not self.ok:
            return
        if self.want != self.playing and self.want in self.music:
            if self.channel.get_busy():
                self.channel.fadeout(400)
            self.channel.play(self.music[self.want], loops=-1, fade_ms=1200)
            self.playing = self.want
        self.channel.set_volume(self.settings["music"] * self.settings["master"])

    # ---------------------------------------------------------------- effects

    def play(self, name, vol=1.0):
        if not self.ok:
            return
        snd = self.sounds.get(name)
        if snd is None:
            return
        now = time.monotonic()
        if now - self.last.get(name, 0.0) < self.MIN_GAP.get(name, 0.02):
            return
        self.last[name] = now
        ch = snd.play()
        if ch is not None:
            ch.set_volume(max(0.0, min(1.0, vol * self.settings["sfx"] * self.settings["master"])))

    def gem(self, combo):
        self.play(f"gem{min(3, combo)}", 0.8)
