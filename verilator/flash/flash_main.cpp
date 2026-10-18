// Pippin_flash against the Am29F010's command sequences, through the CPU's view of it
// (a byte in the top lane of each word at 40000000 + 4 x flash address, bits reversed).
//   make -C verilator flash && ~/.cache/applepippin/verilator/flash/flash_tb
#include <verilated.h>
#include "VPippin_flash.h"
#include <cstdio>
#include <memory>

static VPippin_flash* d;
static void tick() { d->clk = 0; d->eval(); d->clk = 1; d->eval(); }
static uint8_t rev(uint8_t x) { uint8_t r = 0; for (int i = 0; i < 8; i++) if (x & (1 << i)) r |= 0x80 >> i; return r; }
static void wr(uint32_t fa, uint8_t v) {
	d->sel = 1; d->we = 1; d->addr = fa; d->be = 0xF; d->wdata = (uint32_t)rev(v) << 24; tick();
	d->sel = 0; d->we = 0; tick(); tick();
}
static uint8_t rd(uint32_t fa) {
	d->sel = 1; d->we = 0; d->addr = fa; tick(); d->sel = 0;
	uint8_t v = rev((uint8_t)(d->rdata >> 24)); tick(); return v;
}
static int fails = 0;
static void expect(const char* what, uint32_t fa, uint8_t want) {
	uint8_t got = rd(fa);
	if (got != want) { std::printf("FAIL %s: %05X reads %02X, want %02X\n", what, fa, got, want); fails++; }
}
static void unlock() { wr(0x5555, 0xAA); wr(0x2AAA, 0x55); }
static void program(uint32_t fa, uint8_t v) { unlock(); wr(0x5555, 0xA0); wr(fa, v); }
static void erase_wait() { for (int i = 0; i < 140000; i++) tick(); }

int main(int argc, char** argv) {
	Verilated::commandArgs(argc, argv);
	d = new VPippin_flash;
	d->reset = 1; tick(); tick(); d->reset = 0; tick();
	expect("erased at start", 0x00000, 0xFF);
	expect("erased at start", 0x1FFFF, 0xFF);
	program(0x00123, 0x5A);  expect("program", 0x00123, 0x5A);
	program(0x00123, 0xF0);  expect("program ANDs (1 to 0 only)", 0x00123, 0x50);
	wr(0x00124, 0x00);       expect("a write without the sequence changes nothing", 0x00124, 0xFF);
	unlock(); wr(0x5555, 0x90);
	expect("autoselect: manufacturer", 0x00000, 0x01);
	expect("autoselect: device", 0x00001, 0x20);
	wr(0x00000, 0xF0);       expect("reset back to the array", 0x00123, 0x50);
	program(0x04010, 0x11);  program(0x08010, 0x22);
	unlock(); wr(0x5555, 0x80); unlock(); wr(0x04000, 0x30); erase_wait();
	expect("sector erase: its sector", 0x04010, 0xFF);
	expect("sector erase: not the next", 0x08010, 0x22);
	expect("sector erase: not the first", 0x00123, 0x50);
	unlock(); wr(0x5555, 0x80); unlock(); wr(0x5555, 0x10); erase_wait();
	expect("chip erase", 0x00123, 0xFF);
	expect("chip erase", 0x08010, 0xFF);
	// the image port: load a byte, the CPU reads it
	d->ld_we = 1; d->ld_addr = 0x00200; d->ld_data = 0x3C; tick(); d->ld_we = 0; tick();
	expect("loaded through the image port", 0x00200, 0x3C);
	std::printf("%s (%d failures)\n", fails ? "RESULT: FAIL" : "RESULT: PASS", fails);
	delete d;
	return fails ? 1 : 0;
}
