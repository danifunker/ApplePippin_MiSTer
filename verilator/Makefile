# Verilator builds of the CPU test benches (run under Linux), for either CPU
# model: CPU=603 (rtl/DSPPC603, the Pippin's) or CPU=604 (rtl/DSPPC604, as
# imported from MacPPC7300).
#
#   make [CPU=603]  build $(BUILD)/vector_tb   single-instruction golden vectors
#   make core       build $(BUILD)/core/core_tb   programs on the pipeline
#   make flash      build $(BUILD)/flash/flash_tb   the save flash against the Am29F010's commands
#   make cdc        build $(BUILD)/cdc/cdc_tb   the memory port across two clocks
#   make machine    build $(BUILD)/machine/machine_tb   the whole Pippin (Pippin_system, always
#                   DSPPC603) running a ROM
#   make lint       Verilator lint only
#   make clean
#
# The benches name the 604's modules; for another model their sources are
# copied into the build directory with the names changed. Give each model its
# own BUILD (run.py and run_core.py do).
#
# REF_LIB=<path to libdingusref.a> links the dingusppc reference into core_tb
# for lockstep runs. Normally driven by run.py and run_core.py.

VERILATOR ?= verilator
BUILD     ?= build
REF_LIB   ?=
CPU       ?= 604
# the Main's Mac CD layer, for the machine bench's CD (cdhost.h): Main_MiSTer's own
# mac_cdrom*.cpp, its CHD reader and libraries, built by maincd/Makefile
MAIN_MISTER ?= $(HOME)/repos/Main_MiSTer-pippin
MAINCD_DIR  ?= $(HOME)/.cache/applepippin/maincd
MAINCD_LIB  := $(MAINCD_DIR)/libmaincd.a
# extra Pippin_system parameters for the machine bench (e.g. -GSOUND_IN_DMA=0, as the board's top)
MACH_GFLAGS ?=

HERE := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
CPU_NAME := DSPPC$(CPU)
RTL  := $(HERE)../rtl/$(CPU_NAME)

# the CPU's file list lives in its .qip, shared with Quartus
RTL_SRCS := $(addprefix $(RTL)/,$(shell grep -o '[A-Za-z0-9_]*\.sv' $(RTL)/$(CPU_NAME).qip))

# the machine around it, likewise from its .qip
MACH      := $(HERE)../rtl/machine
MACH_SRCS := $(addprefix $(MACH)/,$(shell grep -o '[A-Za-z0-9_]*\.sv' $(MACH)/Pippin_machine.qip))
MACH_RTL  := $(HERE)../rtl/DSPPC603
MACH_CPU  := $(addprefix $(MACH_RTL)/,$(shell grep -o '[A-Za-z0-9_]*\.sv' $(MACH_RTL)/DSPPC603.qip))

# The RTL is kept clean under -Wall. Unused-signal warnings are off because a
# unit legitimately ignores most of the decode bundle it is handed.
# SYMRSVDWORD: Verilator 5.028 (this machine's) flags the top's `logic set`,
# which 5.020 accepted (IBMRS6K7248 suppressed it the same way).
WARN := -Wall -Wno-DECLFILENAME -Wno-UNUSEDSIGNAL -Wno-UNUSEDPARAM -Wno-SYMRSVDWORD
# Verilators that know PROCASSINIT (5.052 on the Mac; not 5.028) also call the RTL's
# power-up idiom, an initial value and then an always_ff, MULTIDRIVEN: both off there
WARN += $(if $(findstring Unknown warning,$(shell $(VERILATOR) -Wno-PROCASSINIT --lint-only 2>&1)),,-Wno-PROCASSINIT -Wno-MULTIDRIVEN)

# Parallel C++ compiles: each of the machine's takes about 2 GB, and this
# machine has 14 GB shared with Quartus (-j 0, all cores, ran it out of
# memory on 2026-10-18).
VJOBS  ?= 3
VFLAGS := --cc --exe --build -j $(VJOBS) $(WARN)

ifneq ($(REF_LIB),)
REF_CFLAGS  := -DWITH_REF -I$(HERE)ref
REF_LDFLAGS := -LDFLAGS "$(REF_LIB)"
CORE_DIR    := $(BUILD)/core_ref
MACH_DIR    := $(BUILD)/machine_ref
else
CORE_DIR    := $(BUILD)/core
MACH_DIR    := $(BUILD)/machine
endif

all: $(BUILD)/vector_tb

$(BUILD)/vector_tb: $(RTL_SRCS) $(HERE)vector_dut.sv $(HERE)sim_main.cpp $(RTL)/$(CPU_NAME).qip $(HERE)Makefile
	@mkdir -p $(BUILD)
	@sed 's/DSPPC604/$(CPU_NAME)/g' $(HERE)vector_dut.sv > $(BUILD)/vector_dut.sv
	@$(VERILATOR) $(VFLAGS) --top-module vector_dut -Mdir $(BUILD) -o vector_tb \
		-CFLAGS "-O2 -std=c++17" \
		$(RTL_SRCS) $(BUILD)/vector_dut.sv $(HERE)sim_main.cpp \
		> $(BUILD)/build.log 2>&1 || (cat $(BUILD)/build.log; false)
	@grep -E '^%Warning' $(BUILD)/build.log || true

core: $(CORE_DIR)/core_tb

$(CORE_DIR)/core_tb: $(RTL_SRCS) $(HERE)core_main.cpp $(RTL)/$(CPU_NAME).qip $(HERE)Makefile $(REF_LIB)
	@mkdir -p $(CORE_DIR)
	@sed 's/DSPPC604/$(CPU_NAME)/g' $(HERE)core_main.cpp > $(CORE_DIR)/core_main.cpp
	@$(VERILATOR) $(VFLAGS) --top-module $(CPU_NAME) -Mdir $(CORE_DIR) -o core_tb \
		-CFLAGS "-O2 -std=c++17 -DCPU_MODEL=$(CPU) $(REF_CFLAGS)" $(REF_LDFLAGS) \
		$(RTL_SRCS) $(CORE_DIR)/core_main.cpp \
		> $(CORE_DIR)/build.log 2>&1 || (cat $(CORE_DIR)/build.log; false)
	@grep -E '^%Warning' $(CORE_DIR)/build.log || true

machine: $(MACH_DIR)/machine_tb

$(MAINCD_LIB): FORCE
	@$(MAKE) -s -C $(HERE)maincd MAIN_MISTER=$(MAIN_MISTER) BUILD=$(MAINCD_DIR) $(MAINCD_LIB)

FORCE:

$(MACH_DIR)/machine_tb: $(MACH_CPU) $(MACH_SRCS) $(HERE)core_main.cpp $(HERE)cdhost.h $(MACH_RTL)/DSPPC603.qip $(MACH)/Pippin_machine.qip $(HERE)Makefile $(REF_LIB) $(MAINCD_LIB)
	@mkdir -p $(MACH_DIR)
	@sed 's/DSPPC604/DSPPC603/g' $(HERE)core_main.cpp > $(MACH_DIR)/core_main.cpp
	@$(VERILATOR) $(VFLAGS) --top-module Pippin_system -GCUDA_FAST_BOOT=1 $(MACH_GFLAGS) -Mdir $(MACH_DIR) -o machine_tb \
		-CFLAGS "-O2 -std=c++17 -DPIPPIN_MACHINE -DCPU_MODEL=603 -I$(HERE) -I$(MAIN_MISTER)/support/mac $(REF_CFLAGS)" $(REF_LDFLAGS) \
		-LDFLAGS "$(MAINCD_LIB)" $(MACH_CPU) $(MACH_SRCS) $(MACH_DIR)/core_main.cpp \
		> $(MACH_DIR)/build.log 2>&1 || (cat $(MACH_DIR)/build.log; false)
	@grep -E '^%Warning' $(MACH_DIR)/build.log || true

flash: $(BUILD)/flash/flash_tb

$(BUILD)/flash/flash_tb: $(MACH)/Pippin_flash.sv $(HERE)flash/flash_main.cpp $(HERE)Makefile
	@mkdir -p $(BUILD)/flash
	@$(VERILATOR) $(VFLAGS) --top-module Pippin_flash -Mdir $(BUILD)/flash -o flash_tb \
		-CFLAGS "-O2 -std=c++17" $(MACH)/Pippin_flash.sv $(HERE)flash/flash_main.cpp \
		> $(BUILD)/flash/build.log 2>&1 || (cat $(BUILD)/flash/build.log; false)

cdc: $(BUILD)/cdc/cdc_tb

$(BUILD)/cdc/cdc_tb: $(RTL)/$(CPU_NAME)_memcdc.sv $(HERE)cdc_main.cpp $(HERE)Makefile
	@mkdir -p $(BUILD)/cdc
	@sed 's/DSPPC604/$(CPU_NAME)/g' $(HERE)cdc_main.cpp > $(BUILD)/cdc/cdc_main.cpp
	@$(VERILATOR) $(VFLAGS) --top-module $(CPU_NAME)_memcdc -Mdir $(BUILD)/cdc -o cdc_tb \
		-CFLAGS "-O2 -std=c++17" \
		$(RTL)/$(CPU_NAME)_memcdc.sv $(BUILD)/cdc/cdc_main.cpp \
		> $(BUILD)/cdc/build.log 2>&1 || (cat $(BUILD)/cdc/build.log; false)
	@grep -E '^%Warning' $(BUILD)/cdc/build.log || true

lint:
	@mkdir -p $(BUILD)
	@sed 's/DSPPC604/$(CPU_NAME)/g' $(HERE)vector_dut.sv > $(BUILD)/vector_dut.sv
	$(VERILATOR) --lint-only $(WARN) --top-module vector_dut $(RTL_SRCS) $(BUILD)/vector_dut.sv
	$(VERILATOR) --lint-only $(WARN) --top-module $(CPU_NAME) $(RTL_SRCS)
	$(VERILATOR) --lint-only $(WARN) --top-module $(CPU_NAME)_memcdc $(RTL)/$(CPU_NAME)_memcdc.sv

lint-machine:
	$(VERILATOR) --lint-only $(WARN) --top-module Pippin_system $(MACH_CPU) $(MACH_SRCS)

clean:
	rm -rf $(BUILD)

.PHONY: all core machine flash cdc lint clean
