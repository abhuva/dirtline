#pragma once
#include "bn_fixed.h"
#include "generated/track_data.h"

namespace driving {
using bn::fixed;

struct Setup {
    const char* name;
    fixed acceleration;
    fixed max_speed;
    fixed grip;
    fixed steer;
    int mass;
};

inline constexpr Setup setups[] = {
    {"GRIP",  fixed(0.045), fixed(2.85), fixed(0.165), fixed(2.65), 950},
    {"RALLY", fixed(0.053), fixed(3.20), fixed(0.120), fixed(2.90),1100},
    {"HEAVY", fixed(0.033), fixed(2.65), fixed(0.105), fixed(2.25),2200},
    {"RAIDER",fixed(0.032), fixed(2.25), fixed(0.100), fixed(2.15), 750},
};

struct Input { bool throttle; bool brake; int steer; };

struct Car {
    fixed x=world::start_x, y=world::start_y;
    fixed vx=0, vy=0;
    fixed heading=0, yaw=0;
    fixed speed=0, slip=0;
    int surface=1;
    int collision_cooldown=0;
    int collisions=0;
    int mass=1100;
    bool hit=false;
    BN_CODE_IWRAM void step(Input input, int setup_index);
};

int surface_at(int x, int y);
bool can_drive(int x,int y);
// Returns positive closing speed for an approaching car-to-car contact.
fixed collide(Car& a,Car& b);
}
