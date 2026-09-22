#pragma once
#include "bn_array.h"
#include "driving.h"
#include "enemy_spawns.h"

// Bounded, fixed-point simulation. No sprites, audio or allocation in this layer.
namespace combat {
constexpr int enemy_count=5, bullet_count=24, enemy_hp=3, player_max_hp=100,player_max_shield=20;
constexpr int spawn_range=560, despawn_range=800, spawn_cooldown=1800;
constexpr int player_range=120, enemy_range=480, player_interval=10, enemy_interval=player_interval;
constexpr int shield_recharge_delay=180,shield_recharge_interval=15,revive_invulnerability=120;
enum class Weapon { gun, chainsaw, sides, missile, trap, count };
constexpr int weapon_count=int(Weapon::count), missile_count=2, trap_count=6;
constexpr int saw_radius=10, saw_damage=2, missile_damage=3, trap_damage=3;
const char* weapon_name(Weapon weapon);
struct Enemy {
    driving::Car car;
    driving::Input input{false,false,0};
    int hp=0, cooldown=0, flash=0, explosion=0, reverse=0, stalled=0;
    int avoidance=0, recoveries=0;
    int side=1,maneuver=0,goal_x=0,goal_y=0,home_x=0,home_y=0;
    int vehicle_avoidance=0,moving_frames=0;
    int spawn_id=-1;
};
struct Bullet {
    bn::fixed x=0,y=0,vx=0,vy=0;
    int remaining=0;
    bool hostile=false;
    bool side=false;
};
struct Missile {
    bn::fixed x=0,y=0,vx=0,vy=0,heading=0;
    int remaining=0,age=0,target_spawn=-1,explosion=0;
};
struct Trap {
    bn::fixed x=0,y=0;
    int remaining=0,arm=0,explosion=0;
};
class World {
public:
    bn::array<Enemy,enemy_count> enemies;
    bn::array<Bullet,bullet_count> bullets;
    bn::array<Missile,missile_count> missiles;
    bn::array<Trap,trap_count> traps;
    Weapon weapon=Weapon::gun;
    bn::array<int,weapon_count> weapon_shots{},weapon_hits{};
    bn::fixed saw_x=0,saw_y=0;
    bool saw_active=false;
    int guidance_updates=0,trap_explosions=0;
    enemy_spawns spawns;
    int spawned=0,despawned=0;
    int player_hp=player_max_hp,player_shield=player_max_shield;
    int player_shield_delay=0,player_invulnerability=0;
    int player_hits=0, player_shots=0, enemy_shots=0;
    int hits=0,kills=0,wall_hits=0,expired=0,ticks=0;
    int bumps=0,player_bumps=0,last_pair=-1;
    bn::fixed last_bump=0;
    bool fired=false,impact=false,destroyed=false,player_destroyed=false;
    void reset(const driving::Car& player,bool enabled,cave_layout::progress_fn progress=nullptr);
    BN_CODE_IWRAM void step(driving::Car& player,bool fire);
    void clear_bullets();
    void refill_player();
    void revive_player();
    void cycle_weapon();
    int living() const;
private:
    bool _enabled=false;
    bn::array<int,weapon_count> _cooldowns{};
    bn::array<int,enemy_count*(enemy_count+1)/2> _contact_cooldowns{};
    void stream(const driving::Car& player,bool initial=false);
    BN_CODE_IWRAM void think(Enemy& enemy,const driving::Car& player);
    bool shoot(const driving::Car& car,bool hostile,int angle=0,bool side=false);
    void fire_weapon(const driving::Car& player,bool fire);
    void update_specials(const driving::Car& player);
    void damage(Enemy& enemy,int amount,Weapon source);
    void damage_player(int amount);
    void explode(int x,int y,int radius,int amount,Weapon source);
    BN_CODE_IWRAM bool hit_at(Bullet& bullet,const driving::Car& player);
};
}
