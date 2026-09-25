"""Controller-driven acceptance checks for the first contract-board slice."""
import json
import test_rom as t


def run():
    (t.OUT/'missions').mkdir(exist_ok=True)
    t.start_map(0)
    for _ in range(360):
        if t.step(t.A)['mode']==3:
            break
    t.check('Mission route reaches the first outpost',t.state()['mode']==3,t.state())
    t.tap(t.UP);t.tap(t.A);t.step(0,10)

    # Its approach zone works regardless of the player's facing direction.
    t.step(t.UP,120);t.step(t.LEFT,40);t.tap(t.RIGHT)
    approach=t.town_state();t.capture('missions/job-prompt')
    t.check('Job approach shows its animated A prompt',approach['prompt'],approach)
    t.tap(t.A)
    offer=t.mission_state();t.capture('missions/contract-board')
    t.check('Outpost dispatch opens without facing its window',offer['board'] and
            offer['status']==0 and offer['selection']==0,offer)
    t.tap(t.RIGHT);hunt=t.mission_state();t.capture('missions/hunt-offer')
    t.check('Contract board exposes the extermination offer',hunt['board'] and
            hunt['selection']==1,hunt)
    t.tap(t.LEFT);t.tap(t.A);active=t.mission_state();t.capture('missions/courier-active')
    t.check('Contract board accepts one courier with a distinct destination',active['status']==1 and
            active['type']==1 and active['origin']==0 and active['target_town'] not in (-1,0) and
            active['reward']>0 and active['serial']==1,active)
    t.tap(t.SELECT)
    t.check('Settings can open over the contract board',t.state()['mode']==6,t.state())
    t.tap(t.SELECT);restored=t.mission_state()
    t.check('Closing settings restores the active contract board',t.state()['mode']==4 and
            restored['board'] and restored['status']==1,restored)
    t.tap(t.B)
    t.step(t.RIGHT,40);t.step(t.DOWN,120);t.tap(t.DOWN);t.tap(t.A);t.step(0,20)
    t.capture('missions/courier-marker')
    t.check('Leaving town preserves the contract and shows its driving target',t.state()['mode']==1 and
            t.mission_state()['status']==1,dict(state=t.state(),mission=t.mission_state(),town=t.town_state()))
    t.tap(t.START);t.capture('missions/pause-active-contract')
    t.check('Pause status reports the active contract',t.state()['mode']==2 and
            t.mission_state()['status']==1,t.mission_state())


if __name__=='__main__':
    assert t.lib.emulator_open(str(t.ROOT/'dist/dustline.gba').encode())
    t.step(0,90)
    try:
        run()
    finally:
        t.lib.emulator_close()
        folder=t.OUT/'missions';folder.mkdir(exist_ok=True)
        report=dict(rom_sha256=t.hashlib.sha256((t.ROOT/'dist/dustline.gba').read_bytes()).hexdigest(),checks=t.checks)
        (folder/'test-results.json').write_text(json.dumps(report,indent=2))
    if not all(c['passed'] for c in t.checks): raise SystemExit(1)
