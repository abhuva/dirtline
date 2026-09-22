#pragma once
#include <cstdint>

// Portable, integer-only operations. Every grid is 64x64, row-major.
// Masks use 1 for wall/selected and 0 for floor/unselected.
namespace mapgen {
inline constexpr int side=64, cells=side*side;
using progress_fn=void(*)(int);
inline uint32_t next(uint32_t& state) {
    state^=state<<13; state^=state>>17; state^=state<<5; return state;
}
inline uint32_t hash(uint32_t value) {
    value^=value>>16; value*=0x7feb352du; value^=value>>15;
    value*=0x846ca68bu; return value^(value>>16);
}
inline uint32_t stream_seed(uint32_t seed,uint32_t stream) {
    uint32_t result=stream?hash(seed^hash(stream)):seed;
    return result?result:1;
}
inline bool edge(int x,int y,int border) {
    return x<border || y<border || x>=side-border || y>=side-border;
}
inline void random_fill(uint8_t* output,uint32_t rng,int density,int border,progress_fn progress=nullptr) {
    // Short-circuit border cells intentionally: preserves the original RNG sequence.
    for(int y=0;y<side;++y) {
        for(int x=0;x<side;++x)
            output[y*side+x]=edge(x,y,border) || next(rng)%100<unsigned(density);
        if(progress && y%4==3) progress(y/8);
    }
}
inline void cellular(const uint8_t* input,uint8_t* output,int birth,int survive,
                     int border,int neighbourhood,const uint8_t* mask=nullptr,progress_fn progress=nullptr) {
    for(int y=0;y<side;++y) {
      for(int x=0;x<side;++x) {
        int at=y*side+x, neighbours=0;
        if(edge(x,y,border)) { output[at]=1; continue; }
        if(mask && !mask[at]) { output[at]=input[at]; continue; }
        for(int dy=-1;dy<=1;++dy) for(int dx=-1;dx<=1;++dx) {
            if((!dx && !dy) || (neighbourhood==4 && dx && dy)) continue;
            int xx=x+dx,yy=y+dy;
            neighbours+=(xx<0 || yy<0 || xx>=side || yy>=side)?1:input[yy*side+xx];
        }
        // Birth/survival are neighbour-count bitsets; the center is excluded.
        output[at]=uint8_t(((input[at]?survive:birth)>>neighbours)&1);
      }
      if(progress && y%4==3) progress(30);
    }
}
}
