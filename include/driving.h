#pragma once
#include "bn_fixed.h"

namespace driving {
using bn::fixed;

struct Setup {
    const char* name;
    fixed acceleration;
    fixed max_speed;
    fixed grip;
    fixed steer;
};

inline constexpr Setup setups[] = {
    {"GRIP",  fixed(0.045), fixed(2.85), fixed(0.165), fixed(2.65)},
    {"RALLY", fixed(0.053), fixed(3.20), fixed(0.120), fixed(2.90)},
    {"HEAVY", fixed(0.033), fixed(2.65), fixed(0.105), fixed(2.25)},
};

struct Input { bool throttle; bool brake; int steer; };

struct Car {
    fixed x=470, y=860;
    fixed vx=0, vy=0;
    fixed heading=0, yaw=0;
    fixed speed=0, slip=0;
    int surface=1;
    int collision_cooldown=0;
    int collisions=0;
    bool hit=false;
    void step(Input input, int setup_index);
};

int surface_at(int x, int y);
}
