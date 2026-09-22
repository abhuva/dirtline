#pragma once
#include <cstdint>

// Platform-independent Q12 oriented rectangles, shared by GBA and host tests.
// Mass is in relative kg; no allocation, floating point or rendering dependencies.
namespace vehicle_contact {
constexpr int one=4096, half_length=11*one, half_width=7*one;
struct Body { int x,y,vx,vy,fx,fy,mass; };
struct Contact { bool overlap=false; int nx=0,ny=0,depth=0,closing=0; };
inline int abs(int n) { return n<0?-n:n; }
inline int mul(int a,int b) { return int((int64_t(a)*b)/one); }
inline int dot(int ax,int ay,int bx,int by) { return int((int64_t(ax)*bx+int64_t(ay)*by)/one); }
inline int radius(const Body& b,int nx,int ny) {
    return mul(abs(dot(b.fx,b.fy,nx,ny)),half_length)+mul(abs(dot(-b.fy,b.fx,nx,ny)),half_width);
}
inline Contact detect(const Body& a,const Body& b) {
    int dx=b.x-a.x,dy=b.y-a.y;
    if(abs(dx)>27*one || abs(dy)>27*one) return {};
    const int axes[][2]={{a.fx,a.fy},{-a.fy,a.fx},{b.fx,b.fy},{-b.fy,b.fx}};
    Contact c; c.depth=100*one;
    for(const auto& axis:axes) {
        int distance=dot(dx,dy,axis[0],axis[1]);
        int depth=radius(a,axis[0],axis[1])+radius(b,axis[0],axis[1])-abs(distance);
        if(depth<=0) return {};
        if(depth<c.depth) {
            c.depth=depth; int sign=distance<0?-1:1;
            c.nx=axis[0]*sign; c.ny=axis[1]*sign;
        }
    }
    c.overlap=true; c.closing=dot(a.vx-b.vx,a.vy-b.vy,c.nx,c.ny);
    return c;
}
template<class ValidPosition>
Contact resolve(Body& a,Body& b,ValidPosition valid) {
    Contact c=detect(a,b);
    if(!c.overlap) return c;
    int total=a.mass+b.mass;
    // Tuned masses are <= 4000 kg: this fits 32 bits and avoids a costly
    // 64-bit division runtime in the GBA's scarce internal code/stack RAM.
    int weight_a=b.mass*one/total,weight_b=one-weight_a;
    // Correct penetration without pushing either car through terrain. A car
    // pinned against a wall makes the other take the remaining correction.
    int separation=c.depth+one/8;
    int ax=mul(c.nx,mul(separation,weight_a)),ay=mul(c.ny,mul(separation,weight_a));
    int bx=mul(c.nx,mul(separation,weight_b)),by=mul(c.ny,mul(separation,weight_b));
    bool move_a=valid(a.x-ax,a.y-ay),move_b=valid(b.x+bx,b.y+by);
    if(move_a && move_b) { a.x-=ax; a.y-=ay; b.x+=bx; b.y+=by; }
    else if(!move_b && valid(a.x-mul(c.nx,separation),a.y-mul(c.ny,separation))) {
        a.x-=mul(c.nx,separation); a.y-=mul(c.ny,separation);
    } else if(!move_a && valid(b.x+mul(c.nx,separation),b.y+mul(c.ny,separation))) {
        b.x+=mul(c.nx,separation); b.y+=mul(c.ny,separation);
    }
    if(c.closing>0) {
        // Restitution 0.2: mass-weighted, mildly inelastic bumper impact.
        int normal=c.closing+c.closing/5;
        int tangent=dot(a.vx-b.vx,a.vy-b.vy,-c.ny,c.nx)/10;
        int jx=mul(normal,c.nx)-mul(tangent,c.ny);
        int jy=mul(normal,c.ny)+mul(tangent,c.nx);
        a.vx-=mul(jx,weight_a); a.vy-=mul(jy,weight_a);
        b.vx+=mul(jx,weight_b); b.vy+=mul(jy,weight_b);
    }
    return c;
}
}
