#pragma once
namespace blueprints {
inline constexpr int count=3;
struct definition { const char* name; int credits,scrap; };
inline constexpr definition catalog[count]={
    {"SALVAGE MAGNET",100,6},
    {"TUNED INJECTOR",260,14},
    {"REINFORCED PLATING",360,20}
};
}
