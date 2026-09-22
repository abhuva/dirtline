#include "vehicle_contact.h"
#include <cassert>
#include <cmath>
#include <iostream>
using namespace vehicle_contact;
Body body(int x,int y,int mass,int vx=0,int vy=0) { return {x*one,y*one,vx*one,vy*one,one,0,mass}; }
int main() {
    auto free=[](int,int){return true;};
    auto a=body(0,0,750,4),b=body(20,0,750);
    auto c=resolve(a,b,free);
    assert(c.overlap && c.closing==4*one && !detect(a,b).overlap);
    assert(std::abs(a.vx-int(1.6*one))<4 && std::abs(b.vx-int(2.4*one))<4);
    int light_speed=b.vx;
    a=body(0,0,750,4); b=body(20,0,2200); resolve(a,b,free);
    assert(b.vx<light_speed*2/3 && a.vx<one);
    int tank_speed=b.vx;
    a=body(0,0,2200,4); b=body(20,0,750); resolve(a,b,free);
    assert(b.vx>3*one && a.vx>2*one && b.vx>tank_speed*2);
    a=body(0,0,750,4,1); b=body(20,0,750); resolve(a,b,free);
    assert(a.vy>int(.9*one) && b.vy>0 && a.vy+b.vy==one);
    a=body(0,0,750,-1); b=body(20,0,750,1); resolve(a,b,free);
    assert(a.vx==-one && b.vx==one); // Already separating: no second bounce.
    a=body(0,0,750); b=body(20,0,750); resolve(a,b,free);
    assert(!detect(a,b).overlap && a.vx==0 && b.vx==0);
    a=body(0,0,750,4); b=body(20,0,2200);
    resolve(a,b,[](int x,int){return x<=20*one;});
    assert(b.x==20*one && a.x<-2*one && !detect(a,b).overlap);
    a=body(0,0,750); b=body(0,18,750); b.fx=0; b.fy=one;
    assert(!detect(a,b).overlap);
    b.y=17*one; assert(detect(a,b).overlap);
    resolve(a,b,free); assert(!detect(a,b).overlap);
    a=body(0,0,750); b=body(27,0,750); assert(!detect(a,b).overlap);
    int checked=0;
    for(int ma:{500,750,1100,2200,4000}) for(int mb:{500,750,1100,2200,4000}) {
        a=body(0,0,ma,4,1); b=body(20,0,mb,-1,0);
        int64_t px=int64_t(a.vx)*ma+int64_t(b.vx)*mb,py=int64_t(a.vy)*ma+int64_t(b.vy)*mb;
        double energy=double(ma)*(double(a.vx)*a.vx+double(a.vy)*a.vy)+double(mb)*(double(b.vx)*b.vx+double(b.vy)*b.vy);
        resolve(a,b,free);
        assert(std::llabs(int64_t(a.vx)*ma+int64_t(b.vx)*mb-px)<(ma+mb)*8);
        assert(std::llabs(int64_t(a.vy)*ma+int64_t(b.vy)*mb-py)<(ma+mb)*8);
        double after=double(ma)*(double(a.vx)*a.vx+double(a.vy)*a.vy)+double(mb)*(double(b.vx)*b.vx+double(b.vy)*b.vy);
        assert(after<=energy && !detect(a,b).overlap); ++checked;
    }
    std::cout<<"PASS vehicle contacts: rectangles, rotation, wall pinning, glancing/separating impacts; "<<checked
             <<" mass pairs conserve momentum and dissipate energy; heavy/light ramming response\n";
}
