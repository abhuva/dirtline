// Compile the shared fixed-point car step as ARM code in fast internal RAM.
#include "driving.h"
#include "bn_math.h"
#include "generated/track_data.h"
#include "world_map.h"
#include "vehicle_contact.h"

namespace driving {
namespace {
fixed absf(fixed v) { return v<0 ? -v : v; }
fixed clamp(fixed v, fixed lo, fixed hi) { return v<lo ? lo : v>hi ? hi : v; }
// Butano's default multiply discards half the fractional bits. Retain all
// fractional precision for small forces and repeated velocity projections.
fixed mul(fixed a,fixed b) { return a.safe_multiplication(b); }
}

int surface_at(int x, int y) {
    return world_map::surface_at(x,y);
}

bool can_drive(int x,int y) {
    constexpr int probes[][2]={{0,0},{7,0},{-7,0},{0,7},{0,-7},{5,5},{-5,5},{5,-5},{-5,-5}};
    for(const auto& p:probes) {
        if(world_map::solid_at(x+p[0],y+p[1])) return false;
    }
    return true;
}

void Car::step(Input input, int setup_index) {
    const Setup& setup = setups[setup_index];
    mass=setup.mass;
    hit=false;
    if(collision_cooldown) --collision_cooldown;
    surface=surface_at(x.integer(), y.integer());
    fixed c=bn::degrees_lut_cos(heading), s=bn::degrees_lut_sin(heading);
    fixed forward=mul(vx,c)+mul(vy,s);
    fixed lateral=-mul(vx,s)+mul(vy,c);
    speed=absf(forward)+absf(lateral)/2;

    // Steering builds with motion; no spinning in place. At high speed the
    // wider radius encourages lifting off before the corner.
    fixed motion=clamp(absf(forward)/fixed(0.65),0,1);
    fixed steer_rate=mul(setup.steer,motion) / (1+mul(speed,fixed(0.23)));
    fixed target_yaw=steer_rate*input.steer*(forward<0 ? -1 : 1);
    yaw+=mul(target_yaw-yaw,fixed(0.19));
    heading+=yaw;
    if(heading<0) heading+=360;
    if(heading>=360) heading-=360;
    c=bn::degrees_lut_cos(heading);
    s=bn::degrees_lut_sin(heading);
    forward=mul(vx,c)+mul(vy,s);
    lateral=-mul(vx,s)+mul(vy,c);
    slip=absf(lateral);

    fixed previous_forward=forward;
    if(input.brake) {
        // B brakes first, then becomes reverse once forward motion stops.
        if(forward>fixed(0.08)) forward-=fixed(0.09);
        else if(forward>-fixed(1.10)) forward=bn::max(forward-fixed(0.028),-fixed(1.10));
    } else if(input.throttle && forward<=setup.max_speed) {
        forward+=setup.acceleration;
    }
    // Coasting is useful but does not erase momentum instantly.
    fixed drag = input.throttle ? fixed(0.006) : fixed(0.014);
    if(surface==0) drag+=fixed(0.045);
    else if(surface==2) drag+=fixed(0.008);
    forward=mul(forward,1-drag);
    // The engine limit must not erase speed imparted by an external impact.
    if(previous_forward<=setup.max_speed && forward>setup.max_speed) forward=setup.max_speed;
    if(!input.throttle && !input.brake && absf(forward)<fixed(0.018)) forward=0;

    // A limited lateral force gives slides a beginning and a recoverable end.
    // Coasting increases the available cornering grip; dirt reduces it.
    fixed grip=setup.grip;
    if(!input.throttle) grip=mul(grip,fixed(1.40));
    if(surface==2) grip=mul(grip,fixed(0.66));
    if(surface==0) grip=mul(grip,fixed(0.72));
    fixed correction=clamp(mul(lateral,fixed(0.24)),-grip,grip);
    lateral-=correction;
    vx=mul(forward,c)-mul(lateral,s);
    vy=mul(forward,s)+mul(lateral,c);
    fixed old_x=x,old_y=y;
    x+=vx;
    y+=vy;

    // The car is a small circle for forgiving, stable arcade collisions.
    auto impact=[&]() {
        if(collision_cooldown==0) { hit=true; ++collisions; collision_cooldown=12; }
    };
    if(!can_drive(x.integer(),y.integer())) {
        const bool move_x=can_drive(x.integer(),old_y.integer());
        const bool move_y=can_drive(old_x.integer(),y.integer());
        if(move_x && (!move_y || absf(vx)>absf(vy))) {
            y=old_y; vy=-vy*fixed(0.25); vx*=fixed(0.90);
        } else if(move_y) {
            x=old_x; vx=-vx*fixed(0.25); vy*=fixed(0.90);
        } else {
            x=old_x; y=old_y; vx=-vx*fixed(0.25); vy=-vy*fixed(0.25);
        }
        impact();
    }
}

fixed collide(Car& a,Car& b) {
    if(bn::abs(a.x-b.x)>27 || bn::abs(a.y-b.y)>27) return 0;
    auto body=[](const Car& c) {
        return vehicle_contact::Body{c.x.data(),c.y.data(),c.vx.data(),c.vy.data(),
            bn::degrees_lut_cos(c.heading).data(),bn::degrees_lut_sin(c.heading).data(),c.mass};
    };
    auto aa=body(a),bb=body(b);
    auto contact=vehicle_contact::resolve(aa,bb,[](int x,int y) { return can_drive(x/4096,y/4096); });
    if(!contact.overlap) return 0;
    auto apply=[](Car& c,const vehicle_contact::Body& v) {
        c.x=fixed::from_data(v.x); c.y=fixed::from_data(v.y);
        c.vx=fixed::from_data(v.vx); c.vy=fixed::from_data(v.vy);
        fixed cs=bn::degrees_lut_cos(c.heading),sn=bn::degrees_lut_sin(c.heading);
        c.slip=bn::abs(-mul(c.vx,sn)+mul(c.vy,cs));
        c.speed=bn::abs(mul(c.vx,cs)+mul(c.vy,sn))+c.slip/2;
    };
    apply(a,aa); apply(b,bb);
    return fixed::from_data(bn::max(0,contact.closing));
}
}
