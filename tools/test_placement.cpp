#include "map_recipe.h"
#include "enemy_spawns.h"
#include "decoration_layout.h"
#include <cassert>
#include <cstring>
#include <cstdio>
static mapgen::workspace work;
static enemy_spawns original,a,b;
static decoration_layout decor;
static uint8_t field[4096];
int main() {
    using namespace mapgen;
    node output{op::spawns,-1,-1,-1,8,{258,128,1}};
    auto r=execute(&output,1,42,work);assert(r.status==error::ok && r.type==kind::spawns);
    for(int i=0;i<4096;++i)assert(r.data[i]==255);
    output.p[0]=259;assert(validate(&output,1)==error::parameter);output.p[0]=0;
    node bad[]{ {op::random,-1,-1,-1,0,{47,2}}, {op::decoration,0,-1,-1,0,{30,40,20,20,20,1}} };
    assert(validate(bad,2)==error::type);
    node converted[]{ {op::random,-1,-1,-1,0,{47,2}}, {op::mask_field,0,-1,-1,0,{}} };
    r=execute(converted,2,42,work);
    assert(r.status==error::ok && r.type==kind::field);
    for(int i=0;i<4096;++i)assert(r.data[i]==work.buffers[0][i]*255);
    for(unsigned seed=0;seed<32;++seed) {
        execute(default_nodes,3,seed,work);original.generate(work.layout);
        a.generate_recipe(work.layout,nullptr,258,128,true,9);
        assert(a.count==original.count);
        for(int i=0;i<a.count;++i)assert(a.points[i].x==original.points[i].x && a.points[i].y==original.points[i].y);
        std::memset(field,0,sizeof(field));a.generate_recipe(work.layout,field,258,128,true,9);assert(!a.count);
        for(int i=0;i<4096;++i)field[i]=i%64>=32?255:0;
        a.generate_recipe(work.layout,field,30,512,false,9);b.generate_recipe(work.layout,field,30,512,false,9);
        assert(a.count<=30 && a.count>0 && a.count==b.count);
        for(int i=0;i<a.count;++i){
            assert(a.points[i].x>=4096 && a.points[i].x==b.points[i].x && a.points[i].y==b.points[i].y);
            for(int j=0;j<i;++j){int dx=int(a.points[i].x)-a.points[j].x,dy=int(a.points[i].y)-a.points[j].y;assert(dx*dx+dy*dy>=512*512);}
        }
    }
    execute(default_nodes,3,42,work);work.roads.generate(work.layout,work.scratch,160,3);
    for(int i=0;i<4096;++i)field[i]=i%64>=32?255:1;
    int high_weight=0;
    for(unsigned stream=1;stream<=128;++stream){
        a.generate_recipe(work.layout,field,1,128,false,stream);assert(a.count==1);
        high_weight+=a.points[0].x>=4096;
    }
    assert(high_weight>120); // Probability magnitude matters, beyond nonzero masking.
    int32_t settings[]{100,40,20,20,20,1};std::memset(field,255,sizeof(field));decor.configure(42,7,field,settings);
    int counts[4]{},placed=0;
    for(int y=0;y<256;++y)for(int x=0;x<256;++x) {
        auto p=decor.patch(x,y,work.layout,&work.roads);
        assert(p==decor.patch(x,y,work.layout,&work.roads));
        if(!p)continue;
        ++placed;++counts[(p&7)-1];int tiles=0;
        for(int yy=0;yy<4;++yy)for(int xx=0;xx<4;++xx)if(auto t=decoration_layout::tile(p,xx,yy)) {
            assert(t>=1 && t<=16);++tiles;
            int wx=x*32+xx*8,wy=y*32+yy*8;
            assert(!work.layout.solid(wx,wy) && work.layout.town_graphic_at(wx,wy)<0 && !work.roads.contains(wx,wy));
        }
        assert(tiles==4);
        // Type weights do not change the placement gates or offsets.
        decor.weights[0]=0;decor.weights[1]=0;decor.weights[2]=100;decor.weights[3]=0;
        auto changed=decor.patch(x,y,work.layout,&work.roads);assert(changed && (changed&7)==3 && (changed&~7)==(p&~7));
        for(int i=0;i<4;++i)decor.weights[i]=settings[i+1];
    }
    assert(placed>1000 && counts[0]>counts[1] && counts[1]>0 && counts[2]>0 && counts[3]>0);
    settings[0]=0;decor.configure(42,7,field,settings);assert(!decor.patch(128,128,work.layout,&work.roads));
    assert(sizeof(decoration_layout)==4120);
    std::printf("PASS placement: deterministic weighted spawns, zero mask, count, spacing, legacy defaults; %d clipped cosmetic patches, independent type weights\n",placed);
}
