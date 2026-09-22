"""Controller-driven vertical-slice test for the walkable town and garage."""
import json
import test_rom as t


def run():
    t.start_map(0)
    for _ in range(360):
        if t.step(t.A)['mode']==3:
            break
    t.check('Town slice reaches the entry prompt through normal driving',t.state()['mode']==3,t.state())
    t.tap(t.UP);t.tap(t.A);t.step(0,10)
    exterior=t.town_state();t.capture('town/exterior')
    t.check('Town slice starts at the south gate',t.state()['mode']==4 and
            exterior['place']==0 and exterior['x']==128 and exterior['y']==226,exterior)

    # The large central obstacle forces a route around its eastern side.
    t.step(t.UP,100);blocked=t.town_state()
    t.check('Town collision blocks the central rock island',blocked['y']>=140,blocked)
    t.step(t.DOWN,50);t.step(t.RIGHT,40);t.step(t.UP,180);t.step(t.LEFT,40);t.tap(t.UP);t.tap(t.A);t.step(0,8)
    garage=t.town_state();t.capture('town/garage')
    t.check('Town garage door changes walkable location',garage['place']==1 and
            garage['x']==128 and garage['y']==228,garage)

    t.step(t.UP,180);counter=t.town_state();t.tap(t.A);menu=t.town_state()
    t.capture('town/garage-menu')
    t.check('Garage counter has solid collision',76<=counter['y']<=94,counter)
    t.check('Mechanic opens the setup menu',menu['menu'],menu)
    t.tap(t.SELECT);t.check('Settings can open over the mechanic menu',t.state()['mode']==6,t.state())
    t.tap(t.SELECT);t.capture('town/garage-menu-resumed')
    t.check('Closing settings restores the mechanic menu',t.state()['mode']==4 and
            t.town_state()['menu'],t.town_state())
    original=t.state()['setup'];t.tap(t.RIGHT);t.tap(t.A)
    t.check('Mechanic applies the selected setup',t.state()['setup']==(original+1)%3,t.state())

    t.step(t.DOWN,150);t.tap(t.A)
    outside=t.town_state()
    t.check('Garage exit returns beside its exterior door',outside['place']==0 and
            outside['x']==128 and outside['y']==67,outside)
    t.step(t.RIGHT,40);t.step(t.DOWN,135);t.step(t.LEFT,40);t.step(t.DOWN,35);t.tap(t.A);t.step(0,20)
    t.check('Town south gate restores the overworld',t.state()['mode']==1,t.state())


if __name__=='__main__':
    assert t.lib.emulator_open(str(t.ROOT/'dist/dustline.gba').encode())
    t.step(0,90)
    try:
        run()
    finally:
        t.lib.emulator_close()
        folder=t.OUT/'town';folder.mkdir(exist_ok=True)
        report=dict(rom_sha256=t.hashlib.sha256((t.ROOT/'dist/dustline.gba').read_bytes()).hexdigest(),checks=t.checks)
        (folder/'test-results.json').write_text(json.dumps(report,indent=2))
    if not all(c['passed'] for c in t.checks): raise SystemExit(1)
