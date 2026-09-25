"""Fixed garage mounts, trigger groups and curved energy-HUD acceptance."""
import hashlib
import json


def run(t):
    (t.OUT/'weapons').mkdir(exist_ok=True)
    peak=0

    def step(keys=0,frames=1):
        nonlocal peak
        for _ in range(frames):
            state=t.step(keys);peak=max(peak,state['cpu'])
        return state

    def fresh():
        if t.state()['mode']==3:t.tap(t.B)
        if t.state()['mode']==6:t.tap(t.B)
        if t.state()['mode']==1:t.tap(t.START)
        if t.state()['mode']==2:t.tap(t.SELECT)
        t.start_map(0)
        state=t.weapon_state()
        assert (state['front'],state['side'],state['special'])==(0,2,3)

    fresh();baseline_missed=t.state()['missed']
    initial=t.weapon_state();step(t.R);grouped=t.weapon_state()
    friendly=[p for p in t.combat_state()['projectiles'] if not p['hostile']]
    t.check('R fires the fitted front gun and both side guns together',
            grouped['shots']==[1,0,2,0,0] and grouped['energy']==initial['energy']-2 and
            len(friendly)==3,grouped)
    side_shots=[p for p in friendly if abs(p['x']-t.state()['x'])<1]
    t.check('The side mount fires in opposite perpendicular directions',
            len(side_shots)==2 and sorted(round(p['y']-t.state()['y']) for p in side_shots)==[-20,20],side_shots)

    before=t.combat_state()['ticks'];fittings=t.weapon_state()
    step(t.L,24);after=t.weapon_state()
    t.check('L has no map-play loadout function and does not pause simulation',
            t.combat_state()['ticks']==before+24 and
            (after['front'],after['side'],after['special'])==
            (fittings['front'],fittings['side'],fittings['special']),after)

    fresh();before=t.state();step(t.B);special=t.weapon_state();missile=special['missiles'][0]
    t.check('B independently fires the fitted top special without firing normal mounts',
            special['shots'][:3]==[0,0,0] and special['shots'][3:]==[1,0] and
            special['energy']==92 and missile['remaining']>0 and
            18<missile['x']-before['x']<21 and abs(missile['y']-before['y'])<1,special)
    step(0,7);guided=t.weapon_state()['missiles'][0]
    t.check('The default garage missile launches straight, then acquires a target',
            guided['remaining']>0 and guided['target']>=0 and t.weapon_state()['guidance']>0,
            dict(missile=guided,weapon=t.weapon_state()))
    t.capture('weapons/missile-homing')

    fresh();step(t.R|t.B,170);energy=t.weapon_state();image=t.capture('weapons/curved-energy-arc')
    amber=(255,206,66)
    amber_pixels=[(x,y) for y in range(140,157) for x in range(181,238) if image.getpixel((x,y))==amber]
    mirrored=sum((image.getpixel((209-d,y))==amber)==(image.getpixel((209+d,y))==amber)
                 for y in range(140,157) for d in range(1,26))
    t.check('Energy is a centered amber segmented arc along the minimap bottom',
            energy['energy']<60 and amber_pixels and mirrored>=400 and
            min(y for _,y in amber_pixels)>=140,
            dict(energy=energy['energy'],amber_pixels=len(amber_pixels),mirrored=mirrored))

    step();t.tap(t.SELECT);frozen=t.weapon_state();step(t.R|t.L|t.B,45)
    after_settings=t.weapon_state()
    gameplay_fields=lambda value:{key:item for key,item in value.items() if key!='settings_panel'}
    t.check('Settings freezes fitted weapons, projectiles and all weapon timers',
            gameplay_fields(after_settings)==gameplay_fields(frozen))
    t.tap(t.B);step(0,3);t.tap(t.START);frozen=t.weapon_state();step(t.R|t.L|t.B,45)
    t.check('Pause freezes both weapon triggers',t.weapon_state()==frozen)
    t.tap(t.START);step()

    fresh();reset=t.weapon_state()
    t.check('A new run restores the three default garage fittings and clears attacks',
            (reset['front'],reset['side'],reset['special'])==(0,2,3) and reset['mask']==13 and
            not any(p['remaining'] for p in reset['traps']) and
            not any(m['remaining'] for m in reset['missiles']),reset)
    t.check('Grouped weapon fire fits the measured driving frame budget',
            peak<1 and t.state()['missed']==baseline_missed,
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
