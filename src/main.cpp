#include "bn_core.h"
#include "bn_keypad.h"
#include "bn_math.h"
#include "bn_regular_bg_ptr.h"
#include "bn_sprite_ptr.h"
#include "bn_sprite_font.h"
#include "bn_sprite_text_generator.h"
#include "bn_string.h"
#include "bn_vector.h"
#include "bn_sound_items.h"
#include "bn_sound_handle.h"
#include "bn_optional.h"
#include "bn_array.h"
#include "bn_regular_bg_items_title.h"
#include "bn_sprite_items_car.h"
#include "bn_sprite_items_font.h"
#include "bn_sprite_items_particles.h"
#include "bn_sprite_items_dot.h"
#include "driving.h"
#include "terrain_streamer.h"
#include "bn_unique_ptr.h"
#include "bn_bg_tiles.h"
#include "bn_bg_maps.h"
#include "bn_bg_palettes.h"
#include "bn_sprite_tiles.h"
#include "world_map.h"
#include "wasteland.h"
#include "local_minimap.h"
#include "bn_memory.h"
#include "bn_regular_bg_items_hud_waste.h"
#include "bn_regular_bg_items_pause_waste.h"
#include "bn_regular_bg_items_town_blank.h"
#include "bn_regular_bg_items_town_dialog.h"
#include "combat.h"
#include "combat_view.h"
#include "decoration_view.h"
#include "town_scene.h"

// Read-only telemetry for emulator regression tests; not a gameplay backdoor.
extern "C" {
// Diagnostic buffers belong in EWRAM; keep the small IWRAM stack available
// for rendering/physics calls rather than reserving it for debug snapshots.
BN_DATA_EWRAM_BSS volatile int dustline_telemetry[54];
BN_DATA_EWRAM_BSS volatile int dustline_combat_telemetry[240];
BN_DATA_EWRAM_BSS volatile int dustline_weapon_telemetry[72];
BN_DATA_EWRAM_BSS volatile int dustline_town_telemetry[8];
}

namespace {
using bn::fixed;
fixed clamp(fixed v,fixed lo,fixed hi) { return v<lo?lo:v>hi?hi:v; }
constexpr int camera_lead_x_limit=80,camera_lead_y_limit=48;
constexpr fixed camera_lead_x_scale=22,camera_lead_y_scale=16,camera_lead_response=fixed(0.12);
constexpr auto font_widths=[] {
    bn::array<int8_t,95> widths{};
    widths.fill(6);
    return widths;
}();
constexpr bn::sprite_font font(bn::sprite_items::font, {}, font_widths);
bn::sprite_text_generator* loading_generator=nullptr;
bn::vector<bn::sprite_ptr,48>* loading_sprites=nullptr;
int loading_progress=0,loading_displayed=-1;
void loading_update(int value) {
    value=value<0?0:value>100?100:value;
    if(value<loading_progress)value=loading_progress;
    loading_progress=value;
    dustline_telemetry[53]=value;
    if(loading_generator && loading_sprites && value!=loading_displayed) {
        loading_displayed=value;
        loading_sprites->clear();
        loading_generator->generate(-48,-18,"GENERATING WORLD",*loading_sprites);
        bn::string<20> bar="[";
        const int filled=value*16/100;
        for(int index=0;index<16;++index)bar+=(index<filled?'#':'-');
        bar+=']';
        loading_generator->generate(-54,4,bar,*loading_sprites);
        bn::string<8> percentage=bn::to_string<4>(value);
        percentage+='%';
        loading_generator->generate(-12,24,percentage,*loading_sprites);
    }
    bn::core::update();
}
void generation_loading_update(int value) { loading_update(value*90/100); }
void spawn_loading_update(int value) { loading_update(90+value*5/100); }

struct Mark {
    bn::sprite_ptr sprite=bn::sprite_items::particles.create_sprite(0,0);
    fixed x=0,y=0;
    int life=0;
    Mark() { sprite.set_visible(false); sprite.set_z_order(10); }
};
}

int main() {
    bn::core::init();
    // Title art owns most background tile VRAM. Allocate map graphics only
    // after a map is selected and the title has been released.
    bn::unique_ptr<terrain_streamer> track;
    bn::optional<bn::regular_bg_ptr> hud;
    bn::optional<bn::regular_bg_ptr> overlay=bn::regular_bg_items::title.create_bg(0,0);
    overlay->set_priority(0);
    auto car_sprite=bn::sprite_items::car.create_sprite(0,0);
    car_sprite.set_z_order(-1);
    car_sprite.set_bg_priority(1);
    car_sprite.set_visible(false);
    auto minimap_dot=bn::sprite_items::dot.create_sprite(0,0);
    minimap_dot.set_bg_priority(0);
    minimap_dot.set_z_order(-3);
    minimap_dot.set_visible(false);
    bn::sprite_text_generator text(font);
    text.set_bg_priority(0);
    text.set_z_order(-3);
    bn::vector<bn::sprite_ptr,48> hud_text;
    bn::vector<bn::sprite_ptr,48> loading_text;
    bn::vector<bn::sprite_ptr,12> speed_text;
    bn::vector<bn::sprite_ptr,12> surface_text;
    bn::vector<bn::sprite_ptr,16> vitality_text;
    bn::string<12> shown_speed_line;
    int shown_surface=-1,shown_hp=-1,shown_shield=-1;
    bn::vector<bn::sprite_ptr,8> weapon_text;
    int shown_weapon=-1;
    bn::array<Mark,24> marks;
    int next_mark=0;
    driving::Car car;
    fixed camera_lead_x=0,camera_lead_y=0,camera_x=car.x,camera_y=car.y-6;
    int state=0; // title=0, driving=1, pause=2, confirm=3, town=4, loading=5, settings=6, wrecked=7
    int zoom_level=0,settings_return=1;
    int setup=1;
    int selected_map=0;
    int lap_frames=0,best[3]={0,0,0},laps=0,checkpoint=0;
    int frame=0,notice_frames=180,engine_tick=0;
    int missed=0;
    bn::optional<bn::sound_handle> engine;
    bn::unique_ptr<local_minimap> radar;
    int ignored_town=-1,current_town=-1,town_visits=0;
    bool town_yes=false,button_guard=false;
    // Keep entity pools off the small IWRAM stack; allocation is once at boot.
    bn::unique_ptr<combat::World> combat_storage(new combat::World());
    auto& combat_world=*combat_storage;
    bn::unique_ptr<combat_view> combat_graphics;
    bn::unique_ptr<decoration_view> decorations;
    bn::unique_ptr<town_scene> town;

    auto reset=[&]() {
        car=driving::Car();
        car.x=world_map::start_x(); car.y=world_map::start_y();
        camera_lead_x=0;camera_lead_y=0;camera_x=car.x;camera_y=car.y-6;
        lap_frames=0; checkpoint=0; laps=0;
        notice_frames=180;
        for(auto& mark:marks) { mark.life=0; mark.sprite.set_visible(false); }
        if(engine && engine->active()) engine->stop();
        engine.reset(); engine_tick=0;
        ignored_town=-1; current_town=-1;
        combat_world.reset(car,true,spawn_loading_update);
    };

    auto unload_scene=[&]() {
        town.reset();
        decorations.reset();
        radar.reset(); overlay.reset(); hud.reset(); track.reset();
        combat_graphics.reset(); combat_world.clear_bullets();
        car_sprite.set_visible(false); minimap_dot.set_visible(false);
        for(auto& mark:marks) { mark.life=0; mark.sprite.set_visible(false); }
        hud_text.clear();
        speed_text.clear();surface_text.clear();vitality_text.clear();
        shown_speed_line.clear();shown_surface=-1;shown_hp=-1;shown_shield=-1;
        weapon_text.clear();shown_weapon=-1;
        if(engine && engine->active()) engine->stop();
        engine.reset(); engine_tick=0;
        // Flush display-manager references before allocating another scene.
        bn::core::update();
    };
    auto create_scene=[&]() {
        track.reset(new terrain_streamer());
        hud=bn::regular_bg_items::hud_waste.create_bg(0,0);
        hud->set_priority(0);
        radar.reset(new local_minimap(car.x.integer(),car.y.integer(),zoom_level));
        track->set_camera(camera_x.integer(),camera_y.integer());
        track->set_visible(true);
        car_sprite.set_position(car.x-camera_x.integer(),car.y-camera_y.integer());
        car_sprite.set_visible(true); minimap_dot.set_visible(true);
        combat_graphics.reset(new combat_view());
        if(wasteland::has_decoration()) {
            decorations.reset(new decoration_view());
            decorations->update(camera_x.integer(),camera_y.integer(),true);
            bn::core::update(); // Populate the initial patch window during scene loading.
            bn::core::update();
        }
    };

    while(true) {
        ++frame;
        // Only the driving HUD has values that change without an input event.
        // Menu text is rebuilt on entry or selection changes, avoiding repeated
        // sprite allocation while a static screen is open.
        bool redraw=frame==1 || (state==1 && frame%6==0);
        if(!bn::keypad::a_held() && !bn::keypad::b_held() && !bn::keypad::start_held()) button_guard=false;
        if(state==0 && (bn::keypad::left_pressed() || bn::keypad::right_pressed())) {
            const int count=wasteland::map_count();
            selected_map=(selected_map+(bn::keypad::left_pressed()?count-1:1))%count;
            redraw=true;
        }
        if(state==0 && bn::keypad::a_pressed()) {
            unload_scene();
            state=5; dustline_telemetry[2]=5;
            bn::bg_palettes::set_transparent_color(bn::color(2,4,5));
            loading_generator=&text;loading_sprites=&loading_text;
            loading_progress=0;loading_displayed=-1;
            loading_update(0);
            world_map::select(selected_map,generation_loading_update);
            loading_update(90);
            reset();loading_update(95);redraw=true;
            loading_update(96);create_scene();loading_update(100);
            loading_text.clear();loading_generator=nullptr;loading_sprites=nullptr;
            state=1;
            bn::sound_items::chime.play(fixed(0.45));
        } else if((state==1 || state==2) && bn::keypad::start_pressed()) {
            state=state==1?2:1;
            if(state==2) {
                overlay=bn::regular_bg_items::pause_waste.create_bg(0,0);
                overlay->set_priority(0);
            } else overlay.reset();
            hud->set_visible(state==1);
            car_sprite.set_visible(state==1);
            minimap_dot.set_visible(state==1);
            if(radar) radar->set_visible(state==1);
            if(engine && engine->active()) engine->stop();
            engine.reset(); engine_tick=0;
            hud_text.clear(); redraw=true;
        }

        if(state==2 && bn::keypad::select_pressed()) {
            state=0;
            unload_scene();
            overlay=bn::regular_bg_items::title.create_bg(0,0);
            overlay->set_priority(0);
            hud_text.clear(); redraw=true;
        }
        if((state==1 || state==4) && bn::keypad::select_pressed()) {
            settings_return=state; state=6;
            if(engine && engine->active()) engine->stop();
            engine.reset(); engine_tick=0;
            if(hud) hud->set_visible(false);
            car_sprite.set_visible(false); minimap_dot.set_visible(false);
            if(radar) radar->set_visible(false);
            if(town) town->set_visible(false);
            overlay.reset(); hud_text.clear(); bn::core::update();
            overlay=bn::regular_bg_items::town_blank.create_bg(0,0);
            overlay->set_priority(0); redraw=true;
        } else if(state==6) {
            if(bn::keypad::left_pressed() && zoom_level>0) { --zoom_level; redraw=true; }
            if(bn::keypad::right_pressed() && zoom_level<3) { ++zoom_level; redraw=true; }
            if(bn::keypad::a_pressed() || bn::keypad::b_pressed() || bn::keypad::select_pressed() || bn::keypad::start_pressed()) {
                hud_text.clear();
                if(radar) radar->set_zoom(zoom_level,car.x.integer(),car.y.integer());
                state=settings_return; button_guard=true; redraw=true;
                if(state==1) {
                    overlay.reset(); hud->set_visible(true); car_sprite.set_visible(true);
                    radar->set_visible(true); minimap_dot.set_visible(true);
                } else if(state==4 && town) {
                    overlay.reset();
                    if(town->menu_open()) {
                        overlay=bn::regular_bg_items::town_dialog.create_bg(0,0);
                        overlay->set_priority(0);
                    }
                    town->set_visible(true);
                }
            }
        }
        if(state==7) {
            if(bn::keypad::a_pressed()) {
                combat_world.revive_player();
                overlay.reset();hud_text.clear();state=1;button_guard=true;redraw=true;
                radar->set_visible(true);minimap_dot.set_visible(true);
                bn::sound_items::chime.play(fixed(0.4));
            }
        } else if(state==3) {
            if(bn::keypad::up_pressed() || bn::keypad::down_pressed() ||
               bn::keypad::left_pressed() || bn::keypad::right_pressed()) { town_yes=!town_yes; redraw=true; }
            if(bn::keypad::b_pressed() || (bn::keypad::a_pressed() && !town_yes)) {
                ignored_town=current_town; state=1; overlay.reset();
                hud_text.clear(); button_guard=true; redraw=true;
            } else if(bn::keypad::a_pressed() && town_yes) {
                combat_world.refill_player();
                unload_scene(); state=4; ++town_visits;
                town.reset(new town_scene(current_town,setup));
                redraw=true;
            }
        } else if(state==4 && town && !button_guard) {
            auto town_event=town->update(setup);
            if(town_event==town_scene::event::return_to_world) {
                overlay.reset();hud_text.clear();town.reset();bn::core::update();
                create_scene();ignored_town=current_town;state=1;button_guard=true;redraw=true;
            } else if(town_event==town_scene::event::menu_opened) {
                overlay=bn::regular_bg_items::town_dialog.create_bg(0,0);
                overlay->set_priority(0);redraw=true;
            } else if(town_event==town_scene::event::menu_closed ||
                      town_event==town_scene::event::setup_applied) {
                overlay.reset();redraw=true;
                if(town_event==town_scene::event::setup_applied)
                    bn::sound_items::chime.play(fixed(0.4));
            } else if(town_event==town_scene::event::redraw) redraw=true;
        }
        if(state==1) {
            driving::Input input {bn::keypad::a_held(),bn::keypad::b_held(),
                (bn::keypad::right_held()?1:0)-(bn::keypad::left_held()?1:0)};
            if(!button_guard) {
                car.step(input,setup); ++lap_frames;
                if(bn::keypad::l_pressed()) { combat_world.cycle_weapon();redraw=true; }
                int combat_start=bn::core::current_cpu_ticks();
                combat_world.step(car,bn::keypad::r_held());
                dustline_combat_telemetry[18]=bn::core::current_cpu_ticks()-combat_start;
                if(combat_world.fired) bn::sound_items::gun.play(fixed(0.28));
                if(combat_world.destroyed) bn::sound_items::bump.play(fixed(0.6));
                else if(combat_world.impact) bn::sound_items::bump.play(fixed(0.18));
            }
            if(notice_frames>0) --notice_frames;
            // Anchor to the car and smooth only the velocity-driven look-ahead.
            // This keeps the car stable while opening more screen in the actual
            // direction of travel, including reverse and controlled slides.
            fixed desired_lead_x=clamp(car.vx*camera_lead_x_scale,-camera_lead_x_limit,camera_lead_x_limit);
            fixed desired_lead_y=clamp(car.vy*camera_lead_y_scale,-camera_lead_y_limit,camera_lead_y_limit);
            camera_lead_x+=(desired_lead_x-camera_lead_x)*camera_lead_response;
            camera_lead_y+=(desired_lead_y-camera_lead_y)*camera_lead_response;
            camera_x=clamp(car.x+camera_lead_x,120,world_map::width()-120);
            camera_y=clamp(car.y+camera_lead_y-6,80,world_map::height()-80);
            track->set_camera(camera_x.integer(),camera_y.integer());
            car_sprite.set_position(car.x-camera_x.integer(),car.y-camera_y.integer());
            int direction=((car.heading*64/360).integer()+64)%64;
            car_sprite.set_tiles(bn::sprite_items::car.tiles_item(),direction);
            radar->update(car.x.integer(),car.y.integer());
            int marker_x=radar->project_x(car.x.integer());
            int marker_y=radar->project_y(car.y.integer());
            minimap_dot.set_position(local_minimap::screen_x+marker_x,local_minimap::screen_y+marker_y);
            bool sliding=car.slip>fixed(0.28) && car.speed>fixed(0.8);
            if(frame%4==0 && (sliding || (car.surface!=1 && car.speed>fixed(0.6)))) {
                Mark& mark=marks[next_mark]; next_mark=(next_mark+1)%marks.size();
                mark.x=car.x-bn::degrees_lut_cos(car.heading)*9;
                mark.y=car.y-bn::degrees_lut_sin(car.heading)*9;
                mark.life=car.surface==1?96:40;
                mark.sprite.set_tiles(bn::sprite_items::particles.tiles_item(),car.surface==1?0:1);
                mark.sprite.set_bg_priority(2);
            }
            if(car.hit) bn::sound_items::bump.play(fixed(0.5));
            if(sliding && frame%14==0) bn::sound_items::skid.play(fixed(0.13));
            if(--engine_tick<=0) {
                fixed pitch=fixed(0.65)+car.speed*fixed(0.55)+(input.throttle?fixed(0.12):fixed(0));
                if(engine && engine->active()) engine->stop();
                engine=bn::sound_items::engine.play(input.throttle?fixed(0.28):fixed(0.15),pitch,0);
                engine_tick=bn::max(5,(fixed(17)/pitch).integer());
            }
            for(auto& mark:marks) {
                if(mark.life>0) --mark.life;
                fixed sx=mark.x-camera_x,sy=mark.y-camera_y;
                bool visible=mark.life>0 && sx>-125 && sx<125 && sy>-85 && sy<85;
                mark.sprite.set_visible(visible);
                if(visible) mark.sprite.set_position(sx,sy);
            }
            // Build only the dialog text on entry, never both text screens in
            // one frame (the renderer retains old sprite references until VBlank).
            int approaching=wasteland::layout().nearby_town(car.x.integer(),car.y.integer());
            if(redraw && !(approaching>=0 && approaching!=ignored_town)) {
                bn::string<12> speed_line=bn::to_string<4>((car.speed*42).integer());
                speed_line+=" KPH";
                if(speed_line!=shown_speed_line || speed_text.empty()) {
                    speed_text.clear();text.generate(-114,-74,speed_line,speed_text);
                    shown_speed_line=speed_line;
                }
                int surface=wasteland::layout().material(car.x.integer(),car.y.integer());
                const char* names[]={"SAND","GRAVEL","HARDPAN","ASPHALT"};
                if(surface!=shown_surface || surface_text.empty()) {
                    surface_text.clear();text.generate(-70,-74,names[surface],surface_text);
                    shown_surface=surface;
                }
                if(combat_world.player_hp!=shown_hp || combat_world.player_shield!=shown_shield || vitality_text.empty()) {
                    bn::string<16> line="H";line+=bn::to_string<4>(combat_world.player_hp);
                    line+=" S";line+=bn::to_string<3>(combat_world.player_shield);
                    vitality_text.clear();text.generate(-20,-74,line,vitality_text);
                    shown_hp=combat_world.player_hp;shown_shield=combat_world.player_shield;
                }
            }
            const auto& layout=wasteland::layout();
            if(ignored_town>=0) {
                auto p=layout.town(ignored_town);
                if(bn::abs(car.x.integer()-p.x)>160 || bn::abs(car.y.integer()-p.y)>160) ignored_town=-1;
            }
            int near=layout.nearby_town(car.x.integer(),car.y.integer());
            if(!combat_world.player_destroyed && near>=0 && near!=ignored_town) {
                state=3; current_town=near; town_yes=false;
                car.vx=0; car.vy=0; car.yaw=0; car.speed=0; car.slip=0;
                if(engine && engine->active()) engine->stop();
                engine.reset(); engine_tick=0;
                hud_text.clear();
                radar->set_visible(false); minimap_dot.set_visible(false);
                if(combat_graphics) combat_graphics->update(combat_world,camera_x.integer(),camera_y.integer(),false);
                // Finish the driving frame before allocating dialog art/text.
                // Combat is already paused; this is a scene/UI transition.
                bn::core::update();
                missed+=bn::core::last_missed_frames();
                overlay=bn::regular_bg_items::town_dialog.create_bg(0,0);
                overlay->set_priority(0); hud_text.clear(); redraw=true;
                radar->set_visible(false);
                minimap_dot.set_visible(false);
            }
            if(state==1) { radar->set_visible(true); minimap_dot.set_visible(true); }
            if(state==1 && combat_world.player_destroyed) {
                state=7;car.vx=0;car.vy=0;car.yaw=0;car.speed=0;car.slip=0;
                if(engine && engine->active())engine->stop();
                engine.reset();engine_tick=0;hud_text.clear();
                radar->set_visible(false);minimap_dot.set_visible(false);
                bn::core::update();missed+=bn::core::last_missed_frames();
                overlay=bn::regular_bg_items::town_dialog.create_bg(0,0);
                overlay->set_priority(0);redraw=true;
            }
        } else {
            for(auto& mark:marks) mark.sprite.set_visible(false);
            if(state==0 && redraw) {
                hud_text.clear();
                bn::string<32> line="<  ";line+=wasteland::map_name(selected_map);line+="  >";
                text.set_center_alignment();
                text.generate(0,52,line,hud_text);
                text.generate(0,68,"PRESS A TO START",hud_text);
                text.set_left_alignment();
            }
        }
        if(state==3 && redraw) {
            hud_text.clear();
            bn::string<32> line="ENTER OUTPOST ";
            line+=bn::to_string<3>(current_town+1); line+='?';
            text.generate(-104,38,line,hud_text);
            text.generate(-104,52,town_yes?"> YES     NO":"  YES   > NO",hud_text);
            text.generate(-104,68,"A CONFIRM  B CANCEL",hud_text);
        }
        if(state==4 && redraw) {
            hud_text.clear();
            if(town && town->menu_open()) {
                bn::string<32> line="MECHANIC / SETUP";
                text.generate(-104,38,line,hud_text);
                line="<  ";line+=driving::setups[town->menu_selection()].name;line+="  >";
                text.generate(-104,52,line,hud_text);
                line=bn::to_string<5>(driving::setups[town->menu_selection()].mass);line+=" KG";
                text.generate(18,52,line,hud_text);
                text.generate(-104,68,"A FIT     B CANCEL",hud_text);
            }
        }
        if(state==7 && redraw) {
            hud_text.clear();
            text.generate(-104,48,"WRECKED",hud_text);
            text.generate(-104,68,"PRESS A TO REVIVE",hud_text);
        }

        if(state==6 && redraw) {
            hud_text.clear();
            text.generate(-96,-52,"SETTINGS",hud_text);
            text.generate(-96,-28,"MINIMAP ZOOM",hud_text);
            for(int i=0;i<4;++i) {
                bn::string<8> option=zoom_level==i?">":" ";
                option+=bn::to_string<2>(1<<i); option+="X";
                text.generate(-96+i*48,-7,option,hud_text);
            }
            bn::string<32> line="VIEW RADIUS: ";
            line+=bn::to_string<5>(26*(128>>zoom_level)); line+=" PX";
            text.generate(-96,14,line,hud_text);
            text.generate(-96,32,"1X WIDEST / 8X CLOSEST",hud_text);
            text.generate(-96,42,"RED ENEMIES / GOLD TOWNS",hud_text);
            text.generate(-96,52,"LEFT/RIGHT CHANGE",hud_text);
            text.generate(-96,66,"A/B/SELECT BACK",hud_text);
        }
        if(state!=1) {
            speed_text.clear();surface_text.clear();vitality_text.clear();
            shown_speed_line.clear();shown_surface=-1;shown_hp=-1;shown_shield=-1;
        }
        if(state==1) {
            if(shown_weapon!=int(combat_world.weapon)) {
                weapon_text.clear();bn::string<16> label="L:";label+=combat::weapon_name(combat_world.weapon);
                text.generate(58,-74,label,weapon_text);shown_weapon=int(combat_world.weapon);
            }
        } else if(shown_weapon>=0) { weapon_text.clear();shown_weapon=-1; }
        int view_start=bn::core::current_cpu_ticks();
        if(decorations)decorations->update(camera_x.integer(),camera_y.integer(),state==1 || state==3 || state==7);
        if(radar)radar->update_enemies(combat_world,state==1);
        if(combat_graphics) combat_graphics->update(combat_world,camera_x.integer(),camera_y.integer(),state==1 || state==7);
        dustline_combat_telemetry[19]=bn::core::current_cpu_ticks()-view_start;
        dustline_combat_telemetry[0]=0x434F4D42;
        dustline_combat_telemetry[1]=combat_world.ticks;
        dustline_combat_telemetry[2]=combat_world.player_hp;
        dustline_combat_telemetry[3]=combat_world.player_hits;
        dustline_combat_telemetry[4]=combat_world.player_shots;
        dustline_combat_telemetry[5]=combat_world.enemy_shots;
        dustline_combat_telemetry[6]=combat_world.hits;
        dustline_combat_telemetry[7]=combat_world.kills;
        dustline_combat_telemetry[8]=combat_world.wall_hits;
        dustline_combat_telemetry[9]=combat_world.expired;
        dustline_combat_telemetry[10]=combat_world.living();
        dustline_combat_telemetry[12]=sizeof(combat_world);
        dustline_combat_telemetry[13]=combat_graphics?1:0;
        dustline_combat_telemetry[14]=combat_world.player_invulnerability;
        int collisions=0,avoidance=0,recoveries=0,bullets=0;
        for(int i=0;i<combat::enemy_count;++i) {
            const auto& e=combat_world.enemies[i]; int at=20+i*12;
            dustline_combat_telemetry[at]=e.car.x.data(); dustline_combat_telemetry[at+1]=e.car.y.data();
            dustline_combat_telemetry[at+2]=e.car.vx.data(); dustline_combat_telemetry[at+3]=e.car.vy.data();
            dustline_combat_telemetry[at+4]=e.car.heading.data(); dustline_combat_telemetry[at+5]=e.hp;
            dustline_combat_telemetry[at+6]=e.car.collisions; dustline_combat_telemetry[at+7]=e.reverse;
            dustline_combat_telemetry[at+8]=e.avoidance; dustline_combat_telemetry[at+9]=e.recoveries;
            dustline_combat_telemetry[at+10]=e.explosion; dustline_combat_telemetry[at+11]=e.flash;
            collisions+=e.car.collisions; avoidance+=e.avoidance; recoveries+=e.recoveries;
        }
        for(int i=0;i<combat::bullet_count;++i) {
            const auto& b=combat_world.bullets[i]; int at=80+i*4;
            dustline_combat_telemetry[at]=b.x.data(); dustline_combat_telemetry[at+1]=b.y.data();
            dustline_combat_telemetry[at+2]=b.remaining; dustline_combat_telemetry[at+3]=b.hostile;
            bullets+=b.remaining>0;
        }
        dustline_combat_telemetry[11]=bullets;
        dustline_combat_telemetry[15]=collisions; dustline_combat_telemetry[16]=avoidance;
        dustline_combat_telemetry[17]=recoveries;
        dustline_combat_telemetry[176]=combat_world.bumps;
        dustline_combat_telemetry[177]=combat_world.last_bump.data();
        dustline_combat_telemetry[178]=car.mass;
        dustline_combat_telemetry[179]=combat_world.last_pair;
        dustline_combat_telemetry[180]=combat_world.player_bumps;
        for(int i=0;i<combat::enemy_count;++i) {
            const auto& e=combat_world.enemies[i]; int at=184+i*9;
            dustline_combat_telemetry[at]=e.vehicle_avoidance;
            dustline_combat_telemetry[at+1]=e.moving_frames;
            dustline_combat_telemetry[at+2]=e.maneuver;
            dustline_combat_telemetry[at+3]=e.side;
            dustline_combat_telemetry[at+4]=e.car.mass;
            dustline_combat_telemetry[at+5]=e.goal_x;
            dustline_combat_telemetry[at+6]=e.goal_y;
            dustline_combat_telemetry[at+7]=e.stalled;
            dustline_combat_telemetry[at+8]=e.spawn_id;
        }
        dustline_combat_telemetry[229]=combat_world.spawns.count;
        dustline_combat_telemetry[230]=combat_world.spawned;
        dustline_combat_telemetry[231]=combat_world.despawned;
        dustline_combat_telemetry[232]=combat::spawn_cooldown;
        dustline_combat_telemetry[233]=int(reinterpret_cast<uintptr_t>(combat_world.spawns.points));
        dustline_combat_telemetry[234]=sizeof(enemy_spawns::point);
        dustline_combat_telemetry[235]=combat::spawn_range;
        dustline_combat_telemetry[236]=combat::despawn_range;
        dustline_combat_telemetry[237]=combat_world.player_shield;
        dustline_combat_telemetry[238]=combat_world.player_shield_delay;
        dustline_combat_telemetry[239]=combat_world.player_invulnerability;
        dustline_weapon_telemetry[0]=int(combat_world.weapon);
        dustline_weapon_telemetry[1]=combat_world.saw_active;
        dustline_weapon_telemetry[2]=combat_world.saw_x.data();dustline_weapon_telemetry[3]=combat_world.saw_y.data();
        dustline_weapon_telemetry[4]=combat_world.guidance_updates;dustline_weapon_telemetry[5]=combat_world.trap_explosions;
        for(int i=0;i<combat::weapon_count;++i) {
            dustline_weapon_telemetry[8+i]=combat_world.weapon_shots[i];dustline_weapon_telemetry[13+i]=combat_world.weapon_hits[i];
        }
        for(int i=0;i<combat::missile_count;++i) {
            const auto& m=combat_world.missiles[i];int at=20+i*9;
            dustline_weapon_telemetry[at]=m.x.data();dustline_weapon_telemetry[at+1]=m.y.data();
            dustline_weapon_telemetry[at+2]=m.vx.data();dustline_weapon_telemetry[at+3]=m.vy.data();
            dustline_weapon_telemetry[at+4]=m.remaining;dustline_weapon_telemetry[at+5]=m.age;
            dustline_weapon_telemetry[at+6]=m.target_spawn;dustline_weapon_telemetry[at+7]=m.heading.data();
            dustline_weapon_telemetry[at+8]=m.explosion;
        }
        for(int i=0;i<combat::trap_count;++i) {
            const auto& t=combat_world.traps[i];int at=40+i*5;
            dustline_weapon_telemetry[at]=t.x.data();dustline_weapon_telemetry[at+1]=t.y.data();
            dustline_weapon_telemetry[at+2]=t.remaining;dustline_weapon_telemetry[at+3]=t.arm;dustline_weapon_telemetry[at+4]=t.explosion;
        }
        dustline_telemetry[0]=0x44555354;
        dustline_telemetry[1]=frame;
        dustline_telemetry[2]=state;
        dustline_telemetry[3]=setup;
        dustline_telemetry[4]=car.x.data(); dustline_telemetry[5]=car.y.data();
        dustline_telemetry[6]=car.vx.data(); dustline_telemetry[7]=car.vy.data();
        dustline_telemetry[8]=car.heading.data(); dustline_telemetry[9]=car.slip.data();
        dustline_telemetry[10]=car.surface; dustline_telemetry[11]=lap_frames;
        dustline_telemetry[12]=best[setup]; dustline_telemetry[13]=laps;
        dustline_telemetry[14]=checkpoint; dustline_telemetry[15]=car.collisions;
        dustline_telemetry[16]=bn::core::last_cpu_usage().data();
        dustline_telemetry[17]=missed;
        dustline_telemetry[18]=camera_x.integer();
        dustline_telemetry[19]=camera_y.integer();
        dustline_telemetry[20]=bn::core::last_vblank_usage().data();
        dustline_telemetry[21]=track?track->uploaded_bytes():0;
        dustline_telemetry[22]=(bn::bg_tiles::used_blocks_count()+bn::bg_maps::used_blocks_count())*2048;
        dustline_telemetry[23]=bn::sprite_tiles::available_tiles_count()*32;
        dustline_telemetry[24]=state==0?selected_map:world_map::index();
        dustline_telemetry[25]=world_map::width();
        dustline_telemetry[26]=world_map::height();
        dustline_telemetry[27]=(car.y.integer()/256)*(world_map::width()/256)+car.x.integer()/256;
        dustline_telemetry[28]=track?track->capacity():0;
        dustline_telemetry[29]=track?track->unique_tiles():0;
        dustline_telemetry[30]=track?track->working_ram_bytes():0;
        dustline_telemetry[31]=world_map::chunk_loads();
        dustline_telemetry[32]=world_map::chunk_decodes();
        dustline_telemetry[33]=world_map::chunk_cache_bytes();
        dustline_telemetry[34]=minimap_dot.x().integer();
        dustline_telemetry[35]=minimap_dot.y().integer();
        dustline_telemetry[36]=wasteland::active()?wasteland::layout().seed():0;
        dustline_telemetry[37]=wasteland::active()?wasteland::layout().signature():0;
        dustline_telemetry[38]=wasteland::generations();
        dustline_telemetry[39]=current_town;
        dustline_telemetry[40]=wasteland::active()?wasteland::layout().town(0).x:0;
        dustline_telemetry[41]=wasteland::active()?wasteland::layout().town(0).y:0;
        dustline_telemetry[42]=wasteland::active()?wasteland::layout_bytes():0;
        dustline_telemetry[43]=wasteland::generation_scratch_bytes();
        dustline_telemetry[44]=bn::memory::available_alloc_ewram();
        dustline_telemetry[45]=wasteland::active()?wasteland::layout().floor_count():0;
        dustline_telemetry[46]=wasteland::generation_updates();
        dustline_telemetry[47]=town_visits;
        dustline_telemetry[48]=radar?radar->center_x():0;
        dustline_telemetry[49]=radar?radar->center_y():0;
        dustline_telemetry[50]=radar?radar->revisions():0;
        dustline_telemetry[51]=zoom_level;
        dustline_telemetry[52]=radar?radar->scale():0;
        dustline_town_telemetry[0]=0x544F574E;
        dustline_town_telemetry[1]=town?int(town->current_place()):-1;
        dustline_town_telemetry[2]=town?town->x():0;
        dustline_town_telemetry[3]=town?town->y():0;
        dustline_town_telemetry[4]=town?town->direction():0;
        dustline_town_telemetry[5]=town&&town->menu_open();
        dustline_town_telemetry[6]=town?town->menu_selection():0;
        dustline_town_telemetry[7]=town?town->town_id():-1;
        bn::core::update();
        missed+=bn::core::last_missed_frames();
    }
}
