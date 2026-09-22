"""Reusable raster kit -> editable Tiled map -> chunked GBA metatiles.

AI source is immutable. Cropping, nearest sampling, palette conversion and
packing are deterministic build steps, not additional image generation.
world.tmj is seeded only when absent; builds never overwrite an edited layout.
"""
from collections import deque
from pathlib import Path
import hashlib
import json
import math
import random
import struct
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT/'maps/open_world'
OUT = ROOT/'artifacts/open_world'
TILE = 16
KINDS = ['grass', 'road', 'dirt', 'water', 'gravel']
SURFACE = [0, 1, 2, 3, 1]
PROP_SPECS = [
    ('pine', 0, 1, 48, 64), ('tree', 1, 1, 64, 64),
    ('rocks', 2, 1, 48, 32), ('bush', 3, 1, 32, 32),
    ('garage', 0, 2, 128, 96), ('cottage', 1, 2, 96, 80),
    ('fence_h', 2, 2, 64, 32), ('fence_v', 3, 2, 32, 64),
    ('pier', 3, 3, 64, 64),
]


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n', encoding='utf8')


def seed_json(path, value):
    if not path.exists(): write_json(path,value)


def prop(name, value, kind='string'):
    return dict(name=name, type=kind, value=value)


def prepare_kit(palette):
    source = Image.open(ASSETS/'source-kit.png').convert('RGBA')
    def cell(x, y, margin=0):
        box = (round(x*source.width/4)+margin, round(y*source.height/4)+margin,
               round((x+1)*source.width/4)-margin, round((y+1)*source.height/4)-margin)
        return source.crop(box)
    pal = Image.new('P', (1, 1))
    # Quantization never uses transparent/UI index zero for opaque scenery.
    pal.putpalette(palette[48:]+palette[48:96])
    def indexed(image):
        result = image.convert('RGB').quantize(palette=pal, dither=Image.Dither.NONE)
        result = result.point([16+(i%240) for i in range(256)])
        result.putpalette(palette)
        return result
    textures = [cell(i, 0, 8).resize((64,64),Image.Resampling.NEAREST) for i in range(4)]
    textures.append(cell(1,3,12).resize((64,64),Image.Resampling.NEAREST))
    atlas = Image.new('P',(512,640)); atlas.putpalette(palette)
    tiles=[]; definitions=[]
    for kind in range(5):
        for edges in range(16):
            for variant in range(16):
                x,y=variant%4*16,variant//4*16
                im=textures[kind].crop((x,y,x+16,y+16)).convert('RGB')
                d=ImageDraw.Draw(im)
                # Matching edge strips are generated once, then reused by ID.
                if kind:
                    edge_color=(222,212,156) if kind in (1,3) else (122,165,52)
                    for bit,box in [(1,(0,0,15,2)),(2,(13,0,15,15)),
                                    (4,(0,13,15,15)),(8,(0,0,2,15))]:
                        if edges&bit: d.rectangle(box,fill=edge_color)
                    if kind==1:
                        for bit,line in [(1,(0,3,15,3)),(2,(12,0,12,15)),
                                         (4,(0,12,15,12)),(8,(3,0,3,15))]:
                            if edges&bit: d.line(line,fill=(238,230,198))
                tile=indexed(im); idx=len(tiles); tiles.append(tile)
                atlas.paste(tile,(idx%32*16,idx//32*16))
                definitions.append(dict(id=idx,properties=[prop('surface',SURFACE[kind],'int'),
                                   prop('terrain',KINDS[kind]),prop('edge_mask',edges,'int')]))
    atlas.save(ASSETS/'terrain.png')
    seed_json(ASSETS/'terrain.tsj',dict(type='tileset',version='1.10',name='Lakeside terrain',
        tilewidth=16,tileheight=16,tilecount=len(tiles),columns=32,image='terrain.png',
        imagewidth=512,imageheight=640,margin=0,spacing=0,tiles=definitions))
    props=[]; records=[]
    for i,(name,x,y,w,h) in enumerate(PROP_SPECS):
        image=cell(x,y,16)
        alpha=image.getchannel('A').point(lambda a:255 if a>=192 else 0)
        box=alpha.getbbox()
        if not box: raise ValueError(f'Empty generated prop: {name}')
        image.putalpha(alpha)
        image=image.crop(box).resize((w,h),Image.Resampling.NEAREST)
        packed=indexed(image).convert('RGBA'); packed.putalpha(image.getchannel('A'))
        packed.save(ASSETS/(name+'.png')); props.append(packed)
        # Conservative footprint prevents the car painting over tree crowns.
        # Foreground canopy occlusion is deliberately not implemented yet.
        solid=name not in ('bush','pier')
        records.append(dict(id=i,image=name+'.png',imagewidth=w,imageheight=h,
            properties=[prop('solid',solid,'bool'),prop('asset',name)],
            objectgroup=dict(type='objectgroup',objects=[dict(id=1,type='solid',x=4,y=4,
                width=w-8,height=h-8,rotation=0,visible=True)] if solid else [])))
    seed_json(ASSETS/'props.tsj',dict(type='tileset',version='1.10',name='Lakeside props',
        tilewidth=128,tileheight=96,tilecount=len(props),columns=0,objectalignment='bottomleft',tiles=records))
    return tiles,props


def seed_map():
    if (ASSETS/'world.tmj').exists(): return
    n=128
    ground=Image.new('L',(n,n),0); d=ImageDraw.Draw(ground)
    # Broad rounded perimeter road, crossroads and an open service yard.
    d.rounded_rectangle((14,14,114,114),radius=15,outline=1,width=6)
    d.rectangle((14,93,114,98),fill=1)
    d.rectangle((61,14,66,114),fill=1)
    d.rectangle((14,29,114,34),fill=1)
    d.rounded_rectangle((23,85,39,99),radius=2,fill=4)
    # Two dirt connections, including a diagonal shortcut through the meadow.
    d.line([(30,93),(39,79),(49,72),(63,72)],fill=2,width=4)
    d.line([(64,72),(76,78),(103,78),(111,84),(111,94)],fill=2,width=4)
    d.rounded_rectangle((80,44,106,70),radius=8,fill=3)
    # A continuous impassable outer border, represented as water.
    d.rectangle((0,0,127,127),outline=3,width=3)
    data=[]
    for y in range(n):
        for x in range(n):
            kind=ground.getpixel((x,y)); edges=0
            for bit,dx,dy in [(1,0,-1),(2,1,0),(4,0,1),(8,-1,0)]:
                if not (0<=x+dx<n and 0<=y+dy<n) or ground.getpixel((x+dx,y+dy))!=kind:
                    edges|=bit
            data.append(1+kind*256+edges*16+(y%4)*4+x%4)
    objects=[]
    def place(kind,x,y):
        _,_,_,w,h=PROP_SPECS[kind]
        objects.append(dict(id=len(objects)+1,name=PROP_SPECS[kind][0],type='scenery',
            gid=1281+kind,x=x,y=y+h,width=w,height=h,rotation=0,visible=True))
    place(4,416,1344); place(5,352,608); place(5,480,640)
    for x in range(400,592,64): place(6,x,1312)
    for x in (1376,1488,1584): place(2,x,1136)
    rng=random.Random(815)
    for y in range(96,1952,64):
        for x in range(96,1952,64):
            # Protect the full asset rectangle and a road-side margin.
            if 320<x<704 and 1248<y<1632 or 288<x<624 and 560<y<752: continue
            if any(ground.getpixel((xx//16,yy//16))!=0
                   for yy in range(y-16,y+80,16) for xx in range(x-16,x+80,16)): continue
            density=.78 if x<400 or x>1664 or y<384 or y>1728 else .24
            if rng.random()<density: place(rng.choices([0,1,2,3],[7,2,1,2])[0],x,y)
    objects.append(dict(id=len(objects)+1,name='start',type='spawn',point=True,
        x=512,y=1536,width=0,height=0,rotation=0,visible=True))
    # Input-driven test route: cross the world, lake shore, dirt and garage.
    route=[(512,1536),(1024,1536),(1728,1536),(1776,1488),(1776,1344),
           (1664,1248),(1280,1248),(1136,1216),(1024,1152),(896,1152),
           (768,1152),(624,1264),(624,1424),(576,1488),(512,1536)]
    objects.append(dict(id=len(objects)+1,name='verification_route',type='test_route',
        x=0,y=0,width=0,height=0,rotation=0,visible=True,
        polyline=[dict(x=x,y=y) for x,y in route]))
    write_json(ASSETS/'world.tmj',dict(type='map',version='1.10',orientation='orthogonal',
        renderorder='right-down',width=n,height=n,tilewidth=16,tileheight=16,infinite=False,
        nextlayerid=3,nextobjectid=len(objects)+1,
        tilesets=[dict(firstgid=1,source='terrain.tsj'),dict(firstgid=1281,source='props.tsj')],
        layers=[dict(id=1,name='Ground',type='tilelayer',width=n,height=n,x=0,y=0,
                     opacity=1,visible=True,data=data),
                dict(id=2,name='Objects',type='objectgroup',x=0,y=0,opacity=1,visible=True,
                     draworder='topdown',objects=objects)]))


def emit_array(name,values,ctype,columns=32):
    return (f'inline constexpr {ctype} {name}[{len(values)}] = {{\n'+
            '\n'.join(','.join(map(str,values[i:i+columns]))+',' for i in range(0,len(values),columns))+'\n};\n')


def generate(palette,save,label):
    OUT.mkdir(parents=True,exist_ok=True)
    tiles,props=prepare_kit(palette)
    seed_map()
    world=json.loads((ASSETS/'world.tmj').read_text())
    n,m=world['width'],world['height']; w,h=n*16,m*16
    if world.get('infinite') or world['tilewidth']!=16 or world['tileheight']!=16 or n%16 or m%16:
        raise ValueError('Use a finite 16px map with dimensions divisible by 16 cells')
    if not (256<=w<=16384 and 256<=h<=16384): raise ValueError('Supported dimensions: 256..16384 pixels')
    if world['tilesets']!=[dict(firstgid=1,source='terrain.tsj'),dict(firstgid=1281,source='props.tsj')]:
        raise ValueError('Keep the two supplied tilesets and their first GIDs')
    ground=next(layer for layer in world['layers'] if layer['name']=='Ground')
    if any(layer['type']!='objectgroup' and layer is not ground for layer in world['layers']):
        raise ValueError('Supported layers: Ground plus object layers; extra tile layers are not yet supported')
    if any(layer.get('offsetx',0) or layer.get('offsety',0) or layer.get('opacity',1)!=1 or
           not layer.get('visible',True) for layer in world['layers']):
        raise ValueError('Keep runtime layers visible, fully opaque, and unoffset')
    if len(ground['data'])!=n*m: raise ValueError('Ground layer dimensions do not match map')
    definitions=json.loads((ASSETS/'terrain.tsj').read_text())['tiles']
    surface_by_id=[next(p['value'] for p in t['properties'] if p['name']=='surface') for t in definitions]
    if len(surface_by_id)!=len(tiles) or any(v not in range(4) for v in surface_by_id):
        raise ValueError('Every terrain tile requires a surface property in 0..3')
    prop_defs=json.loads((ASSETS/'props.tsj').read_text())['tiles']
    from world_compile import compile_world
    compiled=compile_world(world,tiles,props,prop_defs,surface_by_id,palette)
    unique_tiles=compiled['unique_tiles']; metatiles=compiled['metatiles']
    meta_surfaces=compiled['meta_surfaces']; ids=compiled['ids']
    chunks=compiled['chunks']; chunk_ids=compiled['chunk_ids']
    mask=compiled['mask']; start=compiled['start']; route=compiled['route']
    prop_count=compiled['prop_count']; unreachable=compiled['unreachable']
    if len(unique_tiles)>=65535 or len(metatiles)>=65535: raise ValueError('16-bit asset IDs exceeded')
    from map_storage_audit import tile_capacity,pack_chunks
    capacity=tile_capacity(ids,metatiles,n,m,OUT/'cache-fixture.bin',chunks,chunk_ids)
    if not 0<capacity['tile_slots']<=672: raise ValueError('Invalid visible-tile capacity')
    packed,offsets,compression=pack_chunks(chunks,len(chunk_ids),OUT/'chunk-fixture.bin')
    write_json(OUT/'compression.json',compression)
    header='#pragma once\n#include "bn_tile.h"\n#include <cstdint>\nnamespace open_world {\n'
    header+=f'inline constexpr int width={w},height={h},start_x={start[0]},start_y={start[1]},chunk_columns={n//16};\n'
    header+=f'inline constexpr int tile_slots={capacity["tile_slots"]};\n'
    header+=emit_array('chunk_ids',chunk_ids,'uint16_t')
    header+=emit_array('chunk_offsets',offsets,'uint32_t')
    header+='alignas(4) '+emit_array('chunk_data',packed,'uint8_t')
    header+=emit_array('metatiles',[v for meta in metatiles for v in meta],'uint16_t')
    header+=emit_array('surfaces',meta_surfaces,'uint8_t')
    radar_samples=[meta_surfaces[cell*16+10] for chunk in chunks for cell in chunk]
    radar_packed=[sum(radar_samples[i+j]<<(j*2) for j in range(4)) for i in range(0,len(radar_samples),4)]
    header+=emit_array('radar_surfaces',radar_packed,'uint8_t')
    header+=f'inline constexpr bn::tile tiles[{len(unique_tiles)*2}] = {{\n'
    header+='\n'.join('{{'+','.join(hex(v) for v in struct.unpack('<8I',tile[i:i+32]))+'}},'
                       for tile in unique_tiles for i in (0,32))+'\n};\n}\n'
    (ROOT/'include/generated/open_world.h').write_text(header,encoding='utf8')
    mask.save(OUT/'surfaces.png')
    compiled['preview'].save(OUT/'overview-small.png')
    atlas_columns=16
    atlas=Image.new('P',(atlas_columns*256,math.ceil(len(chunks)/atlas_columns)*256)); atlas.putpalette(palette)
    for i,art in enumerate(compiled['chunk_art']): atlas.paste(art,(i%atlas_columns*256,i//atlas_columns*256))
    atlas.save(OUT/'reference-atlas.png')
    write_json(OUT/'reference-layout.json',dict(width=w,height=h,columns=n//16,
                                             atlas_columns=atlas_columns,chunk_ids=chunk_ids))
    debug=Image.new('P',mask.size); debug.putdata(mask.tobytes())
    debug.putpalette([90,150,45,210,205,175,195,145,65,20,35,55]+[0]*756)
    debug.save(OUT/'collision.png')  # One pixel per 4px collision cell, not a huge world raster.
    # HUD uses the same full palette as both maps, avoiding GBA 8bpp conflicts.
    hud=Image.open(ROOT/'graphics/hud.bmp').copy(); hud.putpalette(palette)
    save('hud_open',hud,'regular_bg',bpp_mode='bpp_8')
    stats=dict(width=w,height=h,start=start,route=route,props=prop_count,
        unique_tiles=len(unique_tiles),tile_rom_bytes=len(unique_tiles)*64,
        source_chunk_patterns=compiled['source_patterns'],
        metatiles=len(metatiles),metatile_rom_bytes=len(metatiles)*8,
        collision_rom_bytes=len(meta_surfaces),chunks=len(chunk_ids),unique_chunks=len(chunks),
        radar_surface_rom_bytes=len(radar_packed),
        chunk_rom_bytes=compression['compressed_layout_bytes'],
        uncompressed_chunk_rom_bytes=compression['raw_layout_bytes'],
        compression_enabled=True,chunk_cache_data_bytes=9*512,
        resident_terrain_vram_bytes=capacity['tile_slots']*64,unreachable_cells=unreachable,
        source_sha256=hashlib.sha256((ASSETS/'source-kit.png').read_bytes()).hexdigest())
    stats['total_world_rom_bytes']=sum(stats[k] for k in ['tile_rom_bytes','metatile_rom_bytes','collision_rom_bytes','chunk_rom_bytes','radar_surface_rom_bytes'])
    stats.update(capacity)
    write_json(OUT/'report.json',stats)
    print('Open world:',{k:v for k,v in stats.items() if k!='route'},flush=True)
