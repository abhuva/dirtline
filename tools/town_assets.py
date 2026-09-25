"""Generate the walkable town vertical-slice artwork.

The high resolution source images are original project assets.  This module
reduces them to native GBA dimensions and creates the small walking sprite;
the generated BMP files remain disposable build inputs.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'maps/town'
OUT = ROOT / 'artifacts/town'


def _background(name, source_name, save):
    source = Image.open(SOURCE / source_name).convert('RGB')
    native = ImageOps.fit(source, (256, 256), Image.Resampling.LANCZOS)
    # A single 16-colour bank keeps each complete 256-square scene below
    # 34 KiB of background VRAM, including its tile map.
    quantized = native.quantize(colors=15, method=Image.Quantize.MEDIANCUT,
                                dither=Image.Dither.FLOYDSTEINBERG)
    # Palette index zero is transparent on a GBA regular background.  Keep it
    # unused and shift all fifteen opaque colours into indices 1..15.
    native = Image.new('P', (256, 256), 1)
    native.putdata([pixel + 1 for pixel in quantized.getdata()])
    colors = quantized.getpalette()[:45]
    native.putpalette([0, 0, 0] + colors + [0] * (768 - 48))
    if name == 'town_exterior':
        _stamp_exterior_signs(native)
        # Butano reserves one blank tile in addition to the 1,024 map cells.
        # Reuse one visually equivalent top-corner cliff tile so the dense
        # exterior stays inside the hardware's 1,024 tile-index range.
        native.paste(native.crop((0, 0, 8, 8)), (248, 0))
    save(name, native, 'regular_bg', bpp_mode='bpp_4')
    native.convert('RGB').resize((768, 768), Image.Resampling.NEAREST).save(
        OUT / f'{name}-3x.png')


SIGN_FONT = {
    'A': ('01110', '10001', '10001', '11111', '10001', '10001', '10001'),
    'B': ('11110', '10001', '10001', '11110', '10001', '10001', '11110'),
    'C': ('01111', '10000', '10000', '10000', '10000', '10000', '01111'),
    'E': ('11111', '10000', '10000', '11110', '10000', '10000', '11111'),
    'G': ('01111', '10000', '10000', '10111', '10001', '10001', '01111'),
    'J': ('00111', '00010', '00010', '00010', '10010', '10010', '01100'),
    'O': ('01110', '10001', '10001', '10001', '10001', '10001', '01110'),
    'R': ('11110', '10001', '10001', '11110', '10100', '10010', '10001'),
}


def _nearest_palette_index(image, target):
    palette = image.getpalette()
    return min(range(1, 16), key=lambda index: sum(
        (palette[index * 3 + channel] - target[channel]) ** 2 for channel in range(3)))


def _sign(image, bounds, text):
    draw = ImageDraw.Draw(image)
    dark = _nearest_palette_index(image, (18, 25, 29))
    metal = _nearest_palette_index(image, (195, 150, 90))
    light = _nearest_palette_index(image, (232, 223, 184))
    left, top, right, bottom = bounds
    draw.rectangle(bounds, fill=dark)
    draw.rectangle((left + 1, top + 1, right - 1, bottom - 1), outline=metal)
    x = left + 3
    for character in text:
        for y, row in enumerate(SIGN_FONT[character]):
            for column, pixel in enumerate(row):
                if pixel == '1':
                    draw.point((x + column, top + 2 + y), fill=light)
        x += 6


def _stamp_exterior_signs(native):
    # Native-resolution lettering remains readable after GBA tile conversion.
    _sign(native, (108, 10, 147, 20), 'GARAGE')
    _sign(native, (66, 84, 88, 94), 'JOB')
    _sign(native, (174, 84, 203, 94), 'RACE')


def _interaction_prompt(save):
    icon = Image.new('P', (16, 16), 0)
    colors = [(255, 0, 255), (12, 20, 28), (238, 187, 79), (222, 230, 206)]
    icon.putpalette([channel for color in colors for channel in color] + [0] * (768 - 12))
    draw = ImageDraw.Draw(icon)
    draw.ellipse((1, 2, 14, 15), fill=1)
    draw.ellipse((1, 0, 14, 13), fill=2)
    draw.ellipse((3, 2, 12, 11), fill=3)
    for y, row in enumerate(SIGN_FONT['A']):
        for x, pixel in enumerate(row):
            if pixel == '1':
                draw.point((5 + x, 3 + y), fill=1)
    save('town_interact', icon, 'sprite', bpp_mode='bpp_4')


def _player(save):
    source = Image.open(SOURCE / 'player-overhead-source.png').convert('RGBA')
    rgba = Image.new('RGBA', (16, 32 * 12), (0, 0, 0, 0))
    source_width, source_height = source.size

    def character_component(cell):
        alpha=cell.getchannel('A');width,height=cell.size;pixels=alpha.load()
        candidates=((x,y) for y in range(height) for x in range(width) if pixels[x,y]>=96)
        seed=min(candidates,key=lambda point:(point[0]-width//2)**2+(point[1]-height//2)**2)
        stack=[seed];visited=bytearray(width*height);visited[seed[1]*width+seed[0]]=1
        left=right=seed[0];top=bottom=seed[1]
        while stack:
            x,y=stack.pop();left=min(left,x);right=max(right,x);top=min(top,y);bottom=max(bottom,y)
            for yy in range(max(0,y-1),min(height,y+2)):
                for xx in range(max(0,x-1),min(width,x+2)):
                    at=yy*width+xx
                    if not visited[at] and pixels[xx,yy]>=96:
                        visited[at]=1;stack.append((xx,yy))
        cleaned=Image.new('RGBA',cell.size,(0,0,0,0));source_pixels=cell.load();out=cleaned.load()
        for y in range(top,bottom+1):
            for x in range(left,right+1):
                if visited[y*width+x]:out[x,y]=source_pixels[x,y]
        return cleaned.crop((left,top,right+1,bottom+1))

    frames=[]
    for direction in range(4):
        for phase in range(3):
            left=round(phase*source_width/3);right=round((phase+1)*source_width/3)
            top=round(direction*source_height/4);bottom=round((direction+1)*source_height/4)
            frames.append(character_component(source.crop((left,top,right,bottom))))

    scale=min(14/max(frame.width for frame in frames),22/max(frame.height for frame in frames))
    for index,frame in enumerate(frames):
        size=(max(1,round(frame.width*scale)),max(1,round(frame.height*scale)))
        frame=frame.resize(size,Image.Resampling.LANCZOS)
        # A native shadow and common scale stabilize the contact point and gait.
        ImageDraw.Draw(rgba).ellipse((4,index*32+27,11,index*32+30),fill=(20,24,28,160))
        rgba.alpha_composite(frame,((16-size[0])//2,index*32+30-size[1]))

    opaque=[pixel[:3] for pixel in rgba.getdata() if pixel[3]>=96]
    samples=Image.new('RGB',(len(opaque),1));samples.putdata(opaque)
    reduced=samples.quantize(colors=15,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
    colors=reduced.getpalette()[:45]
    palette=[tuple(colors[i:i+3]) for i in range(0,len(colors),3)]
    sheet=Image.new('P',rgba.size,0)
    sheet.putpalette([255,0,255]+colors+[0]*(768-3-len(colors)))
    indexed=[]
    for red,green,blue,alpha in rgba.getdata():
        if alpha<96:
            indexed.append(0);continue
        best=min(range(len(palette)),key=lambda index:
            (red-palette[index][0])**2+(green-palette[index][1])**2+(blue-palette[index][2])**2)
        indexed.append(best+1)
    sheet.putdata(indexed)
    save('town_player', sheet, 'sprite', height=32, bpp_mode='bpp_4')
    sheet.save(OUT / 'town-player.png', transparency=0)
    sheet.resize((128,32*12*8),Image.Resampling.NEAREST).save(
        OUT / 'town-player-8x.png',transparency=0)


def generate(save):
    OUT.mkdir(parents=True, exist_ok=True)
    _background('town_exterior', 'town-exterior-source.png', save)
    _background('garage_interior', 'garage-interior-source.png', save)
    _player(save)
    _interaction_prompt(save)
    print('Town: signed 256x256 exterior, 256x256 garage interior, prompt and 12 walking frames')
