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
gamepad).

## ROMs, RAM, sound, saves (2026-10-22 afternoon, v0.1.0 and builds 32-33)

| What | Result |
|---|---|
| Kinka 1.0, 1.2, 1.3, GM flash (OSD Load ROM) | each boots Macintosh on Pippin to the Finder (5 MB) |
| 13 MB | Macintosh on Pippin to the Finder (v0.1.0) |
| 21 MB | Macintosh on Pippin to the Finder, Super Marathon to its launcher (build 32) |
| The boot chime | plays on HDMI: `misterkvms-cli record 25s F.wav` around a reset, ~2 s of decaying tone (`scratch/boot_chime_v0.1.0_20261022.wav`) |
| CD audio (Racing Days) | **plays since build 36 (9023a51) with the Main's bae97b3**: the menu music on HDMI (`scratch/racingdays_cd_audio_20261022.wav`). Before, Mac OS's CD driver read block 0 70 ms after the game's PLAY AUDIO MSF, and that data read stopped the audio (in the core's SCSI target and in the Main's playhead); now a read leaves it playing on the Pippin |
| Saving to the flash | **works since 38ac0a1 + 53670e3 (build 34)**: a folder made on Flash!, Shut Down (the Menu key, Return), the image on slot 2 written (the volume's signature "NuMc" at 130C); the core reloaded, the folder is there. Before: the flash answered FF during its erase, the driver's program was lost, and it gave up |

The size Mac OS sees (the bench, Super Marathon's boot, low memory's MemTop at 108; the KVM
cannot open the Apple menu): 5 MB 004EC000 = 5,040K and 13 MB 00CEA000 = 13,224K, both
exactly what Kickstart reports on a real Pippin without a card and with an 8 MB card
(`docs/web-links.md`); 21 MB 014D8000 = 21,344K (no Kickstart figure for a 16 MB card;
About This Mac shows 21,504K Total Memory there, which counts differently).

Build 35 (f945a58, the release flags, slack +0.205): the four titles boot, the chime plays,
and the saved Flash! folder comes back after a core reload. The Flash! volume lives in VRAM between boots of one session (Mac OS's
driver), so before 53670e3 a volume survived core reloads without ever being saved; the
VRAM is now cleared when the core loads. To keep a save: Special > Shut Down (or the PC
keyboard's Menu key, the ADB power key), then the image on the OSD's Advanced > Save flash
slot is written 2 s later.

Before build 29 every title stalled ~16 s into the boot (the floppy
driver's Time Manager task, `docs/prompts/RESUME_pippin_board.md`): on this
board a DQM-masked halfword of an uncached SDRAM word write was written as
zeros; `Pippin_sdram` now writes partial words by read-modify-write.
