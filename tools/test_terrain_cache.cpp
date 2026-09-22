// Host tests exercise the same cache implementation used by the GBA renderer.
#include "terrain_cache.h"
#include <algorithm>
#include <cassert>
#include <cstdio>
#include <fstream>
#include <random>
#include <set>
#include <vector>

int main() {
    terrain_cache cache;
    cache.reset(32);
    bool upload=false;
    const int grass=cache.acquire(7,upload);
    assert(grass>=0 && upload);
    for(int i=0;i<651;++i) {
        assert(cache.acquire(7,upload)==grass && !upload);
    }
    assert(cache.pinned_count()==1);
    // Deliberately collide hash buckets, evict, then look up every survivor.
    for(int round=0;round<500;++round) {
        cache.begin_view();
        for(int i=0;i<32;++i) {
            uint16_t source=uint16_t(i*2048+round%1900);
            int slot=cache.acquire(source,upload);
            assert(slot>=0 && cache.source(slot)==source);
        }
        for(int i=0;i<32;++i) assert(cache.find(uint16_t(i*2048+round%1900))>=0);
        assert(cache.acquire(65000,upload)==-1);
    }
    std::ifstream input("artifacts/open_world/cache-fixture.bin",std::ios::binary);
    uint32_t dims[3]; input.read(reinterpret_cast<char*>(dims),sizeof(dims));
    assert(input && dims[2]<=704);
    int width=int(dims[0]),height=int(dims[1]),capacity=int(dims[2]);
    std::vector<uint16_t> grid(width*height);
    input.read(reinterpret_cast<char*>(grid.data()),int(grid.size()*2));
    assert(input);
    cache.reset(capacity);
    int views=0,maximum=0;
    auto view=[&](int x,int y) {
        std::vector<uint16_t> needed;
        for(int yy=y;yy<y+21;++yy) for(int xx=x;xx<x+31;++xx)
            needed.push_back(grid[std::min(yy,height-1)*width+std::min(xx,width-1)]);
        cache.begin_view();
        for(uint16_t source:needed) { int slot=cache.find(source); if(slot>=0) cache.pin(slot); }
        std::vector<int> mapped;
        for(uint16_t source:needed) {
            int slot=cache.acquire(source,upload);
            assert(slot>=0 && slot<capacity); mapped.push_back(slot);
        }
        for(unsigned i=0;i<needed.size();++i) {
            assert(cache.source(mapped[i])==needed[i]);
            assert(cache.find(needed[i])==mapped[i]);
        }
        assert(cache.pinned_count()==int(std::set<uint16_t>(needed.begin(),needed.end()).size()));
        maximum=std::max(maximum,cache.pinned_count()); ++views;
    };
    // Every view of every distinct 2x2 chunk neighbourhood. The importer proves
    // exact equivalence for all repeated locations, including clamped edges.
    uint32_t origin_count=0;
    input.read(reinterpret_cast<char*>(&origin_count),sizeof(origin_count));
    assert(input && origin_count>0);
    for(uint32_t i=0;i<origin_count;++i) {
        uint16_t xy[2]; input.read(reinterpret_cast<char*>(xy),sizeof(xy));
        assert(input); view(xy[0],xy[1]);
    }
    // Long jumps, reversals, and scene resets stress eviction and hash deletion.
    std::mt19937 rng(815);
    for(int i=0;i<10000;++i) {
        if(i%73==0) cache.reset(capacity);
        view(int(rng()%(width-29)),int(rng()%(height-19)));
    }
    std::printf("PASS shared cache: %d map views, max %d unique / %d slots; duplicates, collisions, exhaustion, jumps and resets\n",
                views,maximum,capacity);
}
