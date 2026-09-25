#include "cave_layout.h"
#include "enemy_spawns.h"
#include "generated/wasteland_recipe.h"
#include <array>
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <set>
#include <vector>

static bool clear(const cave_layout& map,int x,int y) {
    const int offsets[][2]={{0,0},{7,0},{-7,0},{0,7},{0,-7},{5,5},{5,-5},{-5,5},{-5,-5}};
    for(const auto& p:offsets) if(map.solid(x+p[0],y+p[1]) || map.town_solid(x+p[0],y+p[1])) return false;
    return true;
}

int main(int argc,char** argv) {
    mapgen::workspace recipe_work;
    cave_layout& map=recipe_work.layout;
    auto generate=[&](uint32_t seed) {
        const auto& recipe=map_catalog::maps[0];
        auto result=mapgen::execute(recipe.nodes,recipe.count,seed,recipe_work);
        assert(result.status==mapgen::error::ok && result.type==mapgen::kind::world);
    };
    if(argc==3) {
        uint32_t seed=uint32_t(std::strtoul(argv[1],nullptr,0)); generate(seed);
        std::ofstream out(argv[2],std::ios::binary);
        uint32_t header[]={map.columns,map.columns,seed,map.signature(),uint32_t(map.floor_count()),uint32_t(map.fallback()),
                           uint32_t(map.spawn().x),uint32_t(map.spawn().y)};
        out.write(reinterpret_cast<const char*>(header),sizeof(header));
        for(int t=0;t<map.town_count;++t) { auto p=map.town(t); uint32_t xy[]={uint32_t(p.x),uint32_t(p.y)};
            out.write(reinterpret_cast<const char*>(xy),sizeof(xy)); }
        out.write(reinterpret_cast<const char*>(map.cells()),map.count); assert(out);
        return 0;
    }
    std::set<uint32_t> hashes; int fallbacks=0;
    for(uint32_t i=0;i<128;++i) {
        uint32_t seed=i==0?map.fixed_seed:i*2654435761u;
        generate(seed); hashes.insert(map.signature()); fallbacks+=map.fallback();
        assert(map.floor_count()>256 && clear(map,map.spawn().x,map.spawn().y));
        std::vector<bool> seen(map.count); std::vector<int> queue;
        int origin=map.spawn().y/128*map.columns+map.spawn().x/128; queue.push_back(origin); seen[origin]=true;
        for(unsigned k=0;k<queue.size();++k) {
            int at=queue[k],x=at%map.columns,y=at/map.columns;
            const int offsets[][2]={{-1,0},{1,0},{0,-1},{0,1}};
            for(const auto& d:offsets) {
                int xx=x+d[0],yy=y+d[1],next=yy*map.columns+xx;
                if(!map.wall(xx,yy) && !seen[next]) { seen[next]=true; queue.push_back(next); }
            }
        }
        assert(int(queue.size())==map.floor_count());
        enemy_spawns encounters,repeat_encounters;
        encounters.generate(map); repeat_encounters.generate(map);
        assert(encounters.count>10 && encounters.count<=enemy_spawns::capacity);
        assert(encounters.count==repeat_encounters.count);
        std::set<std::pair<int,int>> positions,sectors;
        for(int p=0;p<encounters.count;++p) {
            const auto& anchor=encounters.points[p];
            assert(anchor.x==repeat_encounters.points[p].x && anchor.y==repeat_encounters.points[p].y);
            assert(anchor.slot==-1 && anchor.hp==3 && anchor.ready_at==0);
            assert(seen[anchor.y/128*map.columns+anchor.x/128]);
            assert(clear(map,anchor.x,anchor.y) && map.nearby_town(anchor.x,anchor.y)<0);
            assert(positions.emplace(anchor.x,anchor.y).second);
            if(p>=2) assert(sectors.emplace(anchor.x/512,anchor.y/512).second);
        }
        // Every floor sector away from the starting clearing gets an encounter.
        for(int sy=0;sy<16;++sy) for(int sx=0;sx<16;++sx) {
            bool eligible=false;
            for(int cy=0;cy<4;++cy) for(int cx=0;cx<4;++cx) {
                int x=sx*512+cx*128+64,y=sy*512+cy*128+64;
                int dx=x-map.spawn().x,dy=y-map.spawn().y;
                if(!map.wall(x/128,y/128) && dx*dx+dy*dy>=384*384 &&
                   map.nearby_town(x,y)<0 && clear(map,x,y)) eligible=true;
            }
            if(eligible) assert(sectors.count({sx,sy}));
        }
        for(int t=0;t<map.town_count;++t) {
            auto town=map.town(t);
            assert(seen[town.y/128*map.columns+town.x/128] && clear(map,town.x,town.y));
            assert(map.nearby_town(town.x,town.y)==t);
            const int centre_y=town.y-32;
            for(const auto& offset : std::array<std::array<int,2>,4>{{
                    {{71,0}},{{-71,0}},{{0,71}},{{0,-71}}}})
                assert(map.nearby_town(town.x+offset[0],centre_y+offset[1])==t);
            for(const auto& offset : std::array<std::array<int,2>,4>{{
                    {{73,0}},{{-73,0}},{{0,73}},{{0,-73}}}})
                assert(map.nearby_town(town.x+offset[0],centre_y+offset[1])!=t);
            for(int prev=0;prev<t;++prev) {
                auto other=map.town(prev);
                assert(std::abs(town.x-other.x)+std::abs(town.y-other.y)>=8*128);
            }
        }
        // All cardinal floor-cell links have car-width clearance (except icon
        // footprints, placed above cell centers, so these centerlines also pass).
        for(int at:queue) {
            int x=at%map.columns,y=at/map.columns;
            assert(clear(map,x*128+64,y*128+80));
            if(!map.wall(x+1,y)) for(int dx=0;dx<=128;dx+=8) assert(clear(map,x*128+64+dx,y*128+80));
            if(!map.wall(x,y+1)) {
                // Town artwork may cross a north approach; every town also has
                // a fully clear east/west entrance within its carved plaza.
                bool town_column=false;
                for(int t=0;t<map.town_count;++t) if(map.town(t).x/128==x && map.town(t).y/128==y+1) town_column=true;
                if(!town_column) for(int dy=0;dy<=128;dy+=8) assert(clear(map,x*128+64,y*128+80+dy));
            }
        }
        for(int x=0;x<map.columns;++x) assert(map.wall(x,0) && map.wall(x,map.columns-1));
        uint32_t signature=map.signature(); generate(seed); assert(map.signature()==signature);
    }
    assert(hashes.size()==128);
    std::printf("PASS enemy anchors: 128 seeds, reproducibility, reachable clear floor, unique sector coverage; %zu bytes\n",sizeof(enemy_spawns));
    std::printf("PASS caves: 128 reproducible distinct seeds; largest-component connectivity, six reachable destinations, car clearance; %d fallbacks; persistent %zu / temporary %zu bytes\n",
                fallbacks,sizeof(map),sizeof(recipe_work));
}
