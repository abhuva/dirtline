"""Basic combat acceptance checks against the real ROM; joypad writes only."""
import json
import math
from test_wasteland import Reference

def run(t):
    (t.OUT/'combat').mkdir(exist_ok=True)
    def menu():
        if t.state()['mode']==3: t.tap(t.B)
        if t.state()['mode']==1: t.tap(t.START)
        if t.state()['mode']==2: t.tap(t.SELECT)
        assert t.state()['mode']==0
    menu(); t.start_map(2)
    initial=t.combat_state(); ref=Reference(t,t.state()['seed'])
    t.capture('combat/encounter')
    t.check('Nearby three-HP enemies spawn on reachable clear floor',1<=initial['living']<=5 and
            all(e['hp']==3 and not ref.wall(int(e['x'])//128,int(e['y'])//128) and
                ref.surface(int(e['x']),int(e['y']))!=3 for e in initial['enemies'] if e['hp']),initial)
    t.check('Player starts at 100 HP with test invincibility',initial['hp']==100 and initial['invincible']==1,initial)
    setup=t.state()['setup']; hp_history=[]; peak=0; first_dead=None; gun_geometry=True
    for frame in range(100):
        s=t.step(t.R); c=t.combat_state(); peak=max(peak,s['cpu'])
        hp_history.append(c['enemies'][0]['hp'])
        for b in c['projectiles']:
            gun_geometry &= 0<b['remaining']<=120
            if not b['hostile']:
                gun_geometry &= 0<b['x']-s['x']<=135 and abs(b['y']-s['y'])<1
        if frame==8: t.capture('combat/gunfire')
        if c['enemies'][0]['hp']==0 and first_dead is None:
            first_dead=frame
        if first_dead is not None and frame==first_dead+2: t.capture('combat/destruction')
    t.check('R fires forward without changing vehicle setup',t.state()['setup']==setup and c['player_shots']>=8,c)
    t.check('Player gun travels forward within half-screen range and projectile pool stays bounded',
            gun_geometry and c['bullets']<=24 and c['player_shots']==10,c)
    t.check('Enemy takes three distinct hits then is destroyed',all(h in hp_history for h in (2,1,0)) and
            c['kills']>=1 and c['hits']>=3 and c['living']<=5,dict(history=hp_history,combat=c))
    t.step(0,200); c=t.combat_state(); t.capture('combat/enemy-fire')
    t.check('Enemies drive toward the player and fire',c['enemy_shots']>0 and
            any(math.dist((e['x'],e['y']),(old['x'],old['y']))>15 for e,old in zip(c['enemies'],initial['enemies']) if e['hp']),c)
    t.check('Enemy bullets hit but do not reduce invincible player HP',c['player_hits']>0 and c['hp']==100,c)
    dead_point=t.spawn_state()[initial['enemies'][0]['spawn_id']]
    t.check('Destroyed encounter remains empty during its cooldown',dead_point['slot']==-1 and
            dead_point['hp']==0 and dead_point['ready_at']>c['ticks'],dead_point)
    t.tap(t.SELECT); frozen=t.combat_state(); t.step(t.R,70); later=t.combat_state()
    t.check('Settings freezes enemies, projectiles and weapon timers',t.state()['mode']==6 and
            all(later[k]==frozen[k] for k in frozen if not k.endswith('_cpu')),later)
    t.step(0,3); t.tap(t.SELECT)
    t.tap(t.START); frozen=t.combat_state(); t.step(t.R,60)
    t.check('Pause freezes combat',all(t.combat_state()[k]==frozen[k] for k in frozen if not k.endswith('_cpu')),
            dict(state=t.state(),before=frozen,after=t.combat_state()))
    t.step(0,3); t.tap(t.START)
    # First outpost is east of spawn. Scene unloading must not resurrect kills.
    for _ in range(360):
        if t.step(t.A)['mode']==3: break
    if t.state()['mode']!=3:
        t.capture('combat/approach-failed')
        raise RuntimeError(f'Town approach failed: {t.state()}')
    saved=t.combat_state(); t.tap(t.UP); t.tap(t.A); t.step(0,10); town=t.combat_state()
    t.check('Town unloads combat graphics and clears travelling bullets',t.state()['mode']==4 and
            town['graphics']==0 and town['bullets']==0,town)
    t.tap(t.R); t.step(0,20)
    t.check('R in town only changes setup, never fires',t.combat_state()['player_shots']==town['player_shots'])
    t.tap(t.A); t.step(0,60); returned=t.combat_state()
    t.check('Town return preserves enemy deaths and HP',t.state()['mode']==1 and returned['kills']==saved['kills'] and
            [e['hp'] for e in returned['enemies']]==[e['hp'] for e in saved['enemies']] and returned['graphics']==1,returned)
    # Drive into nearby canyon boundaries; enemies must use look-ahead and stay
    # outside solid terrain, with recovery rather than constant repeated impacts.
    solid_samples=0; enemy_frames=0; frames=[]; slow=[]; last_missed=t.state()['missed']
    for frame in range(900):
        keys=t.A | (t.LEFT if 180<=frame<270 or 550<=frame<630 else 0) | t.R
        s=t.step(keys); c=t.combat_state(); peak=max(peak,s['cpu'])
        if s['missed']>last_missed or s['cpu']>.9:
            slow.append(dict(frame=frame,state=s,combat={k:c[k] for k in ('ticks','bullets','living','avoidance','enemy_shots','simulation_cpu','view_cpu')}))
        last_missed=s['missed']
        if s['mode']==3: t.tap(t.B)
        for e in c['enemies']:
            if e['hp']:
                enemy_frames+=1
                solid_samples+=ref.surface(int(e['x']),int(e['y']))==3
        if frame%30==0: frames.append(t.capture(f'combat/drive-{frame:03d}'))
    frames[0].resize((480,320)).save(t.OUT/'combat/drive.gif',save_all=True,
        append_images=[im.resize((480,320)) for im in frames[1:]],duration=500,loop=0)
    t.check('AI remains on drivable ground',solid_samples==0,dict(samples=enemy_frames,solid=solid_samples))
    t.check('AI look-ahead is exercised without constant impacts',c['avoidance']>0 and c['collisions']<60,c)
    t.check('Projectiles expire at finite range',c['expired']>0,c)
    t.check('Pooled combat fits the measured frame budget',peak<1 and t.state()['missed']==0,
            dict(cpu=peak,missed=t.state()['missed'],ram=c['ram'],sprite_free=t.state()['sprite_free_bytes'],slow=slow))
    menu(); t.start_map(3); random=t.combat_state()
    t.check('Random wasteland starts fresh nearby encounters',1<=random['living']<=5 and random['kills']==0 and
            random['hp']==100,random)
    menu(); t.start_map(0); t.step(t.R,90); comparison=t.combat_state()
    t.check('Comparison circuit remains combat-free',comparison['living']==0 and comparison['graphics']==0 and
            comparison['player_shots']==0,comparison)

if __name__=='__main__':
    import test_rom as t
    assert t.lib.emulator_open(str(t.ROOT/'dist/dustline.gba').encode())
    t.step(0,90)
    try: run(t)
    finally:
        t.lib.emulator_close()
        (t.OUT/'combat/test-results.json').write_text(json.dumps(dict(
            rom_sha256=t.hashlib.sha256((t.ROOT/'dist/dustline.gba').read_bytes()).hexdigest(),checks=t.checks),indent=2))
    if not all(c['passed'] for c in t.checks): raise SystemExit(1)
