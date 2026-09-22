"""Weapon acceptance against the actual ROM; controller input and read-only telemetry."""
import hashlib
import json
import math


def run(t):
    (t.OUT/'weapons').mkdir(exist_ok=True)
    peak=0
    def step(keys=0,frames=1):
        nonlocal peak
        for _ in range(frames):
            s=t.step(keys);peak=max(peak,s['cpu'])
        return s
    def fresh(weapon=0):
        if t.state()['mode']==3:t.tap(t.B)
        if t.state()['mode']==6:t.tap(t.B)
        if t.state()['mode']==1:t.tap(t.START)
        if t.state()['mode']==2:t.tap(t.SELECT)
        t.start_map(0)
        for _ in range(weapon):t.tap(t.L)
        assert t.weapon_state()['selected']==weapon
    fresh();setup=t.state()['setup']
    step(t.L,18);held=t.weapon_state()['selected'];step()
    order=[held]
    for _ in range(4):t.tap(t.L);order.append(t.weapon_state()['selected'])
    t.check('L cycles five weapons once per press without changing vehicle setup',
            order==[1,2,3,4,0] and t.state()['setup']==setup,order)

    fresh(2);before=t.state();step(t.R);w=t.weapon_state();c=t.combat_state()
    shots=[b for b in c['projectiles'] if not b['hostile']]
    t.check('Side guns fire both perpendicular directions together',len(shots)==2 and w['shots'][2]==2 and
            all(abs(b['x']-before['x'])<1 for b in shots) and
            sorted(round(b['y']-before['y']) for b in shots)==[-20,20],dict(shots=shots,weapon=w))
    step(0,2);t.capture('weapons/sides')
    step(t.R,240)
    t.check('Side salvos remain in the bounded shared projectile pool',t.combat_state()['bullets']<=24 and
            t.weapon_state()['shots'][2]>10,t.weapon_state()['shots'])

    fresh(1);start=t.state();step(t.R);w=t.weapon_state()
    t.check('Chainsaw is a short circle ahead and does not create bullets',w['saw'] and
            abs(w['saw_x']-start['x']-24)<1 and abs(w['saw_y']-start['y'])<1 and
            not [b for b in t.combat_state()['projectiles'] if not b['hostile']],w)
    t.capture('weapons/chainsaw')
    history=[]
    for _ in range(150):
        step(t.A|t.R);history.append(t.combat_state()['enemies'][0]['hp'])
        if t.weapon_state()['hits'][1]:t.capture('weapons/chainsaw-hit')
        if t.combat_state()['kills']:break
    t.check('Chainsaw deals two HP per contact pulse and destroys a nearby car',
            1 in history and 0 in history and t.weapon_state()['hits'][1]>=2,dict(hp=history,weapon=t.weapon_state()))
    step();t.check('Releasing R stops the chainsaw immediately',not t.weapon_state()['saw'])

    fresh();step(t.R,100)  # Remove the point-blank starter so guidance has room to turn.
    for _ in range(3):t.tap(t.L)
    step(t.R);launched=t.weapon_state();m=launched['missiles'][0]
    t.check('Missile launches ahead before acquiring a target',m['remaining']>0 and m['age']==1 and
            m['target']==-1 and abs(m['vx']-4)<.01 and abs(m['vy'])<.01,launched)
    t.capture('weapons/missile-launch')
    step(0,7);w=t.weapon_state();m=w['missiles'][0];enemies=[e for e in t.combat_state()['enemies'] if e['hp']]
    # Guidance happened immediately before the last 4px of travel.
    launch_at=(m['x']-m['vx'],m['y']-m['vy'])
    nearest=min(enemies,key=lambda e:math.dist(launch_at,(e['x'],e['y'])))['spawn_id']
    t.check('Missile acquires the closest living enemy after its launch delay',w['guidance']==1 and m['target']==nearest,w)
    step(0,5);g=t.weapon_state()['guidance'];step();w=t.weapon_state()
    t.check('Homing direction is refreshed every six ticks',g==1 and w['guidance']==2,w)
    t.capture('weapons/missile-homing')
    max_live=0
    for frame in range(240):
        step(t.R);w=t.weapon_state();max_live=max(max_live,sum(m['remaining']>0 for m in w['missiles']))
        if frame==60:t.capture('weapons/missiles')
    t.check('Homing missiles deal lethal damage and never exceed two active rockets',
            w['hits'][3]>0 and t.combat_state()['kills']>0 and max_live<=2,dict(max_live=max_live,weapon=w))

    fresh(4);before=t.state();step(t.R);w=t.weapon_state();trap=w['traps'][0]
    location=(trap['x'],trap['y'])
    t.check('Trap is laid behind the car with a short arming delay',trap['remaining']>0 and trap['arm']>0 and
            abs(trap['x']-before['x']+22)<1 and abs(trap['y']-before['y'])<1,w)
    step(0,20);w=t.weapon_state()
    t.check('Trap remains stationary and does not trigger on its owner',
            (w['traps'][0]['x'],w['traps'][0]['y'])==location and not w['traps'][0]['arm'] and
            w['traps'][0]['remaining']>0 and not w['explosions'],w)
    t.capture('weapons/trap-armed')
    # Drive east, leaving mines for pursuing traffic, then circle locally.
    max_traps=0
    for frame in range(650):
        s=step(t.R | (t.A if frame<95 or frame>200 else 0) | (t.LEFT if frame>200 else 0))
        if s['mode']==3:t.tap(t.B)
        w=t.weapon_state();max_traps=max(max_traps,sum(p['remaining']>0 for p in w['traps']))
        if w['explosions']:
            step(0,2)  # Let VBlank present the newly created blast before capture.
            t.capture('weapons/trap-explosion');break
    t.check('Enemy contact detonates a stationary trap and applies blast damage',
            w['explosions']>0 and w['hits'][4]>0,dict(max_traps=max_traps,weapon=w))
    t.check('Trap pool never exceeds six objects',max_traps<=6,max_traps)

    fresh(4);step(t.R,4);step();t.tap(t.SELECT);frozen=t.weapon_state();step(t.R|t.L,45)
    t.check('Settings pauses weapon selection, traps and all weapon timers',t.weapon_state()==frozen)
    t.tap(t.B);step(0,3);t.tap(t.START);frozen=t.weapon_state();step(t.R|t.L,45)
    t.check('Pause freezes weapons and selection',t.weapon_state()==frozen)
    t.tap(t.START);step()
    # Cycle while a trap remains: old deployed weapons continue independently.
    t.tap(t.L);t.check('Switching weapon keeps an already deployed trap',
            t.weapon_state()['selected']==0 and any(p['remaining'] for p in t.weapon_state()['traps']))
    fresh();t.check('New runs reset the loadout and clear every weapon pool',
            t.weapon_state()['selected']==0 and not any(p['remaining'] for p in t.weapon_state()['traps']) and
            not any(m['remaining'] for m in t.weapon_state()['missiles']))
    t.check('New weapons fit the measured driving frame budget',peak<1 and t.state()['missed']==0,
            dict(cpu=peak,missed=t.state()['missed'],ram=t.combat_state()['ram']))


if __name__=='__main__':
    import test_rom as t
    assert t.lib.emulator_open(str(t.ROOT/'dist/dustline.gba').encode())
    t.step(0,90)
    try:run(t)
    finally:
        t.lib.emulator_close()
        (t.OUT/'weapons/test-results.json').write_text(json.dumps(dict(
            rom_sha256=hashlib.sha256((t.ROOT/'dist/dustline.gba').read_bytes()).hexdigest(),checks=t.checks),indent=2))
    raise SystemExit(0 if t.checks and all(c['passed'] for c in t.checks) else 1)
