"""Explicit 4096 -> 16384 editor-layout migration using existing placements only."""
import copy
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]/'maps/open_world'


def main():
    path=ROOT/'world.tmj'; backup=ROOT/'world-4096.tmj'
    original=path.read_bytes(); world=json.loads(original)
    if (world['width'],world['height'])!=(256,256) or backup.exists():
        raise ValueError('Expected the 4096 map and no existing backup; refusing to overwrite/re-expand')
    ground=next(layer for layer in world['layers'] if layer['name']=='Ground')
    old=ground['data']; base=256; n=1024
    data=[old[(y%base)*base+x%base] for y in range(n) for x in range(n)]
    kinds=bytearray((gid-1)//256 for gid in data)
    seams={p for seam in (256,512,768) for p in range(seam-3,seam+3)}
    changed=set()
    for y in range(3,n-3):
        for x in (range(3,n-3) if y in seams else seams):
            at=y*n+x
            if kinds[at]!=0: kinds[at]=0; changed.add(at)
    connections=[(seam-17,93+dy,seam+17,98+dy) for seam in (256,512,768) for dy in range(0,n,128)]
    connections += [(61+dx,seam-17,66+dx,seam+17) for seam in (256,512,768) for dx in range(0,n,128)]
    for left,top,right,bottom in connections:
        for y in range(top,bottom+1):
            for x in range(left,right+1):
                at=y*n+x
                if kinds[at]!=1: kinds[at]=1; changed.add(at)
    repaint=set(changed)
    for at in changed:
        x,y=at%n,at//n
        for xx,yy in [(x-1,y),(x+1,y),(x,y-1),(x,y+1)]:
            if 0<=xx<n and 0<=yy<n: repaint.add(yy*n+xx)
    for at in repaint:
        x,y=at%n,at//n; kind=kinds[at]; edges=0
        for bit,dx,dy in [(1,0,-1),(2,1,0),(4,0,1),(8,-1,0)]:
            if not (0<=x+dx<n and 0<=y+dy<n) or kinds[(y+dy)*n+x+dx]!=kind: edges|=bit
        data[at]=1+kind*256+edges*16+(y%4)*4+x%4
    ground.update(width=n,height=n,data=data)
    for layer in world['layers']:
        if layer['type']!='objectgroup': continue
        expanded=[]
        for dy in range(0,16384,4096):
            for dx in range(0,16384,4096):
                for obj in layer['objects']:
                    if obj.get('type') in ('spawn','test_route') and (dx or dy): continue
                    item=copy.deepcopy(obj); item['x']+=dx; item['y']+=dy
                    if 'gid' in item:
                        x,y,w,h=item['x'],item['y']-item['height'],item['width'],item['height']
                        if any(x<(r+1)*16+16 and x+w>l*16-16 and y<(b+1)*16+16 and y+h>t*16-16
                               for l,t,r,b in connections): continue
                    if item.get('type')=='test_route':
                        # Serpentine across every 4096px sector; test both axes >15k.
                        item['polyline'] += [dict(x=x,y=y) for x,y in [
                            (15296,1536),(15360,1600),(15360,5568),(15296,5632),
                            (1088,5632),(1024,5696),(1024,9664),(1088,9728),
                            (15296,9728),(15360,9792),(15360,15808),(15296,15872),
                            (1088,15872),(1024,15808),(1024,1600),(960,1536),(512,1536)]]
                    expanded.append(item)
        layer['objects']=expanded
    next_id=1
    for layer in world['layers']:
        for obj in layer.get('objects',[]): obj['id']=next_id; next_id+=1
    world.update(width=n,height=n,nextobjectid=next_id)
    backup.write_bytes(original)
    path.write_text(json.dumps(world,indent=2)+'\n',encoding='utf8')
    print('Expanded to 16384 x 16384; retained maps/open_world/world-4096.tmj',flush=True)


if __name__=='__main__': main()
