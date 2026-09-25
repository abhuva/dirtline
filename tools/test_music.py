"""Validate the adaptive tracker source and generated MOD/WAV structure."""
import json
import struct
import tempfile
import wave
from pathlib import Path

from music_generator import SECTION_IDS, build_patterns, build_samples, load_music, validate_music, write_mod, write_preview

ROOT = Path(__file__).resolve().parents[1]
data = load_music()
patterns = build_patterns(data)
assert len(patterns) == 8 and all(len(pattern) == 64 for pattern in patterns)
samples = build_samples(data['seed'])
assert samples[4].looped and samples[4].loop_start > 0, 'horizon pad must have a soft attack and sustain loop'
assert samples[4].loop_length >= 4096, 'horizon pad needs enough resolution for close chorus voices'
assert samples[5].looped and samples[5].loop_length >= 4096, 'desert-air bed needs a long evolving loop'
assert not samples[6].looped and len(samples[6].data) > 4000, 'signal lead must decay naturally'

def signed(value):
    return value - 256 if value >= 128 else value

for name, sample in zip(('bass', 'pad', 'air'), samples[3:6]):
    start = sample.loop_start
    end = start + sample.loop_length
    seam = abs(signed(sample.data[start]) - signed(sample.data[end - 1]))
    entry = abs(signed(sample.data[start]) - signed(sample.data[start - 1]))
    assert seam <= 16 and entry <= 16, f'{name} loop contains a harsh waveform discontinuity'

with tempfile.TemporaryDirectory() as folder:
    folder = Path(folder)
    first = folder / 'first.mod'
    second = folder / 'second.mod'
    preview = folder / 'preview.wav'
    write_mod(data, first)
    write_mod(data, second)
    write_preview(data, preview)
    raw = first.read_bytes()
    assert raw == second.read_bytes(), 'tracker generation is not deterministic'
    assert raw[1080:1084] == b'8CHN'
    assert raw[950] == 8 and list(raw[952:960]) == list(range(8))
    pattern_start = 1084
    pattern_bytes = 64 * 8 * 4
    for pattern in range(8):
        event = pattern_start + pattern * pattern_bytes + (31 * 8 + 7) * 4
        effect = raw[event + 2] & 15
        parameter = raw[event + 3]
        assert (effect, parameter) == ((0xD, 0) if pattern % 2 == 0 else (0xB, pattern - 1))
    with wave.open(str(preview), 'rb') as wav:
        assert wav.getnchannels() == 1 and wav.getsampwidth() == 2 and wav.getframerate() == 16000
        expected_frames = len(patterns) * 32 * round(16000 * 15 / data['bpm'])
        assert wav.getnframes() == expected_frames

invalid = json.loads(json.dumps(data))
invalid['sections']['combat']['patterns']['lead'].pop()
try:
    validate_music(invalid)
    raise AssertionError('invalid 15-step pattern was accepted')
except ValueError:
    pass

with wave.open(str(ROOT / 'audio/engine.wav'), 'rb') as engine:
    assert engine.getnchannels() == 1 and engine.getsampwidth() == 2 and engine.getframerate() == 16000
    assert 0.5 * 16000 <= engine.getnframes() <= 0.6 * 16000
    values = struct.unpack('<' + 'h' * engine.getnframes(), engine.readframes(engine.getnframes()))
    assert 3000 < (sum(value * value for value in values) / len(values)) ** .5 < 6000
    assert max(map(abs, values)) < 12000 and abs(values[0]) < 64 and abs(values[-1]) < 64

print(f'PASS adaptive music: {len(SECTION_IDS)} sections, 8 channels, deterministic {len(raw)}-byte MOD/WAV and subdued engine sample.')
