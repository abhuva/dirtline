"""Exercise town approaches at different HUD, AI and streaming frame phases."""
import json
import test_rom as t

assert t.lib.emulator_open(str(t.ROOT/'dist/dustline.gba').encode())
peak=0
uploads=0
try:
    t.step(0,90);t.start_map(0)
    for trial in range(24):
        if trial:t.tap(t.B);t.reset()
        t.step(0,trial%12)
        baseline=t.state()['missed']
        for tick in range(360):
            s=t.step(t.A)
            peak=max(peak,s['cpu'])
            uploads=max(uploads,s['uploaded_bytes'])
            if s['mode']==3:break
        s=t.step(0,5)
        t.check(f'Town approach phase {trial} opens without dropped frames',
                s['mode']==3 and s['missed']==baseline,
                dict(missed=s['missed'],baseline=baseline,cpu_peak=peak))
    t.check('Resident wasteland tiles need no uploads while driving',uploads==0,uploads)
finally:
    t.lib.emulator_close()
    report=dict(rom_sha256=t.hashlib.sha256((t.ROOT/'dist/dustline.gba').read_bytes()).hexdigest(),checks=t.checks)
    (t.OUT/'wasteland/town-streaming-results.json').write_text(json.dumps(report,indent=2)+'\n')
raise SystemExit(0 if t.checks and all(c['passed'] for c in t.checks) else 1)
