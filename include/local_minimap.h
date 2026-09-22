#pragma once
#include "bn_array.h"
#include "bn_sprite_ptr.h"
#include "bn_tile.h"
#include "bn_unique_ptr.h"
#include "bn_vector.h"
#include "combat.h"

// Wasteland: zoom/crop an immutable logical image. Other maps: local radar.
class local_minimap {
public:
    static constexpr int screen_x=86,screen_y=46,base_scale=12,radius=26;
    local_minimap(int x,int y,int zoom_level=0);
    ~local_minimap();
    void update(int x,int y);
    void set_zoom(int level,int x,int y);
    int scale() const { return _scale; }
    void set_visible(bool value);
    void update_enemies(const combat::World& world,bool visible);
    int project_x(int x) const;
    int project_y(int y) const;
    int center_x() const { return _overview && _pending?_build_x:_shown_x; }
    int center_y() const { return _overview && _pending?_build_y:_shown_y; }
    int revisions() const { return _revisions; }
    static void commit();
private:
    bn::sprite_ptr _sprite;
    bn::array<bn::tile,64> _pixels{};
    bn::unique_ptr<bn::array<uint8_t,4096>> _source;
    bn::vector<bn::sprite_ptr,combat::enemy_count> _enemies;
    bn::tile* _vram;
    int _build_x=0,_build_y=0,_shown_x=0,_shown_y=0,_row=64,_revisions=0;
    int _scale=base_scale;
    bool _overview=false;
    bool _pending=false;
    static local_minimap* _active;
    void plot(int x,int y,unsigned color);
    void begin(int x,int y);
    void build_overview();
    BN_CODE_IWRAM void crop_overview(int x,int y);
    BN_CODE_IWRAM void rows();
};
