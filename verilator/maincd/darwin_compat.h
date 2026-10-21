// macOS only (maincd/Makefile includes it first): unistd.h's int reboot(int)
// comes in now, so the rename below applies only to fpga_io.h's void reboot(int)
#pragma once
#include <unistd.h>
#define reboot mister_reboot
