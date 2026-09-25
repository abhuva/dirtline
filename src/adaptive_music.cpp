#include "adaptive_music.h"
#include "bn_music.h"
#include "bn_music_items.h"

namespace {
constexpr bn::fixed normal_volume(0.34);
constexpr bn::fixed ducked_volume(0.20);
constexpr int downgrade_delay = 180;

int rank(adaptive_music::section value) {
    return int(value);
}
}

void adaptive_music::start() {
    bn::music_items::dustline_drive.play(0, true);
    _active=section::cruise;
    _target=section::cruise;
    _last_position=0;
    _downgrade_frames=0;
    _playing=true;
    _ducked=false;
    _apply_volume();
}

void adaptive_music::stop() {
    if(_playing && bn::music::playing())bn::music::stop();
    _playing=false;
    _last_position=-1;
    _downgrade_frames=0;
}

void adaptive_music::update(section desired) {
    if(! _playing)return;

    if(rank(desired)>rank(_target)) {
        // Escalation is armed immediately, then lands on the next boundary.
        _target=desired;
        _downgrade_frames=0;
    } else if(rank(desired)<rank(_target)) {
        // Keep intense music from fluttering when an enemy or speed threshold
        // is crossed repeatedly over a few frames.
        if(++_downgrade_frames>=downgrade_delay) {
            _target=desired;
            _downgrade_frames=0;
        }
    } else {
        _downgrade_frames=0;
    }

    int current=bn::music::position();
    if(current!=_last_position && _target!=_active) {
        const int destination=adaptive_music_data::section_positions[rank(_target)];
        bn::music::set_position(destination);
        current=destination;
        _active=_target;
    }
    _last_position=current;
}

void adaptive_music::set_ducked(bool ducked) {
    if(_playing && ducked!=_ducked) {
        _ducked=ducked;
        _apply_volume();
    }
}

void adaptive_music::set_user_volume(bn::fixed volume) {
    _user_volume=volume;
    _apply_volume();
}

void adaptive_music::set_muted(bool muted) {
    _muted=muted;
    _apply_volume();
}

void adaptive_music::_apply_volume() {
    if(_playing && bn::music::playing()) {
        const bn::fixed mix_volume=_ducked?ducked_volume:normal_volume;
        bn::music::set_volume(_muted?bn::fixed(0):mix_volume*_user_volume);
    }
}

int adaptive_music::position() const {
    return _playing && bn::music::playing()?bn::music::position():-1;
}
