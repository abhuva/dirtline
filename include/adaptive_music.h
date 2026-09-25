#pragma once
#include "bn_fixed.h"
#include "generated/music_data.h"

// Quantized dynamic-music controller. Section changes are requested every
// frame, but committed only when the module crosses a two-bar boundary.
class adaptive_music {
public:
    using section = adaptive_music_data::section;

    void start();
    void stop();
    void update(section desired);
    void set_ducked(bool ducked);
    void set_user_volume(bn::fixed volume);
    void set_muted(bool muted);

    bool playing() const { return _playing; }
    section active_section() const { return _active; }
    section target_section() const { return _target; }
    int position() const;
    int downgrade_frames() const { return _downgrade_frames; }

private:
    void _apply_volume();

    section _active = section::cruise;
    section _target = section::cruise;
    int _last_position = -1;
    int _downgrade_frames = 0;
    bn::fixed _user_volume = 1;
    bool _playing = false;
    bool _ducked = false;
    bool _muted = false;
};
