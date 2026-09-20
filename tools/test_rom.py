"""Integration tests of the compiled GBA ROM, using headless mGBA.

Only joypad input is written. Telemetry is read from the ELF symbol address.
Run through test.ps1 after build.ps1.
"""
import ctypes as C
import hashlib
import json
import math
from pathlib import Path
import subprocess
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts'
OUT.mkdir(exist_ok=True)
A,B,SELECT,START,RIGHT,LEFT,UP,DOWN,R,L=[1<<i for i in range(10)]
NM='/opt/devkitpro/devkitARM/bin/arm-none-eabi-nm'
symbols=subprocess.check_output([NM,str(ROOT/'dustline.elf')],text=True)
address=int(next(line.split()[0] for line in symbols.splitlines() if line.endswith(' dustline_telemetry')),16)
lib=C.CDLL(str(ROOT/'build/emulator_bridge.so'))
lib.emulator_open.argtypes=[C.c_char_p]
lib.emulator_open.restype=C.c_int
lib.emulator_step.argtypes=[C.c_int,C.c_int]
lib.emulator_read.argtypes=[C.c_uint32]
lib.emulator_read.restype=C.c_int32
lib.emulator_pixels.restype=C.c_void_p

def step(keys=0,frames=1):
    lib.emulator_step(keys,frames)
    return state()

def state():
    v=[lib.emulator_read(address+4*i) for i in range(20)]
    return dict(magic=v[0],frame=v[1],mode=v[2],setup=v[3],
                x=v[4]/4096,y=v[5]/4096,vx=v[6]/4096,vy=v[7]/4096,
                heading=v[8]/4096,slip=v[9]/4096,surface=v[10],
                lap_frames=v[11],best=v[12],laps=v[13],gate=v[14],
                collisions=v[15],cpu=v[16]/4096,missed=v[17])

def capture(name):
    size=lib.emulator_pixel_size()
    raw=C.string_at(lib.emulator_pixels(),240*160*size)
    if size!=4:
        raise RuntimeError(f'Expected 32-bit mGBA pixel buffer, got {size}')
    im=Image.frombytes('RGBA',(240,160),raw).convert('RGB')
    im.save(OUT/(name+'.png'))
    im.resize((960,640),Image.Resampling.NEAREST).save(OUT/(name+'-4x.png'))
    return im

checks=[]
def check(name,condition,details=None):
    checks.append(dict(name=name,passed=bool(condition),details=details))
    print(('PASS' if condition else 'FAIL')+' '+name,details or '',flush=True)

def tap(key):
    step(0,2)
    step(key,2)
    return step(0,2)

def reset():
    tap(SELECT)
    return state()

def angle_delta(target,current):
    return (target-current+180)%360-180

def main():
    assert lib.emulator_open(str(ROOT/'dist/dustline.gba').encode())
    s=step(0,90)
    capture('title')
    check('Boots to title',s['magic']==0x44555354 and s['mode']==0,s)
    s=tap(A)
    capture('driving')
    check('Starts driving',s['mode']==1 and s['setup']==1,s)
    x0=s['x']
    s=step(A,60)
    check('Throttle accelerates',s['x']>x0+50 and s['vx']>1.5,s)
    speed_before=math.hypot(s['vx'],s['vy'])
    s=step(0,35)
    check('Lift preserves but reduces momentum',0.2<math.hypot(s['vx'],s['vy'])<speed_before,s)

    reset()
    s=step(B,50)
    check('B reverses from rest',s['x']<455 and s['vx']<-.5,s)
    reset()
    step(A,55)
    s=step(A|LEFT,45)
    capture('cornering')
    check('Steering changes heading and produces lateral slip',s['heading']>270 and s['slip']>.1,s)

    # Compare equal steering windows after identical acceleration.
    reset(); step(A,65); powered=step(A|LEFT,30)
    reset(); step(A,65); coasting=step(LEFT,30)
    check('Lifting tightens the turn',angle_delta(0,coasting['heading'])>angle_delta(0,powered['heading']),
          dict(powered=powered,coasting=coasting))
    check('Lifting reduces slide',coasting['slip']<powered['slip'],
          dict(powered_slip=powered['slip'],coasting_slip=coasting['slip']))

    s=tap(START)
    capture('controls')
    before=state()
    after=step(A|LEFT,90)
    check('Pause freezes car and lap timer',after['mode']==2 and
          all(before[k]==after[k] for k in ('x','y','heading','lap_frames')),after)
    tap(START)

    speeds=[]
    for _ in range(3):
        s=tap(R)
        check('Preset switch resets run',abs(s['x']-470)<1 and s['gate']==0,s)
        s=step(A,60)
        speeds.append((s['setup'],s['vx']))
    check('Three setups have distinct acceleration',len(set(round(v,2) for _,v in speeds))==3,speeds)
    # Default RALLY for the endurance / course test.
    while state()['setup']!=1: tap(R)
    reset()

    # Continuous throttle without steering reaches the outside wall safely.
    s=step(A,500)
    check('Wall collision keeps car inside world',94<=s['x']<=938 and s['collisions']>0,s)
    check('Finish cannot count without ordered gates',s['laps']==0 and s['best']==0,s)
    reset()

    # Follow the centerline using only normal controls. This is an integration
    # exercise, not a claim that a human will like this handling configuration.
    path=json.loads((OUT/'track_path.json').read_text())[:-1]
    idx=0
    max_cpu=0
    surface_seen=set()
    captured_dirt=False
    frames=[]
    for tick in range(7200):
        s=state()
        # Search a local forward window to avoid jumping across nearby bends.
        candidates=[(idx+i)%len(path) for i in range(-3,24)]
        idx=min(candidates,key=lambda k:(path[k][0]-s['x'])**2+(path[k][1]-s['y'])**2)
        # Look approximately 32 pixels ahead along the centerline.
        goal=idx
        distance=0
        while distance<32:
            nxt=(goal+1)%len(path)
            distance+=math.dist(path[goal],path[nxt]); goal=nxt
        gx,gy=path[goal]
        wanted=math.degrees(math.atan2(gy-s['y'],gx-s['x']))%360
        error=angle_delta(wanted,s['heading'])
        speed=math.hypot(s['vx'],s['vy'])
        keys=LEFT if error<-3 else RIGHT if error>3 else 0
        # Approach tight bends by lifting before rotating.
        target_speed=2.4 if abs(error)<12 else 1.65 if abs(error)<35 else 0.95
        if speed<target_speed: keys|=A
        step(keys)
        max_cpu=max(max_cpu,s['cpu'])
        surface_seen.add(s['surface'])
        if s['surface']==2 and not captured_dirt:
            capture('dirt'); captured_dirt=True
        if tick%6==0 and tick<2400:
            raw=C.string_at(lib.emulator_pixels(),240*160*4)
            frames.append(Image.frombytes('RGBA',(240,160),raw).convert('RGB').resize((480,320),Image.Resampling.NEAREST))
        if s['laps']>0:
            capture('lap-complete')
            break
    s=state()
    check('Can drive a full lap with ordered checkpoints',s['laps']>=1 and s['best']>0,s)
    check('Course includes working dirt surface',2 in surface_seen,sorted(surface_seen))
    check('Frame budget stays below one refresh',max_cpu<1 and s['missed']==0,dict(max_cpu=max_cpu,missed=s['missed']))
    if frames:
        frames[0].save(OUT/'demo.gif',save_all=True,append_images=frames[1:],duration=100,loop=0,optimize=True)
    lib.emulator_close()

if __name__=='__main__':
    try:
        main()
    finally:
        report=dict(rom_sha256=hashlib.sha256((ROOT/'dist/dustline.gba').read_bytes()).hexdigest(),
                    emulator='libmGBA (Debian bookworm)',checks=checks)
        (OUT/'test-results.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    if not checks or not all(c['passed'] for c in checks):
        raise SystemExit(1)
