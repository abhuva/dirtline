// Butano's .bn_iwram.cpp suffix compiles the cache loop as ARM code. Only
// set_camera is placed in IWRAM; setup/teardown stay in ROM.
#include "terrain_streamer.h"
#include "world_map.h"
#include "bn_bg_palette_item.h"
#include "bn_bg_palette_ptr.h"
#include "bn_regular_bg_map_item.h"
#include "bn_core.h"
#include "bn_memory.h"
#include "bn_size.h"
#include "local_minimap.h"
#include "decoration_view.h"

terrain_streamer* terrain_streamer::_active=nullptr;

terrain_streamer::terrain_streamer() :
    _capacity(world_map::tile_slots()),
    _tiles(bn::regular_bg_tiles_ptr::allocate(_capacity*2,bn::bpp_mode::BPP_8,false)),
    _map(bn::regular_bg_map_ptr::create(bn::regular_bg_map_item(_cells[0],bn::size(32,32)),
         _tiles,bn::bg_palette_ptr::create(bn::bg_palette_item(bn::span<const bn::color>(world_map::palette(),world_map::palette_colors()),bn::bpp_mode::BPP_8)))),
    _bg(bn::regular_bg_ptr::create(_map)), _vram(_tiles.vram()->data()) {
    invalidate();
    _bg.set_priority(3);
    _bg.set_visible(false);
    _active=this;
    bn::core::set_vblank_callback(vblank);
}

void terrain_streamer::invalidate() {
    BN_ASSERT(!_pending,"Cannot change map during an upload");
    BN_ASSERT(_capacity>0 && _capacity<=terrain_cache::max_slots,"Invalid terrain cache capacity");
    _cache.reset(_capacity);
    for(auto& entry:_positions) entry=0xFFFFFFFF;
    _left=-1000; _top=-1000;
    _source_tiles=world_map::tiles();
}

terrain_streamer::~terrain_streamer() {
    bn::core::set_vblank_callback(nullptr);
    _active=nullptr;
}

void terrain_streamer::vblank() {
    if(_active) _active->commit();
    local_minimap::commit();
    decoration_view::commit();
}

void terrain_streamer::commit() {
    _uploaded_bytes=0;
    // Large jumps (start/reset) are populated while hidden over several frames.
    for(int i=0;i<96 && _pending;++i) {
        const upload& value=_uploads[--_pending];
        bn::memory::copy(_source_tiles[value.source*2],2,_vram[value.slot*2]);
        _uploaded_bytes+=64;
    }
}

void terrain_streamer::set_visible(bool visible) {
    _visible=visible;
    _bg.set_visible(visible);
}

void terrain_streamer::set_camera(int x,int y) {
    const int left=(x-120)/8,top=(y-80)/8;
    const bool jump=left-_left>1 || _left-left>1 || top-_top>1 || _top-top>1;
    if(left!=_left || top!=_top) {
        BN_ASSERT(!_pending,"Uncommitted terrain uploads");
        // On a jump, wrapped BG cells may have overwritten positions that the
        // smaller bookkeeping ring still remembers. Re-resolve the entire view.
        if(jump) {
            // Whole-view reconstruction is a loading operation, not part of
            // the current physics/HUD frame. Keep it off-screen and give it
            // its own frame budget even when most graphics are already cached.
            _bg.set_visible(false);
            bn::core::update();
            for(auto& entry:_positions) entry=0xFFFFFFFF;
        }
        _cache.begin_view();
        int changes=0;
        // First protect EVERY tile still needed by the next view, including
        // old tiles that newly entering cells will reference. No eviction yet.
        for(int row=top;row<top+terrain_cache::window_rows;++row) {
            for(int col=left;col<left+terrain_cache::window_columns;++col) {
                const int position_slot=(row%22)*32+(col%32);
                const int cell=(row%32)*32+(col%32);
                const uint32_t position=(uint32_t(row)<<16)|uint32_t(col);
                if(_positions[position_slot]==position) {
                    _cache.pin(_cells[cell]);
                    continue;
                }
                _positions[position_slot]=position;
                const uint16_t source=world_map::tile_at(col,row);
                int slot=_cache.find(source);
                if(slot>=0) _cache.pin(slot);
                _uploads[changes++]={uint16_t(cell),source};
            }
        }
        // Repeated source IDs resolve to the same slot, even within one upload
        // batch. Old off-screen slots may now be safely recycled.
        for(int i=0;i<changes;++i) {
            const auto cell_change=_uploads[i];
            bool upload_needed=false;
            const int slot=_cache.acquire(cell_change.source,upload_needed);
            BN_ASSERT(slot>=0,"Terrain cache exceeded: regenerate map capacity audit");
            _cells[cell_change.slot]=uint16_t(slot);
            // _pending <= i: only overwrite scratch entries already consumed.
            if(upload_needed) _uploads[_pending++]={uint16_t(slot),cell_change.source};
        }
        _map.reload_cells_ref();
        _left=left; _top=top;
    }
    _bg.set_position(128-(x%256),128-(y%256));
    if(jump || _pending>96) {
        _bg.set_visible(false);
        do { bn::core::update(); } while(_pending);
        _bg.set_visible(_visible);
    }
}
