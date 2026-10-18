# Day 1 with the Performa 62xx — checklist

Prepared 2026-10-16 for the first session with the machine. Everything
below is in `cputest/`; nothing has run on a real 603 yet, so expect to
tweak as we go. Keep the terminal on this machine open: rebuilding any
disk image takes seconds.

## Bring

- The Performa, keyboard, mouse, monitor. Note the model number and CPU
  speed (75 MHz = 603; 100/120 MHz = 603e).
- BlueSCSI v2 (DB-25 for the external port, or internal 50-pin), its SD
  card, and a USB cable to power it if the port's termination power is
  weak.
- The SD card with the three images below copied to its root.
- A camera/phone for the screen.

## Images on the SD card (built here)

| File on SD | What | Built by |
|---|---|---|
| `HD4.hda` | 64 MB disk the Mac mounts at boot (Apple partition map + Apple_Driver43 from the 040 bench disks + HFS). Holds `PPC603Test` and `ppc603.vec`. Results land on it. | `python3 ppc603test.py image --out HD4.hda` |
| `HD5_probe.hda` | 32 MB **bootable** probe disk: its boot blocks run the supervisor-mode question (see below) and write a 512-byte record to `/Results`. | `python3 probe/build_probe.py build` |
| (optional) `HD6_blank.hda` | a copy of `HD4.hda` with nothing on it, in case the Mac wants to initialise a disk itself | `cp` |

BlueSCSI naming: `HD<scsi-id>.hda`; keep IDs clear of the internal
drive (0) and CD (3). `bluescsi.ini` is not needed for these.

## Session plan

1. **Boot the Mac normally** (internal disk) with the BlueSCSI attached
   carrying only `HD4.hda`. The `PPC603Test` volume should appear on the
   desktop. If it does not: check termination power (USB-power the
   BlueSCSI), SCSI ID, cable; then try the BlueSCSI's log file on the SD
   card. If the Mac offers to initialise the disk, say **no** (it would
   erase the files); report back and we rebuild.
2. **Write down** Apple menu → About This Macintosh (system version,
   RAM) and the Gestalt line `PPC603Test` prints.
3. **Run `PPC603Test`** (double-click). One dot per 64 vectors, about
   1,245 dots; a 75 MHz 603 should finish in well under a minute. It ends
   with `n=00013708 sum=… miss=… ticks=… write=ok` and says where
   `ppc603.res` went (beside the app, or on the startup disk's desktop
   if the volume was locked). Photograph the summary line.
   - If it stops dead or the Mac bombs: note the dot count (vector
     number ≈ dots × 64) and the bomb ID. We can rebuild the vector file
     without the offending source in a minute (`vectors.py` sources are
     selectable).
   - If it complains it cannot find `ppc603.vec`: the app's folder is not
     the default directory; move both files to the top level of the
     volume and run again.
4. **Shut down cleanly**, pull the SD card, and on this machine:
   ```bash
   hmount HD4.hda 1 && hcopy -r :ppc603.res . && humount
   python3 ppc603test.py decode ppc603.res --machine 6200
   ```
   (if the file went to the desktop of the internal disk, copy it onto
   the `PPC603Test` volume in the Finder first, or onto a floppy.)
   Look at the `differ` column against the 604 run: `fres`/`frsqrte`,
   denormals and undefined divides are the expected 603-vs-604
   differences; anything else is news.
5. **The supervisor-mode question.** Put `HD5_probe.hda` on the SD card
   as well (a second BlueSCSI ID). Make it the startup disk: Startup Disk
   control panel, or hold Cmd-Opt-Shift-Delete at the chime to skip the
   internal drive. The screen will stay at the happy Mac or go blank; the
   probe writes to `/Results` within a second. Wait 10 s, power off, pull
   the SD card:
   ```bash
   python3 probe/build_probe.py read HD5_probe.hda
   ```
   - `PRB1 CAL1 MSR=… PVR=… DONE` with PR=0: code reached from the boot
     blocks runs in **supervisor mode**. Then the whole `super603` blob
     can be loaded from boot blocks the same way (that is the next thing
     to build; most of it exists).
   - `PRB1 CAL1` only: the PowerPC `mfmsr` trapped; emulated code is in
     user mode and we take the MkLinux-Booter route for the supervisor
     tier.
   - Nothing written: the Mac did not boot from the probe disk (check it
     was the startup disk; a `CAL1`-less record means the driver `_Write`
     failed).
   The probe does not touch the internal disk; after it the Mac must be
   restarted from the internal disk (reset, or power-cycle).
6. If time allows, run `PPC603Test` a second time and confirm the two
   result files are identical (`ppc603test.py diff` on the two CSVs):
   that is the "recorded twice, bit-identically" standard the 604 data
   met.

## Fallbacks

- The Mac mounts nothing from the BlueSCSI: initialise `HD6_blank.hda`
  on the Mac with Drive Setup / HD SC Setup (BlueSCSI's Apple vendor
  quirk may be needed), copy the image back, and put the files onto it
  here with `hmount HD6_blank.hda 1; hcopy …`.
- No writable path at all: `PPC603Test` falls back to the desktop of
  the startup disk; a floppy or a second session gets it off.
- The application will not launch ("not enough memory", a bomb at
  start): it is a Retro68 CFM application; needs System 7.1.2 or later
  on a PowerPC. Note the error exactly.

## What we want to leave with

- `ppc603.res` from a complete run (ideally two).
- The probe record.
- Photos of the Gestalt line, About This Macintosh, and any error.
- The machine's exact model, CPU, RAM, System version, and whether the
  BlueSCSI needed USB power.
