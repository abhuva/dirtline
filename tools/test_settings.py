"""Handling, battery, audio and fixed-minimap checks in the ROM."""
import json
import math
from test_wasteland import Reference,check_hud_radar


PRESETS=(
    (0.045,2.85,0.165,2.65,0.001,0.09,950),
    (0.053,3.20,0.120,2.90,0.001,0.09,1100),
    (0.033,2.65,0.105,2.25,0.001,0.09,2200),
)


def close(a,b,tolerance=0.001):
    return abs(a-b)<=tolerance


def run(t):
    (t.OUT/'settings').mkdir(exist_ok=True)

    car_assets=('car','car_sand_buggy','car_old','car_truck','car_pickup')
    car_images=[t.Image.open(t.ROOT/f'graphics/{name}.bmp') for name in car_assets]
    base_palette=car_images[0].getpalette()[:48]
    t.check('All five car bodies share the palette-swap contract and 64 headings',
            all(image.size==(32,32*64) and image.getpalette()[:48]==base_palette and
                {4,5,6}.issubset(set(image.getdata())) for image in car_images),
            [dict(name=name,size=image.size) for name,image in zip(car_assets,car_images)])
    for image in car_images:image.close()

    def menu():
        if t.state()['mode']==3:t.tap(t.B)
        if t.state()['mode']==1:t.tap(t.START)
        if t.state()['mode']==2:t.tap(t.SELECT)
        assert t.state()['mode']==0

    def hold(key,frames):
        t.step(0,2);t.step(key,frames);return t.step(0,2)

    menu()
    loose_map=next(i for i,entry in enumerate(t.GAME_MAPS) if entry['id']=='voronoi-passages')
    t.start_map(loose_map)
    loose_samples=[t.step(t.A) for _ in range(70)]
    loose_slip=max(abs(sample['slip']) for sample in loose_samples if sample['material_kind']==0)
    t.check('Loose ground creates a sustained lateral wander without camera chatter',
            loose_slip>0.04 and max(abs(sample['terrain_rumble']) for sample in loose_samples)==0,
            dict(peak_slip=loose_slip,material=loose_samples[-1]['material_kind']))

    menu();initial=t.start_map(0);ref=Reference(t,initial['seed'])
    t.check('Wasteland opens at the fixed 2x player-centered view',
            initial['zoom_level']==1 and initial['radar_scale']==64,initial)
    down_idle=t.step(t.DOWN,18)
    t.check('Down has no driving action',
            all(down_idle[key]==initial[key] for key in ('x','y','vx','vy','heading')),
            dict(before=initial,after=down_idle))

    accelerated=initial
    for _ in range(40):
        accelerated=t.step(t.A)
    coast_start=math.hypot(accelerated['vx'],accelerated['vy'])
    coast_end=math.hypot(*(t.step(0,6)[axis] for axis in ('vx','vy')))

    # Repeat the same deterministic run so braking and coasting begin from the
    # same location, speed, encounter state and terrain sample.
    menu();initial=t.start_map(0);ref=Reference(t,initial['seed'])
    t.step(t.DOWN,18)
    rough_slip=0;rough_rumble=0
    for _ in range(40):
        accelerated=t.step(t.A)
        if accelerated['material_kind'] in (1,2):
            rough_slip=max(rough_slip,abs(accelerated['slip']))
            rough_rumble=max(rough_rumble,abs(accelerated['terrain_rumble']))
    brake_start=math.hypot(accelerated['vx'],accelerated['vy'])
    brake_end=math.hypot(*(t.step(t.B,6)[axis] for axis in ('vx','vy')))
    coast_drop=coast_start-coast_end
    brake_drop=brake_start-brake_end
    t.check('B braking is materially stronger than neutral coasting',
            t.state()['mode']==1 and coast_drop>0 and
            abs(brake_start-coast_start)<0.001 and brake_end<coast_end*0.6,
            dict(coast_start=coast_start,coast_end=coast_end,coast_drop=coast_drop,
                 brake_start=brake_start,brake_end=brake_end,brake_drop=brake_drop))
    t.check('Stony ground produces soft lateral chatter and a rumble signal',
            rough_slip>0.003 and rough_rumble>0.5,
            dict(peak_slip=rough_slip,peak_rumble=rough_rumble,
                 material=accelerated['material_kind']))

    # Up/Down have no driving action and no longer zoom the minimap.
    generation=initial['generations']
    before_zoom=t.state();t.tap(t.UP);t.tap(t.DOWN);t.step(0,24);s=t.state()
    t.capture('settings/radar-fixed-2x')
    t.check('Driving Up/Down leave the fixed minimap unchanged',s['mode']==1 and
            s['zoom_level']==1 and s['radar_scale']==64 and s['generations']==generation and
            s['radar_revisions']==before_zoom['radar_revisions'],s)
    check_hud_radar(t,ref,'fixed 2x minimap')

    before=t.state();opened=t.tap(t.SELECT)
    t.capture('settings/handling-lab')
    t.check('Select opens the handling lab without resetting the car',opened['mode']==6 and
            opened['generations']==before['generations'] and opened['signature']==before['signature'],opened)
    frozen=t.step(0,40)
    t.check('Handling lab freezes position, velocity and simulation time',all(frozen[k]==opened[k] for k in
            ('x','y','vx','vy','heading','lap_frames','seed','signature')),frozen)

    default_loadout=t.weapon_state()
    t.tap(t.R);audio=t.audio_state();t.capture('settings/audio-control')
    t.check('R opens Audio Control with music off and sound effects at full volume',
            t.weapon_state()['settings_panel']==1 and default_loadout['mask']==13 and
            (default_loadout['front'],default_loadout['side'],default_loadout['special'])==(0,2,3) and audio['music_volume']==0 and
            audio['sound_volume']==10 and not audio['muted'] and audio['sound_master']==1,audio)
    t.tap(t.RIGHT)                   # Music 10%.
    t.tap(t.DOWN);t.tap(t.LEFT);t.tap(t.LEFT)  # Sound effects 80%.
    t.tap(t.DOWN);t.tap(t.A)         # Mute all.
    muted=t.audio_state();t.capture('settings/audio-muted')
    t.check('Audio levels are independently adjustable and master mute silences both buses',
            muted['music_volume']==1 and muted['sound_volume']==8 and muted['muted'] and
            muted['sound_master']==0 and muted['music_output']==0,muted)
    t.tap(t.B);t.step(0,4);t.tap(t.SELECT);t.tap(t.R)
    persisted=t.audio_state()
    t.check('Audio choices persist after closing and reopening the panel',
            persisted['music_volume']==1 and persisted['sound_volume']==8 and persisted['muted'],persisted)
    t.tap(t.A)                       # Unmute.
    t.tap(t.UP);t.tap(t.A)           # Reset sound effects.
    t.tap(t.UP);t.tap(t.A)           # Reset music.
    restored_audio=t.audio_state();t.tap(t.L)  # Audio -> Handling.
    t.check('A restores both buses and unmute reapplies them immediately',
            restored_audio['music_volume']==10 and restored_audio['sound_volume']==10 and
            not restored_audio['muted'] and restored_audio['sound_master']==1 and
            restored_audio['music_output']>0,restored_audio)

    t.check('Weapon fitting is absent from the field settings panels',
            t.weapon_state()['settings_panel']==0 and t.weapon_state()['mask']==13,t.weapon_state())

    # The CAR row is the last Handling entry; every body uses the fitted garage weapons.
    t.tap(t.UP)
    for expected,name in enumerate(('sand-buggy','old-car','truck','pickup'),1):
        t.tap(t.RIGHT);selected=t.weapon_state()
        t.check(f'Handling panel selects the {name} body',selected['car_type']==expected,selected)
        t.tap(t.B);t.step(0,4);t.capture(f'settings/car-{name}')
        t.tap(t.SELECT)
    t.tap(t.A)
    t.check('A restores the original roadster on the CAR row',t.weapon_state()['car_type']==0,t.weapon_state())
    t.tap(t.UP);standard=t.weapon_state();t.tap(t.RIGHT);large=t.weapon_state()
    t.capture('settings/battery-large')
    t.check('Handling panel equips a larger battery with a mass tradeoff',
            standard['max_energy']==100 and large['max_energy']==150 and
            t.combat_state()['player_mass']==opened['tune_mass']+200,
            dict(standard=standard,large=large,combat=t.combat_state()))
    t.tap(t.A)
    t.check('A restores the standard 100-energy battery',t.weapon_state()['max_energy']==100,t.weapon_state())
    t.tap(t.DOWN);t.tap(t.DOWN)

    base=PRESETS[opened['setup']]
    t.check('Handling lab starts from the fitted preset',
            close(opened['tune_acceleration'],base[0]) and close(opened['tune_max_speed'],base[1]) and
            close(opened['tune_grip'],base[2]) and close(opened['tune_steer'],base[3]) and
            close(opened['tune_coast'],base[4]) and close(opened['tune_brake'],base[5]) and
            opened['tune_mass']==base[6],opened)

    # Verify individual steps in both directions before exercising the broad ranges.
    t.tap(t.RIGHT);acc=t.state()
    t.tap(t.DOWN);t.tap(t.RIGHT);speed=t.state()
    t.tap(t.DOWN);t.tap(t.LEFT);grip=t.state()
    t.tap(t.DOWN);t.tap(t.RIGHT);steer=t.state()
    t.tap(t.DOWN);t.tap(t.RIGHT);coast=t.state()
    t.tap(t.DOWN);t.tap(t.LEFT);brake=t.state()
    t.tap(t.DOWN);t.tap(t.RIGHT);mass=t.state()
    t.check('Every handling property supports manual increase and decrease',
            close(acc['tune_acceleration'],base[0]+0.005) and
            close(speed['tune_max_speed'],base[1]+0.1) and
            close(grip['tune_grip'],base[2]-0.005) and
            close(steer['tune_steer'],base[3]+0.1) and
            close(coast['tune_coast'],base[4]+0.001) and
            close(brake['tune_brake'],base[5]-0.01) and mass['tune_mass']==base[6]+100,mass)

    # Held Left/Right repeats quickly enough to reach intentionally extreme test values.
    t.tap(t.A)
    for _ in range(6):t.tap(t.UP)
    hold(t.RIGHT,220)
    t.tap(t.DOWN);hold(t.RIGHT,200)
    t.tap(t.DOWN);hold(t.RIGHT,400)
    t.tap(t.DOWN);hold(t.RIGHT,210)
    t.tap(t.DOWN);hold(t.RIGHT,130)
    t.tap(t.DOWN);hold(t.RIGHT,100)
    t.tap(t.DOWN);hold(t.RIGHT,210)
    extreme=t.state();t.capture('settings/handling-extremes')
    t.check('Handling lab exposes very wide clamped test ranges',
            close(extreme['tune_acceleration'],0.5) and close(extreme['tune_max_speed'],12) and
            close(extreme['tune_grip'],1) and close(extreme['tune_steer'],12) and
            close(extreme['tune_coast'],0.05) and close(extreme['tune_brake'],0.3) and
            extreme['tune_mass']==10000,extreme)
    hold(t.LEFT,240);minimum=t.state()
    t.check('Mass can also be reduced across a wide range',minimum['tune_mass']==100,minimum)

    # Reset, make a small custom tune, and verify it survives normal scene changes.
    t.tap(t.A)
    t.tap(t.DOWN);t.tap(t.DOWN);t.tap(t.DOWN);t.tap(t.RIGHT)  # Skip BAT/CAR; ACC +0.005.
    t.tap(t.UP);t.tap(t.UP);t.tap(t.UP);t.tap(t.LEFT)         # Skip CAR/BAT; MASS -100.
    custom=t.state();t.capture('settings/handling-custom')
    t.tap(t.B);t.step(0,12);driving=t.state()
    t.check('Closing the lab applies the custom values to the player car',driving['mode']==1 and
            close(driving['tune_acceleration'],base[0]+0.005) and
            driving['tune_mass']==base[6]-100 and t.combat_state()['player_mass']==base[6]-100,driving)
    t.tap(t.START);t.step(0,20);t.tap(t.START);resumed=t.step(0,10)
    t.check('Pause and resume preserve the custom handling tune',
            close(resumed['tune_acceleration'],base[0]+0.005) and resumed['tune_mass']==base[6]-100,resumed)

    for _ in range(360):
        if t.step(t.A)['mode']==3:break
    assert t.state()['mode']==3
    t.tap(t.UP);t.tap(t.A);t.step(0,12)
    town=t.state();assert town['mode']==4
    t.tap(t.SELECT);inside=t.state()
    t.check('Handling lab also opens in town without loading driving graphics',inside['mode']==6 and
            inside['tile_capacity']==0 and inside['tune_mass']==base[6]-100,inside)
    t.tap(t.SELECT);t.step(0,10)
    t.step(t.DOWN,18);t.tap(t.A);returned=t.step(0,45)
    t.check('Town round trip preserves the custom handling tune',returned['mode']==1 and
            close(returned['tune_acceleration'],base[0]+0.005) and returned['tune_mass']==base[6]-100,returned)

    # Do not leak an extreme or custom test tune into the remaining combat suites.
    t.tap(t.SELECT);t.tap(t.A);t.tap(t.B);final=t.step(0,12)
    t.check('A restores all fitted preset values',close(final['tune_acceleration'],base[0]) and
            close(final['tune_max_speed'],base[1]) and close(final['tune_grip'],base[2]) and
            close(final['tune_steer'],base[3]) and close(final['tune_coast'],base[4]) and
            close(final['tune_brake'],base[5]) and final['tune_mass']==base[6],final)
    t.check('Minimap and tuning operations add no missed driving frames',
            driving['missed']==opened['missed'],dict(before=opened['missed'],after=driving['missed']))


if __name__=='__main__':
    import test_rom as t
    assert t.lib.emulator_open(str(t.ROOT/'dist/dustline.gba').encode())
    t.step(0,90)
    try:run(t)
    finally:
        t.lib.emulator_close()
        (t.OUT/'settings/test-results.json').write_text(json.dumps(dict(
            rom_sha256=t.hashlib.sha256((t.ROOT/'dist/dustline.gba').read_bytes()).hexdigest(),checks=t.checks),indent=2))
    if not all(c['passed'] for c in t.checks):raise SystemExit(1)
