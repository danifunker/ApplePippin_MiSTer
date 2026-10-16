# Apple Pippin reference library

Research material collected 2026-10-16 for building a MiSTer core for the Apple/Bandai Pippin (@WORLD / Atmark).

Downloaded third-party material (PDFs, emulator and MiSTer source excerpts, archived articles; about 290 MB) lives in **`../scratch/`**, which is git-ignored. Paths in the table below are relative to `scratch/`. Re-download it with the sources listed in [pdf-index.md](pdf-index.md) and [core-dev/README.md](core-dev/README.md).

## Start here

1. **[core-dev/README.md](core-dev/README.md)**: the hardware as MAME and DingusPPC model it, with the memory map, chips, interrupts and clocks cited `file:line`. It also covers the MiSTer framework, prior art, feasibility and risks, and open questions.
2. **[pdf-index.md](pdf-index.md)**: a catalogue of the 44 PDFs, plus a list of documents known to exist but not yet found.
3. **[`../../MacPPC7300_MiSTer`](../../MacPPC7300_MiSTer)**: the sibling Power Mac 7300 core. It already has a working 32-bit PowerPC CPU and most of the Pippin's I/O chips (Grand Central, MESH, Cuda, AWACS, DBDMA, the serial chip, SWIM3). Its README names the Pippin as the long-term goal.
4. **[implementation_plan.md](implementation_plan.md)**: the phased plan for building the core.
5. **[prompts/DSPPC603_tlb_reload.md](prompts/DSPPC603_tlb_reload.md)**: a resume prompt for implementing the real 603 TLB reload and checking it against a real 603 machine.
6. **[rom-map.md](rom-map.md)**: byte-accurate map of the Kinka 1.0 and Dev boot ROMs (regions, landmarks, 1.0-vs-Dev differences, MMIO the startup code touches), with full disassembly in `../disasm/disasm.tar.xz` (unpack with `python3 tools/rom/pack.py unpack`) produced by `../tools/rom/`.

## Layout

| Folder (under `scratch/`) | What's in it |
|---|---|
| `core-dev/reference-src/` | Pinned excerpts of MAME (`pippin.cpp` and its devices), DingusPPC (Pippin machine, PPC interpreter, docs), Main_MiSTer CD code, and Template_MiSTer. Commit hashes and licenses are in core-dev/README.md |
| `core-dev/mister/` | MiSTer developer wiki pages as Markdown, and the CD-core `hps_ext.v` bridges |
| `pdfs/apple/` | Apple Pippin Technical Notes (Dec 1996 Developer CD), Tech Info Library specs, the "66 Most Asked Questions" |
| `pdfs/bandai/` | @WORLD / Atmark user manual and setup guide |
| `pdfs/related_macs/` | Developer Notes for the 7200, 7500/8500, 9500 and 6100; Apple's internal spec for the 7500/8500 ("TNT", with Bandit, Grand Central and DBDMA registers); PCI card and driver design guide |
| `pdfs/chips/` | MPC603e user's manual, PowerPC programming and 60x bus manuals, 68HC05E1, 53C94, Z8530, Bt856, Am29F010, and Crystal CS4215/16 as stand-ins for the CS4217 |
| `pdfs/cdrom/` | Apple CD-ROM Handbook (Apple's SCSI CD command set), Panasonic CR-501 spec |
| `pdfs/components/` | PSU capacitor and CD firmware EPROM datasheets |
| `pdfs/emulator_notes/` | Kaisershot's "Exploring the Pippin ROM(s)" parts 2–9 (part 5 has the Open Firmware device tree), DingusPPC dev notes |
| `retrostuff/` | Archived retrostuff.org articles with full-size photos (below) |

## retrostuff.org archive

- [Troubleshooting and Repair Information](../scratch/retrostuff/2024-04-troubleshooting-and-repair/README.md) (2024): front-button cable pinout, the CR-504-L CD drive (SCSI ID 3, the ID string it reports, BlueSCSI settings), the CD-audio dependency, and the PSU pinout
- [PA-82001-S Monitoring Unit](../scratch/retrostuff/2019-09-pa-82001-s-monitoring-unit/README.md) (2019): full disassembly
- [AppleJack Controller](../scratch/retrostuff/2019-09-applejack-controller/README.md) (2019)
- [Floppy Unit PA-82002](../scratch/retrostuff/2020-05-floppy-unit-pa-82002/README.md) (2020)
- [Controller for Macintosh](../scratch/retrostuff/2020-09-controller-for-macintosh/README.md) (2020)

Text and photos © retrostuff.org; kept locally in `scratch/` for internal reference only, not committed.

## Known gaps

- No public Pippin hardware developer note, schematic or service manual. There is no register documentation for Taos (video) or Aspen (memory and PCI controller), so MAME and DingusPPC are the best reference.
- No datasheet for the CS4217, the Athens Prime clock chip or Grand Central itself. The TNT spec covers Grand Central.
- MAME and DingusPPC disagree on which SCSI controller the CD-ROM sits on (MESH vs. 53C94) and on the default RAM size. The real board is the tiebreaker.
- Main_MiSTer only turns on its Mac-family CD-image support for certain core names (`maclc`, `macplus`, `macquadra800`, `macppc7300`), so a Pippin core needs an upstream change or a matching name.
- blitter.net (part 1 of the ROM series, Pippin Kickstart) and the misterfpga.org forum threads couldn't be fetched.
