"""Read the diagnostic ROM's byte-parity results from headless mGBA."""
import ctypes as C
import json
import hashlib
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
elf = ROOT / 'build/map_recipe_probe.elf'
rom = ROOT / 'build/map_recipe_probe.gba'
symbols = subprocess.check_output(['/opt/devkitpro/devkitARM/bin/arm-none-eabi-nm', str(elf)], text=True)
address = int(next(line.split()[0] for line in symbols.splitlines() if line.endswith(' recipe_probe')), 16)
count = len(json.loads((ROOT / 'build/map-recipe-tests/manifest.json').read_text()))
render_count=len(json.loads((ROOT / 'build/map-recipe-tests/render-manifest.json').read_text()))
lib = C.CDLL(str(ROOT / 'build/map_recipe_emulator_bridge.so'))
lib.emulator_open.argtypes = [C.c_char_p]
lib.emulator_read.argtypes = [C.c_uint32]
lib.emulator_read.restype = C.c_uint32
assert lib.emulator_open(str(rom).encode())
try:
    for frames in range(0, 60000, 30):
        lib.emulator_step(0, 30)
        state = [lib.emulator_read(address + i*4) for i in range(4)]
        assert state[2] == 0, f'GBA recipe mismatch: fixture {state[2]-1}, byte {state[3]-1}'
        if state[0] == 0x52435031 and state[1] == count+render_count:
            break
    else:
        raise AssertionError(f'GBA probe did not complete: {state}')
finally:
    lib.emulator_close()
report = dict(cases=count, nativeGbaByteParity=True, emulatorFrames=frames+30,
              renderCases=render_count,renderAndSurfaceParity=True,
              diagnosticRomSha256=hashlib.sha256(rom.read_bytes()).hexdigest())
(ROOT / 'artifacts/map_editor').mkdir(parents=True, exist_ok=True)
(ROOT / 'artifacts/map_editor/gba-parity-results.json').write_text(json.dumps(report, indent=2)+'\n')
print(f'PASS {count} native / GBA byte comparisons in mGBA ({frames+30} emulated frames)')
