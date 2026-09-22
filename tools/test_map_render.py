"""Check PNG encoding, source tile pixels, and the downsampled editor preview."""
import json
import struct
from pathlib import Path
from PIL import Image, ImageChops

ROOT=Path(__file__).resolve().parents[1]
art=json.loads((ROOT/'tools/map_editor/generated/art.json').read_text())
for name in ('original','natural','roads','roads-wide','active'):
    path=ROOT/f'artifacts/map_editor/{name}-full-map.png'
    with Image.open(path) as check:
        check.verify()
    with Image.open(path) as image:
        assert image.size==(8192,8192) and image.mode=='P'
        raw=(ROOT/f'build/map-recipe-tests/{name}.render').read_bytes()
        # Sample inside tiles, at borders, and throughout all map quadrants.
        for y in range(0,8192,37):
            for x in range(0,8192,43):
                reference=struct.unpack_from('<H',raw,8272+((y//8)*1024+x//8)*2)[0]
                expected=art['tiles'][art['refs'][reference]*64+(y%8)*8+x%8]
                assert image.getpixel((x,y))==expected,(name,x,y)
        preview=Image.frombytes('RGBA',(2048,2048),(ROOT/f'build/map-recipe-tests/{name}-overview.rgba').read_bytes()).convert('RGB')
        reference=image.convert('RGB').resize((2048,2048),Image.Resampling.BOX)
        diff=ImageChops.difference(preview,reference)
        assert max(high for low,high in diff.getextrema())<=1
        preview.save(ROOT/f'artifacts/map_editor/{name}-overview.png')
        image.crop((3840,3840,4480,4480)).save(ROOT/f'artifacts/map_editor/{name}-detail.png')
print('PASS full PNG integrity, sampled source-art pixels, and overview downsampling.')
