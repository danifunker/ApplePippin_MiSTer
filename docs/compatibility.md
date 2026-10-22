# Compatibility

Titles tried on the board (MiSTer, 192.168.99.92, Kinka 1.3 as `boot.rom`,
5 MB), each to its first interactive screen. Mounted from the OSD (the
first item; `.cue/.bin` and `.chd`), then the core reloaded so the ROM
boots the disc.

| Title | Image | Result | Date, core |
|---|---|---|---|
| Super Marathon (U) | cue/bin | Boots to the "Choose one: Marathon / Marathon 2" launcher at ~55 s | 2026-10-22, build 29 (bfcfb4f) |
| Racing Days (J) | chd | Boots to the car-select screen; the car rotates (the menu animates) | 2026-10-22, build 29 |
| Power Rangers Zeo vs. The Machine Empire (USA) | chd | Saban logo, then the main menu (Load Game / Go / Options) | 2026-10-22, build 29 |
| Macintosh on Pippin (USA) | chd | The Mac OS Finder desktop; the mouse moves the pointer and its button selects an icon, the keyboard selects icons by name (misterkvms-cli's keyboard and mouse through the MiSTer's input) | 2026-10-22, build 29 |

Not yet tried past the first screen: playing (the AppleJack through a
gamepad), sound (the HDMI capture used for these tests carries no audio;
the boot chime's DMA runs), CD audio (Racing Days), saving to the flash.

Before build 29 every title stalled ~16 s into the boot (the floppy
driver's Time Manager task, `docs/prompts/RESUME_pippin_board.md`): on this
board a DQM-masked halfword of an uncached SDRAM word write was written as
zeros; `Pippin_sdram` now writes partial words by read-modify-write.
