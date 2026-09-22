#include "world_map.h"
#include "generated/track_data.h"
#include "generated/course_graphics.h"
#include "generated/open_world.h"
#include "chunk_cache.h"
#include "bn_assert.h"
#include "wasteland.h"
#include "generated/wasteland_art.h"

namespace world_map {
namespace {
int selected=0;
chunk_cache decoded;
uint16_t metatile_at(int x,int y) {
    const int cx=x/16,cy=y/16;
    const int chunk=open_world::chunk_ids[cy*open_world::chunk_columns+cx];
    const int slot=chunk_cache::slot_at(cx,cy);
    if(const auto* cells=decoded.find(slot,chunk)) return cells[(y%16)*16+x%16];
    const uint32_t entry=open_world::chunk_offsets[chunk];
    const uint32_t offset=entry&chunk_cache::offset_mask;
    const int size=int((open_world::chunk_offsets[chunk+1]&chunk_cache::offset_mask)-offset);
    const auto* cells=decoded.get(slot,chunk,
        open_world::chunk_data+offset,size,entry&chunk_cache::raw_flag);
    BN_ASSERT(cells,"Invalid compressed map chunk");
    return cells[(y%16)*16+x%16];
}
}
void select(int index,uint32_t seed,void(*progress)(int)) {
    selected=index>=0 && index<4?index:0; decoded.reset();
    if(selected>=2) wasteland::generate(selected==2?wasteland::fixed_seed():seed,progress);
    else wasteland::release();
}
int index() { return selected; }
int width() { return selected>=2 ? cave_layout::extent : selected ? open_world::width : world::width; }
int height() { return selected>=2 ? cave_layout::extent : selected ? open_world::height : world::height; }
int start_x() { return selected>=2 ? wasteland::layout().spawn().x : selected ? open_world::start_x : world::start_x; }
int start_y() { return selected>=2 ? wasteland::layout().spawn().y : selected ? open_world::start_y : world::start_y; }
int tile_slots() { return selected>=2 ? wasteland_art::tile_slots : selected ? open_world::tile_slots : 672; }
int chunk_loads() { return decoded.loads(); }
int chunk_decodes() { return decoded.decodes(); }
int chunk_cache_bytes() { return sizeof(decoded); }
bool solid_at(int x,int y) {
    if(selected>=2) {
        const auto& cave=wasteland::layout();
        return cave.solid(x,y) || cave.town_solid(x,y);
    }
    return surface_at(x,y)==3;
}
int surface_at(int x,int y) {
    if(x<0 || y<0 || x>=width() || y>=height()) return 3;
    if(selected>=2) return wasteland::surface_at(x,y);
    if(!selected) return world::surfaces[(y/world::cell_size)*world::columns+x/world::cell_size];
    const auto id=metatile_at(x/16,y/16);
    // Four-pixel subcells preserve prop footprints independently of their art.
    return open_world::surfaces[id*16+(y%16)/4*4+(x%16)/4];
}
uint16_t tile_at(int x,int y) {
    const int columns=width()/8,rows=height()/8;
    x=x<0?0:x>=columns?columns-1:x;
    y=y<0?0:y>=rows?rows-1:y;
    if(selected>=2) return wasteland::tile_at(x,y);
    if(!selected) return course_graphics::tile_ids[y*columns+x];
    const auto id=metatile_at(x/2,y/2);
    return open_world::metatiles[id*4+(y%2)*2+x%2];
}
int radar_surface_at(int x,int y) {
    // Wasteland surface_at already checks bounds; skip generic map dispatch.
    if(selected>=2) return wasteland::surface_at(x,y);
    if(selected!=1) return surface_at(x,y);
    if(x<0 || y<0 || x>=width() || y>=height()) return 3;
    // Broad radar queries must not churn the nearby physics/graphics decoder.
    // Four 16px-cell surface samples per byte, deduplicated with ROM chunks.
    int chunk=open_world::chunk_ids[(y/256)*open_world::chunk_columns+x/256];
    int at=chunk*256+(y%256)/16*16+(x%256)/16;
    return (open_world::radar_surfaces[at/4]>>((at%4)*2))&3;
}
const bn::tile* tiles() { return selected>=2 ? wasteland_art::tiles : selected ? open_world::tiles : course_graphics::tiles; }
const bn::color* palette() { return selected>=2 ? wasteland_art::palette : course_graphics::palette; }
int palette_colors() { return selected>=2 ? wasteland_art::palette_colors : 256; }
}
