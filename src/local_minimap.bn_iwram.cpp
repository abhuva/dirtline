// ARM code for the radar rasterizer: leaves headroom for five simulated cars.
#include "local_minimap.h"
#include "bn_algorithm.h"
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
struct circle_masks { unsigned inside[512]{},rim[512]{},overwrite[512]{}; };
constexpr int vitality_inner=23,vitality_outer=27;
constexpr int vitality_segments(int value,int maximum) {
    return maximum>0?bn::min(10,(value*10+maximum-1)/maximum):0;
}
constexpr int energy_segments(int value,int maximum) {
    return maximum>0?bn::min(5,(value*5+maximum-1)/maximum):0;
}
constexpr int absolute(int value) { return value<0?-value:value; }
// Three near-equal sectors around the radar.  The narrow top break leaves the
// gauges readable as separate instruments without reserving room for an icon.
constexpr int gauge_at(int dx,int dy) {
    const int d=dx*dx+dy*dy;
    if(d<=vitality_inner*vitality_inner || d>vitality_outer*vitality_outer)return 0;
    if(dy<0 && absolute(dx)*5<=-dy)return 0;
    if(dy>0 && dy*10>=absolute(dx)*7)return 3;
    return dx<0?1:dx>0?2:0;
}
struct gauge_pixel { uint8_t x,y,segment; bool gap; };
template<int Gauge>
constexpr int gauge_pixel_count() {
    int count=0;
    for(int dy=-vitality_outer;dy<=vitality_outer;++dy)
        for(int dx=-vitality_outer;dx<=vitality_outer;++dx)count+=gauge_at(dx,dy)==Gauge;
    return count;
}
template<int Gauge>
constexpr auto make_gauge_pixels() {
    bn::array<gauge_pixel,gauge_pixel_count<Gauge>()> result{};int at=0;
    for(int dy=-vitality_outer;dy<=vitality_outer;++dy)
    for(int dx=-vitality_outer;dx<=vitality_outer;++dx) {
        const int gauge=gauge_at(dx,dy);if(gauge!=Gauge)continue;
        int segment=0;bool gap=false;
        if(gauge==3) {
            const int angular=dy>0?absolute(dx)*35/dy:50;
            segment=bn::min(4,angular/10);gap=angular>0 && angular%10<2;
        } else {
            const int progress=bn::max(0,bn::min(41,dy+27));
            segment=bn::min(9,progress*10/42);gap=progress>0 && progress%4==0;
        }
        result[at++]={uint8_t(32+dx),uint8_t(32+dy),uint8_t(segment),gap};
    }
    return result;
}
constexpr auto health_pixels=make_gauge_pixels<1>();
constexpr auto shield_pixels=make_gauge_pixels<2>();
constexpr auto energy_pixels=make_gauge_pixels<3>();
constexpr auto masks=[] {
    circle_masks result;
    for(int y=0;y<64;++y)for(int x=0;x<64;++x) {
        int dx=x-32,dy=y-32,d=dx*dx+dy*dy,index=y*8+x/8,shift=(x&7)*4;
        if(d<=local_minimap::radius*local_minimap::radius)result.inside[index]|=15u<<shift;
        else result.rim[index]|=(d<=(local_minimap::radius+2)*(local_minimap::radius+2)?2u:
                                 d<=(local_minimap::radius+3)*(local_minimap::radius+3)?1u:0u)<<shift;
        if(d<=(local_minimap::radius+3)*(local_minimap::radius+3) && !gauge_at(dx,dy))
            result.overwrite[index]|=15u<<shift;
    }
    return result;
}();
}

local_minimap::local_minimap(int x,int y) :
    _sprite(bn::sprite_ptr::create(screen_x,screen_y,bn::sprite_shape_size(64,64),
        bn::sprite_tiles_ptr::allocate(64,bn::bpp_mode::BPP_4),
        bn::sprite_palette_ptr::create(bn::sprite_items::overview_palette.palette_item()))),
    _vram(nullptr) {
    auto tiles=_sprite.tiles(); _vram=tiles.vram()->data();
    _sprite.set_bg_priority(0); _sprite.set_z_order(-1); _sprite.set_visible(false);
    _overview=true;
    _active=this;
    if(_overview) {
        _scale=fixed_scale;build_overview();
        do crop_overview(x,y); while(_row<64);
        draw_vitals();draw_energy();
        for(int i=0;i<combat::enemy_count;++i) {
            auto dot=bn::sprite_items::enemy_dot.create_sprite(0,0);
            dot.set_bg_priority(0);dot.set_z_order(-2);dot.set_visible(false);
            _enemies.push_back(dot);
        }
        bn::core::update();_sprite.set_visible(true);return;
    }
    _scale=base_scale;
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
void local_minimap::draw_vitals(int sides) {
    const int health_segments=vitality_segments(_hp,_hp_max);
    const int shield_segments=vitality_segments(_shield,_shield_max);
    const int energy_filled=energy_segments(_energy,_energy_max);
    auto* words=reinterpret_cast<unsigned*>(_pixels.data());
    auto draw=[&](const auto& pixels,int lit,unsigned bright,bool centered) {
        for(const auto& pixel:pixels) {
            const unsigned color=!pixel.gap && (centered?pixel.segment<lit:pixel.segment>=10-lit)?bright:1;
            const int x=pixel.x,y=pixel.y;
            const int tile=(y>>3)*8+(x>>3),word=tile*8+(y&7),shift=(x&7)*4;
            const unsigned previous=(words[word]>>shift)&15;
            if(previous!=color) {
                words[word]=(words[word]&~(15u<<shift))|(color<<shift);
                _vitality_dirty_tiles|=uint64_t(1)<<tile;
            }
        }
    };
    if(sides&1)draw(health_pixels,health_segments,13,false);
    if(sides&2)draw(shield_pixels,shield_segments,14,false);
    if(sides&4)draw(energy_pixels,energy_filled,4,true);
}
void local_minimap::draw_energy() { draw_vitals(4); }
void local_minimap::set_vitals(int hp,int hp_max,int shield,int shield_max,int energy,int energy_max) {
    hp=bn::max(0,bn::min(hp,hp_max));shield=bn::max(0,bn::min(shield,shield_max));
    energy=bn::max(0,bn::min(energy,energy_max));
    if(hp==_hp && hp_max==_hp_max && shield==_shield && shield_max==_shield_max &&
       energy==_energy && energy_max==_energy_max)return;
    const int old_health_segments=vitality_segments(_hp,_hp_max);
    const int old_shield_segments=vitality_segments(_shield,_shield_max);
    const int new_health_segments=vitality_segments(hp,hp_max);
    const int new_shield_segments=vitality_segments(shield,shield_max);
    const int old_energy_segments=energy_segments(_energy,_energy_max);
    const int new_energy_segments=energy_segments(energy,energy_max);
    int sides=0;
    if(new_health_segments!=old_health_segments)sides|=1;
    if(new_shield_segments!=old_shield_segments)sides|=2;
    if(new_energy_segments!=old_energy_segments)sides|=4;
    _hp=hp;_hp_max=hp_max;_shield=shield;_shield_max=shield_max;_energy=energy;_energy_max=energy_max;
    if(sides&3)draw_vitals(sides&3);
    if(sides&4)draw_energy();
}
void local_minimap::crop_overview(int x,int y) {
    // Follow the player in whole display pixels. Runtime recenters are built
    // into the invisible backing store in four slices, then committed at once;
    // this avoids charging a whole 64x64 repack to one driving frame.
    if(_row==64) {
        _build_x=x/_scale*_scale;
        _build_y=y/_scale*_scale;
        _row=0;
    }
    auto* words=reinterpret_cast<unsigned*>(_pixels.data());
    const auto* source=_source->data();
    unsigned line[8];int previous_y=-100;
    const int end=bn::min(64,_row+16);
    for(int py=_row;py<end;++py) {
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
            unsigned& destination=words[(py>>3)*64+column*8+(py&7)];
            const unsigned overwrite=masks.overwrite[at];
            const unsigned terrain=(line[column]&masks.inside[at])|masks.rim[at];
            destination=(destination&~overwrite)|(terrain&overwrite);
        }
    }
    _row=end;
    if(_row==64)_pending=true;
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
        bool on=visible && enemy.hp>0 && x*x+y*y<=(radius-2)*(radius-2);
        _enemies[i].set_visible(on);
        if(on)_enemies[i].set_position(screen_x+x,screen_y+y);
    }
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
            unsigned color=d<=radius*radius?terrain:
                           d<=(radius+2)*(radius+2)?12:d<=(radius+3)*(radius+3)?1:0;
            plot(x+xx,_row+yy,color);
        }
    }
    if(_row==64) {
        for(int i=0;i<cave_layout::town_count;++i) {
            auto town=wasteland::layout().town(i);
            int dx=(town.x-_build_x)/_scale,dy=(town.y-_build_y)/_scale;
            if(dx*dx+dy*dy>23*23) continue;
            for(int yy=-2;yy<=2;++yy) for(int xx=-2;xx<=2;++xx)
                if(yy!=-2 || xx==0) plot(32+dx+xx,32+dy+yy,12);
        }
        draw_vitals();draw_energy();_pending=true;
    }
}
void local_minimap::update(int x,int y) {
    if(_overview) {
        if(_row<64)crop_overview(x,y);
        else if(!_pending && (x/_scale*_scale!=_shown_x || y/_scale*_scale!=_shown_y))crop_overview(x,y);
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
    if(_active && (_active->_pending || _active->_vitality_dirty_tiles)) {
        auto& m=*_active;
        if(m._pending) {
            bn::memory::copy(m._pixels[0],64,m._vram[0]);
            m._shown_x=m._build_x; m._shown_y=m._build_y;
            ++m._revisions;m._pending=false;m._vitality_dirty_tiles=0;
        } else {
            const uint64_t dirty=m._vitality_dirty_tiles;m._vitality_dirty_tiles=0;
            for(int tile=0;tile<64;++tile)if(dirty&(uint64_t(1)<<tile))
                bn::memory::copy(m._pixels[tile],1,m._vram[tile]);
        }
    }
}
