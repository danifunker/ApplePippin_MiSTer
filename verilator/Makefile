# Verilator builds of the CPU test benches (run under Linux), for either CPU
# model: CPU=603 (rtl/DSPPC603, the Pippin's) or CPU=604 (rtl/DSPPC604, as
# imported from MacPPC7300).
#
#   make [CPU=603]  build $(BUILD)/vector_tb   single-instruction golden vectors
#   make core       build $(BUILD)/core/core_tb   programs on the pipeline
#   make cdc        build $(BUILD)/cdc/cdc_tb   the memory port across two clocks
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

HERE := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
CPU_NAME := DSPPC$(CPU)
RTL  := $(HERE)../rtl/$(CPU_NAME)

# the CPU's file list lives in its .qip, shared with Quartus
RTL_SRCS := $(addprefix $(RTL)/,$(shell grep -o '[A-Za-z0-9_]*\.sv' $(RTL)/$(CPU_NAME).qip))

# The RTL is kept clean under -Wall. Unused-signal warnings are off because a
# unit legitimately ignores most of the decode bundle it is handed.
# SYMRSVDWORD: Verilator 5.028 (this machine's) flags the top's `logic set`,
# which 5.020 accepted (IBMRS6K7248 suppressed it the same way).
WARN := -Wall -Wno-DECLFILENAME -Wno-UNUSEDSIGNAL -Wno-UNUSEDPARAM -Wno-SYMRSVDWORD

VFLAGS := --cc --exe --build -j 0 $(WARN)

ifneq ($(REF_LIB),)
REF_CFLAGS  := -DWITH_REF -I$(HERE)ref
REF_LDFLAGS := -LDFLAGS "$(REF_LIB)"
CORE_DIR    := $(BUILD)/core_ref
else
CORE_DIR    := $(BUILD)/core
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
		-CFLAGS "-O2 -std=c++17 $(REF_CFLAGS)" $(REF_LDFLAGS) \
		$(RTL_SRCS) $(CORE_DIR)/core_main.cpp \
		> $(CORE_DIR)/build.log 2>&1 || (cat $(CORE_DIR)/build.log; false)
	@grep -E '^%Warning' $(CORE_DIR)/build.log || true

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

clean:
	rm -rf $(BUILD)

.PHONY: all core cdc lint clean
