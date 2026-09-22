#pragma once
#include "bn_regular_bg_ptr.h"
#include "bn_regular_bg_tiles_ptr.h"
#include "bn_regular_bg_map_ptr.h"
#include "bn_regular_bg_map_cell.h"
#include "bn_tile.h"
#include "terrain_cache.h"

// Visible cells share content-addressed 8bpp tiles; complete maps stay in ROM.
class terrain_streamer {
public:
    terrain_streamer();
    ~terrain_streamer();
    BN_CODE_IWRAM void set_camera(int x,int y);
    void set_visible(bool visible);
    void invalidate();
    int uploaded_bytes() const { return _uploaded_bytes; }
    int capacity() const { return _capacity; }
    int unique_tiles() const { return _cache.pinned_count(); }
    int working_ram_bytes() const { return sizeof(*this); }
private:
    struct upload { uint16_t slot, source; };
    alignas(4) bn::regular_bg_map_cell _cells[1024] = {};
    terrain_cache _cache;
    uint32_t _positions[704];
    // Reused as (BG cell, source) scratch before compacting to (VRAM slot, source).
    upload _uploads[704];
    int _pending=0, _uploaded_bytes=0, _left=-1000, _top=-1000;
    bool _visible=false;
    int _capacity;
    bn::regular_bg_tiles_ptr _tiles;
    bn::regular_bg_map_ptr _map;
    bn::regular_bg_ptr _bg;
    bn::tile* _vram;
    const bn::tile* _source_tiles=nullptr;
    void commit();
    static terrain_streamer* _active;
    static void vblank();
};
