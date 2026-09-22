"""Select settings and four zoom levels, using only emulated joypad input."""
import json
from test_wasteland import Reference,check_hud_radar


def run(t):
    (t.OUT/'settings').mkdir(exist_ok=True)
    def menu():
        if t.state()['mode']==1: t.tap(t.START)
        if t.state()['mode']==2: t.tap(t.SELECT)
        assert t.state()['mode']==0

    def select_zoom(level,exit_key=None):
        if t.state()['mode']==3:t.tap(t.B)
        before=t.state(); s=t.tap(t.SELECT)
        t.check('Select opens settings, not reset',s['mode']==6 and s['generations']==before['generations'] and
                s['seed']==before['seed'] and abs(s['x']-before['x'])<12 and abs(s['y']-before['y'])<12,s)
        frozen=t.step(0,40)
        t.check('Settings pause car, velocity, heading and run timer',all(frozen[k]==s[k] for k in
                ('x','y','vx','vy','heading','lap_frames','seed','signature')),frozen)
        for _ in range(4):
            current=t.state()['zoom_level']
            if current==level: break
            t.tap(t.RIGHT if current<level else t.LEFT)
        t.capture(f'settings/map-{s["map"]}-menu-{1<<level}x')
        t.tap(t.A if exit_key is None else exit_key); after=t.step(0,30)
        t.check(f'Map {s["map"]} settings retain correct minimap scale without regenerating map',
                after['mode']==1 and after['zoom_level']==level and after['radar_scale']==(128>>level if s['map']>=2 else 12*(1<<level)) and
                after['generations']==s['generations'] and after['signature']==s['signature'],after)
        return after

    menu(); initial=t.start_map(2); ref=Reference(t,initial['seed'])
    t.check('Wasteland opens at the widest player-centered zoom',initial['radar_scale']==128,initial)
    for level,key in enumerate((t.SELECT,t.A,t.B,t.START)):
        s=select_zoom(level,key)
        check_hud_radar(t,ref,f'{1<<level}x')
        t.capture(f'settings/radar-{1<<level}x')
        t.check(f'{1<<level}x keeps the same graphics allocation',s['bg_bytes']==initial['bg_bytes'] and
                s['free_ewram']==initial['free_ewram'],s)
        baseline=t.state()['missed'];peak=0
        for _ in range(100):
            moving=t.step(t.A);peak=max(peak,moving['cpu'])
            if moving['mode']==3:t.tap(t.B)
        t.check(f'Wasteland driving at {1<<level}x stays within a frame',
                peak<1 and t.state()['missed']==baseline,dict(cpu=peak,missed=t.state()['missed'],baseline=baseline))
        for _ in range(80):
            t.step(t.B)
            if t.state()['mode']==3:t.tap(t.B)
        t.step(0,3)
        check_hud_radar(t,ref,f'{1<<level}x after movement')
    # Restart at the original spawn for the town-entry and held-button tests.
    menu();initial=t.start_map(2)
    t.tap(t.SELECT); t.tap(t.RIGHT)
    t.check('Right clamps at maximum enlargement',t.state()['zoom_level']==3)
    for _ in range(6): t.tap(t.LEFT)
    t.check('Left clamps at the widest zoom',t.state()['zoom_level']==0)
    t.tap(t.B); t.step(0,24)
    # Moving entry makes an accidental spawn reset or velocity loss detectable.
    t.step(t.A,28); before=t.state(); t.tap(t.SELECT); entered=t.state(); t.step(0,80)
    t.check('Opening settings while moving does not teleport or alter velocity',entered['mode']==6 and
            entered['x']>initial['x']+8 and abs(entered['x']-before['x'])<12 and
            all(t.state()[k]==entered[k] for k in ('x','y','vx','vy','heading','lap_frames')),entered)
    for _ in range(3): t.tap(t.RIGHT)
    t.step(t.A,28); held=t.state()
    t.check('Held confirm cannot accelerate when returning from settings',held['mode']==1 and
            held['x']==entered['x'] and held['y']==entered['y'] and held['vx']==entered['vx'],held)
    t.step(0,2)
    for _ in range(360):
        if t.step(t.A)['mode']==3: break
    assert t.state()['mode']==3
    t.step(0,4); t.tap(t.UP); t.tap(t.A); t.step(0,12)
    town=t.state(); assert town['mode']==4
    t.tap(t.SELECT); s=t.state()
    t.check('Settings also opens inside town without loading the overworld',s['mode']==6 and s['tile_capacity']==0,s)
    t.tap(t.LEFT); t.tap(t.A); s=t.step(0,10)
    t.check('Closing town settings returns to town, not directly to driving',s['mode']==4 and s['zoom_level']==2 and
            all(s[k]==town[k] for k in ('x','y','seed','generations','setup')),s)
    t.tap(t.A); s=t.step(0,45)
    t.check('Town return retains zoom and saved position',s['mode']==1 and s['radar_scale']==32 and
            all(s[k]==town[k] for k in ('x','y','seed','generations')),s)
    menu(); random=t.start_map(3)
    t.check('Random map retains the selected image zoom',random['zoom_level']==2 and random['radar_scale']==32,random)
    # Wider Commons views used to churn compressed chunks on each sample.
    # Exercise every zoom while driving, including full-scene switches.
    for map_index in (1,0):
        menu(); t.start_map(map_index)
        for level in range(4):
            select_zoom(level)
            baseline=t.state()['missed']; peak=0
            for _ in range(100):
                s=t.step(t.A); peak=max(peak,s['cpu'])
            t.check(f'Map {map_index} driving at {1<<level}x stays within a frame',
                    peak<1 and s['missed']==baseline,dict(cpu=peak,missed=s['missed'],baseline=baseline))
            t.capture(f'settings/map-{map_index}-{1<<level}x')
    t.check('No missed driving frames across all settings operations',t.state()['missed']==0,t.state())


if __name__=='__main__':
    import test_rom as t
    assert t.lib.emulator_open(str(t.ROOT/'dist/dustline.gba').encode())
    t.step(0,90)
    try: run(t)
    finally:
        t.lib.emulator_close()
        (t.OUT/'settings/test-results.json').write_text(json.dumps(dict(
            rom_sha256=t.hashlib.sha256((t.ROOT/'dist/dustline.gba').read_bytes()).hexdigest(),checks=t.checks),indent=2))
    if not all(c['passed'] for c in t.checks): raise SystemExit(1)
