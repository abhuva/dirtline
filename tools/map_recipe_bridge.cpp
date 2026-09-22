#include "map_recipe.h"
#include "wasteland_tiles.h"
#include "enemy_spawns.h"
#include "decoration_layout.h"
#include <cstdio>
#include <cstdlib>

namespace {
mapgen::node nodes[mapgen::max_nodes];
#ifdef MAP_RECIPE_GBA_PROBE
mapgen::workspace work __attribute__((section(".ewram")));
#else
mapgen::workspace work;
#endif
mapgen::result result;
uint32_t metadata[20];
uint8_t ground[4096];
bool ground_active=false,world_ready=false;
enemy_spawns spawn_points;
decoration_layout decoration;
bool spawn_ready=false,decoration_active=false;
mapgen::node last_node;
uint32_t current_seed=0;
uint16_t point_coordinates[enemy_spawns::capacity*2];
#ifndef MAP_RECIPE_GBA_PROBE
uint8_t decoration_tiles[1024*1024];
#endif
#ifdef __EMSCRIPTEN__
uint8_t collision[1024*1024];
uint16_t render_tiles[1024*1024];
#endif
}
extern "C" {
mapgen::node* recipe_input() { return nodes; }
const uint8_t* recipe_cells() { return result.data; }
const uint32_t* recipe_meta() { return metadata; }
int recipe_run(int count,uint32_t seed) {
    result=mapgen::execute(nodes,count,seed,work);
    for(auto& v:metadata) v=0;
    metadata[0]=uint32_t(result.status); metadata[1]=uint32_t(result.type);
    metadata[2]=uint32_t(result.peak_buffers); metadata[3]=result.fallback;
    if(result.status!=mapgen::error::ok) return int(result.status);
    last_node=nodes[count-1];current_seed=seed;
    uint32_t signature=2166136261u;
    for(int i=0;i<mapgen::cells;++i) {
        signature=(signature^result.data[i])*16777619u;
        metadata[5]+=!result.data[i];
    }
    metadata[4]=signature;
    if(result.type==mapgen::kind::world) {
        world_ready=true;ground_active=false;
        spawn_ready=false;decoration_active=false;
        auto spawn=work.layout.spawn(); metadata[6]=uint32_t(spawn.x); metadata[7]=uint32_t(spawn.y);
        for(int t=0;t<6;++t) {
            auto town=work.layout.town(t); metadata[8+t*2]=uint32_t(town.x); metadata[9+t*2]=uint32_t(town.y);
        }
    }
    return 0;
}
int recipe_apply_spawns() {
    if(!world_ready || result.status!=mapgen::error::ok || result.type!=mapgen::kind::spawns)return 1;
    spawn_points.generate_recipe(work.layout,result.data,last_node.p[0],last_node.p[1],last_node.p[2],last_node.stream);
    spawn_ready=true;return 0;
}
int recipe_spawn_count() {
    if(!world_ready)return 0;
    if(!spawn_ready){spawn_points.generate(work.layout);spawn_ready=true;}
    return spawn_points.count;
}
const uint16_t* recipe_spawns() {
    for(int i=0;i<recipe_spawn_count();++i){point_coordinates[i*2]=spawn_points.points[i].x;point_coordinates[i*2+1]=spawn_points.points[i].y;}
    return point_coordinates;
}
int recipe_apply_decoration() {
    if(!world_ready || result.status!=mapgen::error::ok || result.type!=mapgen::kind::decoration)return 1;
    decoration.configure(current_seed,last_node.stream,result.data,last_node.p);decoration_active=true;return 0;
}
#ifndef MAP_RECIPE_GBA_PROBE
const uint8_t* recipe_decorations() {
    for(int cy=0;cy<256;++cy)for(int cx=0;cx<256;++cx) {
        uint8_t patch=decoration_active?decoration.patch(cx,cy,work.layout,&work.roads):0;
        for(int y=0;y<4;++y)for(int x=0;x<4;++x)decoration_tiles[(cy*4+y)*1024+cx*4+x]=decoration_layout::tile(patch,x,y);
    }
    return decoration_tiles;
}
#endif
int recipe_apply_materials() {
    if(!world_ready || result.status!=mapgen::error::ok || result.type!=mapgen::kind::material) return 1;
    for(int i=0;i<4096;++i) ground[i]=result.data[i];
    ground_active=true;return 0;
}
const uint8_t* recipe_ground() {
    if(!world_ready)return nullptr;
    if(!ground_active)for(int y=0;y<64;++y)for(int x=0;x<64;++x)ground[y*64+x]=uint8_t(work.layout.material(x*128+64,y*128+64));
    return ground;
}
uint32_t recipe_render_signature() {
    uint32_t value=2166136261u;
    for(int y=0;y<1024;y+=7)for(int x=0;x<1024;x+=7) {
        value=(value^wasteland_tiles::reference(work.layout,ground_active?ground:nullptr,x,y,&work.roads))*16777619u;
        value=(value^wasteland_tiles::surface(work.layout,ground_active?ground:nullptr,x*8+4,y*8+4,&work.roads))*16777619u;
    }
    return value;
}
#ifdef __EMSCRIPTEN__
const uint16_t* recipe_tiles() {
    if(!world_ready)return nullptr;
    for(int y=0;y<1024;++y)for(int x=0;x<1024;++x)
        render_tiles[y*1024+x]=wasteland_tiles::reference(work.layout,ground_active?ground:nullptr,x,y,&work.roads);
    return render_tiles;
}
const uint8_t* recipe_collision() {
    if(!world_ready) return nullptr;
    for(int y=0;y<1024;++y) for(int x=0;x<1024;++x)
        collision[y*1024+x]=uint8_t(work.layout.solid(x*8+4,y*8+4) || work.layout.town_solid(x*8+4,y*8+4));
    return collision;
}
#elif defined(MAP_RECIPE_GBA_PROBE)
#include "fixtures.h"
volatile uint32_t recipe_probe[4]={};
int main() {
    recipe_probe[0]=0x52435031;
    for(int f=0;f<fixture_count;++f) {
        const auto& fixture=fixtures[f];
        for(int n=0;n<fixture.count;++n) nodes[n]=fixture.program[n];
        recipe_run(fixture.count,fixture.seed);
        const auto* bytes=reinterpret_cast<const uint8_t*>(metadata);
        for(int i=0;i<80+4096;++i) {
            uint8_t actual=i<80?bytes[i]:result.data?result.data[i-80]:0;
            if(actual!=fixture.expected[i]) {
                recipe_probe[2]=uint32_t(f+1);recipe_probe[3]=uint32_t(i+1);
                while(true) asm volatile("nop");
            }
        }
        recipe_probe[1]=uint32_t(f+1);
    }
    for(int f=0;f<render_fixture_count;++f) {
        const auto& fixture=render_fixtures[f];
        for(int n=0;n<fixture.world_count;++n)nodes[n]=fixture.world[n];
        recipe_run(fixture.world_count,fixture.seed);
        if(fixture.material_count){
            for(int n=0;n<fixture.material_count;++n)nodes[n]=fixture.materials[n];
            recipe_run(fixture.material_count,fixture.seed);recipe_apply_materials();
        }
        if(recipe_render_signature()!=fixture.expected){recipe_probe[2]=uint32_t(fixture_count+f+1);while(true)asm volatile("nop");}
        recipe_probe[1]=uint32_t(fixture_count+f+1);
    }
    while(true) asm volatile("nop");
}
#else
int main(int argc,char** argv) {
    if(argc!=4 && argc!=5 && argc!=7) return 2;
    auto* input=std::fopen(argv[1],"rb"); if(!input) return 3;
    int count=int(std::fread(nodes,sizeof(mapgen::node),mapgen::max_nodes,input)); std::fclose(input);
    int status=recipe_run(count,uint32_t(std::strtoul(argv[2],nullptr,0)));
    auto* output=std::fopen(argv[3],"wb"); if(!output) return 4;
    std::fwrite(metadata,sizeof(metadata),1,output);
    if(!status) std::fwrite(result.data,1,mapgen::cells,output);
    if(!status && argc>=5) {
        if(argv[4][0]!='-'){
            input=std::fopen(argv[4],"rb");if(!input){std::fclose(output);return 3;}
            count=int(std::fread(nodes,sizeof(mapgen::node),mapgen::max_nodes,input));std::fclose(input);
            status=recipe_run(count,uint32_t(std::strtoul(argv[2],nullptr,0)));
            if(status || recipe_apply_materials()){std::fclose(output);return 5;}
        }
        std::fwrite(recipe_ground(),1,4096,output);
        for(int y=0;y<1024;++y)for(int x=0;x<1024;++x){
            uint16_t tile=wasteland_tiles::reference(work.layout,ground_active?ground:nullptr,x,y,&work.roads);
            std::fwrite(&tile,2,1,output);
        }
        uint32_t signature=recipe_render_signature();std::fwrite(&signature,4,1,output);
        if(argc==7) {
            for(int arg=5;arg<=6;++arg)if(argv[arg][0]!='-') {
                input=std::fopen(argv[arg],"rb");if(!input){std::fclose(output);return 3;}
                count=int(std::fread(nodes,sizeof(mapgen::node),mapgen::max_nodes,input));std::fclose(input);
                status=recipe_run(count,uint32_t(std::strtoul(argv[2],nullptr,0)));
                if(status || (arg==5?recipe_apply_spawns():recipe_apply_decoration())){std::fclose(output);return 5;}
            }
            std::fwrite(recipe_decorations(),1,1024*1024,output);
            uint32_t points=recipe_spawn_count();std::fwrite(&points,4,1,output);
            std::fwrite(recipe_spawns(),4,points,output);
        }
    }
    std::fclose(output); return status;
}
#endif
}
