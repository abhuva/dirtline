#pragma once
#include <cstdint>

// Fixed working set for 256px world chunks, shared by graphics and collision.
// 3x3 modulo placement is collision-free for any neighbouring 3x3 region.
// IDs and compressed bytes remain in ROM. No heap allocation during driving.
class chunk_cache {
public:
    static constexpr int slot_count=9, cells_per_chunk=256, bytes_per_chunk=512;
    static constexpr uint32_t raw_flag=0x80000000u, offset_mask=0x7fffffffu;

    void reset() {
        for(auto& tag:_tags) tag=-1;
        _loads=0; _decodes=0;
    }
    static int slot_at(int chunk_x,int chunk_y) { return (chunk_y%3)*3+chunk_x%3; }
    const uint16_t* find(int slot,int id) const { return _tags[slot]==id ? _cells[slot] : nullptr; }
    const uint16_t* get(int slot,int id,const uint8_t* data,int size,bool raw) {
        if(_tags[slot]==id) return _cells[slot];
        // Invalidate first: a failed decode must never leave a valid old tag.
        _tags[slot]=-1;
        auto* output=reinterpret_cast<uint8_t*>(_cells[slot]);
        if(raw) {
            if(size!=bytes_per_chunk) return nullptr;
            for(int i=0;i<bytes_per_chunk;++i) output[i]=data[i];
        } else {
            if(!decode(data,size,output)) return nullptr;
            ++_decodes;
        }
        _tags[slot]=id; ++_loads;
        return _cells[slot];
    }
    int loads() const { return _loads; }
    int decodes() const { return _decodes; }

    // Bounded LZ77 decoder. Overlapping copies (including distance 1) are legal.
    // Byte writes target ordinary RAM, never VRAM. Input is importer-validated.
    static bool decode(const uint8_t* src,int size,uint8_t* dst) {
        if(size<4 || src[0]!=0x10 || src[1]!=0 || src[2]!=2 || src[3]!=0) return false;
        int input=4,output=0;
        while(output<bytes_per_chunk) {
            if(input>=size) return false;
            unsigned flags=src[input++];
            for(unsigned bit=128;bit && output<bytes_per_chunk;bit>>=1) {
                if(flags&bit) {
                    if(input+2>size) return false;
                    unsigned token=(unsigned(src[input])<<8)|src[input+1]; input+=2;
                    int length=int(token>>12)+3, distance=int(token&4095)+1;
                    if(distance>output || output+length>bytes_per_chunk) return false;
                    for(int i=0;i<length;++i) { dst[output]=dst[output-distance]; ++output; }
                } else {
                    if(input>=size) return false;
                    dst[output++]=src[input++];
                }
            }
        }
        return true;
    }
private:
    alignas(4) uint16_t _cells[slot_count][cells_per_chunk];
    int _tags[slot_count]={-1,-1,-1,-1,-1,-1,-1,-1,-1};
    int _loads=0,_decodes=0;
};
