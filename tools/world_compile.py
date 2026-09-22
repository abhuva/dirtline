"""Compile editor chunks without ever allocating a world-sized RGB image."""
from array import array
from collections import deque
import math
from PIL import Image, ImageDraw


def disconnected_cells(mask, start):
    # Scanline flood: O(surface cells), but long spans are searched/marked in C.
    # A Python queue entry per pixel would be unnecessarily costly at 16k scale.
    width,height=mask.size
    remaining=bytearray(mask.tobytes().translate(bytes([1,1,1,0]+[0]*252)))
    queue=deque([start[1]//4*width+start[0]//4])
    while queue:
        at=queue.popleft()
        if not remaining[at]: continue
        row=at//width; lo=row*width; hi=lo+width
        left=max(lo,remaining.rfind(b'\0',lo,at)+1)
        right=remaining.find(b'\0',at,hi)
        if right<0: right=hi
        remaining[left:right]=bytes(right-left)
        for delta in (-width,width):
            if not 0<=left+delta<width*height: continue
            pos=left+delta; end=right+delta
            while pos<end:
                pos=remaining.find(b'\1',pos,end)
                if pos<0: break
                queue.append(pos)
                stop=remaining.find(b'\0',pos,end)
                pos=end if stop<0 else stop+1
    return sum(remaining)


def compile_world(world,tiles,props,prop_defs,surface_by_id,palette):
    n,m=world['width'],world['height']; w,h=n*16,m*16
    columns,rows=n//16,m//16
    ground=next(layer for layer in world['layers'] if layer['name']=='Ground')['data']
    if any(not 1<=gid<=len(tiles) for gid in ground):
        raise ValueError('Ground must use unflipped terrain tiles (no empty cells)')
    # Preserve the previous RGB->palette canonicalization, including duplicate colors.
    colors={tuple(palette[i:i+3]):i//3 for i in range(48,768,3)}
    lut=[colors.get(tuple(palette[i:i+3]),0) for i in range(0,768,3)]
    terrain=[tile.point(lut) for tile in tiles]
    prop_pixels=[]
    for image in props:
        indexed=Image.new('P',image.size); indexed.putpalette(palette)
        indexed.putdata([colors[p] for p in image.convert('RGB').getdata()])
        prop_pixels.append(indexed)
    commands=[[] for _ in range(columns*rows)]
    objects=[o for layer in world['layers'] if layer['type']=='objectgroup' for o in layer['objects']]
    start=None; route=[]; prop_count=0
    for obj in sorted(objects,key=lambda o:o['y']):
        if obj.get('rotation',0)!=0: raise ValueError('Object rotation is not supported')
        kind=obj.get('type')
        if kind=='spawn':
            if start: raise ValueError('Exactly one spawn is required')
            start=[round(obj['x']),round(obj['y'])]; continue
        if kind=='test_route':
            route=[(p['x']+obj['x'],p['y']+obj['y']) for p in obj['polyline']]; continue
        rectangles=[]; idx=-1
        if 'gid' in obj:
            idx=obj['gid']-1281
            if not 0<=idx<len(props): raise ValueError('Unknown or flipped prop')
            image=props[idx]; x,y=round(obj['x']),round(obj['y']-image.height)
            ow,oh=image.size
            if obj['width']!=ow or obj['height']!=oh or x%16 or y%16:
                raise ValueError('Place props at native size on the 16px grid')
            if x<0 or y<0 or x+ow>w or y+oh>h: raise ValueError('Prop outside map')
            prop_count+=1
            solid=next((p['value'] for p in prop_defs[idx].get('properties',[]) if p['name']=='solid'),True)
            for shape in (prop_defs[idx].get('objectgroup',{}).get('objects',[]) if solid else []):
                if any(k in shape for k in ('ellipse','polygon','polyline','point')) or shape.get('rotation',0):
                    raise ValueError('Prop collisions currently support axis-aligned rectangles only')
                sx,sy=x+shape['x'],y+shape['y']
                rectangles.append((int(sx//4),int(sy//4),int((sx+shape['width']-1)//4),
                                   int((sy+shape['height']-1)//4)))
        elif kind=='solid':
            x,y,ow,oh=obj['x'],obj['y'],obj['width'],obj['height']
            rectangles=[(int(x//4),int(y//4),int((x+ow-1)//4),int((y+oh-1)//4))]
        else: raise ValueError(f'Unsupported object: {obj.get("name")}')
        # Include collision shapes that extend beyond an object's visual rectangle.
        bounds=[(x,y,x+ow-1,y+oh-1)]+[(a*4,b*4,c*4+3,d*4+3) for a,b,c,d in rectangles]
        x0=max(0,int(min(b[0] for b in bounds))//256)
        y0=max(0,int(min(b[1] for b in bounds))//256)
        x1=min(columns-1,int(max(b[2] for b in bounds))//256)
        y1=min(rows-1,int(max(b[3] for b in bounds))//256)
        for cy in range(y0,y1+1):
            for cx in range(x0,x1+1):
                commands[cy*columns+cx].append((idx,x-cx*256,y-cy*256,
                    tuple((a-cx*64,b-cy*64,c-cx*64,d-cy*64) for a,b,c,d in rectangles)))
    if not start or not route: raise ValueError('Keep one spawn and a verification_route polyline')
    mask=Image.new('L',(w//4,h//4),3)
    preview=Image.new('P',(min(1024,w),min(1024,h))); preview.putpalette(palette)
    unique_tiles=[]; tile_lookup={}; metatiles=[]; meta_lookup={}; meta_surfaces=[]
    ids=array('H',[0])*(n*m); chunks=[]; chunk_ids=[]; chunk_lookup={}
    source_cache={}; chunk_art=[]; chunk_masks=[]
    for cy in range(rows):
        for cx in range(columns):
            gids=tuple(ground[(cy*16+dy)*n+cx*16+dx] for dy in range(16) for dx in range(16))
            key=gids,tuple(commands[cy*columns+cx])
            chunk_id=source_cache.get(key)
            if chunk_id is None:
                art=Image.new('P',(256,256)); art.putpalette(palette)
                cells=Image.new('L',(64,64),3); md=ImageDraw.Draw(cells)
                for i,gid in enumerate(gids):
                    x,y=i%16*16,i//16*16
                    art.paste(terrain[gid-1],(x,y))
                    md.rectangle((x//4,y//4,x//4+3,y//4+3),fill=surface_by_id[gid-1])
                for idx,x,y,rectangles in key[1]:
                    if idx>=0: art.paste(prop_pixels[idx],(int(x),int(y)),props[idx].getchannel('A'))
                    for rect in rectangles: md.rectangle(rect,fill=3)
                chunk=[]
                for y in range(0,256,16):
                    for x in range(0,256,16):
                        refs=[]
                        for dy,dx in [(0,0),(0,8),(8,0),(8,8)]:
                            pixels=art.crop((x+dx,y+dy,x+dx+8,y+dy+8)).tobytes()
                            if pixels not in tile_lookup: tile_lookup[pixels]=len(unique_tiles); unique_tiles.append(pixels)
                            refs.append(tile_lookup[pixels])
                        surface=cells.crop((x//4,y//4,x//4+4,y//4+4)).tobytes()
                        meta_key=tuple(refs),surface
                        if meta_key not in meta_lookup:
                            meta_lookup[meta_key]=len(metatiles); metatiles.append(refs); meta_surfaces.extend(surface)
                        chunk.append(meta_lookup[meta_key])
                chunk=tuple(chunk)
                if chunk not in chunk_lookup:
                    chunk_lookup[chunk]=len(chunks); chunks.append(chunk); chunk_art.append(art); chunk_masks.append(cells)
                chunk_id=chunk_lookup[chunk]; source_cache[key]=chunk_id
            chunk_ids.append(chunk_id)
            mask.paste(chunk_masks[chunk_id],(cx*64,cy*64))
            px,py=cx*preview.width//columns,cy*preview.height//rows
            pw,ph=(cx+1)*preview.width//columns-px,(cy+1)*preview.height//rows-py
            preview.paste(chunk_art[chunk_id].resize((pw,ph),Image.Resampling.NEAREST),(px,py))
            chunk=chunks[chunk_id]
            for dy in range(16):
                begin=(cy*16+dy)*n+cx*16
                ids[begin:begin+16]=array('H',chunk[dy*16:dy*16+16])
    def driveable(x,y):
        return all(0<=x+dx<w and 0<=y+dy<h and mask.getpixel(((x+dx)//4,(y+dy)//4))!=3
                   for dx,dy in [(0,0),(7,0),(-7,0),(0,7),(0,-7),(5,5),(-5,5),(5,-5),(-5,-5)])
    if not driveable(*start): raise ValueError('Spawn footprint is obstructed')
    for a,b in zip(route,route[1:]):
        count=max(1,int(math.dist(a,b)))
        for i in range(count+1):
            p=[round(a[k]+(b[k]-a[k])*i/count) for k in range(2)]
            if not driveable(*p): raise ValueError(f'Verification route obstructed at {p}')
    unreachable=disconnected_cells(mask,start)
    if unreachable: raise ValueError(f'{unreachable} traversable cells are disconnected from spawn')
    return dict(unique_tiles=unique_tiles,metatiles=metatiles,meta_surfaces=meta_surfaces,ids=ids,
                chunks=chunks,chunk_ids=chunk_ids,chunk_art=chunk_art,mask=mask,preview=preview,
                start=start,route=route,prop_count=prop_count,unreachable=unreachable,
                source_patterns=len(source_cache))
