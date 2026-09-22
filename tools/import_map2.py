"""Map2 pixel-art import, authored driving corridor and streaming tile data."""
from pathlib import Path
from collections import deque
import json
import struct
import hashlib
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'artifacts/map2'
SIZE = 1280

# Counterclockwise route in normalized world pixels. The generated input contains a
# disconnected inner cul-de-sac; the short 800,965 -> 635,1008 connector repairs it.
WAYPOINTS = [(540,1105),(780,1105),(1010,1102),(1100,1080),(1160,1025),
 (1180,951),(1174,884),(1145,810),(1134,749),(1143,653),(1150,568),
 (1134,515),(1090,459),(1073,413),(1076,358),(1100,287),(1140,210),
 (1160,150),(1150,108),(1110,84),(1065,84),(972,102),(844,129),
 (731,153),(677,174),(642,197),(590,204),(510,183),(407,149),
 (308,115),(247,111),(209,125),(195,161),(206,203),(246,250),
 (302,290),(357,330),(391,380),(403,431),(402,483),(424,518),
 (491,557),(574,604),(661,655),(749,711),(835,770),(898,816),
 (929,856),(932,894),(913,929),(875,951),(823,969),(780,975),
 (709,996),(637,1008),(567,972),(481,932),(385,892),(301,875),
 (239,880),(193,904),(166,943),(161,978),(177,1019),(216,1064),
 (267,1095),(337,1105),(435,1105)]


def generate(save, ui_palette, smooth):
    source = inspect()
    original = source.copy()
    draw = ImageDraw.Draw(source)
    # Open the dead end into the existing lower-left road; preserve source PNG.
    connector = [(809,965),(780,975),(709,996),(637,1008),(593,985)]
    draw.line(connector, fill=(234,228,195), width=79, joint='curve')
    for x,y in connector[1:-1]:
        draw.ellipse((x-39,y-39,x+39,y+39),fill=(234,228,195))
    draw.line(connector, fill=(185,171,144), width=67, joint='curve')
    for x,y in connector[1:-1]:
        draw.ellipse((x-33,y-33,x+33,y+33),fill=(185,171,144))
    # Reuse a clean patch of this map's own pavement for the repair's texture.
    # The white edge remains, while the interior matches the original grain.
    core = Image.new('L',(SIZE,SIZE))
    cd = ImageDraw.Draw(core)
    cd.line(connector,fill=255,width=67,joint='curve')
    for x,y in connector[1:-1]:
        cd.ellipse((x-33,y-33,x+33,y+33),fill=255)
    texture = original.crop((760,1114,824,1130))
    bounds = core.getbbox()
    pavement = Image.new('RGB',(bounds[2]-bounds[0],bounds[3]-bounds[1]))
    for y in range(0,pavement.height,16):
        for x in range(0,pavement.width,64):
            pavement.paste(texture,(x,y))
    source.paste(pavement,(bounds[0],bounds[1]),core.crop(bounds))
    draw = ImageDraw.Draw(source)
    distance=0
    for a,b in zip(connector,connector[1:]):
        length=((a[0]-b[0])**2+(a[1]-b[1])**2)**.5
        for step in range(int(length)):
            if int(distance+step)%27<12:
                t=step/length
                x=round(a[0]+(b[0]-a[0])*t); y=round(a[1]+(b[1]-a[1])*t)
                draw.rectangle((x,y,x+1,y+1),fill=(236,224,186))
        distance+=length
    path = smooth(WAYPOINTS)
    # Infer only tan pavement. Morphological closing fills lane paint; flood
    # filling keeps disconnected tan scenery out of the driving mask.
    candidate = Image.new('L',(SIZE,SIZE))
    candidate.putdata([255 if r>135 and g>120 and b>90 and 5<=r-g<=48 and 8<=g-b<=52 else 0
                       for r,g,b in source.getdata()])
    candidate = candidate.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.MinFilter(9))
    ImageDraw.Draw(candidate).rectangle((625,1074,653,1137),fill=255)
    # Work at 4px collision resolution, preserving a forgiving curb shoulder.
    small = candidate.resize((320,320),Image.Resampling.NEAREST)
    raw = list(small.getdata())
    connected = bytearray(320*320)
    start = (1105//4)*320+540//4
    if not raw[start]:
        raise ValueError('Start is not on detected pavement')
    queue = deque([start]); connected[start] = 255
    while queue:
        p = queue.popleft(); x,y=p%320,p//320
        for nx,ny in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
            if 0<=nx<320 and 0<=ny<320:
                q=ny*320+nx
                if raw[q] and not connected[q]:
                    connected[q]=255; queue.append(q)
    road = Image.frombytes('L',(320,320),bytes(connected))
    shoulder = road.filter(ImageFilter.MaxFilter(3))
    cells = [1 if r else 0 if s else 3 for r,s in zip(road.getdata(),shoulder.getdata())]
    overlay = source.copy()
    od = ImageDraw.Draw(overlay)
    od.line(path,fill=(255,0,255),width=2)
    for i,(x,y) in enumerate(WAYPOINTS):
        od.text((x+3,y+3),str(i),fill='black',stroke_width=1,stroke_fill='white')
    overlay.save(OUT/'route-overlay.png')
    mask = Image.new('P',(320,320)); mask.putdata(cells)
    mask.putpalette([100,165,70,220,218,190,150,110,70,20,35,55]+[0]*(768-12))
    mask.resize((SIZE,SIZE),Image.Resampling.NEAREST).convert('RGB').save(OUT/'collision-mask.png')
    # Full-resolution 8bpp art. First palette bank retains the UI's colors.
    quantized = source.quantize(colors=240,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
    palette = [c for rgb in ui_palette for c in rgb]+quantized.getpalette()[:720]
    palette = [(c>>3)*255//31 for c in palette]
    indexed = quantized.point([min(i+16,255) for i in range(256)])
    indexed.putpalette(palette)
    indexed.convert('RGB').save(OUT/'converted.png')
    source.save(OUT/'repaired-source.png')
    comparison = Image.new('RGB',(880,390))
    comparison.paste(original.crop((560,850,1000,1240)),(0,0))
    comparison.paste(source.crop((560,850,1000,1240)),(440,0))
    comparison.save(OUT/'connector-before-after.png')
    # Deduplicate storage in ROM. VRAM receives only camera-near tiles.
    tile_ids, unique, lookup = [], [], {}
    for y in range(0,SIZE,8):
        for x in range(0,SIZE,8):
            tile=indexed.crop((x,y,x+8,y+8)).tobytes()
            if tile not in lookup:
                lookup[tile]=len(unique); unique.append(tile)
            tile_ids.append(lookup[tile])
    gen=ROOT/'include/generated'
    header='#pragma once\n#include "bn_tile.h"\n#include "bn_color.h"\nnamespace course_graphics {\n'
    header+='inline constexpr bn::color palette[256] = {'
    header+=','.join('bn::color(%d,%d,%d)'%tuple(v>>3 for v in palette[i:i+3]) for i in range(0,768,3))+'};\n'
    header+=f'inline constexpr uint16_t tile_ids[{len(tile_ids)}] = {{\n'
    header+='\n'.join(','.join(map(str,tile_ids[i:i+160]))+',' for i in range(0,len(tile_ids),160))+'\n};\n'
    header+=f'inline constexpr bn::tile tiles[{len(unique)*2}] = {{\n'
    header+='\n'.join('{{'+','.join(hex(v) for v in struct.unpack('<8I',tile[i:i+32]))+'}},'
                       for tile in unique for i in (0,32))+'\n};\n}\n'
    (gen/'course_graphics.h').write_text(header,encoding='utf8')
    checkpoints=[path[int(i*(len(path)-1)/12)] for i in range(1,13)]
    world='#pragma once\n#include <cstdint>\nnamespace world {\n'
    world+='inline constexpr int width=1280,height=1280,cell_size=4,columns=320;\n'
    world+='inline constexpr int start_x=540,start_y=1105,finish_x=640,finish_top=1070,finish_bottom=1140;\n'
    world+='inline constexpr uint8_t surfaces[102400] = {\n'
    world+='\n'.join(','.join(map(str,cells[i:i+320]))+',' for i in range(0,len(cells),320))+'\n};\n'
    world+='struct Point { int x,y; };\ninline constexpr Point checkpoints[] = {'
    world+=','.join('{%d,%d}'%(round(x),round(y)) for x,y in checkpoints)+'};\n}\n'
    (gen/'track_data.h').write_text(world,encoding='utf8')
    (ROOT/'artifacts/track_path.json').write_text(json.dumps(path),encoding='utf8')
    indexed.convert('RGB').save(ROOT/'artifacts/track.png')
    metadata=dict(width=SIZE,height=SIZE,start=[540,1105],finish_x=640,
                  finish_y=[1070,1140],checkpoints=[list(map(round,p)) for p in checkpoints],
                  source_sha256=hashlib.sha256((ROOT/'maps/map2/background.png').read_bytes()).hexdigest(),
                  unique_rom_tiles=len(unique),tile_rom_bytes=len(unique)*64,
                  streaming_slots=672,streaming_vram_bytes=672*64,
                  surface_cell_size=4,road_cells=cells.count(1),shoulder_cells=cells.count(0))
    (OUT/'course.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf8')
    print('Map2:',metadata,flush=True)
    return path, palette


def inspect():
    OUT.mkdir(parents=True, exist_ok=True)
    source = Image.open(ROOT/'maps/map2/background.png').convert('RGB')
    print('Map2 source:', source.size, flush=True)
    source = source.resize((SIZE,SIZE), Image.Resampling.NEAREST)
    source.crop((540,750,1000,1090)).resize((920,680),Image.Resampling.NEAREST).save(OUT/'junction-detail.png')
    overlay = source.copy()
    draw = ImageDraw.Draw(overlay)
    for y in range(0,SIZE,100):
        for x in range(0,SIZE,100):
            draw.text((x+2,y+2),f'{x},{y}',fill='magenta',stroke_width=1,stroke_fill='black')
    overlay.save(OUT/'coordinates.png')
    return source


if __name__ == '__main__':
    inspect()
