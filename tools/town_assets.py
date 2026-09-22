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
        # Butano reserves one blank tile in addition to the 1,024 map cells.
        # Reuse one visually equivalent top-corner cliff tile so the dense
        # exterior stays inside the hardware's 1,024 tile-index range.
        native.paste(native.crop((0, 0, 8, 8)), (248, 0))
    save(name, native, 'regular_bg', bpp_mode='bpp_4')
    native.convert('RGB').resize((768, 768), Image.Resampling.NEAREST).save(
        OUT / f'{name}-3x.png')


def _player(save):
    palette = [
        (255, 0, 255), (27, 24, 25), (55, 43, 40), (91, 61, 45),
        (139, 83, 48), (190, 119, 61), (232, 168, 91), (247, 207, 139),
        (37, 72, 76), (47, 111, 115), (69, 157, 151), (146, 207, 179),
        (83, 88, 84), (137, 140, 126), (207, 204, 174), (238, 230, 196),
    ]
    sheet = Image.new('P', (16, 32 * 12), 0)
    sheet.putpalette([c for color in palette for c in color] + [0] * (768 - 48))

    for direction in range(4):
        for phase in range(3):
            tile = Image.new('P', (16, 32), 0)
            tile.putpalette(sheet.getpalette())
            d = ImageDraw.Draw(tile)
            step = 0 if phase == 0 else (-1 if phase == 1 else 1)
            # Shadow and boots anchor the collision point at y=28.
            d.ellipse((3, 26, 12, 30), fill=1)
            if direction in (0, 3):
                d.rectangle((5 + max(step, 0), 22, 7 + max(step, 0), 27), fill=2)
                d.rectangle((9 + min(step, 0), 22, 11 + min(step, 0), 27), fill=2)
                d.rectangle((4, 12, 12, 23), fill=8, outline=1)
                d.rectangle((5, 13, 11, 20), fill=10 if direction == 0 else 9)
                d.rectangle((3, 14, 4, 21), fill=5)
                d.rectangle((12, 14, 13, 21), fill=5)
                d.ellipse((4, 4, 12, 13), fill=6, outline=1)
                if direction == 0:
                    d.rectangle((6, 8, 7, 9), fill=1)
                    d.rectangle((10, 8, 11, 9), fill=1)
                    d.rectangle((5, 3, 11, 6), fill=3)
                else:
                    d.rectangle((4, 4, 12, 8), fill=3)
                    d.rectangle((5, 9, 11, 12), fill=5)
            else:
                facing_left = direction == 1
                boot_a = 4 if phase != 2 else 7
                boot_b = 9 if phase != 1 else 7
                d.rectangle((boot_a, 22, boot_a + 2, 27), fill=2)
                d.rectangle((boot_b, 22, boot_b + 2, 27), fill=2)
                d.rectangle((4, 12, 11, 23), fill=8, outline=1)
                d.rectangle((5, 13, 10, 20), fill=10)
                arm_x = 3 if facing_left else 12
                d.rectangle((arm_x, 14, arm_x + 1, 21), fill=5)
                d.ellipse((4, 4, 12, 13), fill=6, outline=1)
                d.rectangle((5 if facing_left else 9, 3, 11 if facing_left else 12, 7), fill=3)
                d.point((5 if facing_left else 11, 8), fill=1)
            sheet.paste(tile, (0, (direction * 3 + phase) * 32))

    save('town_player', sheet, 'sprite', height=32, bpp_mode='bpp_4')
    sheet.save(OUT / 'town-player.png', transparency=0)


def generate(save):
    OUT.mkdir(parents=True, exist_ok=True)
    _background('town_exterior', 'town-exterior-source.png', save)
    _background('garage_interior', 'garage-interior-source.png', save)
    _player(save)
    print('Town: 256x256 exterior, 256x256 garage interior and 12 walking frames')
