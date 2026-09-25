"""Controller-only smoke test for the Town roads shared catalog entry."""
import hashlib
import json
import struct
import test_rom as t

output=t.OUT/'map_editor'
library=json.loads((t.ROOT/'maps/map-library.json').read_text())
game_maps=[entry for entry in library['maps'] if entry['includeInGame']]
road_index=next(i for i,entry in enumerate(game_maps) if entry['id']=='town-roads')
reference=t.Image.open(output/'roads-full-map.png').convert('RGB')
raw=(t.ROOT/'build/map-recipe-tests/roads.render').read_bytes()
base=(t.ROOT/'build/map-recipe-tests/natural.render').read_bytes()

def tile(data,x,y):
    return struct.unpack_from('<H',data,8272+(y//8*1024+x//8)*2)[0]

assert t.lib.emulator_open(str(t.ROOT/'dist/dustline.gba').encode())
try:
    t.step(0,90)
    t.start_map(road_index);state=t.step(0,30)
    t.check('Road recipe allocates ground and connection grids',state['layout_bytes']==4168+4096+4104,state['layout_bytes'])
    x,y=int(state['x']),int(state['y']);texture=tile(raw,x,y)//16
    t.check('Material telemetry uses the same road-aware sample as driving',
            state['shown_material']==state['material_id'] and state['material_kind']==texture,
            dict(material=state['material_id'],shown=state['shown_material'],kind=state['material_kind'],texture=texture))
    t.check_scene_pixels('Road ROM terrain matches exported full-map render',reference)
    t.capture('map_editor/roads-rom-start')
    samples=0;road_samples=0;errors=[];max_cpu=0
    material_match=False;rough_rumble=0;road_rumble=0
    for keys,frames in [(t.A,50),(t.A|t.LEFT,40),(t.A,60),(t.A|t.RIGHT,40),(0,30)]:
        for _ in range(frames):
            before=t.state();state=t.step(keys,1)
            if before['mode']!=1 or state['mode']!=1:continue
            x,y=int(before['x']),int(before['y']);ref=tile(raw,x,y)
            if ref>=64:continue
            expected=1 if ref//16 in (2,3) else 2
            if state['surface']!=expected:errors.append(dict(x=x,y=y,expected=expected,actual=state['surface']))
            samples+=1;road_samples+=ref!=tile(base,x,y);max_cpu=max(max_cpu,state['cpu'])
            if state['material_kind'] in (1,2):rough_rumble=max(rough_rumble,abs(state['terrain_rumble']))
            elif state['material_kind']==3:
                road_rumble=max(road_rumble,abs(state['terrain_rumble']))
                if state['shown_material']==state['material_id'] and not material_match:
                    settled=t.step(0)
                    material_match=settled['material_kind']==3 and settled['shown_material']==settled['material_id']
                    if material_match:t.capture('map_editor/roads-rom-road-label')
    t.check('Driving surface follows rendered material at every sampled frame',samples>100 and not errors,dict(samples=samples,errors=errors[:5]))
    t.check('Controller route crosses generated road overlay',road_samples>0,road_samples)
    t.check('Road overlay updates material state and removes terrain rumble',
            material_match and rough_rumble>0 and road_rumble==0,
            dict(material_match=material_match,rough_rumble=rough_rumble,road_rumble=road_rumble))
    t.check('Road driving stays within frame budget',state['mode']==1 and state['missed']==0,dict(max_cpu=max_cpu,missed=state['missed']))
    t.check_scene_pixels('Moving camera keeps roads aligned with full-map render',reference)
    t.capture('map_editor/roads-rom-driving')
    t.tap(t.START);t.tap(t.SELECT);t.start_map(0)
    t.check('Changing catalog map replaces the active generated layout',t.state()['map']==0,t.state())
    t.tap(t.START);t.tap(t.SELECT);t.start_map(road_index);t.step(0,30)
    t.check_scene_pixels('Restart regenerates road overlay consistently',reference)
finally:
    t.lib.emulator_close()
report=dict(rom_sha256=hashlib.sha256((t.ROOT/'dist/dustline.gba').read_bytes()).hexdigest(),checks=t.checks)
(output/'road-rom-results.json').write_text(json.dumps(report,indent=2)+'\n')
assert t.checks and all(check['passed'] for check in t.checks)
print('PASS actual road ROM: terrain pixels, road crossing, grip, frame budget and lifecycle.')
