"""Original, deterministic pixel art, collision data, and synthesized audio.

Imports map2 through import_map2.py; retains the original procedural course
generator for reference. No commercial game assets are used.
"""
from pathlib import Path
import json
import math
import random
import struct
import wave
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
GFX = ROOT / "graphics"
GEN = ROOT / "include/generated"
AUDIO = ROOT / "audio"
for folder in (GFX, GEN, AUDIO):
    folder.mkdir(parents=True, exist_ok=True)

# Index zero is transparent on GBA. Every background uses this same palette.
PALETTE = [
    (12, 20, 28), (24, 35, 43), (39, 51, 57), (57, 69, 70),
    (66, 82, 67), (78, 96, 72), (99, 117, 81), (129, 143, 101),
    (121, 88, 61), (156, 116, 73), (195, 150, 90), (238, 187, 79),
    (222, 230, 206), (47, 123, 134), (91, 191, 184), (190, 77, 52),
]
SPRITE_PALETTE = [
    (255, 0, 255), (12, 20, 28), (27, 40, 49), (45, 65, 73),
    (40, 112, 134), (58, 164, 181), (106, 217, 211), (209, 243, 224),
    (238, 187, 79), (163, 98, 46), (234, 93, 59), (125, 45, 41),
    (222, 230, 206), (113, 143, 128), (81, 99, 91), (57, 72, 69),
]

# A compact original 5x7 font, packed into 8x8 GBA sprite cells.
FONT = {
 'A':['01110','10001','10001','11111','10001','10001','10001'],
 'B':['11110','10001','10001','11110','10001','10001','11110'],
 'C':['01111','10000','10000','10000','10000','10000','01111'],
 'D':['11110','10001','10001','10001','10001','10001','11110'],
 'E':['11111','10000','10000','11110','10000','10000','11111'],
 'F':['11111','10000','10000','11110','10000','10000','10000'],
 'G':['01111','10000','10000','10111','10001','10001','01111'],
 'H':['10001','10001','10001','11111','10001','10001','10001'],
 'I':['111','010','010','010','010','010','111'],
 'J':['00111','00010','00010','00010','10010','10010','01100'],
 'K':['10001','10010','10100','11000','10100','10010','10001'],
 'L':['10000','10000','10000','10000','10000','10000','11111'],
 'M':['10001','11011','10101','10101','10001','10001','10001'],
 'N':['10001','11001','10101','10011','10001','10001','10001'],
 'O':['01110','10001','10001','10001','10001','10001','01110'],
 'P':['11110','10001','10001','11110','10000','10000','10000'],
 'Q':['01110','10001','10001','10001','10101','10010','01101'],
 'R':['11110','10001','10001','11110','10100','10010','10001'],
 'S':['01111','10000','10000','01110','00001','00001','11110'],
 'T':['11111','00100','00100','00100','00100','00100','00100'],
 'U':['10001','10001','10001','10001','10001','10001','01110'],
 'V':['10001','10001','10001','10001','10001','01010','00100'],
 'W':['10001','10001','10001','10101','10101','10101','01010'],
 'X':['10001','10001','01010','00100','01010','10001','10001'],
 'Y':['10001','10001','01010','00100','00100','00100','00100'],
 'Z':['11111','00001','00010','00100','01000','10000','11111'],
 '0':['01110','10001','10011','10101','11001','10001','01110'],
 '1':['010','110','010','010','010','010','111'],
 '2':['01110','10001','00001','00010','00100','01000','11111'],
 '3':['11110','00001','00001','01110','00001','00001','11110'],
 '4':['00010','00110','01010','10010','11111','00010','00010'],
 '5':['11111','10000','10000','11110','00001','00001','11110'],
 '6':['01110','10000','10000','11110','10001','10001','01110'],
 '7':['11111','00001','00010','00100','01000','01000','01000'],
 '8':['01110','10001','10001','01110','10001','10001','01110'],
 '9':['01110','10001','10001','01111','00001','00001','01110'],
 ':':['0','1','0','0','1','0','0'], '.':['0','0','0','0','0','1','0'],
 '-':['000','000','000','111','000','000','000'],
 '/':['00001','00001','00010','00100','01000','10000','10000'],
 '+':['000','010','010','111','010','010','000'],
 '>':['100','010','001','0001','001','010','100'],
 '?':['01110','10001','00010','00100','00100','00000','00100'],
}

def img(size, color=0, sprite=False):
    result = Image.new('P', size, color)
    palette = SPRITE_PALETTE if sprite else PALETTE
    result.putpalette([c for rgb in palette for c in rgb] + [0] * (768-48))
    return result

def label(im, x, y, text, color=12, scale=1, spacing=6):
    d = ImageDraw.Draw(im)
    for ch in text.upper():
        for yy, row in enumerate(FONT.get(ch, [])):
            for xx, bit in enumerate(row):
                if bit == '1':
                    d.rectangle((x+xx*scale,y+yy*scale,x+(xx+1)*scale-1,y+(yy+1)*scale-1),fill=color)
        x += spacing * scale

def save(name, im, kind, **options):
    im.save(GFX / (name + '.bmp'))
    (GFX / (name + '.json')).write_text(json.dumps(dict(type=kind, **options)), encoding='utf8')

def smooth(points):
    result = []
    for i in range(len(points)):
        a,b,c,d = [points[j % len(points)] for j in (i-1,i,i+1,i+2)]
        for step in range(16):
            t = step / 16
            result.append(tuple(0.5*((2*b[k])+(-a[k]+c[k])*t+
                (2*a[k]-5*b[k]+4*c[k]-d[k])*t*t+
                (-a[k]+3*b[k]-3*c[k]+d[k])*t*t*t) for k in (0,1)))
    result.append(result[0])
    return result

WAYPOINTS = [(460,860),(760,860),(870,780),(870,650),(760,570),
 (650,650),(510,550),(590,410),(810,340),(860,230),(760,140),
 (510,140),(410,240),(260,240),(150,340),(150,650),(270,740),
 (370,740),(410,800),(360,860)]
PATH = smooth(WAYPOINTS)

def track():
    # Draw at half resolution; 2x2 pixel geometry keeps the tile budget modest.
    road = Image.new('L',(512,512),0)
    rd = ImageDraw.Draw(road)
    line = [(round(x/2),round(y/2)) for x,y in PATH]
    rd.line(line, fill=255, width=34, joint='curve')
    edge = Image.new('L',(512,512),0)
    ImageDraw.Draw(edge).line(line,fill=255,width=39,joint='curve')
    im = img((512,512),5)
    d = ImageDraw.Draw(im)
    # Tile-aligned grass variation repeats instead of consuming unique tiles.
    for y in range(0,512,4):
        for x in range(0,512,4):
            d.point((x+1,y+2), fill=4 if (x//4+y//4)%3 else 6)
    im.paste(10,(0,0),edge)
    im.paste(2,(0,0),road)
    # Dirt sector on the west side; same road shape, different tire response.
    dirt = road.copy()
    dd = ImageDraw.Draw(dirt)
    dd.rectangle((125,0,511,511),fill=0)
    dd.rectangle((0,0,511,145),fill=0)
    dd.rectangle((0,325,511,511),fill=0)
    im.paste(8,(0,0),dirt)
    # Dashed centerline with even arc-length spacing.
    travel = 0
    for a,b in zip(line,line[1:]):
        travel += math.dist(a,b)
        if int(travel/9)%2 == 0:
            d.line((a,b),fill=10 if a[0]<125 and 145<a[1]<325 else 3,width=1)
    # Trackside tire walls; aligned to tiles for reuse.
    for x in range(48,464,8):
        for y in (40,464):
            d.rectangle((x,y,x+5,y+4),fill=1)
            d.line((x+1,y,x+4,y),fill=3)
    for y in range(48,464,8):
        for x in (40,472):
            d.rectangle((x,y,x+4,y+5),fill=1)
            d.line((x,y+1,x,y+4),fill=3)
    im = im.resize((1024,1024),Image.Resampling.NEAREST)
    surface = road.resize((1024,1024),Image.Resampling.NEAREST)
    dirt_full = dirt.resize((1024,1024),Image.Resampling.NEAREST)
    d = ImageDraw.Draw(im)
    # Start/finish strip and direction arrow.
    for y in range(828,892,4):
        for x in range(448,456,4):
            d.rectangle((x,y,x+3,y+3),fill=12 if ((y//4+x//4)%2) else 1)
    d.polygon([(490,855),(500,855),(500,850),(511,860),(500,870),(500,865),(490,865)],fill=11)
    # Workshop and paddock inside the circuit, with original signage.
    d.rectangle((470,695,695,794),fill=4)
    for x in range(488,681,32):
        d.line((x,758,x,782),fill=7,width=2)
    d.rectangle((476,690,690,750),fill=1)
    d.rectangle((480,682,682,739),fill=3)
    d.rectangle((480,682,682,689),fill=13)
    for x in range(488,673,8):
        d.line((x,693,x,734),fill=2)
    d.rectangle((497,702,666,721),fill=1)
    label(im,510,708,'DUSTLINE MOTOR WORKS',14)
    label(im,478,913,'PROVING GROUNDS / 01',12)
    label(im,86,550,'DIRT',11)
    label(im,755,460,'LIFT',11,2)
    label(im,732,482,'BEFORE THE TURN',12)
    # Repeating shrubs off-road. They are low scrub, intentionally drive-through.
    rng = random.Random(901)
    for _ in range(200):
        x,y = rng.randrange(12,116)*8,rng.randrange(12,116)*8
        if surface.getpixel((x,y)) or 450<x<710 and 675<y<810:
            continue
        d.rectangle((x+2,y+3,x+13,y+12),fill=4)
        d.rectangle((x,y,x+11,y+9),fill=6)
        d.rectangle((x+2,y,x+8,y+2),fill=7)
    # Solid cones in the straight and tire stacks outside a few bends.
    obstacles = [(565,845,5),(630,877,5),(696,845,5),
                 (917,750,9),(467,555,9),(847,103,9),(116,260,9)]
    for x,y,r in obstacles:
        if r==5:
            d.rectangle((x-5,y+2,x+5,y+5),fill=1)
            d.polygon([(x,y-7),(x-4,y+3),(x+4,y+3)],fill=15)
            d.line((x-2,y-1,x+2,y-1),fill=12,width=2)
        else:
            d.ellipse((x-9,y-7,x+9,y+8),fill=1)
            d.ellipse((x-7,y-7,x+7,y+4),fill=3)
            d.ellipse((x-3,y-5,x+3,y),fill=1)
    # Canonicalize flips when counting actual hardware tile usage.
    unique=set()
    for y in range(0,1024,8):
        for x in range(0,1024,8):
            tile=im.crop((x,y,x+8,y+8))
            variants=[tile,tile.transpose(Image.Transpose.FLIP_LEFT_RIGHT),
                      tile.transpose(Image.Transpose.FLIP_TOP_BOTTOM),tile.rotate(180)]
            unique.add(min(v.tobytes() for v in variants))
    print(f'Track: {len(unique)} unique tiles (limit 1024)')
    if len(unique)>1024:
        raise RuntimeError('Track exceeds GBA tile budget')
    save('track',im,'regular_bg',bpp_mode='bpp_4',big=True)
    im.convert('RGB').save(ROOT/'artifacts/track.png')
    cells=[]
    for y in range(128):
        for x in range(128):
            p=(x*8+4,y*8+4)
            cells.append(2 if dirt_full.getpixel(p) else 1 if surface.getpixel(p) else 0)
    checkpoints = [WAYPOINTS[i] for i in (2,4,6,8,10,12,14,16,18)]
    header = '#pragma once\n#include <cstdint>\nnamespace world {\n'
    header += 'inline constexpr uint8_t surfaces[16384] = {\n'
    header += '\n'.join(','.join(map(str,cells[i:i+128]))+',' for i in range(0,len(cells),128))+'\n};\n'
    header += 'struct Obstacle { int x,y,r; };\ninline constexpr Obstacle obstacles[] = {'
    header += ','.join('{%d,%d,%d}'%v for v in obstacles)+'};\n'
    header += 'struct Point { int x,y; };\ninline constexpr Point checkpoints[] = {'
    header += ','.join('{%d,%d}'%v for v in checkpoints)+'};\n}\n'
    (GEN/'track_data.h').write_text(header,encoding='utf8')
    # Test driver follows exactly the same centerline as the visible track.
    (ROOT/'artifacts/track_path.json').write_text(json.dumps(PATH),encoding='utf8')

def sprites():
    # Render each direction from a flat model; y projection gives a mild elevated view.
    sheet=img((32,32*64),sprite=True)
    for frame in range(64):
        tile=img((32,32),sprite=True)
        d=ImageDraw.Draw(tile)
        angle=frame*math.tau/64
        c,s=math.cos(angle),math.sin(angle)
        def poly(points,color,z=0):
            pts=[(round(16+x*c-y*s),round(17+(x*s+y*c)*0.82-z)) for x,y in points]
            d.polygon(pts,fill=color)
        poly([(-11,-7),(11,-7),(13,6),(-10,8)],1)
        for x in (-7,7):
            for y in (-6,6):
                poly([(x-3,y-2),(x+3,y-2),(x+3,y+2),(x-3,y+2)],1,1)
        hull=[(-11,-5),(-8,-7),(8,-6),(12,-4),(12,4),(8,6),(-8,7),(-11,5)]
        poly(hull,3,1)
        poly(hull,5,3)
        poly([(-10,-5),(8,-5),(11,-3),(-10,-3)],6,3)
        poly([(-5,-4),(4,-4),(6,-3),(6,3),(4,4),(-5,4)],2,4)
        poly([(2,-4),(5,-3),(5,3),(2,4)],6,4)
        poly([(-4,-4),(1,-4),(1,4),(-4,4)],4,5)
        poly([(-4,-4),(1,-4),(1,-3),(-4,-3)],7,5)
        poly([(7,-1),(11,-1),(11,1),(7,1)],8,3)
        for y in (-4,3):
            poly([(10,y),(12,y),(12,y+1),(10,y+1)],7,3)
            poly([(-11,y),(-9,y),(-9,y+1),(-11,y+1)],10,3)
        sheet.paste(tile,(0,frame*32))
    save('car',sheet,'sprite',height=32)
    fx=img((8,8*4),sprite=True)
    d=ImageDraw.Draw(fx)
    d.rectangle((2,2,5,5),fill=2)
    d.rectangle((1,10,5,13),fill=9)
    d.rectangle((2,17,6,22),fill=14)
    d.rectangle((2,26,5,29),fill=8)
    save('particles',fx,'sprite',height=8)
    # Tiny combat UI/effects extend the existing procedural sprite palette.
    bullet=img((8,24),sprite=True); d=ImageDraw.Draw(bullet)
    d.rectangle((2,3,5,4),fill=7); d.rectangle((3,2,4,5),fill=8)
    d.rectangle((2,11,5,12),fill=10); d.rectangle((3,10,4,13),fill=8)
    d.rectangle((2,18,5,21),fill=6);d.point((3,19),fill=7)
    save('combat_bullet',bullet,'sprite',height=8)
    # Original 4bpp weapon art. Pre-rotated missiles avoid affine sprite costs.
    saw=img((32,128),sprite=True)
    for frame in range(4):
        d=ImageDraw.Draw(saw);cy=frame*32+16
        points=[]
        for k in range(24):
            a=(k/24+frame/48)*math.tau;r=11 if k%2==0 else 8
            points.append((round(16+math.cos(a)*r),round(cy+math.sin(a)*r)))
        d.polygon(points,fill=12,outline=3)
        d.ellipse((9,cy-7,23,cy+7),fill=14,outline=7)
        d.line((10,cy-2,22,cy+2),fill=3,width=2)
        d.ellipse((13,cy-3,19,cy+3),fill=8,outline=9)
    save('weapon_saw',saw,'sprite',height=32,bpp_mode='bpp_4')
    missile=img((16,256),sprite=True)
    for frame in range(16):
        d=ImageDraw.Draw(missile);a=frame*math.tau/16;cs=math.cos(a);sn=math.sin(a)
        def poly(points,fill):
            d.polygon([(round(7.5+x*cs-y*sn),round(frame*16+7.5+x*sn+y*cs)) for x,y in points],fill=fill)
        poly([(-7,0),(-3,-2),(-3,2)],8)
        poly([(-5,-4),(-1,-2),(4,0),(-1,2),(-5,4)],3)
        poly([(-4,-2),(2,-2),(6,0),(2,2),(-4,2)],12)
        poly([(2,-2),(6,0),(2,2)],10)
    save('weapon_missile',missile,'sprite',height=16,bpp_mode='bpp_4')
    trap=img((16,32),sprite=True)
    for frame in range(2):
        d=ImageDraw.Draw(trap);y=frame*16
        d.ellipse((2,y+4,13,y+13),fill=1)
        d.rectangle((4,y+3,11,y+11),fill=14,outline=3)
        d.line((4,y+9,11,y+9),fill=8,width=2)
        d.rectangle((6,y+4,9,y+6),fill=10 if frame else 2)
    save('weapon_trap',trap,'sprite',height=16,bpp_mode='bpp_4')
    blast=img((32,128),sprite=True)
    for frame in range(4):
        d=ImageDraw.Draw(blast);y=frame*32;r=(7,15,13,8)[frame]
        d.ellipse((16-r,y+16-r,16+r,y+16+r),fill=10 if frame<2 else 9)
        d.ellipse((16-r//2,y+16-r//2,16+r//2,y+16+r//2),fill=7 if frame==0 else 8)
        if frame>=2:d.ellipse((12,y+12,20,y+20),fill=0)
    save('weapon_blast',blast,'sprite',height=32,bpp_mode='bpp_4')
    icons=img((16,80),sprite=True)
    for frame in range(5):
        d=ImageDraw.Draw(icons);y=frame*16
        if frame==0:
            d.rectangle((3,y+6,13,y+9),fill=12);d.rectangle((3,y+9,6,y+13),fill=9)
        elif frame==1:
            icons.paste(saw.crop((8,8,24,24)),(0,y))
        elif frame==2:
            d.polygon([(1,y+8),(5,y+4),(5,y+12)],fill=6)
            d.polygon([(14,y+8),(10,y+4),(10,y+12)],fill=6)
            d.rectangle((6,y+6,9,y+12),fill=12)
        elif frame==3:icons.paste(missile.crop((0,0,16,16)),(0,y))
        else:icons.paste(trap.crop((0,16,16,32)),(0,y))
    save('weapon_icons',icons.resize((8,40),Image.Resampling.NEAREST),'sprite',height=8,bpp_mode='bpp_4')
    hp=img((16,24),sprite=True); d=ImageDraw.Draw(hp)
    for frame in range(3):
        y=frame*8; d.rectangle((0,y+2,15,y+6),fill=1)
        for pip in range(frame+1): d.rectangle((2+pip*4,y+3,4+pip*4,y+5),fill=10 if frame==0 else 8 if frame==1 else 6)
    save('combat_hp',hp,'sprite',height=8)
    burst=img((16,64),sprite=True); d=ImageDraw.Draw(burst)
    for frame in range(4):
        y=frame*16; r=(4,7,6,3)[frame]
        d.ellipse((8-r,y+8-r,8+r,y+8+r),fill=10 if frame<2 else 9)
        if frame<3: d.ellipse((6,y+6,10,y+10),fill=7 if frame==0 else 8)
    save('combat_burst',burst,'sprite',height=16)
    dot=img((8,8),sprite=True)
    ImageDraw.Draw(dot).rectangle((2,2,5,5),fill=8)
    save('dot',dot,'sprite')
    enemy_dot=img((8,8),sprite=True)
    ImageDraw.Draw(enemy_dot).rectangle((3,3,4,4),fill=10)
    save('enemy_dot',enemy_dot,'sprite')
    # Dedicated overview palette: transparent, dark floor, bright wall, grey
    # road, warm town dots. Runtime fills the 64x64 sprite from logical cells.
    overview=img((8,8),sprite=True)
    colors=[(255,0,255),(24,24,24),(224,224,224),(112,112,112),(248,200,64)]+[(0,0,0)]*11
    overview.putpalette([c for rgb in colors for c in rgb]+[0]*(768-48))
    save('overview_palette',overview,'sprite')
    font=img((8,8*94),sprite=True)
    for i in range(94):
        label(font,1,i*8,chr(33+i),12)
    save('font',font,'sprite',height=8)

def screens(path, palette):
    title=img((256,256),1)
    d=ImageDraw.Draw(title)
    # Visible viewport in a centered 256x256 BG: (8,48)..(247,207).
    for y in range(48,208):
        d.line((8,y,247,y),fill=1 if y<140 else 2)
    d.polygon([(8,150),(166,90),(247,114),(247,155),(86,208),(8,208)],fill=3)
    d.line((8,184,247,101),fill=11,width=2)
    for i in range(8):
        x=22+i*31
        d.line((x,190-int(i*10.7),x+15,185-int(i*10.7)),fill=12,width=2)
    label(title,24,64,'DUSTLINE',12,4)
    label(title,26,101,'CHOOSE YOUR MAP',14)
    label(title,26,116,'COMBAT PROTOTYPE / 11',11)
    d.rectangle((20,132,235,205),fill=1)
    label(title,30,195,'UP/DOWN CHOOSE  A DRIVE',11)
    title.putpalette(palette)
    save('title',title,'regular_bg',bpp_mode='bpp_8')
    hud=img((256,256),0)
    d=ImageDraw.Draw(hud)
    d.rectangle((8,48,247,59),fill=1)
    hud.putpalette(palette)
    save('hud',hud,'regular_bg',bpp_mode='bpp_8')
    blank=img((256,256),1); blank.putpalette(palette)
    save('menu_blank',blank,'regular_bg',bpp_mode='bpp_8')
    pause=img((256,256),1)
    d=ImageDraw.Draw(pause)
    d.rectangle((16,56,239,198),outline=13,width=2)
    label(pause,32,70,'PIT / CONTROLS',11,2)
    label(pause,32,97,'A       THROTTLE',12)
    label(pause,32,109,'B       BRAKE / REVERSE',12)
    label(pause,32,121,'LEFT/RIGHT  STEER',12)
    label(pause,32,133,'L/R SETUP IN TOWN ONLY',14)
    label(pause,32,145,'SELECT  MAP MENU',12)
    label(pause,32,157,'L WEAPON / R FIRE',11)
    label(pause,32,168,'LIFT BEFORE TIGHT TURNS',11)
    label(pause,32,184,'START   BACK TO TRACK',12)
    pause.putpalette(palette)
    save('pause',pause,'regular_bg',bpp_mode='bpp_8')

def audio():
    rng=random.Random(14)
    rate=16000
    for name,duration in [('engine',0.30),('bump',0.13),('chime',0.20),('skid',0.15),('gun',0.07)]:
        samples=[]
        for i in range(int(rate*duration)):
            t=i/rate
            env=min(1,t*150)*min(1,(duration-t)*100)
            if name=='engine':
                value=(math.sin(math.tau*80*t)+0.45*math.sin(math.tau*160*t)+0.2*math.sin(math.tau*320*t))*0.32
            elif name=='bump':
                value=rng.uniform(-1,1)*(1-t/duration)**2*0.6
            elif name=='skid':
                value=(rng.uniform(-0.4,0.4)+math.sin(math.tau*950*t)*0.16)*0.35
            elif name=='gun':
                value=(rng.uniform(-1,1)*0.6+math.sin(math.tau*180*t)*0.4)*(1-t/duration)**3
            else:
                value=math.sin(math.tau*(660 if t<0.10 else 880)*t)*0.25
            samples.append(int(max(-1,min(1,value*env))*30000))
        with wave.open(str(AUDIO/(name+'.wav')),'wb') as f:
            f.setparams((1,2,rate,len(samples),'NONE','not compressed'))
            f.writeframes(struct.pack('<'+'h'*len(samples),*samples))

def decoration_tiles(palette):
    """Four original 16px cosmetic patches; index zero stays transparent."""
    patches=[]
    for kind in range(4):
        im=Image.new('P',(16,16),0);im.putpalette(palette);d=ImageDraw.Draw(im)
        if kind==0:  # Dry grass, narrow stalks and shaded roots.
            for x,y,h in [(3,12,5),(6,13,8),(9,12,6),(12,11,4)]:
                d.line((x,y,x-1,y-h),fill=9);d.line((x+1,y,x+2,y-h+2),fill=10)
            d.line((3,13,12,13),fill=8)
        elif kind==1:  # Low scrub, with scattered holes between leaves.
            for x,y,r in [(5,9,3),(9,7,4),(12,10,2)]:
                d.ellipse((x-r,y-r,x+r,y+r),fill=4)
                d.line((x-r+1,y-1,x+1,y-2),fill=6)
            d.line((7,11,8,14),fill=8)
        elif kind==2:
            for x,y,w in [(3,9,3),(8,6,4),(11,12,3)]:
                d.rectangle((x,y,x+w,y+2),fill=3);d.line((x,y,x+w-1,y),fill=7)
        else:
            d.line((3,13,11,4),fill=8,width=2);d.line((3,12,11,3),fill=10)
            d.line((7,8,3,5),fill=9);d.line((8,7,13,8),fill=9)
        patches.append(im)
    tiles=[bytes(64)]
    for im in patches:
        for y in (0,8):
            for x in (0,8):tiles.append(im.crop((x,y,x+8,y+8)).tobytes())
    header='#pragma once\n#include "bn_tile.h"\nnamespace decoration_art {\ninline constexpr bn::tile tiles[]={\n'
    packed=[bytes(tile[i] | (tile[i+1]<<4) for i in range(0,64,2)) for tile in tiles]
    header+='\n'.join('{{'+','.join(hex(v) for v in struct.unpack('<8I',tile))+'}},' for tile in packed)+'\n};\n}\n'
    (GEN/'decoration_art.h').write_text(header)
    atlas=Image.new('P',(64,16),0);atlas.putpalette(palette)
    for i,im in enumerate(patches):atlas.paste(im,(i*16,0))
    atlas.save(ROOT/'artifacts/wasteland/decoration.png')
    return list(b''.join(tiles))

if __name__=='__main__':
    (ROOT/'artifacts').mkdir(exist_ok=True)
    from compile_recipe import generate as generate_recipe
    generate_recipe()
    from import_map2 import generate
    path, palette = generate(save, PALETTE, smooth)
    sprites()
    screens(path, palette)
    from open_world import generate as generate_open_world
    generate_open_world(palette,save,label)
    from wasteland_assets import generate as generate_wasteland
    generate_wasteland(palette,save,label)
    audio()
    print('Generated track, car directions, UI, font, particles and audio.')
