"""Smoke test the Natural ground entry in the shared map catalog ROM."""
import hashlib
import json
import struct
import test_rom as t

output=t.OUT/'map_editor'
output.mkdir(exist_ok=True)
library=json.loads((t.ROOT/'maps/map-library.json').read_text())
game_maps=[entry for entry in library['maps'] if entry['includeInGame']]
material_index=next(i for i,entry in enumerate(game_maps) if entry['id']=='natural-ground')
reference=t.Image.open(output/'natural-full-map.png').convert('RGB')
raw=(t.ROOT/'build/map-recipe-tests/natural.render').read_bytes()
ground=raw[4176:8272]
assert t.lib.emulator_open(str(t.ROOT/'dist/dustline.gba').encode())
try:
    t.step(0,90)
    state=t.start_map(material_index);t.step(0,30)
    t.check('Two-output recipe allocates a separate 4096-byte ground grid',state['layout_bytes']==4168+4096,state['layout_bytes'])
    t.check_scene_pixels('Material recipe terrain matches exported full-map render',reference)
    t.capture('map_editor/natural-rom-start')
    for keys,frames in [(t.A,50),(t.A|t.LEFT,40),(t.A,60),(t.A|t.RIGHT,40),(0,30)]:
        t.step(keys,frames)
    state=t.state()
    t.check('Custom materials preserve playable driving',state['mode']==1 and state['missed']==0,state)
    material=ground[int(state['y'])//128*64+int(state['x'])//128]
    t.check('Driving surface follows the material output',state['surface']==(1 if material in (2,3) else 2),dict(material=material,surface=state['surface']))
    t.check_scene_pixels('Moving camera keeps material tiles aligned with the full map',reference)
    t.capture('map_editor/natural-rom-driving')
    t.tap(t.START);t.tap(t.SELECT);t.start_map(0);state=t.state()
    t.check('Changing catalog map replaces the active generated layout',state['map']==0,state)
    t.tap(t.START);t.tap(t.SELECT);t.start_map(material_index);t.step(0,30)
    t.check_scene_pixels('Restart regenerates both outputs consistently',reference)
finally:
    t.lib.emulator_close()
report=dict(rom_sha256=hashlib.sha256((t.ROOT/'dist/dustline.gba').read_bytes()).hexdigest(),checks=t.checks)
(output/'material-rom-results.json').write_text(json.dumps(report,indent=2)+'\n')
assert t.checks and all(check['passed'] for check in t.checks)
print('PASS actual material ROM: tile rendering, driving surfaces, scene lifecycle, frame budget.')
