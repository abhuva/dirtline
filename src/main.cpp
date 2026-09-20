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
#include "bn_regular_bg_items_track.h"
#include "bn_regular_bg_items_title.h"
#include "bn_regular_bg_items_hud.h"
#include "bn_regular_bg_items_pause.h"
#include "bn_sprite_items_car.h"
#include "bn_sprite_items_font.h"
#include "bn_sprite_items_particles.h"
#include "bn_sprite_items_dot.h"
#include "driving.h"
#include "generated/track_data.h"

// Read-only telemetry for emulator regression tests; not a gameplay backdoor.
extern "C" {
volatile int dustline_telemetry[20] = {};
}

namespace {
using bn::fixed;
fixed clamp(fixed v,fixed lo,fixed hi) { return v<lo?lo:v>hi?hi:v; }
constexpr auto font_widths=[] {
    bn::array<int8_t,95> widths{};
    widths.fill(6);
    return widths;
}();
constexpr bn::sprite_font font(bn::sprite_items::font, {}, font_widths);

bn::string<16> time_string(int frames) {
    // GBA refresh is 16777216 / 280896 Hz, not precisely 60 Hz.
    int centiseconds=int((int64_t(frames)*280896*100)/16777216);
    int seconds=centiseconds/100;
    bn::string<16> result;
    result+=bn::to_string<8>(seconds);
    result+='.';
    int fraction=centiseconds%100;
    if(fraction<10) result+='0';
    result+=bn::to_string<4>(fraction);
    return result;
}

struct Mark {
    bn::sprite_ptr sprite=bn::sprite_items::particles.create_sprite(0,0);
    fixed x=0,y=0;
    int life=0;
    Mark() { sprite.set_visible(false); sprite.set_z_order(10); }
};
}

int main() {
    bn::core::init();
    auto track=bn::regular_bg_items::track.create_bg(0,0);
    track.set_priority(3);
    auto hud=bn::regular_bg_items::hud.create_bg(0,0);
    hud.set_priority(0);
    auto overlay=bn::regular_bg_items::title.create_bg(0,0);
    overlay.set_priority(0);
    hud.set_visible(false);
    auto car_sprite=bn::sprite_items::car.create_sprite(0,0);
    car_sprite.set_z_order(-1);
    car_sprite.set_bg_priority(1);
    car_sprite.set_visible(false);
    auto minimap_dot=bn::sprite_items::dot.create_sprite(0,0);
    minimap_dot.set_bg_priority(0);
    minimap_dot.set_z_order(-2);
    minimap_dot.set_visible(false);
    bn::sprite_text_generator text(font);
    text.set_bg_priority(0);
    text.set_z_order(-3);
    bn::vector<bn::sprite_ptr,48> hud_text;
    bn::array<Mark,24> marks;
    int next_mark=0;
    driving::Car car;
    fixed camera_x=car.x+25, camera_y=car.y;
    int state=0; // title=0, driving=1, pause=2
    int setup=1;
    int lap_frames=0,best[3]={0,0,0},laps=0,checkpoint=0;
    int frame=0,notice_frames=180,engine_tick=0;
    int missed=0;
    bn::optional<bn::sound_handle> engine;

    auto reset=[&]() {
        car=driving::Car();
        camera_x=car.x+25; camera_y=car.y;
        lap_frames=0; checkpoint=0; laps=0;
        notice_frames=180;
        for(auto& mark:marks) { mark.life=0; mark.sprite.set_visible(false); }
        if(engine && engine->active()) engine->stop();
        engine.reset(); engine_tick=0;
    };

    while(true) {
        ++frame;
        bool redraw=(frame%6==0);
        if(state==0 && (bn::keypad::a_pressed() || bn::keypad::start_pressed())) {
            state=1;
            overlay.set_visible(false);
            hud.set_visible(true);
            car_sprite.set_visible(true);
            minimap_dot.set_visible(true);
            reset(); redraw=true;
            bn::sound_items::chime.play(fixed(0.45));
        } else if(state!=0 && bn::keypad::start_pressed()) {
            state=state==1?2:1;
            overlay.set_item(bn::regular_bg_items::pause);
            overlay.set_visible(state==2);
            hud.set_visible(state==1);
            car_sprite.set_visible(state==1);
            minimap_dot.set_visible(state==1);
            if(engine && engine->active()) engine->stop();
            engine.reset(); engine_tick=0;
            hud_text.clear(); redraw=true;
        }

        if(state!=0) {
            if(bn::keypad::r_pressed() || bn::keypad::l_pressed()) {
                setup=(setup+(bn::keypad::r_pressed()?1:2))%3;
                reset(); redraw=true;
                bn::sound_items::chime.play(fixed(0.4));
            }
            if(bn::keypad::select_pressed()) { reset(); redraw=true; }
        }
        if(state==1) {
            fixed previous_x=car.x;
            driving::Input input {bn::keypad::a_held(),bn::keypad::b_held(),
                (bn::keypad::right_held()?1:0)-(bn::keypad::left_held()?1:0)};
            car.step(input,setup);
            ++lap_frames;
            if(notice_frames>0) --notice_frames;
            if(checkpoint<int(sizeof(world::checkpoints)/sizeof(world::checkpoints[0]))) {
                auto point=world::checkpoints[checkpoint];
                int dx=car.x.integer()-point.x,dy=car.y.integer()-point.y;
                if(dx*dx+dy*dy<52*52) ++checkpoint;
            } else if(previous_x<452 && car.x>=452 && car.y>825 && car.y<896 && car.vx>0) {
                if(best[setup]==0 || lap_frames<best[setup]) best[setup]=lap_frames;
                lap_frames=0; checkpoint=0; ++laps; notice_frames=120;
                bn::sound_items::chime.play(fixed(0.6)); redraw=true;
            }
            // Camera leads actual motion; smoothed and clamped to the map.
            fixed target_x=clamp(car.x+car.vx*13,120,904);
            fixed target_y=clamp(car.y+car.vy*13-6,80,944);
            camera_x+=(target_x-camera_x)*fixed(0.095);
            camera_y+=(target_y-camera_y)*fixed(0.095);
            track.set_position(512-camera_x,512-camera_y);
            car_sprite.set_position(car.x-camera_x,car.y-camera_y);
            int direction=((car.heading*64/360).integer()+64)%64;
            car_sprite.set_tiles(bn::sprite_items::car.tiles_item(),direction);
            minimap_dot.set_position(72+car.x*42/1024,18+car.y*42/1024);
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
            if(redraw) {
                hud_text.clear();
                bn::string<64> line="";
                line+=driving::setups[setup].name;
                line+="  "; line+=bn::to_string<4>((car.speed*42).integer());
                line+=" KPH  "; line+=car.surface==2?"DIRT":car.surface==0?"GRASS":"ROAD";
                text.generate(-114,-73,line,hud_text);
                line="LAP "; line+=time_string(lap_frames); line+="  BEST ";
                line+=best[setup]?time_string(best[setup]):bn::string<16>("--.--");
                text.generate(-114,-63,line,hud_text);
                if(notice_frames>0) line=laps?"LAP COMPLETE! KEEP GOING":"A GAS  B BRAKE  START HELP";
                else {
                    line="GATES "; line+=bn::to_string<3>(checkpoint); line+="/9  L/R SETUP  SELECT RESET";
                }
                // Compact font uses six-pixel spacing for a 39-character line.
                text.generate(-114,73,line,hud_text);
            }
        } else {
            for(auto& mark:marks) mark.sprite.set_visible(false);
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
        bn::core::update();
        missed+=bn::core::last_missed_frames();
    }
}
