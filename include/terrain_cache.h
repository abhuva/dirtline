#pragma once
#include <cstdint>

// Content-addressed cache, independent of Butano so the actual eviction logic
// can be stress-tested on the host. Pin the complete next view before acquiring
// missing tiles; an evicted slot must never still be referenced by that view.
class terrain_cache {
public:
    static constexpr int max_slots=704;
    static constexpr int window_columns=31,window_rows=21;

    void reset(int capacity) {
        _capacity=capacity; _next=0; _used=0;
        for(auto& entry:_lookup) entry=-1;
        for(auto& entry:_source) entry=65535;
        begin_view();
    }
    void begin_view() {
        _pinned_count=0;
        for(auto& entry:_pinned) entry=false;
    }
    int find(uint16_t source) const {
        int bucket=hash(source);
        while(_lookup[bucket]>=0) {
            const int slot=_lookup[bucket];
            if(_source[slot]==source) return slot;
            bucket=(bucket+1)&mask;
        }
        return -1;
    }
    void pin(int slot) {
        if(!_pinned[slot]) { _pinned[slot]=true; ++_pinned_count; }
    }
    // Returns -1 on exhaustion, with no cache mutation. Caller handles errors.
    int acquire(uint16_t source,bool& upload) {
        upload=false;
        int slot=find(source);
        if(slot>=0) { pin(slot); return slot; }
        for(int count=0;count<_capacity;++count) {
            slot=_next;
            _next=(_next+1==_capacity)?0:_next+1;
            if(_pinned[slot]) continue;
            if(_source[slot]!=65535) erase(_source[slot]);
            else ++_used;
            _source[slot]=source;
            int bucket=hash(source);
            while(_lookup[bucket]>=0) bucket=(bucket+1)&mask;
            _lookup[bucket]=int16_t(slot);
            pin(slot); upload=true;
            return slot;
        }
        return -1;
    }
    uint16_t source(int slot) const { return _source[slot]; }
    int pinned_count() const { return _pinned_count; }
    int used_count() const { return _used; }
private:
    static constexpr int mask=2047;
    int16_t _lookup[mask+1];
    uint16_t _source[max_slots];
    bool _pinned[max_slots];
    int _capacity=0,_next=0,_used=0,_pinned_count=0;
    static int hash(uint16_t source) { return (unsigned(source)*40503)&mask; }
    void erase(uint16_t source) {
        int hole=hash(source);
        while(_source[_lookup[hole]]!=source) hole=(hole+1)&mask;
        // Back-shift deletion avoids tombstones accumulating on long drives.
        for(int next=(hole+1)&mask;_lookup[next]>=0;next=(next+1)&mask) {
            int home=hash(_source[_lookup[next]]);
            if(((next-home)&mask)>=((next-hole)&mask)) {
                _lookup[hole]=_lookup[next]; hole=next;
            }
        }
        _lookup[hole]=-1;
    }
};
