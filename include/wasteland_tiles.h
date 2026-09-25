#pragma once
#include "cave_layout.h"
#include "road_network.h"
#include "generated/ground_materials.h"

// Shared by the ROM and browser. Coordinates for reference() are 8px tile units.
namespace wasteland_tiles {
inline int material(const cave_layout& layout,const uint8_t* ground,int x,int y,const road_network* roads=nullptr) {
    if(x<0 || y<0 || x>=cave_layout::extent || y>=cave_layout::extent) return 0;
    if(roads && roads->contains(x,y)) return roads->material;
    return ground ? ground[(y/128)*64+x/128] : layout.material(x,y);
}
inline int surface(const cave_layout& layout,const uint8_t* ground,int x,int y,const road_network* roads=nullptr,
                   const uint8_t* surfaces=ground_materials::surfaces) {
    if(layout.solid(x,y) || layout.town_solid(x,y)) return 3;
    return surfaces[material(layout,ground,x,y,roads)];
}
inline uint16_t reference(const cave_layout& layout,const uint8_t* ground,int x,int y,const road_network* roads=nullptr,
                          const uint8_t* textures=ground_materials::textures) {
    const int px=x*8+4,py=y*8+4,town=layout.town_graphic_at(px,py);
    if(town>=0) {
        const auto point=layout.town(town);
        return uint16_t(96+(town%2)*64+((py-(point.y-64))/8)*8+(px-(point.x-32))/8);
    }
    const int texture=layout.solid(px,py) ? (layout.solid(px,py+24)?4:5) :
        textures[material(layout,ground,px,py,roads)];
    return uint16_t(texture*16+(y%4)*4+x%4);
}
}
