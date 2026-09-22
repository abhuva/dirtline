"""Check exported art, packed GBA scenery and repeat/alpha proof sheets."""
import json
import re
import struct
from pathlib import Path
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/wasteland'
art=json.loads((ROOT/'tools/map_editor/generated/art.json').read_text())
report=json.loads((OUT/'report.json').read_text())
palette=art['palette']
tiles=art['tiles']
assert all(0<p<report['palette_colors']<=224 for p in tiles)
assert bytes(palette)==(OUT/'palette.bin').read_bytes()

# Decode the actual generated 4bpp words and compare their RGB output with the
# editor's 8bpp export, including every transparent pixel.
header=(ROOT/'include/generated/decoration_art.h').read_text()
packed=b''.join(struct.pack('<I',int(v,16)) for v in re.findall(r'0x[0-9a-f]+',header))
local=[p for byte in packed for p in (byte&15,byte>>4)]
assert len(packed)==17*32
assert [224+p if p else 0 for p in local]==art['decoration']
assert all(0<=c<=248 and c%8==0 for c in palette[224*3:240*3])

atlas=Image.open(OUT/'tiles.png').convert('RGB')
details=Image.open(OUT/'decoration.png').convert('RGBA')
assert set(details.getchannel('A').getdata())=={0,255}
for kind in range(4):
    patch=details.crop((kind*16,0,kind*16+16,16))
    alpha=patch.getchannel('A')
    box=alpha.getbbox()
    assert box and box[0]>=1 and box[1]>=1 and box[2]<=15 and box[3]<=15
    assert 12<sum(bool(a) for a in alpha.getdata())<200

# A seamless texture need not duplicate its first and last row: adjacency over
# its wrap should have comparable contrast to adjacency inside the texture.
names=['Dusty soil','Gravel','Cracked hardpan','Worn asphalt','Plateau top','Cliff face']
proof=Image.new('RGB',(4*264,2*322+104),(24,28,29))
draw=ImageDraw.Draw(proof)
seams=[]
for n,name in enumerate(names):
    im=atlas.crop(((n%4)*32,(n//4)*32,(n%4+1)*32,(n//4+1)*32))
    rgb=list(im.getdata())
    def difference(a,b):return sum(abs(x-y) for x,y in zip(a,b))/3
    horizontal=sum(difference(rgb[y*32],rgb[y*32+31]) for y in range(32))/32
    vertical=sum(difference(rgb[x],rgb[31*32+x]) for x in range(32))/32
    inner_h=sum(difference(rgb[y*32+x],rgb[y*32+x+1]) for y in range(32) for x in range(31))/(32*31)
    inner_v=sum(difference(rgb[y*32+x],rgb[(y+1)*32+x]) for y in range(31) for x in range(32))/(32*31)
    assert horizontal<inner_h*1.75+1 and vertical<inner_v*1.75+1, name
    seams.append(dict(material=name,wrap_h=round(horizontal,2),inside_h=round(inner_h,2),
                      wrap_v=round(vertical,2),inside_v=round(inner_v,2)))
    repeat=Image.new('RGB',(96,96))
    for y in range(3):
        for x in range(3):repeat.paste(im,(x*32,y*32))
    ox=(n%3)*352+32;oy=(n//3)*322+24
    draw.text((ox,oy-16),name,fill=(220,220,208))
    proof.paste(repeat.resize((288,288),Image.Resampling.NEAREST),(ox,oy))
draw.text((8,648),'Transparent details on all four ground materials (4x)',fill=(220,220,208))
for n in range(4):
    panel=Image.new('RGBA',(64,16))
    texture=atlas.crop((n*32,0,n*32+32,32))
    panel.paste(texture,(0,0));panel.paste(texture,(32,0))
    panel.alpha_composite(details)
    proof.paste(panel.convert('RGB').resize((256,64),Image.Resampling.NEAREST),(n*264+4,672))
proof.save(OUT/'muted-art-proof.png')
audit=dict(terrain_tiles=len(tiles)//64,
           terrain_tiles_exceeding_15_opaque_colors=sum(len(set(tiles[i:i+64]))>15 for i in range(0,len(tiles),64)),
           decoration_8bpp_bytes=len(local),decoration_4bpp_bytes=len(packed),
           decoration_pixels_identical=True,terrain_palette_entries=report['palette_colors'],
           decoration_palette_entries=16,decoration_alpha='binary, transparent border on every patch',
           texture_repeat_contrast=seams)
(ROOT/'artifacts/graphics-format-audit.json').write_text(json.dumps(audit,indent=2)+'\n')
print('PASS opaque terrain, palette reservations, GBA/editor decoration pixels, alpha masks and repeat boundaries.')
