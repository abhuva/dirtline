#include "wasteland.h"
#include "generated/wasteland_art.h"
#include "generated/wasteland_recipe.h"
#include "bn_unique_ptr.h"
#include "wasteland_tiles.h"
#include "decoration_layout.h"

namespace wasteland {
namespace {
bn::unique_ptr<cave_layout> current;
struct ground_grid { uint8_t ids[64*64]; };
bn::unique_ptr<ground_grid> ground;
bn::unique_ptr<road_network> roads;
struct spawn_locations { uint16_t xy[enemy_spawns::capacity*2];int count=0; };
bn::unique_ptr<spawn_locations> spawn_points;
bn::unique_ptr<decoration_layout> decoration;
int serial=0,updates=0;
cave_layout::progress_fn loading_callback=nullptr;
void progress(int value) { ++updates; if(loading_callback) loading_callback(value); }
}
void generate(uint32_t seed,cave_layout::progress_fn callback) {
    if(!current) current.reset(new cave_layout());
    bn::unique_ptr<mapgen::workspace> scratch(new mapgen::workspace());
    loading_callback=callback; updates=0;
    auto result=mapgen::execute(active_recipe::nodes,active_recipe::count,seed,*scratch,progress);
    BN_ASSERT(result.status==mapgen::error::ok && result.type==mapgen::kind::world,"Invalid map recipe");
    *current=scratch->layout;
    if(scratch->roads.width) {
        if(!roads) roads.reset(new road_network());
        *roads=scratch->roads;
    } else roads.reset();
    if(active_recipe::material_count) {
        auto materials=mapgen::execute(active_recipe::material_nodes,active_recipe::material_count,seed,*scratch,progress);
        BN_ASSERT(materials.status==mapgen::error::ok && materials.type==mapgen::kind::material,"Invalid ground recipe");
        if(!ground) ground.reset(new ground_grid());
        for(int i=0;i<64*64;++i) ground->ids[i]=materials.data[i];
    } else ground.reset();
    if(active_recipe::spawn_count) {
        auto field=mapgen::execute(active_recipe::spawn_nodes,active_recipe::spawn_count,seed,*scratch,progress);
        BN_ASSERT(field.status==mapgen::error::ok && field.type==mapgen::kind::spawns);
        const auto& config=active_recipe::spawn_nodes[active_recipe::spawn_count-1];
        bn::unique_ptr<enemy_spawns> generated(new enemy_spawns());
        generated->generate_recipe(*current,field.data,config.p[0],config.p[1],config.p[2],config.stream,progress);
        if(!spawn_points)spawn_points.reset(new spawn_locations());
        spawn_points->count=generated->count;
        for(int i=0;i<generated->count;++i) {
            spawn_points->xy[i*2]=generated->points[i].x;spawn_points->xy[i*2+1]=generated->points[i].y;
        }
    } else spawn_points.reset();
    if(active_recipe::decoration_count) {
        auto field=mapgen::execute(active_recipe::decoration_nodes,active_recipe::decoration_count,seed,*scratch,progress);
        BN_ASSERT(field.status==mapgen::error::ok && field.type==mapgen::kind::decoration);
        if(!decoration)decoration.reset(new decoration_layout());
        const auto& config=active_recipe::decoration_nodes[active_recipe::decoration_count-1];
        decoration->configure(seed,config.stream,field.data,config.p);
    } else decoration.reset();
    loading_callback=nullptr; ++serial;
}
void release() { current.reset(); ground.reset(); roads.reset();spawn_points.reset();decoration.reset(); }
void populate_spawns(enemy_spawns& out,cave_layout::progress_fn callback) {
    if(!spawn_points){out.generate(*current,callback);return;}
    out.count=spawn_points->count;
    for(int i=0;i<out.count;++i){out.points[i]=enemy_spawns::point();out.points[i].x=spawn_points->xy[i*2];out.points[i].y=spawn_points->xy[i*2+1];}
}
bool has_decoration() { return bool(decoration); }
uint8_t decoration_patch(int x,int y) { return decoration?decoration->patch(x,y,*current,roads.get()):0; }
bool active() { return bool(current); }
const cave_layout& layout() { BN_ASSERT(current); return *current; }
uint32_t fixed_seed() { return active_recipe::seed; }
int minimap_cell(int x,int y) {
    if(current->wall(x,y))return 2;
    return roads && (roads->links[y*64+x]&15)?3:1;
}
int generations() { return serial; }
int generation_updates() { return updates; }
int generation_scratch_bytes() { return sizeof(mapgen::workspace); }
int layout_bytes() { return sizeof(cave_layout)+(ground?sizeof(ground_grid):0)+(roads?sizeof(road_network):0)+(spawn_points?sizeof(spawn_locations):0)+(decoration?sizeof(decoration_layout):0); }
int surface_at(int x,int y) {
    return wasteland_tiles::surface(*current,ground?ground->ids:nullptr,x,y,roads.get());
}
uint16_t tile_at(int x,int y) {
    return wasteland_art::refs[wasteland_tiles::reference(*current,ground?ground->ids:nullptr,x,y,roads.get())];
}
}
