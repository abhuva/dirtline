#include "mission.h"

namespace missions {
namespace {
int abs(int value) { return value<0?-value:value; }
uint32_t mix(uint32_t value) {
    value^=value>>16;value*=0x7feb352du;
    value^=value>>15;value*=0x846ca68bu;
    return value^(value>>16);
}
}

const char* type_name(type value) {
    constexpr const char* names[]={"NONE","COURIER","HUNT"};
    return names[int(value)];
}

void manager::reset(uint32_t map_seed) {
    _map_seed=map_seed;_current=contract();
    _credits=0;_completed=0;_serial=0;
}

contract manager::offer(type kind,int origin,const cave_layout& layout,
                        const enemy_spawns& spawns) const {
    contract result;
    if(kind==type::none || origin<0 || origin>=cave_layout::town_count) return result;
    result.kind=kind;result.origin_town=origin;result.serial=_serial;
    const uint32_t hash=mix(_map_seed^uint32_t(origin*0x9e3779b9u)^uint32_t(_serial*0x85ebca6bu)^uint32_t(int(kind)*97));
    if(kind==type::courier) {
        result.target_town=(origin+1+int(hash%uint32_t(cave_layout::town_count-1)))%cave_layout::town_count;
        const auto from=layout.town(origin),to=layout.town(result.target_town);
        result.target_x=to.x;result.target_y=to.y;result.goal=1;
        result.reward=200+(abs(to.x-from.x)+abs(to.y-from.y))/128*8;
    } else {
        if(!spawns.count) return contract();
        const auto from=layout.town(origin);
        int best=0x7fffffff;
        for(int candidate=0;candidate<spawns.count;++candidate) {
            const auto& point=spawns.points[candidate];
            if(point.hp) {
                const int dx=int(point.x)-from.x,dy=int(point.y)-from.y;
                // Seeded jitter varies repeat offers while keeping first jobs
                // near their issuing outpost instead of across the whole map.
                const int score=dx*dx+dy*dy+int(mix(hash^uint32_t(candidate))&0xffffu)*4;
                if(score<best) {
                    best=score;result.target_spawn=candidate;
                    result.target_x=point.x;result.target_y=point.y;
                }
            }
        }
        if(result.target_spawn<0)return contract();
        result.goal=1;
        result.reward=300+(abs(result.target_x-from.x)+abs(result.target_y-from.y))/64*5;
    }
    return result;
}

bool manager::accept(type kind,int origin,const cave_layout& layout,const enemy_spawns& spawns) {
    if(_current.state!=status::none)return false;
    auto next=offer(kind,origin,layout,spawns);
    if(next.kind==type::none)return false;
    next.state=status::active;_current=next;++_serial;
    return true;
}

void manager::_complete() {
    if(_current.state!=status::active)return;
    _current.progress=_current.goal;_current.state=status::complete;
    _credits+=_current.reward;++_completed;
}

bool manager::on_town_enter(int town_id) {
    if(_current.state==status::active && _current.kind==type::courier &&
       town_id==_current.target_town) {
        _complete();return true;
    }
    return false;
}

bool manager::on_enemy_destroyed(int spawn_id) {
    if(_current.state==status::active && _current.kind==type::extermination &&
       spawn_id==_current.target_spawn) {
        _complete();return true;
    }
    return false;
}

void manager::acknowledge() {
    if(_current.state==status::complete)_current=contract();
}
}
