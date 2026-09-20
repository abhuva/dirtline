// Minimal headless mGBA adapter. Tests send ordinary joypad input and only read
// game memory; no state injection or modifications to the ROM under test.
#include <mgba/core/core.h>
#include <mgba/core/log.h>
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>

static struct mCore* core;
static color_t pixels[240*160];
static void test_log(struct mLogger* logger, int category, enum mLogLevel level,
                     const char* format, va_list args) {
    (void)logger; (void)category;
    if(level & (mLOG_FATAL | mLOG_ERROR)) { vfprintf(stderr,format,args); fputc('\n',stderr); }
}
static struct mLogger logger={.log=test_log,.filter=NULL};

int emulator_open(const char* path) {
    mLogSetDefaultLogger(&logger);
    core=mCoreFind(path);
    if(!core || !core->init(core)) return 0;
    mCoreInitConfig(core,"dustline-tests");
    core->setVideoBuffer(core,pixels,240);
    core->setAudioBufferSize(core,1024);
    if(!mCoreLoadFile(core,path)) return 0;
    core->reset(core);
    return 1;
}
void emulator_step(int keys,int frames) {
    core->setKeys(core,keys);
    for(int i=0;i<frames;++i) core->runFrame(core);
}
uint32_t emulator_read(uint32_t address) { return core->busRead32(core,address); }
void* emulator_pixels(void) { return pixels; }
int emulator_pixel_size(void) { return sizeof(color_t); }
void emulator_close(void) {
    if(core) { mCoreConfigDeinit(&core->config); core->deinit(core); core=NULL; }
}
