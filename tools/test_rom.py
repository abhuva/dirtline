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
from world_reference import WorldReference

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts'
OUT.mkdir(exist_ok=True)
COURSE=json.loads((OUT/'map2/course.json').read_text())
START_X,START_Y=COURSE['start']
A,B,SELECT,START,RIGHT,LEFT,UP,DOWN,R,L=[1<<i for i in range(10)]
NM='/opt/devkitpro/devkitARM/bin/arm-none-eabi-nm'
symbols=subprocess.check_output([NM,str(ROOT/'dustline.elf')],text=True)
address=int(next(line.split()[0] for line in symbols.splitlines() if line.endswith(' dustline_telemetry')),16)
combat_address=int(next(line.split()[0] for line in symbols.splitlines() if line.endswith(' dustline_combat_telemetry')),16)
weapon_address=int(next(line.split()[0] for line in symbols.splitlines() if line.endswith(' dustline_weapon_telemetry')),16)
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
    v=[lib.emulator_read(address+4*i) for i in range(53)]
    return dict(magic=v[0],frame=v[1],mode=v[2],setup=v[3],
                x=v[4]/4096,y=v[5]/4096,vx=v[6]/4096,vy=v[7]/4096,
                heading=v[8]/4096,slip=v[9]/4096,surface=v[10],
                lap_frames=v[11],best=v[12],laps=v[13],gate=v[14],
                collisions=v[15],cpu=v[16]/4096,missed=v[17],camera_x=v[18],camera_y=v[19],
                vblank=v[20]/4096,uploaded_bytes=v[21],bg_bytes=v[22],sprite_free_bytes=v[23],
                map=v[24],width=v[25],height=v[26],chunk=v[27],tile_capacity=v[28],unique_tiles=v[29],
                renderer_working_ram_bytes=v[30],chunk_loads=v[31],chunk_decodes=v[32],chunk_cache_bytes=v[33],
                minimap_x=v[34],minimap_y=v[35],seed=v[36]&0xffffffff,signature=v[37]&0xffffffff,
                generations=v[38],town=v[39],town_x=v[40],town_y=v[41],layout_bytes=v[42],
                scratch_bytes=v[43],free_ewram=v[44],floor_cells=v[45],generation_updates=v[46],town_visits=v[47],
                radar_x=v[48],radar_y=v[49],radar_revisions=v[50],zoom_level=v[51],radar_scale=v[52])

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

def combat_state():
    v=[lib.emulator_read(combat_address+4*i) for i in range(240)]
    result=dict(zip(('magic','ticks','hp','player_hits','player_shots','enemy_shots','hits','kills',
                    'wall_hits','expired','living','bullets','ram','graphics','invincible','collisions',
                    'avoidance','recoveries'),v[:18]))
    result['simulation_cpu']=v[18]/4389
    result['view_cpu']=v[19]/4389
    result['bumps']=v[176]; result['last_bump']=v[177]/4096; result['player_mass']=v[178]
    result['last_pair']=v[179]; result['player_bumps']=v[180]
    result['enemies']=[dict(x=v[a]/4096,y=v[a+1]/4096,vx=v[a+2]/4096,vy=v[a+3]/4096,
                           heading=v[a+4]/4096,hp=v[a+5],collisions=v[a+6],reverse=v[a+7],
                           avoidance=v[a+8],recoveries=v[a+9],explosion=v[a+10],flash=v[a+11])
                       for a in range(20,80,12)]
    for i,e in enumerate(result['enemies']):
        a=184+i*9
        e.update(vehicle_senses=v[a],moving_frames=v[a+1],maneuver=v[a+2],side=v[a+3],
                 mass=v[a+4],goal_x=v[a+5],goal_y=v[a+6],stalled=v[a+7],spawn_id=v[a+8])
    result['projectiles']=[dict(x=v[a]/4096,y=v[a+1]/4096,remaining=v[a+2],hostile=bool(v[a+3]))
                           for a in range(80,176,4) if v[a+2]]
    result.update(spawn_count=v[229],spawned=v[230],despawned=v[231],respawn_delay=v[232],
                  spawn_address=v[233],spawn_stride=v[234],spawn_range=v[235],despawn_range=v[236])
    return result

def weapon_state():
    v=[lib.emulator_read(weapon_address+4*i) for i in range(70)]
    return dict(selected=v[0],saw=bool(v[1]),saw_x=v[2]/4096,saw_y=v[3]/4096,
                guidance=v[4],explosions=v[5],shots=v[8:13],hits=v[13:18],
                missiles=[dict(x=v[a]/4096,y=v[a+1]/4096,vx=v[a+2]/4096,vy=v[a+3]/4096,
                               remaining=v[a+4],age=v[a+5],target=v[a+6],heading=v[a+7]/4096,explosion=v[a+8])
                          for a in (20,29)],
                traps=[dict(x=v[a]/4096,y=v[a+1]/4096,remaining=v[a+2],arm=v[a+3],explosion=v[a+4])
                       for a in range(40,70,5)])

def spawn_state():
    c=combat_state(); points=[]
    for i in range(c['spawn_count']):
        address=c['spawn_address']+i*c['spawn_stride']
        xy=lib.emulator_read(address)&0xffffffff
        timer=lib.emulator_read(address+4); flags=lib.emulator_read(address+8)&0xffffffff
        slot=flags&255
        points.append(dict(x=xy&65535,y=xy>>16,ready_at=timer,slot=slot if slot<128 else slot-256,hp=(flags>>8)&255))
    return points

def combat_pixel_mask(s):
    if s['map']<2 or s['mode']!=1: return lambda x,y:False
    c=combat_state(); boxes=[]
    for e in c['enemies']:
        if e['hp'] or e['explosion']:
            x=e['x']-s['camera_x']+120; y=e['y']-s['camera_y']+80
            boxes.append((x-20,y-26,x+20,y+20))
    for b in c['projectiles']:
        x=b['x']-s['camera_x']+120; y=b['y']-s['camera_y']+80
        boxes.append((x-12,y-12,x+12,y+12))
    return lambda x,y:any(l<=x<=r and top<=y<=bottom for l,top,r,bottom in boxes)
def check(name,condition,details=None):
    checks.append(dict(name=name,passed=bool(condition),details=details))
    print(('PASS' if condition else 'FAIL')+' '+name,details or '',flush=True)

def tap(key):
    step(0,2)
    step(key,2)
    return step(0,2)

def reset():
    # Select now opens settings. Restart tests through the actual map menu.
    selected=state()['map']
    if state()['mode']==1: tap(START)
    if state()['mode']==2: tap(SELECT)
    start_map(selected)
    step(0,48)
    return state()

def choose_map(index):
    assert state()['mode']==0
    for _ in range(4):
        if state()['map']==index: return state()
        tap(DOWN)
    raise RuntimeError('Map menu did not respond')

def start_map(index):
    choose_map(index); tap(A)
    for _ in range(100):
        s=step(0,30)
        if s['mode']==1: return s
    capture('loading-failed')
    raise RuntimeError('World loading did not finish')

def angle_delta(target,current):
    return (target-current+180)%360-180


def check_scene_pixels(name,art):
    s=state(); step()
    combat_mask=combat_pixel_mask(s)
    actual=Image.frombytes('RGBA',(240,160),C.string_at(lib.emulator_pixels(),240*160*4)).convert('RGB')
    matches=[]
    cx=s['x']-s['camera_x']+120; cy=s['y']-s['camera_y']+80
    for py in range(32,132,5):
        for px in range(3,238,5):
            if abs(px-cx)<30 and abs(py-cy)<30 or px>174 and py>94: continue
            if combat_mask(px,py): continue
            expected=art.getpixel((s['camera_x']-120+px,s['camera_y']-80+py))
            matches.append(max(abs(a-b) for a,b in zip(actual.getpixel((px,py)),expected))<=8)
    check(name,sum(matches)/len(matches)>=.99,sum(matches)/len(matches))

def main():
    assert lib.emulator_open(str(ROOT/'dist/dustline.gba').encode())
    s=step(0,90)
    capture('title')
    check('Boots to title',s['magic']==0x44555354 and s['mode']==0,s)
    check('Fixed wasteland is selected by default',s['map']==2,s)
    s=choose_map(0)
    check('Title can select the preserved circuit',s['map']==0,s)
    s=start_map(0)
    s=step(0,16)
    capture('driving')
    check('Starts driving',s['mode']==1 and s['setup']==1,s)
    if s['mode']!=1: raise RuntimeError('Scene initialization failed; see driving capture')
    x0=s['x']
    s=step(A,60)
    check('Throttle accelerates',s['x']>x0+50 and s['vx']>1.5,s)
    speed_before=math.hypot(s['vx'],s['vy'])
    s=step(0,35)
    check('Lift preserves but reduces momentum',0.2<math.hypot(s['vx'],s['vy'])<speed_before,s)

    reset()
    s=step(B,50)
    check('B reverses from rest',s['x']<START_X-15 and s['vx']<-.5,s)
    reset()
    step(A,40)
    s=step(A|LEFT,25)
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

    before=state(); tap(R); s=tap(L)
    check('Vehicle setup keys do not reset or change setup while driving',s['setup']==before['setup'] and
          s['lap_frames']>before['lap_frames'],s)
    reset()

    # Continuous throttle without steering reaches the outside wall safely.
    s=step(A,500)
    check('Roadside collision keeps car inside course',0<=s['x']<COURSE['width'] and s['collisions']>0,s)
    check('Finish cannot count without ordered gates',s['laps']==0 and s['best']==0,s)
    reset()

    # Follow the centerline using only normal controls. This is an integration
    # exercise, not a claim that a human will like this handling configuration.
    path=json.loads((OUT/'track_path.json').read_text())[:-1]
    idx=0
    max_cpu=0
    max_vblank=0
    max_upload=0
    minimum_match=1
    art=Image.open(OUT/'map2/converted.png').convert('RGB')
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
        max_vblank=max(max_vblank,s['vblank'])
        max_upload=max(max_upload,s['uploaded_bytes'])
        surface_seen.add(s['surface'])
        if tick%120==0:
            # Compare stable background pixels away from UI and the car.
            # mGBA's completed pixel buffer is the frame whose simulation state
            # was sampled before step(); CPU telemetry can already describe the
            # following frame, waiting for the next VBlank.
            now=s
            actual=Image.frombytes('RGBA',(240,160),C.string_at(lib.emulator_pixels(),240*160*4)).convert('RGB')
            cx=now['x']-now['camera_x']+120; cy=now['y']-now['camera_y']+80
            errors=[]
            for py in range(32,132,5):
                for px in range(3,238,5):
                    if abs(px-cx)<23 and abs(py-cy)<23 or px>174 and py>94: continue
                    expected=art.getpixel((now['camera_x']-120+px,now['camera_y']-80+py))
                    errors.append(max(abs(a-b) for a,b in zip(actual.getpixel((px,py)),expected))<=8)
            match=sum(errors)/len(errors)
            if match<minimum_match:
                minimum_match=match
                if match<.95: capture('map2/streaming-mismatch')
        if 500<s['x']<580 and 540<s['y']<650 and not captured_dirt:
            capture('map2/bridge'); captured_dirt=True
        if tick%6==0 and tick<2400:
            raw=C.string_at(lib.emulator_pixels(),240*160*4)
            frames.append(Image.frombytes('RGBA',(240,160),raw).convert('RGB').resize((480,320),Image.Resampling.NEAREST))
        if s['laps']>0:
            capture('lap-complete')
            break
    s=state()
    check('Can drive a full lap with ordered checkpoints',s['laps']>=1 and s['best']>0,s)
    check('Lap stays on road or curb shoulder',surface_seen.issubset({0,1}) and 1 in surface_seen,sorted(surface_seen))
    check('Streamed background matches source throughout lap',minimum_match>=.95,minimum_match)
    check('Tile uploads fit within VBlank',max_vblank<1,dict(max_vblank=max_vblank,max_upload=max_upload))
    check('Sprite VRAM has room for four more car frames',s['sprite_free_bytes']>=4*512,s['sprite_free_bytes'])
    check('Frame budget stays below one refresh',max_cpu<1 and s['missed']==0,dict(max_cpu=max_cpu,missed=s['missed']))
    if frames:
        frames[0].save(OUT/'demo.gif',save_all=True,append_images=frames[1:],duration=100,loop=0,optimize=True)
    test_open_world()
    from test_wasteland import run
    import sys
    run(sys.modules[__name__])
    from test_settings import run as settings_tests
    settings_tests(sys.modules[__name__])
    from test_combat import run as combat_tests
    combat_tests(sys.modules[__name__])
    from test_traffic import run as traffic_tests
    traffic_tests(sys.modules[__name__])
    from test_spawning import run as spawning_tests
    spawning_tests(sys.modules[__name__])
    from test_weapons import run as weapon_tests
    weapon_tests(sys.modules[__name__])
    lib.emulator_close()


def test_open_world():
    # Repeated switching exercises palette, tile cache invalidation and HUDs.
    tap(START); s=tap(SELECT)
    check('Pause Select returns to map menu',s['mode']==0,s)
    start_map(1); s=step(0,20)
    info=json.loads((OUT/'open_world/report.json').read_text())
    check('Open world loads from menu at its own spawn',s['map']==1 and s['mode']==1 and
          abs(s['x']-info['start'][0])<1 and abs(s['y']-info['start'][1])<1,s)
    capture('open_world/start')
    check('Commons VRAM allocation matches the exhaustive capacity audit',
          s['tile_capacity']==info['tile_slots'] and s['bg_bytes']==info['resident_terrain_vram_bytes']+6144,s)
    check('Commons releases at least 12 KiB of background VRAM',s['bg_bytes']<=53248-12288,s['bg_bytes'])
    check('Repeated terrain cells share actual resident tiles',0<s['unique_tiles']<31*21,s['unique_tiles'])
    if s['map']!=1 or s['mode']!=1:
        raise RuntimeError('Map switch failed; stop dependent driving checks')
    check('Open world is larger than comparison circuit',s['width']>COURSE['width'],s['width'])
    check('Expanded world has sixteen times the 4096-square area',s['width']==16384 and s['height']==16384,s)
    check('Runtime actually decodes compressed chunks',s['chunk_decodes']>0,s)
    check('Decoded chunk cache is bounded to nine chunks plus metadata',
          s['chunk_cache_bytes']==4652,s['chunk_cache_bytes'])
    initial_loads=s['chunk_loads']; idle=step(0,90)
    check('Stationary scene reuses decoded chunks',idle['chunk_loads']==initial_loads,idle)
    route=info['route']
    path=[]
    for a,b in zip(route,route[1:]):
        count=max(1,round(math.dist(a,b)/6))
        path.extend([(a[0]+(b[0]-a[0])*i/count,a[1]+(b[1]-a[1])*i/count) for i in range(count)])
    path.append(route[-1])
    idx=0; surfaces=set(); chunks=set(); districts=set(); max_cpu=0; max_vblank=0; minimum_match=1
    max_x=0; max_y=0; minimap_correct=True
    art=WorldReference(OUT/'open_world')
    captured=set()
    for tick in range(70000):
        s=state()
        idx=min(range(max(0,idx-3),min(len(path),idx+24)),
                key=lambda k:math.dist(path[k],(s['x'],s['y'])))
        goal=min(len(path)-1,idx+5)
        wanted=math.degrees(math.atan2(path[goal][1]-s['y'],path[goal][0]-s['x']))%360
        error=angle_delta(wanted,s['heading']); speed=math.hypot(s['vx'],s['vy'])
        keys=LEFT if error<-3 else RIGHT if error>3 else 0
        target=2.4 if abs(error)<12 else 1.65 if abs(error)<35 else .8
        if speed<target: keys|=A
        step(keys)
        surfaces.add(s['surface']); chunks.add(s['chunk'])
        districts.add((int(s['x'])//4096,int(s['y'])//4096))
        max_x=max(max_x,s['x']); max_y=max(max_y,s['y'])
        minimap_correct &= (s['minimap_x']==86+int((int(s['x'])-s['radar_x'])/12) and
                            s['minimap_y']==46+int((int(s['y'])-s['radar_y'])/12) and
                            abs(s['x']-s['radar_x'])<128 and abs(s['y']-s['radar_y'])<128)
        max_cpu=max(max_cpu,s['cpu']); max_vblank=max(max_vblank,s['vblank'])
        if tick%90==0:
            actual=Image.frombytes('RGBA',(240,160),C.string_at(lib.emulator_pixels(),240*160*4)).convert('RGB')
            cx=s['x']-s['camera_x']+120; cy=s['y']-s['camera_y']+80
            matches=[]
            for py in range(32,132,5):
                for px in range(3,238,5):
                    if abs(px-cx)<30 and abs(py-cy)<30 or px>174 and py>94: continue
                    expected=art.getpixel((s['camera_x']-120+px,s['camera_y']-80+py))
                    matches.append(max(abs(a-b) for a,b in zip(actual.getpixel((px,py)),expected))<=8)
            minimum_match=min(minimum_match,sum(matches)/len(matches))
        for name,condition in [('junction',960<s['x']<1040 and s['y']>1490),
                               ('dirt',s['surface']==2 and s['x']>1300),
                               ('shore',1520<s['x']<1600 and 1200<s['y']<1300),
                               ('garage',s['x']<660 and 1400<s['y']<1480),
                               ('east-connection',2010<s['x']<2090 and s['y']<2048),
                               ('southeast',s['x']>2800 and s['y']>3200),
                               ('southwest',s['x']<1400 and s['y']>3200),
                               ('far-east',s['x']>15000 and s['y']<2048),
                               ('far-southeast',s['x']>15000 and s['y']>15000),
                               ('far-southwest',s['x']<1400 and s['y']>15000)]:
            if condition and name not in captured: capture('open_world/'+name); captured.add(name)
        if idx>=len(path)-4 and math.dist((s['x'],s['y']),path[-1])<24: break
        if tick and tick%6000==0:
            print('Long-drive progress',dict(frames=tick,x=round(s['x']),y=round(s['y']),
                  sectors=len(districts),decodes=s['chunk_decodes'],missed=s['missed']),flush=True)
    s=state()
    check('Open-world route traverses roads, dirt shortcut and garage yard',idx>=len(path)-4,
          dict(progress=idx,total=len(path),frames=tick+1,state=s))
    check('Open world has drivable road, dirt and grass',surfaces=={0,1,2},sorted(surfaces))
    check('Open-world route crosses multiple world chunks',len(chunks)>=8,len(chunks))
    check('Driving reaches all sixteen connected 4096px sectors',
          districts=={(x,y) for y in range(4) for x in range(4)},sorted(districts))
    check('Both world coordinates exceed 15000px without wrapping',max_x>15000 and max_y>15000,[max_x,max_y])
    check('Local radar follows the car across the full comparison world',minimap_correct)
    check('Compressed chunks are streamed beyond the nine-slot working set',
          s['chunk_decodes']>9 and len(chunks)>24,dict(chunks=len(chunks),decodes=s['chunk_decodes']))
    check('Open-world route avoids solid scenery',s['collisions']==0,s)
    check('Open world does not award circuit laps',s['laps']==0 and s['gate']==0,s)
    check('Open-world streamed pixels match compiled map',minimum_match>=.95,minimum_match)
    check('Open-world CPU and VBlank fit a frame',max_cpu<1 and max_vblank<1 and s['missed']==0,
          dict(cpu=max_cpu,vblank=max_vblank,missed=s['missed']))
    check('Open-world graphics leave space for four extra cars',s['sprite_free_bytes']>=2048,s['sprite_free_bytes'])
    reset(); s=step(A,7500)
    capture('open_world/boundary')
    check('Open-world solid boundary stops continuous throttle',
          s['collisions']>0 and info['width']-128<s['x']<info['width']-48,s)
    reset(); tap(START); before=state(); after=step(A|LEFT,60)
    check('Open-world pause freezes simulation',all(before[k]==after[k] for k in ('x','y','lap_frames')),after)
    tap(SELECT); start_map(0); s=step(0,20)
    check('Switching back restores circuit spawn and dimensions',s['map']==0 and s['width']==1280 and
          abs(s['x']-START_X)<1 and abs(s['y']-START_Y)<1,s)
    check('Detailed circuit receives its larger cache again',s['tile_capacity']==672,s)
    check('Switching to circuit clears the decoded world cache',s['chunk_loads']==0,s)
    capture('open_world/circuit-return')
    check_scene_pixels('Returning to circuit restores its actual graphics',
                       Image.open(OUT/'map2/converted.png').convert('RGB'))
    tap(START); tap(SELECT); start_map(1); s=step(0,20)
    check('Second world load resets state',s['map']==1 and
          abs(s['x']-info['start'][0])<1 and s['collisions']==0,s)
    check_scene_pixels('Second world load has no stale circuit graphics',art)
    # Drive to the western lake edge, then deliberately try to enter the water.
    # This also brings the camera into the upper half of the chunk grid.
    goals=[(960,1536),(1024,1472),(1024,1008),(1072,960),(1248,960),(1408,960)]
    goal=0
    for tick in range(2200):
        s=state(); gx,gy=goals[goal]
        if math.dist((s['x'],s['y']),(gx,gy))<22 and goal<len(goals)-1:
            goal+=1; gx,gy=goals[goal]
        error=angle_delta(math.degrees(math.atan2(gy-s['y'],gx-s['x']))%360,s['heading'])
        keys=LEFT if error<-3 else RIGHT if error>3 else 0
        if math.hypot(s['vx'],s['vy'])<(2.0 if abs(error)<20 else .9): keys|=A
        step(keys)
        if s['collisions']: break
    s=state(); capture('open_world/lake')
    check('Lake water blocks the car at the visible western shoreline',goal==len(goals)-1 and
          s['collisions']>0 and 1250<s['x']<1280 and 920<s['y']<1000,s)
    check_scene_pixels('Lake region streams correctly',art)
    check('No missed frames through later resets, boundaries and scene switches',state()['missed']==0,state())

if __name__=='__main__':
    try:
        main()
    finally:
        report=dict(rom_sha256=hashlib.sha256((ROOT/'dist/dustline.gba').read_bytes()).hexdigest(),
                    emulator='libmGBA (Debian bookworm)',checks=checks)
        (OUT/'test-results.json').write_text(json.dumps(report,indent=2),encoding='utf8')
        start=next((i for i,c in enumerate(checks) if c['name']=='Fixed wasteland uses reproducible shared generator'),len(checks))
        (OUT/'wasteland/test-results.json').write_text(json.dumps(dict(report,checks=checks[start:]),indent=2),encoding='utf8')
        combat_start=next((i for i,c in enumerate(checks) if c['name']=='Nearby three-HP enemies spawn on reachable clear floor'),len(checks))
        if combat_start<len(checks):
            (OUT/'combat/test-results.json').write_text(json.dumps(dict(report,checks=checks[combat_start:]),indent=2),encoding='utf8')
        spawning_start=next((i for i,c in enumerate(checks) if c['name']=='World-wide encounter anchors are reachable, sparse and lightweight'),len(checks))
        if spawning_start<len(checks):
            (OUT/'spawning/test-results.json').write_text(json.dumps(dict(report,checks=checks[spawning_start:]),indent=2),encoding='utf8')
        traffic_start=next((i for i,c in enumerate(checks) if c['name']=='Stationary player cannot make enemy drivers permanently park'),len(checks))
        if traffic_start<len(checks):
            (OUT/'traffic/test-results.json').write_text(json.dumps(dict(report,checks=checks[traffic_start:]),indent=2),encoding='utf8')
    if not checks or not all(c['passed'] for c in checks):
        raise SystemExit(1)
