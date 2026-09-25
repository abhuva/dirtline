#pragma once
#include "combat.h"
#include "bn_sprite_ptr.h"
#include "bn_optional.h"

class combat_view {
public:
    static constexpr int pickup_sprite_count=3;
    combat_view();
    void update(const combat::World& world,int camera_x,int camera_y,bool visible);
private:
    bn::array<bn::optional<bn::sprite_ptr>,combat::enemy_count> _cars,_mounts,_hp,_bursts;
    bn::array<bn::optional<bn::sprite_ptr>,combat::bullet_count> _bullets;
    bn::array<bn::optional<bn::sprite_ptr>,combat::missile_count> _missiles,_missile_bursts;
    bn::array<bn::optional<bn::sprite_ptr>,combat::trap_count> _traps,_trap_bursts;
    bn::array<bn::optional<bn::sprite_ptr>,pickup_sprite_count> _pickups;
    bn::optional<bn::sprite_ptr> _saw;
};
