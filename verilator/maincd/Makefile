# The Main's Mac CD layer on the host (maincd_host.cpp): Main_MiSTer's own
# support/mac/mac_cdrom*.cpp, support/chd/mister_chd.cpp and its libraries
# (libchdr, lzma, zstd, miniz), from the MAIN_MISTER checkout, as a library for
# the machine bench, and cdcheck (README in maincd_host.cpp and cdcheck.cpp).
#
#   make -C verilator/maincd            libmaincd.a and cdcheck in BUILD
#   $(BUILD)/cdcheck IMAGE [IMAGE_B]

MAIN_MISTER ?= $(HOME)/repos/Main_MiSTer-pippin
BUILD       ?= $(HOME)/.cache/applepippin/maincd
M := $(MAIN_MISTER)

INC  := -I$(M) -I$(M)/lib/libchdr/include -I$(M)/lib/lzma -I$(M)/lib/zstd/lib -I$(M)/lib/miniz
DEFS := -D_7ZIP_ST -DPACKAGE_VERSION=\"1.3.3\" -DHAVE_LROUND -DHAVE_STDINT_H -DHAVE_STDLIB_H \
        -DHAVE_SYS_PARAM_H -DENABLE_64_BIT_WORDS=0 -D_FILE_OFFSET_BITS=64 -D_LARGEFILE64_SOURCE \
        -DZSTD_DISABLE_ASM
ifeq ($(shell uname -s),Darwin)
# macOS: off_t is 64 bits and there are no *64 calls (miniz takes fopen64 when
# _LARGEFILE64_SOURCE is set); unistd.h's int reboot(int) clashes with fpga_io.h's
# (darwin_compat.h)
DEFS := $(filter-out -D_LARGEFILE64_SOURCE,$(DEFS)) -D__off64_t=off_t -include $(CURDIR)/darwin_compat.h
endif
CFLAGS   := -O2 -w -Wno-error=incompatible-pointer-types $(INC) $(DEFS)   # (libchdr: uInt for size_t, the same on the board's 32-bit ARM)
CXXFLAGS := -O2 -w -std=gnu++17 $(INC) $(DEFS)

C_SRC := $(wildcard $(M)/lib/libchdr/*.c) $(wildcard $(M)/lib/lzma/*.c) \
         $(wildcard $(M)/lib/zstd/lib/common/*.c) $(wildcard $(M)/lib/zstd/lib/decompress/*.c) \
         $(M)/lib/miniz/miniz.c
CPP_SRC := $(M)/support/mac/mac_cdrom.cpp $(M)/support/mac/mac_cdrom_resp.cpp \
           $(M)/support/mac/mac_cdrom_play.cpp $(M)/support/chd/mister_chd.cpp
OBJ := $(patsubst $(M)/%.c,$(BUILD)/main/%.o,$(C_SRC)) $(patsubst $(M)/%.cpp,$(BUILD)/main/%.o,$(CPP_SRC)) \
       $(BUILD)/maincd_host.o

all: $(BUILD)/libmaincd.a $(BUILD)/cdcheck

$(BUILD)/main/%.o: $(M)/%.c
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/main/%.o: $(M)/%.cpp
	@mkdir -p $(dir $@)
	$(CXX) $(CXXFLAGS) -c $< -o $@

$(BUILD)/maincd_host.o: maincd_host.cpp
	@mkdir -p $(dir $@)
	$(CXX) $(CXXFLAGS) -c $< -o $@

$(BUILD)/libmaincd.a: $(OBJ)
	rm -f $@
	ar rcs $@ $^

$(BUILD)/cdcheck: cdcheck.cpp $(BUILD)/libmaincd.a
	$(CXX) $(CXXFLAGS) $< $(BUILD)/libmaincd.a -o $@

.PHONY: all
