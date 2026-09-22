"""One-time, explicit layout migration: repeat the existing district 2 x 2.

Not run by builds. Keeps a byte-for-byte original beside the expanded map;
only joins internal borders/roads and clears scenery across those connections.
No new artwork or tileset definitions are introduced.
"""
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'maps/open_world'


def expand():
    path = ROOT / 'world.tmj'
    original = path.read_bytes()
    world = json.loads(original)
    if (world['width'], world['height']) != (128, 128):
        raise ValueError('Expected the original 2048-square map; refusing repeated expansion')
    backup = ROOT / 'world-2048.tmj'
    if backup.exists():
        raise ValueError('Backup already exists; refusing to overwrite it')
    ground = next(layer for layer in world['layers'] if layer['name'] == 'Ground')
    old = ground['data']
    n = 256
    kinds = [(old[(y % 128)*128+x % 128]-1)//256 for y in range(n) for x in range(n)]
    # Remove only the two internal water borders; outer shores remain solid.
    for y in range(n):
        for x in range(n):
            if (125 <= x <= 130 or 125 <= y <= 130) and 3 <= x < n-3 and 3 <= y < n-3:
                kinds[y*n+x] = 0
    connections = [(111, 93+dy, 145, 98+dy) for dy in (0,128)]
    connections += [(61+dx, 111, 66+dx, 145) for dx in (0,128)]
    for left, top, right, bottom in connections:
        for y in range(top, bottom+1):
            for x in range(left, right+1):
                kinds[y*n+x] = 1
    data = [old[(y % 128)*128+x % 128] for y in range(n) for x in range(n)]
    # Repaint only changed cells and their edge neighbours using the same atlas.
    for y in range(n):
        for x in range(n):
            neighbours = [(x,y),(x,y-1),(x+1,y),(x,y+1),(x-1,y)]
            if not any(0 <= xx < n and 0 <= yy < n and
                       kinds[yy*n+xx] != (old[(yy % 128)*128+xx % 128]-1)//256
                       for xx,yy in neighbours):
                continue
            kind = kinds[y*n+x]; edges = 0
            for bit,dx,dy in [(1,0,-1),(2,1,0),(4,0,1),(8,-1,0)]:
                if not (0 <= x+dx < n and 0 <= y+dy < n) or kinds[(y+dy)*n+x+dx] != kind:
                    edges |= bit
            data[y*n+x] = 1+kind*256+edges*16+(y % 4)*4+x % 4
    ground.update(width=n, height=n, data=data)
    for layer in world['layers']:
        if layer['type'] != 'objectgroup':
            continue
        expanded = []
        for dy in (0,2048):
            for dx in (0,2048):
                for obj in layer['objects']:
                    if obj.get('type') in ('spawn','test_route') and (dx or dy):
                        continue
                    item = copy.deepcopy(obj)
                    item['x'] += dx; item['y'] += dy
                    if 'gid' in item:
                        x,y,w,h = item['x'],item['y']-item['height'],item['width'],item['height']
                        if any(x < (r+1)*16+16 and x+w > l*16-16 and
                               y < (b+1)*16+16 and y+h > t*16-16 for l,t,r,b in connections):
                            continue
                    if item.get('type') == 'test_route':
                        # Keep the old garage/dirt loop, then visit all four districts.
                        item['polyline'] += [dict(x=x,y=y) for x,y in [
                            (3008,1536),(3072,1600),(3072,3520),(3008,3584),
                            (1088,3584),(1024,3520),(1024,1600),(960,1536),(512,1536)]]
                    expanded.append(item)
        layer['objects'] = expanded
    next_id = 1
    for layer in world['layers']:
        for obj in layer.get('objects',[]):
            obj['id'] = next_id; next_id += 1
    world.update(width=n, height=n, nextobjectid=next_id)
    backup.write_bytes(original)
    path.write_text(json.dumps(world,indent=2)+'\n',encoding='utf8')
    print('Expanded to 4096 x 4096; original retained at maps/open_world/world-2048.tmj')


if __name__ == '__main__':
    expand()
