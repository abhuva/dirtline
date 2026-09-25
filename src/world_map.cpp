#include "world_map.h"
#include "wasteland.h"
#include "generated/wasteland_art.h"

namespace world_map {
namespace { int selected=0; }

void select(int index,void(*progress)(int)) {
    selected=index>=0 && index<wasteland::map_count()?index:0;
    wasteland::generate(selected,progress);
}
int index() { return selected; }
int width() { return cave_layout::extent; }
int height() { return cave_layout::extent; }
int start_x() { return wasteland::layout().spawn().x; }
int start_y() { return wasteland::layout().spawn().y; }
int tile_slots() { return wasteland_art::banks[wasteland::art_bank()].tile_slots; }
int resident_tile_count() { return wasteland_art::banks[wasteland::art_bank()].unique_tiles; }
int chunk_loads() { return 0; }
int chunk_decodes() { return 0; }
int chunk_cache_bytes() { return 0; }
terrain_sample terrain_at(int x,int y) {
    if(x<0 || y<0 || x>=width() || y>=height())return {0,0,3};
    const auto& art=wasteland_art::banks[wasteland::art_bank()];
    const int material=wasteland::material_at(x,y);
    const bool solid=wasteland::layout().solid(x,y) || wasteland::layout().town_solid(x,y);
    return {material,art.material_behaviors[material],solid?3:art.material_surfaces[material]};
}
int material_at(int x,int y) { return terrain_at(x,y).material; }
int material_kind(int material) {
    return wasteland_art::banks[wasteland::art_bank()].material_behaviors[material&255];
}
const char* material_name(int material) {
    const auto& art=wasteland_art::banks[wasteland::art_bank()];
    return art.material_names[art.material_textures[material&255]];
}
bool solid_at(int x,int y) {
    const auto& cave=wasteland::layout();
    return cave.solid(x,y) || cave.town_solid(x,y);
}
int surface_at(int x,int y) {
    return terrain_at(x,y).surface;
}
uint16_t tile_at(int x,int y) {
    const int columns=width()/8,rows=height()/8;
    x=x<0?0:x>=columns?columns-1:x;
    y=y<0?0:y>=rows?rows-1:y;
    return wasteland::tile_at(x,y);
}
int radar_surface_at(int x,int y) { return wasteland::surface_at(x,y); }
const bn::tile* tiles() { return wasteland_art::banks[wasteland::art_bank()].tiles; }
const bn::color* palette() { return wasteland_art::banks[wasteland::art_bank()].palette; }
int palette_colors() { return wasteland_art::banks[wasteland::art_bank()].palette_colors; }
}
