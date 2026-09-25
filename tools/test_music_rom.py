"""Smoke-test adaptive music lifetime and generated metadata in the ROM."""
import ctypes as C
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BPM = json.loads((ROOT / 'music/dustline-drive.json').read_text())['bpm']
NM = '/opt/devkitpro/devkitARM/bin/arm-none-eabi-nm'
A, SELECT, START = 1, 1 << 2, 1 << 3
symbols = subprocess.check_output([NM, str(ROOT / 'dustline.elf')], text=True)

def symbol(name):
    return int(next(line.split()[0] for line in symbols.splitlines() if line.endswith(' ' + name)), 16)

state_address = symbol('dustline_telemetry')
music_address = symbol('dustline_music_telemetry')
lib = C.CDLL(str(ROOT / 'build/emulator_bridge.so'))
lib.emulator_open.argtypes = [C.c_char_p]
lib.emulator_open.restype = C.c_int
lib.emulator_step.argtypes = [C.c_int, C.c_int]
lib.emulator_read.argtypes = [C.c_uint32]
lib.emulator_read.restype = C.c_int32

def step(keys=0, frames=1):
    lib.emulator_step(keys, frames)

def read(address, count):
    return [lib.emulator_read(address + 4 * index) for index in range(count)]

def tap(key):
    step(0, 2); step(key, 2); step(0, 2)

assert lib.emulator_open(str(ROOT / 'dist/dustline.gba').encode())
step(0, 90)
assert read(state_address, 3)[2] == 0
assert read(music_address, 8)[1] == 0
tap(A)
for _ in range(120):
    step(0, 30)
    if read(state_address, 3)[2] == 1:
        break
state = read(state_address, 3)
music = read(music_address, 14)
assert state[2] == 1, 'map loading did not finish'
assert music[0] == 0x4D555343 and music[1] == 1
assert 0 <= music[2] <= 3 and 0 <= music[3] <= 3 and 0 <= music[4] <= 7
assert music[6] == EXPECTED_BPM and music[7] == 4
assert music[8] == 0 and music[13] == 0
step(0, 300)
later = read(music_address, 8)
assert later[1] == 1 and 0 <= later[4] <= 7
tap(START); tap(SELECT); step(0, 4)
assert read(state_address, 3)[2] == 0 and read(music_address, 8)[1] == 0
lib.emulator_close()
print('PASS adaptive music ROM: starts with gameplay, advances tracker positions, exports four sections and stops on title return.')
