# Build with Retro68's PowerPC toolchain:
#   cmake -S . -B build -DCMAKE_TOOLCHAIN_FILE=$RETRO68/powerpc-apple-macos/cmake/retroppc.toolchain.cmake
#   cmake --build build
# yields build/PPC603Test.bin (MacBinary, for hcopy -m) and PPC603Test.dsk.
cmake_minimum_required(VERSION 3.9)
project(PPC603Test C CXX)

add_application(PPC603Test main.c CONSOLE)
set_target_properties(PPC603Test PROPERTIES COMPILE_OPTIONS "-O2;-Wall;-ffunction-sections")
set_target_properties(PPC603Test PROPERTIES LINK_FLAGS "-Wl,-gc-sections")
