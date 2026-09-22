"""Controller-only smoke test after building maps/recipes/town-roads.json."""
import hashlib
import json
import struct
import test_rom as t

output=t.OUT/'map_editor'
reference=t.Image.open(output/'roads-full-map.png').convert('RGB')
raw=(t.ROOT/'build/map-recipe-tests/roads.render').read_bytes()
base=(t.ROOT/'build/map-recipe-tests/natural.render').read_bytes()

def tile(data,x,y):
    return struct.unpack_from('<H',data,8272+(y//8*1024+x//8)*2)[0]

assert t.lib.emulator_open(str(t.ROOT/'dist/dustline.gba').encode())
try:
    t.step(0,90)
    state=t.start_map(2);t.step(0,30)
    t.check('Road recipe allocates ground and connection grids',state['layout_bytes']==4168+4096+4104,state['layout_bytes'])
    t.check_scene_pixels('Road ROM terrain matches exported full-map render',reference)
    t.capture('map_editor/roads-rom-start')
    samples=0;road_samples=0;errors=[];max_cpu=0
    for keys,frames in [(t.A,50),(t.A|t.LEFT,40),(t.A,60),(t.A|t.RIGHT,40),(0,30)]:
        for _ in range(frames):
            before=t.state();state=t.step(keys,1)
            if before['mode']!=1 or state['mode']!=1:continue
            x,y=int(before['x']),int(before['y']);ref=tile(raw,x,y)
            if ref>=64:continue
            expected=1 if ref//16 in (2,3) else 2
            if state['surface']!=expected:errors.append(dict(x=x,y=y,expected=expected,actual=state['surface']))
            samples+=1;road_samples+=ref!=tile(base,x,y);max_cpu=max(max_cpu,state['cpu'])
    t.check('Driving surface follows rendered material at every sampled frame',samples>100 and not errors,dict(samples=samples,errors=errors[:5]))
    t.check('Controller route crosses generated road overlay',road_samples>0,road_samples)
    t.check('Road driving stays within frame budget',state['mode']==1 and state['missed']==0,dict(max_cpu=max_cpu,missed=state['missed']))
    t.check_scene_pixels('Moving camera keeps roads aligned with full-map render',reference)
    t.capture('map_editor/roads-rom-driving')
    t.tap(t.START);t.tap(t.SELECT);t.start_map(0)
    t.check('Leaving wasteland releases road and material grids',t.state()['layout_bytes']==0,t.state()['layout_bytes'])
    t.tap(t.START);t.tap(t.SELECT);t.start_map(2);t.step(0,30)
    t.check_scene_pixels('Restart regenerates road overlay consistently',reference)
finally:
    t.lib.emulator_close()
report=dict(rom_sha256=hashlib.sha256((t.ROOT/'dist/dustline.gba').read_bytes()).hexdigest(),checks=t.checks)
(output/'road-rom-results.json').write_text(json.dumps(report,indent=2)+'\n')
assert t.checks and all(check['passed'] for check in t.checks)
print('PASS actual road ROM: terrain pixels, road crossing, grip, frame budget and lifecycle.')
