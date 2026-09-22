#pragma once
#include "bn_tile.h"
#include "bn_color.h"

// Scene data stays in ROM; only nearby chunk IDs are decoded into fixed RAM.
// Physics queries surfaces without knowing the renderer.
namespace world_map {
void select(int index,uint32_t seed=0,void(*progress)(int)=nullptr);
int index();
int width();
int height();
int start_x();
int start_y();
int tile_slots();
int chunk_loads();
int chunk_decodes();
int chunk_cache_bytes();
int surface_at(int x, int y);
bool solid_at(int x,int y);
int radar_surface_at(int x,int y);
uint16_t tile_at(int x, int y);
const bn::tile* tiles();
const bn::color* palette();
int palette_colors();
}
