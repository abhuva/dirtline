// ARM code for the radar rasterizer: leaves headroom for five simulated cars.
#include "local_minimap.h"
#include "bn_core.h"
#include "bn_memory.h"
#include "bn_sprite_tiles_ptr.h"
#include "bn_sprite_palette_ptr.h"
#include "bn_sprite_shape_size.h"
#include "bn_sprite_items_dot.h"
#include "bn_sprite_items_overview_palette.h"
#include "bn_sprite_items_enemy_dot.h"
#include "world_map.h"
#include "wasteland.h"

local_minimap* local_minimap::_active=nullptr;

namespace {
// ROM masks avoid per-pixel circle arithmetic during image scrolling.
struct circle_masks { unsigned inside[512]{},rim[512]{}; };
constexpr auto masks=[] {
    circle_masks result;
    for(int y=0;y<64;++y)for(int x=0;x<64;++x) {
        int dx=x-32,dy=y-32,d=dx*dx+dy*dy,index=y*8+x/8,shift=(x&7)*4;
        if(d<=local_minimap::radius*local_minimap::radius)result.inside[index]|=15u<<shift;
        else result.rim[index]|=(d<=28*28?2u:d<=29*29?1u:0u)<<shift;
    }
    return result;
}();
}

local_minimap::local_minimap(int x,int y,int zoom_level) :
    _sprite(bn::sprite_ptr::create(screen_x,screen_y,bn::sprite_shape_size(64,64),
        bn::sprite_tiles_ptr::allocate(64,bn::bpp_mode::BPP_4),
        bn::sprite_palette_ptr::create(world_map::index()>=2?bn::sprite_items::overview_palette.palette_item():bn::sprite_items::dot.palette_item()))),
    _vram(nullptr) {
    auto tiles=_sprite.tiles(); _vram=tiles.vram()->data();
    _sprite.set_bg_priority(0); _sprite.set_z_order(-1); _sprite.set_visible(false);
    _overview=world_map::index()>=2;
    _active=this;
    if(_overview) {
        _scale=128>>zoom_level;build_overview();crop_overview(x,y);
        for(int i=0;i<combat::enemy_count;++i) {
            auto dot=bn::sprite_items::enemy_dot.create_sprite(0,0);
            dot.set_bg_priority(0);dot.set_z_order(-2);dot.set_visible(false);
            _enemies.push_back(dot);
        }
        bn::core::update();_sprite.set_visible(true);return;
    }
    _scale=base_scale<<zoom_level;
    begin(x,y);
    while(_row<64) { rows(); bn::core::update(); }
    // The terrain renderer's VBlank callback commits the completed raster.
    bn::core::update();
    _sprite.set_visible(true);
}
local_minimap::~local_minimap() { _active=nullptr; }
void local_minimap::plot(int x,int y,unsigned color) {
    auto* words=reinterpret_cast<unsigned*>(_pixels.data());
    unsigned& row=words[(y>>3)*64+(x>>3)*8+(y&7)];
    int shift=(x&7)*4; row=(row&~(15u<<shift))|(color<<shift);
}
void local_minimap::begin(int x,int y) {
    _build_x=x/_scale*_scale; _build_y=y/_scale*_scale; _row=0;
}
void local_minimap::build_overview() {
    _source.reset(new bn::array<uint8_t,4096>());
    for(int y=0;y<64;++y)for(int x=0;x<64;++x)
        (*_source)[y*64+x]=wasteland::minimap_cell(x,y);
    for(int t=0;t<cave_layout::town_count;++t) {
        auto town=wasteland::layout().town(t);
        (*_source)[town.y/128*64+town.x/128]=4;
    }
}
void local_minimap::crop_overview(int x,int y) {
    // Every zoom follows the player in whole display pixels. Only copy source
    // pixels: never sample world tiles. Outside the source image is wall.
    _build_x=x/_scale*_scale;
    _build_y=y/_scale*_scale;
    auto* words=reinterpret_cast<unsigned*>(_pixels.data());
    const auto* source=_source->data();
    unsigned line[8];int previous_y=-100;
    for(int py=0;py<64;++py) {
        int sy=(_build_y+(py-32)*_scale)>>7;
        // Enlarged source rows repeat. Pack each only once, then apply the
        // circle to whole words (eight display pixels per write).
        if(sy!=previous_y) {
            previous_y=sy;
            for(int column=0;column<8;++column) {
                unsigned word=0;
                for(int i=0;i<8;++i) {
                    int sx=(_build_x+(column*8+i-32)*_scale)>>7;
                    unsigned color=sx>=0 && sx<64 && sy>=0 && sy<64?source[sy*64+sx]:2;
                    word|=color<<(i*4);
                }
                line[column]=word;
            }
        }
        for(int column=0;column<8;++column) {
            int at=py*8+column;
            words[(py>>3)*64+column*8+(py&7)]=(line[column]&masks.inside[at])|masks.rim[at];
        }
    }
    _row=64;_pending=true;
}
int local_minimap::project_x(int x) const {
    return _overview?x/_scale-center_x()/_scale:(x-center_x())/_scale;
}
int local_minimap::project_y(int y) const {
    return _overview?y/_scale-center_y()/_scale:(y-center_y())/_scale;
}
void local_minimap::set_visible(bool value) {
    _sprite.set_visible(value);
    if(!value)for(auto& dot:_enemies)dot.set_visible(false);
}
void local_minimap::update_enemies(const combat::World& world,bool visible) {
    for(int i=0;i<_enemies.size();++i) {
        const auto& enemy=world.enemies[i];
        int x=project_x(enemy.car.x.integer()),y=project_y(enemy.car.y.integer());
        // Leave enough space for the complete 2x2 dot inside the mask.
        bool on=visible && enemy.hp>0 && x*x+y*y<=24*24;
        _enemies[i].set_visible(on);
        if(on)_enemies[i].set_position(screen_x+x,screen_y+y);
    }
}
void local_minimap::set_zoom(int level,int x,int y) {
    BN_ASSERT(level>=0 && level<=3);
    int next_scale=_overview?128>>level:base_scale<<level;
    if(next_scale==_scale) return;
    if(_overview) { _scale=next_scale;crop_overview(x,y);bn::core::update();return; }
    // Called while settings have paused and hidden the driving UI.
    _pending=false; _scale=next_scale; begin(x,y);
    while(_row<64) { rows(); bn::core::update(); }
    bn::core::update();
}
void local_minimap::rows() {
    // One terrain sample per 2x2 radar block, but a pixel-exact circular mask.
    // This bounds CPU work to about 54 surface queries per driving frame.
    for(int end=_row+4;_row<end;_row+=2) for(int x=0;x<64;x+=2) {
        int dx=x-32,dy=_row-32;
        unsigned terrain=2;
        if(dx*dx+dy*dy<=(radius+2)*(radius+2)) {
            int surface=world_map::radar_surface_at(_build_x+dx*_scale,_build_y+dy*_scale);
            terrain=surface==3?2:surface==0?4:surface==1?7:9;
        }
        if(dx*dx+dy*dy<=(radius-2)*(radius-2)) {
            // Interior 2x2 blocks share one color: merge two pixels per word,
            // avoiding four separate EWRAM read/modify/writes and mask tests.
            auto* words=reinterpret_cast<unsigned*>(_pixels.data());
            int at=(_row>>3)*64+(x>>3)*8+(_row&7),shift=(x&7)*4;
            unsigned mask=255u<<shift,color=(terrain*17)<<shift;
            words[at]=(words[at]&~mask)|color;
            words[at+1]=(words[at+1]&~mask)|color;
        } else for(int yy=0;yy<2;++yy) for(int xx=0;xx<2;++xx) {
            int d=(dx+xx)*(dx+xx)+(dy+yy)*(dy+yy);
            unsigned color=d<=radius*radius?terrain:d<=28*28?12:d<=29*29?1:0;
            plot(x+xx,_row+yy,color);
        }
    }
    if(_row==64) {
        if(world_map::index()>=2) for(int i=0;i<cave_layout::town_count;++i) {
            auto town=wasteland::layout().town(i);
            int dx=(town.x-_build_x)/_scale,dy=(town.y-_build_y)/_scale;
            if(dx*dx+dy*dy>23*23) continue;
            for(int yy=-2;yy<=2;++yy) for(int xx=-2;xx<=2;++xx)
                if(yy!=-2 || xx==0) plot(32+dx+xx,32+dy+yy,12);
        }
        // Small north tick; clear sprite pixels outside the circular rim.
        plot(32,4,11); plot(32,5,11); _pending=true;
    }
}
void local_minimap::update(int x,int y) {
    if(_overview) {
        if(x/_scale*_scale!=_shown_x || y/_scale*_scale!=_shown_y)crop_overview(x,y);
        return;
    }
    if(x-_shown_x>radius*_scale || _shown_x-x>radius*_scale ||
       y-_shown_y>radius*_scale || _shown_y-y>radius*_scale) {
        // Spawn resets are loading operations, not a slowly scrolling radar.
        _sprite.set_visible(false); _pending=false; begin(x,y);
        while(_row<64) { rows(); bn::core::update(); }
        bn::core::update(); _sprite.set_visible(true); return;
    }
    if(_pending) return;
    if(_row==64) {
        if(x/_scale*_scale==_shown_x && y/_scale*_scale==_shown_y) return;
        begin(x,y);
    }
    rows();
}
void local_minimap::commit() {
    if(_active && _active->_pending) {
        auto& m=*_active;
        bn::memory::copy(m._pixels[0],64,m._vram[0]);
        m._shown_x=m._build_x; m._shown_y=m._build_y;
        ++m._revisions; m._pending=false;
    }
}
