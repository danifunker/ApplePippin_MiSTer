# Releases

## BandaiPippin_20261022 (v0.1.0) — the first titles boot

The first release of the Bandai Pippin core for MiSTer: `BandaiPippin_20261022.rbf`
(CPU_MHZ 58, TRACE 0, PERF 0: no debug instruments).

Needs, in `games/Pippin/`: `boot.rom` (Kinka 1.3; 1.0 and the Dev ROM boot to
the insert-disc screen too, see `docs/rom-map.md`), and discs as `.cue/.bin`
or `.chd` (mounted from the OSD's first item; reload the core so the ROM
boots the disc).

What works on the board (`docs/compatibility.md`): Super Marathon, Racing
Days, Power Rangers Zeo and "Macintosh on Pippin" boot to their first
interactive screen; the keyboard and the mouse reach Mac OS. The AppleJack
(OSD Input > Controller) maps the MiSTer gamepad; sound goes out on HDMI
(AWACS and CD audio mixed), with the MT32-pi option as in MacPPC7300.

Known limits: not yet played through (the AppleJack in a game, CD audio,
the flash save); Athens never receives Mac OS's video clock (the picture
is kept right by `STD_DOT`); 5 MB of RAM (the OSD's larger sizes are
MacPPC7300's and untested on the Pippin's map); the CPU at 58 MHz (70 MHz
fails timing by ~2 ns).

The stall every title had at ~16 s before this release is fixed in the
SDRAM controller: on the test board a DQM-masked halfword of an uncached
word write was written as zeros, which zeroed the floppy driver's Time
Manager task; partial words are now written by read-modify-write
(`Pippin_sdram`, `RMW = 1`). The whole hunt is in
`docs/prompts/RESUME_pippin_board.md` and `LOG_pippin_board_20261021.md`.
