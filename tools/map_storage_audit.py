"""Visible-tile capacity audit and lossless runtime chunk packing.

LZ77 has a four-byte header and 8-token flag groups; every chunk round-trips.
"""
import struct
from array import array
import sys


def tile_capacity_brute(ids, metatiles, columns, rows, fixture_path=None):
    width,height=columns*2,rows*2
    grid=[[metatiles[ids[(y//2)*columns+x//2]][(y%2)*2+x%2]
           for x in range(width)] for y in range(height)]
    # Match terrain_cache::window_columns/rows, including edge-clamped cells.
    maximum=0; busiest=None; total=0; windows=0
    for top in range(height-20+1):
        counts={}
        strip=[grid[min(y,height-1)] for y in range(top,top+21)]
        for row in strip:
            for x in range(31):
                value=row[min(x,width-1)]
                counts[value]=counts.get(value,0)+1
        for left in range(width-30+1):
            unique=len(counts); total+=unique; windows+=1
            if unique>maximum: maximum=unique; busiest=[left*8+120,top*8+80]
            if left==width-30: break
            for row in strip:
                value=row[left]
                counts[value]-=1
                if not counts[value]: del counts[value]
                value=row[min(left+31,width-1)]
                counts[value]=counts.get(value,0)+1
    slots=(maximum+31)//32*32
    if fixture_path is not None:
        fixture_path.write_bytes(struct.pack('<3I',width,height,slots)+
                                 struct.pack('<'+'H'*(width*height),*(v for row in grid for v in row)))
    return dict(window_tiles=[31,21],camera_windows_checked=windows,
                max_visible_unique_tiles=maximum,busiest_camera=busiest,
                average_visible_unique_tiles=round(total/windows,2),
                tile_slots=slots)


def tile_capacity(ids,metatiles,columns,rows,fixture_path=None,chunks=None,chunk_ids=None):
    if chunks is None:
        return tile_capacity_brute(ids,metatiles,columns,rows,fixture_path)
    width,height=columns*2,rows*2; cc,cr=columns//16,rows//16
    graphic_chunks=[]
    for chunk in chunks:
        graphic_chunks.append([array('H',(metatiles[chunk[(y//2)*16+x//2]][(y%2)*2+x%2]
                                           for x in range(32))) for y in range(32)])
    grid=[array('H') for _ in range(height)]
    patterns={}
    for cy in range(cr):
        for cx in range(cc):
            tile=graphic_chunks[chunk_ids[cy*cc+cx]]
            for dy in range(32): grid[cy*32+dy].extend(tile[dy])
            # A 31x21 view cannot span more than this exact 2x2 neighbourhood.
            key=tuple(chunk_ids[min(cy+dy,cr-1)*cc+min(cx+dx,cc-1)]
                      for dy,dx in [(0,0),(0,1),(1,0),(1,1)])+(cx==cc-1,cy==cr-1)
            if key in patterns: patterns[key][2]+=1
            else: patterns[key]=[cx*32,cy*32,1]
    maximum=0; busiest=None; total=0; windows=0; audited=0; origins=bytearray()
    for x0,y0,multiplicity in patterns.values():
        nx=min(32,width-29-x0); ny=min(32,height-19-y0)
        for dy in range(ny):
            top=y0+dy
            strip=[grid[min(y,height-1)] for y in range(top,top+21)]
            counts={}
            for row in strip:
                for x in range(x0,x0+31):
                    value=row[min(x,width-1)]; counts[value]=counts.get(value,0)+1
            for dx in range(nx):
                left=x0+dx; unique=len(counts)
                windows+=multiplicity; total+=unique*multiplicity; audited+=1
                if fixture_path is not None: origins.extend(struct.pack('<HH',left,top))
                if unique>maximum: maximum=unique; busiest=[left*8+120,top*8+80]
                if dx+1==nx: break
                for row in strip:
                    value=row[left]; counts[value]-=1
                    if not counts[value]: del counts[value]
                    value=row[min(left+31,width-1)]; counts[value]=counts.get(value,0)+1
    assert windows==(width-29)*(height-19)
    slots=(maximum+31)//32*32
    if fixture_path is not None:
        if sys.byteorder!='little':
            for row in grid: row.byteswap()
        fixture_path.write_bytes(struct.pack('<3I',width,height,slots)+
            b''.join(row.tobytes() for row in grid)+struct.pack('<I',audited)+origins)
    return dict(window_tiles=[31,21],camera_windows_checked=windows,
                distinct_neighbourhoods=len(patterns),representative_windows_audited=audited,
                max_visible_unique_tiles=maximum,busiest_camera=busiest,
                average_visible_unique_tiles=round(total/windows,2),tile_slots=slots)


def lz77_encode(data):
    result=bytearray([0x10,len(data)&255,(len(data)>>8)&255,(len(data)>>16)&255])
    pos=0
    while pos<len(data):
        flag_pos=len(result); result.append(0)
        for token in range(8):
            if pos>=len(data): break
            length=0; offset=0
            if pos+3<=len(data):
                candidate=data.rfind(data[pos:pos+3],max(0,pos-4096),pos+2)
                while candidate>=max(0,pos-4096) and candidate<pos:
                    size=3
                    while size<18 and pos+size<len(data) and data[candidate+size]==data[pos+size]: size+=1
                    if size>length: length=size; offset=pos-candidate
                    if length==18: break
                    candidate=data.rfind(data[pos:pos+3],max(0,pos-4096),candidate+2)
            if length>=3:
                result[flag_pos]|=1<<(7-token)
                value=((length-3)<<12)|(offset-1)
                result.extend(struct.pack('>H',value)); pos+=length
            else:
                result.append(data[pos]); pos+=1
    # Independent chunks start on a 4-byte boundary.
    result.extend(bytes((-len(result))%4))
    return bytes(result)


def lz77_decode(data):
    assert data[0]==0x10
    size=int.from_bytes(data[1:4],'little'); pos=4; out=bytearray()
    while len(out)<size:
        flags=data[pos]; pos+=1
        for bit in range(7,-1,-1):
            if len(out)==size: break
            if flags&(1<<bit):
                value=int.from_bytes(data[pos:pos+2],'big'); pos+=2
                length=(value>>12)+3; offset=(value&4095)+1
                assert 0<offset<=len(out) and len(out)+length<=size
                for _ in range(length): out.append(out[-offset])
            else: out.append(data[pos]); pos+=1
    return bytes(out)


def pack_chunks(chunks, chunk_id_count, fixture_path=None):
    packed=bytearray(); offsets=[]; raw_chunks=[]; compressed=0
    for chunk in chunks:
        raw=struct.pack('<256H',*chunk)
        encoded=lz77_encode(raw)
        assert lz77_decode(encoded)==raw
        use_raw=len(encoded)>=len(raw)
        offsets.append(len(packed)|(0x80000000 if use_raw else 0))
        packed.extend(raw if use_raw else encoded)
        raw_chunks.append(raw)
        compressed+=not use_raw
    offsets.append(len(packed))  # End sentinel; flags are masked before subtraction.
    raw_size=len(chunks)*512+chunk_id_count*2
    encoded_size=len(packed)+len(offsets)*4+chunk_id_count*2
    if fixture_path is not None:
        fixture_path.write_bytes(struct.pack('<2I',len(chunks),len(packed))+
            struct.pack('<'+'I'*len(offsets),*offsets)+packed+b''.join(raw_chunks))
    report=dict(status='enabled in ROM; decoded on demand into a fixed nine-slot RAM cache',
                codec='independent LZ77 chunks; raw fallback; 4-byte alignment',
                raw_layout_bytes=raw_size,compressed_layout_bytes=encoded_size,
                saved_bytes=raw_size-encoded_size,
                saved_percent=round((raw_size-encoded_size)*100/raw_size,1),
                compressed_chunks=compressed,raw_chunks=len(chunks)-compressed,
                includes_chunk_offsets_and_id_grid=True,roundtripped_chunks=len(chunks),
                decoded_bytes_per_chunk=512,nine_chunk_working_set_bytes=9*512)
    return packed,offsets,report
