#pragma once
#include "bn_common.h"
#include "cave_layout.h"
#include "enemy_spawns.h"

namespace wasteland {
void generate(uint32_t seed,cave_layout::progress_fn progress);
void release();
BN_CODE_IWRAM bool active();
BN_CODE_IWRAM const cave_layout& layout();
uint32_t fixed_seed();
int minimap_cell(int x,int y); // 1 floor, 2 wall, 3 road.
int generations();
int generation_updates();
int generation_scratch_bytes();
int layout_bytes();
void populate_spawns(enemy_spawns& out,cave_layout::progress_fn progress);
bool has_decoration();
BN_CODE_IWRAM uint8_t decoration_patch(int cell_x,int cell_y);
BN_CODE_IWRAM int surface_at(int x,int y);
BN_CODE_IWRAM uint16_t tile_at(int tile_x,int tile_y);
}
