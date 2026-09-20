#include "driving.h"
#include "bn_math.h"
#include "generated/track_data.h"

namespace driving {
namespace {
fixed absf(fixed v) { return v<0 ? -v : v; }
fixed clamp(fixed v, fixed lo, fixed hi) { return v<lo ? lo : v>hi ? hi : v; }
// Butano's default multiply discards half the fractional bits. Retain all
// fractional precision for small forces and repeated velocity projections.
fixed mul(fixed a,fixed b) { return a.safe_multiplication(b); }
}

int surface_at(int x, int y) {
    if(x<0 || y<0 || x>=1024 || y>=1024) return 0;
    return world::surfaces[(y/8)*128+x/8];
}

void Car::step(Input input, int setup_index) {
    const Setup& setup = setups[setup_index];
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

    if(input.brake) {
        // B brakes first, then becomes reverse once forward motion stops.
        forward-= forward>fixed(0.08) ? fixed(0.09) : fixed(0.028);
        forward=clamp(forward,-fixed(1.10),setup.max_speed);
    } else if(input.throttle) {
        forward+=setup.acceleration;
    }
    // Coasting is useful but does not erase momentum instantly.
    fixed drag = input.throttle ? fixed(0.006) : fixed(0.014);
    if(surface==0) drag+=fixed(0.045);
    else if(surface==2) drag+=fixed(0.008);
    forward=mul(forward,1-drag);
    forward=clamp(forward,-fixed(1.10),setup.max_speed);
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
    x+=vx;
    y+=vy;

    // The car is a small circle for forgiving, stable arcade collisions.
    auto impact=[&]() {
        if(collision_cooldown==0) { hit=true; ++collisions; collision_cooldown=12; }
    };
    if(x<94) { x=94; vx=absf(vx)*fixed(0.30); impact(); }
    if(x>938) { x=938; vx=-absf(vx)*fixed(0.30); impact(); }
    if(y<94) { y=94; vy=absf(vy)*fixed(0.30); impact(); }
    if(y>918) { y=918; vy=-absf(vy)*fixed(0.30); impact(); }
    for(const auto& obstacle: world::obstacles) {
        int ix=x.integer()-obstacle.x, iy=y.integer()-obstacle.y;
        int radius=obstacle.r+7;
        if(ix*ix+iy*iy<radius*radius) {
            fixed dx=x-obstacle.x, dy=y-obstacle.y;
            fixed length=bn::sqrt(dx*dx+dy*dy);
            if(length<fixed(0.1)) { dx=1; dy=0; length=1; }
            fixed nx=dx/length, ny=dy/length;
            x=obstacle.x+nx*radius;
            y=obstacle.y+ny*radius;
            fixed approach=vx*nx+vy*ny;
            if(approach<0) {
                vx-=nx*approach*fixed(1.35);
                vy-=ny*approach*fixed(1.35);
                vx*=fixed(0.75); vy*=fixed(0.75);
                impact();
            }
        }
    }
    // Solid workshop building matches its visible footprint.
    if(x>469 && x<698 && y>678 && y<751) {
        fixed left=x-469,right=698-x,top=y-678,bottom=751-y;
        fixed m=left;
        if(right<m)m=right;
        if(top<m)m=top;
        if(bottom<m)m=bottom;
        if(m==left) { x=469; vx=-absf(vx)*fixed(0.25); }
        else if(m==right) { x=698; vx=absf(vx)*fixed(0.25); }
        else if(m==top) { y=678; vy=-absf(vy)*fixed(0.25); }
        else { y=751; vy=absf(vy)*fixed(0.25); }
        impact();
    }
}
}
