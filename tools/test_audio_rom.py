"""Focused ROM check for the subdued, settling motor loop."""
import test_rom as t


assert t.lib.emulator_open(str(t.ROOT / 'dist/dustline.gba').encode())
t.step(0, 90)
t.tap(t.A)
for _ in range(120):
    if t.step(0, 30)['mode'] == 1:
        break
assert t.state()['mode'] == 1, 'map loading did not finish'

t.step(t.A | t.RIGHT, 45)
initial = t.audio_state()
t.step(t.A | t.RIGHT, 480)
settled = t.audio_state()

assert initial['engine_volume'] > 0.1, initial
assert t.state()['mode'] == 1, t.state()
assert 0 < settled['engine_volume'] <= initial['engine_volume'] * 0.3, (initial, settled)
assert 0.7 <= initial['engine_pitch'] <= 1.3 and 0.7 <= settled['engine_pitch'] <= 1.3

t.lib.emulator_close()
print('PASS audio ROM: motor pitch stays restrained and sustained throttle fades to a quiet bed.')
