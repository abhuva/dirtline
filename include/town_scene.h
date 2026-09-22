#pragma once
#include "bn_optional.h"
#include "bn_regular_bg_ptr.h"
#include "bn_sprite_ptr.h"

class town_scene {
public:
    struct rect { int left,top,right,bottom; };
    enum class place { exterior, garage };
    enum class event { none, redraw, menu_opened, menu_closed, setup_applied, return_to_world };

    town_scene(int town_id,int setup);
    event update(int& setup);
    void set_visible(bool visible);

    int town_id() const { return _town_id; }
    int x() const { return _x; }
    int y() const { return _y; }
    int direction() const { return _direction; }
    int menu_selection() const { return _menu_selection; }
    place current_place() const { return _place; }
    bool menu_open() const { return _menu_open; }

private:
    void _load(place next);
    void _refresh_sprite();
    bool _blocked(int x,int y) const;
    bool _inside(const rect& area,int x,int y) const;

    bn::optional<bn::regular_bg_ptr> _background;
    bn::sprite_ptr _player;
    int _town_id;
    int _x=128,_y=226;
    int _direction=3;
    int _walk_ticks=0;
    int _menu_selection=0;
    place _place=place::exterior;
    bool _menu_open=false;
    bool _visible=true;
};
