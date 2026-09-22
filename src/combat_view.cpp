#include "combat_view.h"
#include "bn_sprite_items_car.h"
#include "bn_sprite_items_combat_bullet.h"
#include "bn_sprite_items_combat_hp.h"
#include "bn_sprite_items_combat_burst.h"
#include "bn_sprite_items_weapon_saw.h"
#include "bn_sprite_items_weapon_missile.h"
#include "bn_sprite_items_weapon_trap.h"
#include "bn_sprite_items_weapon_blast.h"
#include "bn_sprite_items_weapon_icons.h"
#include "bn_sprite_palette_ptr.h"
#include "bn_color.h"
#include "bn_core.h"

combat_view::combat_view() {
    auto palette=bn::sprite_palette_ptr::create_new(bn::sprite_items::car.palette_item());
    palette.set_color(4,bn::color(15,3,3));
    palette.set_color(5,bn::color(25,7,4));
    palette.set_color(6,bn::color(31,16,8));
    for(int i=0;i<combat::enemy_count;++i) {
        _cars[i]=bn::sprite_items::car.create_sprite(0,0);
        _cars[i]->set_palette(palette); _cars[i]->set_bg_priority(1); _cars[i]->set_z_order(0);
        _hp[i]=bn::sprite_items::combat_hp.create_sprite(0,0);
        _hp[i]->set_bg_priority(1); _hp[i]->set_z_order(-1);
        _bursts[i]=bn::sprite_items::combat_burst.create_sprite(0,0);
        _bursts[i]->set_bg_priority(1); _bursts[i]->set_z_order(-2);
        _cars[i]->set_visible(false); _hp[i]->set_visible(false); _bursts[i]->set_visible(false);
        bn::core::update(); // Scene loading, never charge allocation to driving.
    }
    for(auto& b:_bullets) {
        b=bn::sprite_items::combat_bullet.create_sprite(0,0);
        b->set_bg_priority(1); b->set_z_order(-2); b->set_visible(false);
    }
    auto prepare=[](bn::optional<bn::sprite_ptr>& sprite,const bn::sprite_item& item) {
        sprite=item.create_sprite(0,0);sprite->set_bg_priority(1);sprite->set_z_order(-3);sprite->set_visible(false);
    };
    for(int i=0;i<combat::missile_count;++i) {
        prepare(_missiles[i],bn::sprite_items::weapon_missile);prepare(_missile_bursts[i],bn::sprite_items::weapon_blast);
    }
    for(int i=0;i<combat::trap_count;++i) {
        prepare(_traps[i],bn::sprite_items::weapon_trap);prepare(_trap_bursts[i],bn::sprite_items::weapon_blast);
    }
    prepare(_saw,bn::sprite_items::weapon_saw);prepare(_weapon_icon,bn::sprite_items::weapon_icons);
    _weapon_icon->set_bg_priority(0);_weapon_icon->set_position(108,-74);
    bn::core::update();
}
void combat_view::update(const combat::World& world,int cx,int cy,bool visible) {
    for(int i=0;i<combat::enemy_count;++i) {
        const auto& e=world.enemies[i]; int x=e.car.x.integer()-cx,y=e.car.y.integer()-cy;
        bool on=visible && x>-140 && x<140 && y>-90 && y<96;
        _cars[i]->set_visible(on && e.hp>0 && (!e.flash || e.flash%4<2));
        _hp[i]->set_visible(on && e.hp>0 && y>-54);
        _bursts[i]->set_visible(on && e.explosion>0);
        if(on) {
            if(e.hp>0) {
                _cars[i]->set_position(x,y);
                _cars[i]->set_tiles(bn::sprite_items::car.tiles_item(),((e.car.heading*64/360).integer()+64)%64);
                _hp[i]->set_position(x,y-19);
                _hp[i]->set_tiles(bn::sprite_items::combat_hp.tiles_item(),e.hp-1);
            }
            if(e.explosion) {
                _bursts[i]->set_position(x,y);
                _bursts[i]->set_tiles(bn::sprite_items::combat_burst.tiles_item(),(24-e.explosion)/6);
            }
        }
    }
    for(int i=0;i<combat::bullet_count;++i) {
        const auto& b=world.bullets[i]; int x=b.x.integer()-cx,y=b.y.integer()-cy;
        bool on=visible && b.remaining>0 && x>-124 && x<124 && y>-64 && y<84;
        _bullets[i]->set_visible(on);
        if(on) {
            _bullets[i]->set_position(x,y);
            _bullets[i]->set_tiles(bn::sprite_items::combat_bullet.tiles_item(),b.hostile?1:b.side?2:0);
        }
    }
    auto effect=[&](bn::sprite_ptr& sprite,int x,int y,bool active,const bn::sprite_tiles_item& tiles,int frame) {
        bool on=visible && active && x>-140 && x<140 && y>-96 && y<96;
        sprite.set_visible(on);
        if(on){sprite.set_position(x,y);sprite.set_tiles(tiles,frame);}
    };
    effect(*_saw,world.saw_x.integer()-cx,world.saw_y.integer()-cy,world.saw_active,
           bn::sprite_items::weapon_saw.tiles_item(),(world.ticks/2)%4);
    for(int i=0;i<combat::missile_count;++i) {
        const auto& m=world.missiles[i];int x=m.x.integer()-cx,y=m.y.integer()-cy;
        effect(*_missiles[i],x,y,m.remaining>0,bn::sprite_items::weapon_missile.tiles_item(),(m.heading*16/360).integer()%16);
        effect(*_missile_bursts[i],x,y,m.explosion>0,bn::sprite_items::weapon_blast.tiles_item(),(24-m.explosion)/6);
    }
    for(int i=0;i<combat::trap_count;++i) {
        const auto& t=world.traps[i];int x=t.x.integer()-cx,y=t.y.integer()-cy;
        effect(*_traps[i],x,y,t.remaining>0,bn::sprite_items::weapon_trap.tiles_item(),!t.arm && (world.ticks/12)%2);
        effect(*_trap_bursts[i],x,y,t.explosion>0,bn::sprite_items::weapon_blast.tiles_item(),(24-t.explosion)/6);
    }
    _weapon_icon->set_visible(visible);
    if(visible)_weapon_icon->set_tiles(bn::sprite_items::weapon_icons.tiles_item(),int(world.weapon));
}
