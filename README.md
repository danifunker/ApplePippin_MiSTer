# Bandai Pippin for MiSTer

An FPGA core of the Apple/Bandai Pippin (@WORLD / Atmark) for the MiSTer: the PowerPC 603
(DSPPC603), Grand Central (VIA, Cuda, MESH SCSI, SWIM3, serial, DMA), Taos video, AWACS
sound, the save flash and the CD-ROM drive, enough to boot the Pippin ROMs and play titles
from CD images.

## Status (2026-10-23)

| | |
|---|---|
| Titles | Super Marathon, Racing Days, Power Rangers Zeo and Macintosh on Pippin boot to their menus or the Finder (`docs/compatibility.md`); playing through is not yet tested |
| ROMs | Kinka 1.0, 1.2, 1.3 and GM flash boot; Kinka 1.3 recommended |
| RAM | 5 MB (the retail Pippin), 13 MB and 21 MB (the 8 and 16 MB cards; 64 MB SDRAM board or larger) |
| CPU | 58.3 MHz (the real Pippin runs at 66 MHz; see Known limits) |
| Sound | AWACS and CD audio on HDMI; the boot chime and Racing Days's CD music play |
| Saves | the Flash! volume and Mac OS's settings, on the SD card |
| Internet | PPP over the modem port to the MiSTer (the @WORLD Dialer, @World Browser) |
| Controllers | AppleJack from the MiSTer's gamepad, a second AppleJack from the second gamepad; the keyboard and mouse as ADB devices |
| Discs | eject, insert and change discs from the OSD |

The last published build is v0.1.0 (`releases/`, 2026-10-22). Everything below (saves,
the second controller, progressive video, eject and insert) is in the current builds and
goes into the next release.

## What you need

- **The core**: `BandaiPippin_<date>.rbf` in `/media/fat/_Console/`.
- **A Main_MiSTer with the Pippin's CD support**: the stock Main turns on its Mac-family CD
  layer only for the Mac cores it knows; the Pippin's support (CHD and CUE/BIN, CD audio that
  keeps playing during data reads) is on the `pippin-cdrom` branch of
  [danifunker/Main_MiSTer](https://github.com/danifunker/Main_MiSTer) until it is merged
  upstream. Without it there is no CD drive.
- **A boot ROM**: `/media/fat/games/Pippin/boot.rom` (loaded when the core starts), or
  OSD > Load ROM. Not included except where noted in `releases/`.
- **Discs**: `.chd` or `.cue/.bin` images in `/media/fat/games/Pippin/`.
- **A save image** (optional, for saves): a 136 KB file, for example made on the MiSTer with
  `head -c 139264 /dev/zero | tr '\0' '\377' > "/media/fat/games/Pippin/Pippin flash.sav"`
  (an erased flash), selected once in OSD > Advanced > Save flash. A 128 KB image from v0.1.0
  still works and keeps the flash only.

## Using it

**Starting a title.** Choose the disc in the OSD's first item (Pri. CD-ROM). The Pippin
boots whatever is in the drive when it starts; with no disc it plays its insert-disc
animation and boots the disc as soon as one goes in.

**Changing discs**, as on the console:

1. OSD > Advanced > **Eject disc**. This presses the console's eject button: Mac OS ejects
   the disc and restarts the Pippin, which shows the insert-disc animation (the tray open,
   empty).
2. Choose the next disc in the OSD's first item. It goes into the tray, the tray closes, and
   the Pippin boots it.
   Or OSD > Advanced > **Insert disc** to put the same disc back.

Choosing a disc in the OSD while a title runs swaps the media under Mac OS without a restart;
eject first.

**Saving.** Pippin titles save to Flash!, a 128 KB volume in the console's flash memory. Mac
OS keeps the volume in video memory and, on real hardware, writes it to the flash only at Shut
Down or Restart. With OSD > Advanced > **Flash! saves: Instant** (the default) every change
Mac OS writes to the volume goes to the flash at once, and the save image on the SD card is
written a second later, so a save survives switching off the MiSTer, changing discs or
loading another core. Two things to know:

- A save reaches the card once Mac OS has written it to the volume. On the console a title's
  save has to be written out to survive the eject button (which restarts the Pippin without a
  shut down), so titles are expected to do that; it is not yet checked title by title.
  Changes made in the Finder can stay in Mac OS's memory until Special > Shut Down or
  Restart.
- **At Shut Down** gives the original behaviour: the flash is written only at Shut Down or
  Restart (the PC keyboard's Menu key is the Pippin's power button).

Mac OS's settings (the alert sound, the browser's and the dialer's preferences, ...) live in
the flash too, in its system area, so they are saved the same way. The image's last 8 KB keep
Grand Central's NVRAM, which the Pippin's Mac OS does not use.

**Controls.** OSD > Input > Controller: AppleJack (the default; the gamepad's buttons map to
the AppleJack's, see the core's button names) or MouseStick II, Firebird, GamePad, SideWinder.
AppleJack 2 adds a second AppleJack from the MiSTer's second gamepad. The keyboard and the
mouse are always there.

**Video.** OSD > Video: Video out NTSC (the default), VGA or PAL (the console's switch; reset
to apply). PAL shows Mac OS's 640x480 picture centred in the 50 Hz frame, with black borders,
as a PAL Pippin does. NTSC and PAL are interlaced: Interlace: Progressive (the default) shows every line
each frame without flicker, Original shows the fields as the console sends them.

**Internet (PPP).** The Pippin's modem port is the MiSTer's UART. The "Macintosh on Pippin"
disc has the @WORLD Dialer (a MacTCP PPP link that dials a modem), @World Browser and
Netscape. The MiSTer can stand in for the modem and the ISP: copy `syn/fakemodem.py` to the
MiSTer and run `python3 fakemodem.py 57600` there with the OSD's UART mode at None (it answers
the dialer's AT commands like a modem, then starts the MiSTer's pppd with its usual
`/media/fat/linux/ppp_options`). In @World Browser press Connect in the dialer: the Pippin
gets the address <MiSTer's network>.254. MacTCP still has the @WORLD service's DNS servers,
so open pages by IP address, or set a DNS server in the MacTCP control panel (More...).
Netscape needs more than 5 MB (choose 13 MB).

**Other OSD settings.** Memory (reset to apply), Audio (MT32-pi for MIDI on the modem port),
Advanced > Boot: ROM or the core's memory test. "Changes pending" shows settings that wait
for Apply and reset.

## Known limits

- **CPU speed**: 58.3 MHz against the Pippin's 66 MHz. The CPU's longest paths (DSPPC603's
  condition-register and TLB-valid logic) barely meet timing at 58.3 MHz; 66 MHz needs them
  shortened. Titles run, a little slower than on the console.
- **Video clock**: the core uses the standard dot clocks (NTSC 15.734 kHz, PAL 15.625 kHz,
  VGA 31.469 kHz lines) rather than the Athens clock chips' outputs, which Mac OS programs only
  in part; the rates are right on the board (NTSC and VGA 59.9 Hz, PAL 50 Hz).
- **Eject pressed twice**: pressing Eject again during the insert-disc animation should close
  the empty tray; the ROM does not see that press yet. Use Insert disc or choose a disc.
- **The 603's misaligned page-crossing exception** is not modelled on the main branch
  (`align603` has it; it slows the boot and no title needs it so far).
- Not yet: playing titles through, the compatibility sweep.

## Repository

| | |
|---|---|
| `BandaiPippin.sv`, `rtl/machine/` | the MiSTer top and the Pippin's chips (`Pippin_*.sv`) |
| `rtl/DSPPC603/` | the PowerPC 603 (`docs/DSPPC603_notes.md`) |
| `verilator/` | the benches: the CPU, the whole machine (`run_machine.py`), the flash, the SDRAM, the Main's CD layer |
| `syn/mister.py` | board tooling: copy the core, ROMs and discs, read the core's trace |
| `docs/` | the hardware reference library, the ROM map, compatibility, plans; `docs/prompts/RESUME_pippin_board.md` is the current development state |
| `releases/` | published builds and their notes |

Build with Quartus 17.0 (`BandaiPippin.qpf`); the switches at the top of `BandaiPippin.sv`
(`TRACE`, `PERF`, `CAPTURE`, ...) are debug instruments and are 0 in release builds.
