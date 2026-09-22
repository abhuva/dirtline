#include "town_scene.h"
#include "bn_core.h"
#include "bn_keypad.h"
#include "bn_regular_bg_items_town_exterior.h"
#include "bn_regular_bg_items_garage_interior.h"
#include "bn_sprite_items_town_player.h"

namespace {
constexpr town_scene::rect exterior_solids[]={
    {0,0,256,12},{0,0,10,256},{246,0,256,256},
    {54,12,182,59},              // garage
    {0,48,76,133},               // western house and yard
    {194,45,256,121},            // water tower yard
    {84,77,153,139},             // central rock and scrub island
    {176,133,256,197},           // eastern house
    {13,154,76,207},             // western scrap yard
    {0,204,103,256},{157,204,256,256}, // southern cliffs, gate left open
};
constexpr town_scene::rect garage_solids[]={
    {0,0,256,14},{0,0,13,256},{243,0,256,256},
    {54,20,170,75},              // mechanic counter
    {13,14,54,108},{13,72,93,116},
    {12,111,56,211},{12,173,100,211},
    {155,70,225,155},            // car chassis and lift
    {177,146,243,211},
    {0,210,101,256},{157,210,256,256}, // south wall, doorway left open
};

template<int Size>
bool hits(const town_scene::rect (&areas)[Size],int left,int top,int right,int bottom) {
    for(const auto& area:areas)
        if(right>area.left && left<area.right && bottom>area.top && top<area.bottom) return true;
    return false;
}
}

town_scene::town_scene(int town_id,int setup) :
    _player(bn::sprite_items::town_player.create_sprite(0,0)),
    _town_id(town_id),_menu_selection(setup) {
    _player.set_bg_priority(1);
    _player.set_z_order(-2);
    _load(place::exterior);
}

bool town_scene::_inside(const rect& area,int x,int y) const {
    return x>=area.left && x<area.right && y>=area.top && y<area.bottom;
}

bool town_scene::_blocked(int x,int y) const {
    if(x<6 || x>250 || y<8 || y>250) return true;
    const int left=x-5,right=x+6,top=y-3,bottom=y+4;
    return _place==place::exterior ? hits(exterior_solids,left,top,right,bottom) :
                                     hits(garage_solids,left,top,right,bottom);
}

void town_scene::_load(place next) {
    _background.reset();
    bn::core::update();
    _place=next;
    if(next==place::exterior) {
        _background=bn::regular_bg_items::town_exterior.create_bg(0,0);
        if(_y<100) { _x=128;_y=67;_direction=0; }
        else { _x=128;_y=226;_direction=3; }
    } else {
        _background=bn::regular_bg_items::garage_interior.create_bg(0,0);
        _x=128;_y=228;_direction=3;
    }
    _background->set_priority(3);
    _background->set_visible(_visible);
    _refresh_sprite();
}

void town_scene::_refresh_sprite() {
    int camera_x=_x<120?120:_x>136?136:_x;
    int camera_y=_y<80?80:_y>176?176:_y;
    _background->set_position(128-camera_x,128-camera_y);
    _player.set_position(_x-camera_x,_y-camera_y-13);
    int phase=_walk_ticks ? 1+((_walk_ticks/8)&1) : 0;
    _player.set_tiles(bn::sprite_items::town_player.tiles_item(),_direction*3+phase);
}

town_scene::event town_scene::update(int& setup) {
    if(_menu_open) {
        if(bn::keypad::left_pressed()) {
            _menu_selection=(_menu_selection+2)%3;
            return event::redraw;
        }
        if(bn::keypad::right_pressed()) {
            _menu_selection=(_menu_selection+1)%3;
            return event::redraw;
        }
        if(bn::keypad::b_pressed()) {
            _menu_open=false;
            return event::menu_closed;
        }
        if(bn::keypad::a_pressed()) {
            setup=_menu_selection;
            _menu_open=false;
            return event::setup_applied;
        }
        return event::none;
    }

    int dx=0,dy=0;
    if(bn::keypad::up_held()) { dy=-1;_direction=3; }
    else if(bn::keypad::down_held()) { dy=1;_direction=0; }
    else if(bn::keypad::left_held()) { dx=-1;_direction=1; }
    else if(bn::keypad::right_held()) { dx=1;_direction=2; }
    if(dx || dy) {
        if(!_blocked(_x+dx,_y+dy)) { _x+=dx;_y+=dy; }
        ++_walk_ticks;
    } else _walk_ticks=0;
    _refresh_sprite();

    if(!bn::keypad::a_pressed()) return event::none;
    if(_place==place::exterior) {
        if(_direction==3 && _inside({108,58,148,76},_x,_y)) {
            _load(place::garage);
            return event::redraw;
        }
        if(_direction==0 && _inside({105,228,153,256},_x,_y)) return event::return_to_world;
    } else {
        if(_direction==0 && _inside({101,224,157,256},_x,_y)) {
            _x=128;_y=67;
            _load(place::exterior);
            return event::redraw;
        }
        if(_direction==3 && _inside({91,76,173,94},_x,_y)) {
            _menu_open=true;
            _menu_selection=setup;
            _walk_ticks=0;
            _refresh_sprite();
            return event::menu_opened;
        }
    }
    return event::none;
}

void town_scene::set_visible(bool visible) {
    _visible=visible;
    if(_background)_background->set_visible(visible);
    _player.set_visible(visible);
}
