// Exercise the actual runtime decoder/cache against uncompressed build inputs.
#include "chunk_cache.h"
#include <algorithm>
#include <array>
#include <cassert>
#include <cstdio>
#include <fstream>
#include <random>
#include <vector>

int main() {
    std::ifstream input("artifacts/open_world/chunk-fixture.bin",std::ios::binary);
    uint32_t header[2]; input.read(reinterpret_cast<char*>(header),sizeof(header));
    assert(input && header[0]>0 && header[1]>0);
    int count=int(header[0]);
    std::vector<uint32_t> offsets(count+1);
    std::vector<uint8_t> blob(header[1]),expected(count*512);
    input.read(reinterpret_cast<char*>(offsets.data()),int(offsets.size()*4));
    input.read(reinterpret_cast<char*>(blob.data()),int(blob.size()));
    input.read(reinterpret_cast<char*>(expected.data()),int(expected.size()));
    assert(input);
    chunk_cache cache;
    int checked=0;
    auto load=[&](int slot,int id) {
        uint32_t offset=offsets[id]&chunk_cache::offset_mask;
        int size=int((offsets[id+1]&chunk_cache::offset_mask)-offset);
        assert(offset+size<=blob.size());
        const auto* cells=cache.get(slot,id,blob.data()+offset,size,offsets[id]&chunk_cache::raw_flag);
        assert(cells && std::equal(expected.begin()+id*512,expected.begin()+(id+1)*512,
                                  reinterpret_cast<const uint8_t*>(cells)));
        int loads=cache.loads();
        assert(cache.find(slot,id)==cells);
        assert(cache.get(slot,id,blob.data()+offset,size,offsets[id]&chunk_cache::raw_flag)==cells);
        assert(cache.loads()==loads); // Repeated graphic/collision reads do not decode again.
        ++checked;
    };
    for(int id=0;id<count;++id) load(id%9,id);
    assert(cache.decodes()>0 && cache.loads()==count);
    std::mt19937 rng(917);
    for(int i=0;i<20000;++i) {
        if(i%79==0) { cache.reset(); assert(cache.loads()==0 && cache.decodes()==0); }
        load(int(rng()%9),int(rng()%count));
    }
    // Every translated neighbouring 3x3 set maps to nine distinct cache slots.
    for(int y=0;y<32;++y) for(int x=0;x<32;++x) {
        std::array<bool,9> seen{};
        for(int yy=y;yy<y+3;++yy) for(int xx=x;xx<x+3;++xx) {
            int slot=chunk_cache::slot_at(xx,yy); assert(!seen[slot]); seen[slot]=true;
        }
    }
    // Raw fallback and rejection of bad input, including failed-load invalidation.
    cache.reset();
    std::array<uint8_t,512> raw{},decoded{};
    for(auto& value:raw) value=uint8_t(rng());
    const auto* cells=cache.get(0,count,raw.data(),512,true);
    assert(cells && std::equal(raw.begin(),raw.end(),reinterpret_cast<const uint8_t*>(cells)));
    assert(cache.loads()==1 && cache.decodes()==0);
    const uint8_t bad_distance[]={0x10,0,2,0,128,0,0};
    assert(!cache.get(0,count+1,bad_distance,sizeof(bad_distance),false));
    assert(!cache.find(0,count));
    assert(!chunk_cache::decode(raw.data(),3,decoded.data()));
    assert(!chunk_cache::decode(bad_distance,sizeof(bad_distance),decoded.data()));
    assert(!cache.get(0,count+2,raw.data(),511,true));
    // Every truncated prefix of a real stream must fail until all output tokens exist.
    for(int id=0;id<count;++id) if(!(offsets[id]&chunk_cache::raw_flag)) {
        int offset=int(offsets[id]),size=int((offsets[id+1]&chunk_cache::offset_mask)-offset);
        for(int length=0;length<size-4;++length)
            assert(!chunk_cache::decode(blob.data()+offset,length,decoded.data()));
        break;
    }
    std::printf("PASS compressed chunk cache: %d exact comparisons; hits, eviction, resets, raw fallback, malformed streams; %zu bytes RAM\n",
                checked,sizeof(cache));
}
