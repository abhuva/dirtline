"""Generate Dustline's adaptive 8-channel tracker module and reference WAV."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import struct
import wave
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MUSIC_PATH = ROOT / "music" / "dustline-drive.json"
MOD_PATH = ROOT / "audio" / "dustline_drive.mod"
HEADER_PATH = ROOT / "include" / "generated" / "music_data.h"
PREVIEW_PATH = ROOT / "tools" / "map_editor" / "generated" / "music-preview.wav"

SECTION_IDS = ("cruise", "drive", "danger", "combat")
SCALES = {
    "minor_pentatonic": (0, 3, 5, 7, 10),
    "natural_minor": (0, 2, 3, 5, 7, 8, 10),
    "dorian": (0, 2, 3, 5, 7, 9, 10),
}
TRACK_IDS = ("kick", "snare", "hat", "bass", "chord", "drive", "lead", "metal")
TRACK_KINDS = ("drum", "drum", "drum", "tone", "tone", "tone", "tone", "drum")
DRUM_NOTES = (48, 48, 60, 48, 48, 48, 48, 55)


def revision(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _integer(value, name: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f"{name} must be an integer from {low} to {high}")
    return value


def validate_music(data: object) -> dict:
    if not isinstance(data, dict):
        raise ValueError("Music document must be an object")
    if data.get("version") != 1:
        raise ValueError("Only music document version 1 is supported")
    title = data.get("title")
    if not isinstance(title, str) or not title.strip() or len(title) > 20:
        raise ValueError("title must contain 1 to 20 characters")
    _integer(data.get("bpm"), "bpm", 80, 180)
    _integer(data.get("seed"), "seed", 0, 0xFFFFFFFF)
    _integer(data.get("root"), "root", 24, 48)
    if data.get("scale") not in SCALES:
        raise ValueError(f"scale must be one of {', '.join(SCALES)}")
    _integer(data.get("variation"), "variation", 0, 100)
    tracks = data.get("tracks")
    if not isinstance(tracks, list) or len(tracks) != 8:
        raise ValueError("tracks must contain the eight fixed GBA channels")
    for index, (track, expected_id, expected_kind) in enumerate(zip(tracks, TRACK_IDS, TRACK_KINDS)):
        if not isinstance(track, dict) or track.get("id") != expected_id or track.get("kind") != expected_kind:
            raise ValueError(f"track {index + 1} must be {expected_id} ({expected_kind})")
        if not isinstance(track.get("label"), str) or not track["label"] or len(track["label"]) > 16:
            raise ValueError(f"{expected_id} label must contain 1 to 16 characters")
        _integer(track.get("volume"), f"{expected_id} volume", 0, 64)
        _integer(track.get("octave"), f"{expected_id} octave", -2, 3)
    sections = data.get("sections")
    if not isinstance(sections, dict) or tuple(sections) != SECTION_IDS:
        raise ValueError("sections must be cruise, drive, danger and combat in that order")
    scale_size = len(SCALES[data["scale"]])
    for section_id in SECTION_IDS:
        section = sections[section_id]
        if not isinstance(section, dict) or not isinstance(section.get("label"), str):
            raise ValueError(f"{section_id} must have a label")
        patterns = section.get("patterns")
        if not isinstance(patterns, dict) or tuple(patterns) != TRACK_IDS:
            raise ValueError(f"{section_id} patterns must contain all eight tracks in order")
        for track_id, kind in zip(TRACK_IDS, TRACK_KINDS):
            steps = patterns[track_id]
            if not isinstance(steps, list) or len(steps) != 16:
                raise ValueError(f"{section_id}.{track_id} must contain 16 steps")
            for step in steps:
                if step is None:
                    continue
                if kind == "drum":
                    if step != 1:
                        raise ValueError(f"{section_id}.{track_id} steps must be null or 1")
                else:
                    _integer(step, f"{section_id}.{track_id} degree", -scale_size * 2, scale_size * 4)
    return data


def load_music(path: Path = MUSIC_PATH) -> dict:
    return validate_music(json.loads(path.read_text(encoding="utf8")))


def degree_note(data: dict, track_index: int, degree: int) -> int:
    scale = SCALES[data["scale"]]
    octave, index = divmod(degree, len(scale))
    return data["root"] + data["tracks"][track_index]["octave"] * 12 + octave * 12 + scale[index]


def note_name(note: int) -> str:
    names = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
    return f"{names[note % 12]}{note // 12 - 1}"


@dataclass(frozen=True)
class Event:
    note: int | None = None
    sample: int = 0
    effect: int = 0
    parameter: int = 0


def _variant_value(data: dict, section_index: int, track_index: int, row: int, value):
    if row < 16 or data["variation"] == 0:
        return value
    rng = random.Random(data["seed"] ^ (section_index * 0x9E3779B1) ^ (track_index * 0x85EBCA6B) ^ row)
    chance = data["variation"]
    track_id = TRACK_IDS[track_index]
    step = row & 15
    if value is None and track_id == "hat" and step & 1 and rng.randrange(100) < chance:
        return 1
    if value is None and track_id == "kick" and step in (14, 15) and rng.randrange(100) < chance // 2:
        return 1
    if value is not None and track_id == "lead" and rng.randrange(100) < chance // 2:
        # Answer the authored melody instead of turning every variation into an
        # octave fill.  Scale steps keep the response consonant in every mode.
        return value + (-1 if rng.randrange(2) else 1)
    if value is not None and track_id == "drive" and rng.randrange(100) < chance // 4:
        return value + len(SCALES[data["scale"]])
    if value is None and track_id == "metal" and step == 15 and rng.randrange(100) < chance // 2:
        return 1
    return value


def build_patterns(data: dict) -> list[list[list[Event]]]:
    """Return eight 64-row MOD patterns; only their first 32 rows are played."""
    patterns = []
    for section_index, section_id in enumerate(SECTION_IDS):
        source = data["sections"][section_id]["patterns"]
        for variant in (False, True):
            rows = [[Event() for _ in TRACK_IDS] for _ in range(64)]
            for row in range(32):
                step = row & 15
                for track_index, (track_id, kind) in enumerate(zip(TRACK_IDS, TRACK_KINDS)):
                    value = source[track_id][step]
                    if variant:
                        value = _variant_value(data, section_index, track_index, row, value)
                    if value is not None:
                        note = DRUM_NOTES[track_index] if kind == "drum" else degree_note(data, track_index, value)
                        rows[row][track_index] = Event(note, track_index + 1)
                # Stop channels absent from this section instead of carrying a note across a state change.
                if row == 0:
                    for track_index, track_id in enumerate(TRACK_IDS):
                        if not any(value is not None for value in source[track_id]):
                            rows[row][track_index] = Event(effect=0xC, parameter=0)
            rows[0][0] = Event(rows[0][0].note, rows[0][0].sample, 0xF, data["bpm"])
            if variant:
                rows[31][7] = Event(rows[31][7].note, rows[31][7].sample, 0xB, section_index * 2)
            else:
                rows[31][7] = Event(rows[31][7].note, rows[31][7].sample, 0xD, 0)
            patterns.append(rows)
    return patterns


def _signed(samples):
    return bytes(max(-127, min(127, round(sample * 127))) & 0xFF for sample in samples)


def _smootherstep(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * value * (value * (value * 6 - 15) + 10)


def _circular_smooth(values: list[float], passes: int) -> list[float]:
    """Band-limit a seamless loop without introducing a boundary click."""
    result = values
    for _ in range(passes):
        size = len(result)
        result = [
            (result[(index - 2) % size] + 4 * result[(index - 1) % size] +
             6 * result[index] + 4 * result[(index + 1) % size] +
             result[(index + 2) % size]) / 16
            for index in range(size)
        ]
    return result


@dataclass(frozen=True)
class Sample:
    data: bytes
    loop_start: int = 0
    loop_length: int = 2

    @property
    def looped(self) -> bool:
        return self.loop_length > 2


def build_samples(seed: int) -> list[Sample]:
    rate = 8287
    rng = random.Random(seed ^ 0xD05711E)

    def oneshot(duration, function):
        count = int(rate * duration) & ~1
        return Sample(_signed(function(i / rate, i / max(1, count - 1)) for i in range(count)))

    kick = oneshot(.19, lambda t, p: math.sin(math.tau * (92 - 54 * p) * t) * (1 - p) ** 2)
    snare = oneshot(.13, lambda t, p: (rng.uniform(-1, 1) * .8 + math.sin(math.tau * 175 * t) * .2) * (1 - p) ** 2)
    hat = oneshot(.055, lambda _t, p: rng.uniform(-1, 1) * (1 - p) ** 3)

    def attack_loop_values(attack_seconds, loop_values):
        length = len(loop_values)
        attack = int(rate * attack_seconds) & ~1
        # Read backwards from the loop boundary so the attack enters at the
        # exact same phase as the sustain seam.  Resetting an arbitrary attack
        # phase to sample zero is itself an audible tracker click.
        values = []
        for index in range(attack):
            source_index = (length - attack + index) % length
            envelope = _smootherstep(index / max(1, attack - 1))
            values.append(loop_values[source_index] * envelope)
        values.extend(loop_values)
        return Sample(_signed(values), attack, length)

    def attack_loop(attack_seconds, length, function):
        return attack_loop_values(attack_seconds, [function(index / length) for index in range(length)])

    # Warm, band-limited curves replace the original saw/pulse palette.  The
    # fundamental still spans 64 samples so tracker pitch remains unchanged.
    bass = attack_loop(.045, 256, lambda p:
                       .55 * math.sin(math.tau * p * 4) +
                       .13 * math.sin(math.tau * (p * 8 + .08)) +
                       .045 * math.sin(math.tau * (p * 12 + .21)))

    # A 4096-sample table permits a real chorus: 63/64/65-cycle voices are only
    # about 27 cents apart and meet again perfectly at the loop boundary.
    chord = attack_loop(.32, 4096, lambda p:
                        .22 * math.sin(math.tau * (p * 64 + .02)) +
                        .105 * math.sin(math.tau * (p * 63 + .31)) +
                        .105 * math.sin(math.tau * (p * 65 + .67)) +
                        .065 * math.sin(math.tau * (p * 96 + .14)) +
                        .025 * math.sin(math.tau * (p * 128 + .43)))

    # Circularly filtered noise produces a seamless wind bed.  A quiet tonal
    # center lets the authored degrees still color it without sounding like a
    # bank of unrelated metallic oscillators.
    air_length = 4096
    air_noise = _circular_smooth([rng.uniform(-1, 1) for _ in range(air_length)], 9)
    air_peak = max(abs(value) for value in air_noise)
    drive_values = []
    for index, noise_value in enumerate(air_noise):
        phase = index / air_length
        motion = .72 + .18 * math.sin(math.tau * phase * 3) + .10 * math.sin(math.tau * phase * 7 + .9)
        tone = (.075 * math.sin(math.tau * (phase * 64 + .37)) +
                .035 * math.sin(math.tau * (phase * 96 + .11)))
        drive_values.append(tone + .22 * noise_value / air_peak * motion)
    drive = attack_loop_values(.24, drive_values)

    base_frequency = rate / 64

    def lead_voice(t, progress):
        vibrato = .035 * math.sin(math.tau * 5.1 * t) * _smootherstep(min(1, t / .22))
        phase = math.tau * base_frequency * t + vibrato
        attack = _smootherstep(min(1, t / .025))
        return attack * (
            .56 * math.sin(phase) * (1 - progress) ** 1.35 +
            .12 * math.sin(phase * 2 + .18) * (1 - progress) ** 2.8 +
            .035 * math.sin(phase * 3 + .52) * (1 - progress) ** 4.2)

    lead = oneshot(.82, lead_voice)

    def chime_voice(t, progress):
        attack = _smootherstep(min(1, t / .008))
        tail = max(0, 1 - progress)
        return attack * (
            .40 * math.sin(math.tau * 420 * t) * tail ** 1.5 +
            .18 * math.sin(math.tau * 843 * t + .4) * tail ** 2.4 +
            .09 * math.sin(math.tau * 1121 * t + 1.1) * tail ** 3.4 +
            .035 * math.sin(math.tau * 1697 * t + .2) * tail ** 5)

    metal = oneshot(.82, chime_voice)
    return [kick, snare, hat, bass, chord, drive, lead, metal]


def _period(note: int) -> int:
    return max(113, min(1712, round(428 * 2 ** ((48 - note) / 12))))


def write_mod(data: dict, path: Path = MOD_PATH) -> None:
    patterns = build_patterns(data)
    samples = build_samples(data["seed"])
    output = bytearray(data["title"].encode("ascii", "replace")[:20].ljust(20, b"\0"))
    for index in range(31):
        if index < len(samples):
            sample = samples[index]
            label = data["tracks"][index]["label"].encode("ascii", "replace")[:22]
            volume = data["tracks"][index]["volume"]
            output += label.ljust(22, b"\0") + struct.pack(
                ">HBBHH", len(sample.data) // 2, 0, volume,
                sample.loop_start // 2, sample.loop_length // 2)
        else:
            output += bytes(30)
    output += bytes((len(patterns), 0))
    output += bytes(range(len(patterns))) + bytes(128 - len(patterns))
    output += b"8CHN"
    for rows in patterns:
        for row in rows:
            for event in row:
                period = _period(event.note) if event.note is not None else 0
                output += bytes(((event.sample & 0xF0) | (period >> 8), period & 0xFF,
                                 ((event.sample & 0x0F) << 4) | event.effect, event.parameter))
    for sample in samples:
        output += sample.data
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(output)


def write_header(data: dict, path: Path = HEADER_PATH) -> None:
    labels = ", ".join(f'"{data["sections"][key]["label"]}"' for key in SECTION_IDS)
    text = f'''#pragma once
// Generated by tools/music_generator.py from music/dustline-drive.json.
namespace adaptive_music_data {{
enum class section {{ cruise, drive, danger, combat }};
inline constexpr int section_count = {len(SECTION_IDS)};
inline constexpr int section_positions[section_count] = {{ 0, 2, 4, 6 }};
inline constexpr const char* section_names[section_count] = {{ {labels} }};
inline constexpr int bpm = {data["bpm"]};
}}
'''
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf8")


def write_preview(data: dict, path: Path = PREVIEW_PATH) -> None:
    rate = 16000
    patterns = build_patterns(data)
    samples = build_samples(data["seed"])
    voices = [{"sample": None, "position": 0.0, "step": 0.0, "volume": 0.0,
               "loop_start": 0, "loop_end": 0, "looped": False} for _ in TRACK_IDS]
    pcm: list[int] = []
    row_frames = round(rate * 15 / data["bpm"])
    for pattern in patterns:
        for row in pattern[:32]:
            for channel, event in enumerate(row):
                voice = voices[channel]
                if event.effect == 0xC:
                    voice["volume"] = event.parameter / 64
                if event.note is not None:
                    sample = samples[event.sample - 1]
                    voice.update(sample=sample.data, position=0.0,
                                 step=(3546895 / _period(event.note)) / rate,
                                 volume=data["tracks"][channel]["volume"] / 64,
                                 loop_start=sample.loop_start,
                                 loop_end=(sample.loop_start + sample.loop_length
                                           if sample.looped else len(sample.data)),
                                 looped=sample.looped)
            for _ in range(row_frames):
                mixed = 0.0
                for voice in voices:
                    sample = voice["sample"]
                    if sample is None or voice["volume"] == 0:
                        continue
                    position = int(voice["position"])
                    if position >= voice["loop_end"]:
                        if voice["looped"]:
                            voice["position"] = voice["loop_start"] + (
                                voice["position"] - voice["loop_start"]) % (
                                    voice["loop_end"] - voice["loop_start"])
                            position = int(voice["position"])
                        else:
                            voice["sample"] = None
                            continue
                    value = sample[position]
                    if value >= 128:
                        value -= 256
                    mixed += value / 128 * voice["volume"]
                    voice["position"] += voice["step"]
                pcm.append(round(max(-1, min(1, mixed / 3.2)) * 30000))
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as output:
        output.setparams((1, 2, rate, len(pcm), "NONE", "not compressed"))
        output.writeframes(struct.pack("<" + "h" * len(pcm), *pcm))


def generate(path: Path = MUSIC_PATH) -> dict:
    data = load_music(path)
    write_mod(data)
    write_header(data)
    write_preview(data)
    return data


def save_music(data: dict, expected_revision: str | None = None, path: Path = MUSIC_PATH) -> str:
    validate_music(data)
    current = path.read_bytes()
    if expected_revision is not None and revision(current) != expected_revision:
        raise RuntimeError("The music source changed on disk. Reload before saving.")
    encoded = (json.dumps(data, indent=2) + "\n").encode("utf8")
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(encoded)
    os.replace(temporary, path)
    generate(path)
    return revision(encoded)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="validate without writing generated files")
    args = parser.parse_args()
    music = load_music()
    if not args.check:
        generate()
    print(f'{music["title"]}: {music["bpm"]} BPM, 8 channels, 4 adaptive sections')
