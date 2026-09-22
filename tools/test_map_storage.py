"""Check the optimized exhaustive audit/flood against simple independent versions."""
from collections import deque
import random
from PIL import Image
from map_storage_audit import tile_capacity,tile_capacity_brute
from world_compile import disconnected_cells


def main():
    rng=random.Random(781)
    for columns,rows in [(32,32),(64,48),(96,64)]:
        metas=[tuple(rng.randrange(400) for _ in range(4)) for _ in range(90)]
        chunks=[tuple(rng.randrange(30*i,30*i+30) for _ in range(256)) for i in range(3)]
        chunk_ids=[rng.randrange(3) for _ in range(columns//16*rows//16)]
        ids=[chunks[chunk_ids[(y//16)*(columns//16)+x//16]][y%16*16+x%16]
             for y in range(rows) for x in range(columns)]
        fast=tile_capacity(ids,metas,columns,rows,chunks=chunks,chunk_ids=chunk_ids)
        slow=tile_capacity_brute(ids,metas,columns,rows)
        for key in ('max_visible_unique_tiles','camera_windows_checked','average_visible_unique_tiles','tile_slots'):
            assert fast[key]==slow[key],(key,fast,slow)
    for _ in range(100):
        width,height=27,19
        raw=bytes(rng.choice([0,1,2,3,3]) for _ in range(width*height))
        start=next(i for i,v in enumerate(raw) if v!=3)
        seen={start}; queue=deque([start])
        while queue:
            i=queue.popleft(); x,y=i%width,i//width
            for xx,yy in [(x-1,y),(x+1,y),(x,y-1),(x,y+1)]:
                j=yy*width+xx
                if 0<=xx<width and 0<=yy<height and raw[j]!=3 and j not in seen:
                    seen.add(j); queue.append(j)
        expected=sum(v!=3 and i not in seen for i,v in enumerate(raw))
        mask=Image.frombytes('L',(width,height),raw)
        assert disconnected_cells(mask,(start%width*4,start//width*4))==expected
    print('PASS build audits: exhaustive neighbourhood audit equals brute force; scanline connectivity equals pixel flood',flush=True)


if __name__=='__main__': main()
