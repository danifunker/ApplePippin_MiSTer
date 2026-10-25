# Releases

## 20261024: the CPU at 66.67 MHz; saves, disc changes, PPP, PAL, hard disk

`BandaiPippin_20261024.rbf` (115d132; **CPU 66.67 MHz, the console's own clock**; the debug
instruments off). Timing: the SDRAM clock and hold are met; the CPU's internal paths miss
setup by 0.84 ns at the analyser's slow 100 °C corner (Fmax 63.1 MHz there), so the core
relies on the board's real margin. It is untested on a board at this clock: if it misbehaves
when warm (a black boot, a crash), use the 20261022 build or ask for a 58.3 MHz build. The
CPU's slow paths were shortened all day (DSPPC603 changes 2-17, each checked against the
instruction-level benches and a 420 M-instruction lockstep boot of Super Marathon against
dingusppc; `docs/prompts/RESUME_pippin_cpu66.md` has the account). Needs a Main_MiSTer
with the Pippin's CD support (the `pippin-cdrom` branch of danifunker/Main_MiSTer until it is
merged), `games/Pippin/boot.rom` (Kinka 1.3 recommended) and discs as `.chd` or `.cue/.bin`.
Setup and use: the repository's `README.md`.

New since the 20261022 release, each checked on the board (MiSTer 192.168.99.92):

- **Saves**: the Flash! volume and Mac OS's settings are kept in a 136 KB image (OSD Save
  file). Saves to SD: Immediately (the default) writes every change Mac OS
  makes to the volume through to the image a second later, so no Shut Down is needed; At
  Shut Down keeps the console's behaviour. (the 20261022 build's flash never accepted a save: its erase
  answered too early.)
- **Changing discs**: Eject disc (the OSD's top level) presses the console's eject button (Mac OS
  ejects, the Pippin restarts into its insert-disc animation, the tray stays open); choosing
  a disc in Game disc inserts it and closes the tray; Insert disc puts the last disc
  back (Advanced).
- **CD audio** plays (Racing Days's music), also while the title reads the disc.
- **Second controller**: Input > Player 2 Controller, from the MiSTer's second gamepad.
- **Video**: Interlace: Progressive (the default) shows NTSC and PAL without field flicker;
  PAL shows the 640x480 picture centred with borders (it showed a broken 776-dot line).
- **PPP** over the modem port to the MiSTer (the disc's @WORLD Dialer and @World Browser),
  with `syn/fakemodem.py` on the MiSTer standing in for the modem.
- **Hard disk**: Hard disk (SCSI ID 0) on the OSD's first page, a data disk beside the CD
  (this build has it on the first page; the morning's build 50 still had it under Advanced).
- **Memory**: 13 and 21 MB (64 MB SDRAM boards or larger) as well as 5 MB.
- **ROMs**: Kinka 1.0, 1.2, 1.3 and the GM flash all boot.
- Inside: partial SDRAM writes masked on A12-A11 as the MiSTer boards wire DQM (no more
  read-modify-write), MacPPC7300's serial DMA fixes, Cuda's clock flagged as set.

Known limits: the CPU's clock is the console's but its timing is not fully met (above); a
second Eject during the insert-disc animation is not seen (use Insert disc); titles have been
booted to their menus but not played through.

## 20261022 (tagged v0.1.0) — the first titles boot

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
