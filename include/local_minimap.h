#pragma once
#include "bn_array.h"
#include "bn_sprite_ptr.h"
#include "bn_tile.h"
#include "bn_unique_ptr.h"
#include "bn_vector.h"
#include "combat.h"
#include <cstdint>

// Fixed 2x player-centred overview with integrated vitality and energy gauges.
class local_minimap {
public:
    // The live map is deliberately smaller than its 64px backing sprite. The
    // transparent margin carries the two vitality arcs without growing the HUD.
    static constexpr int screen_x=89,screen_y=46,base_scale=12,fixed_scale=64;
    static constexpr int radius=21,marker_radius=17;
    local_minimap(int x,int y);
    ~local_minimap();
    void update(int x,int y);
    int scale() const { return _scale; }
    void set_visible(bool value);
    void set_vitals(int hp,int hp_max,int shield,int shield_max,int energy,int energy_max);
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
    int _scale=fixed_scale;
    bool _overview=false;
    bool _pending=false;
    int _hp=100,_hp_max=100,_shield=20,_shield_max=20,_energy=100,_energy_max=100;
    uint64_t _vitality_dirty_tiles=0;
    static local_minimap* _active;
    void plot(int x,int y,unsigned color);
    void begin(int x,int y);
    void build_overview();
    BN_CODE_IWRAM void crop_overview(int x,int y);
    BN_CODE_IWRAM void rows();
    void draw_vitals(int sides=3);
    void draw_energy();
};
