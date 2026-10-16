# Apple Pippin MiSTer core: implementation plan

Drafted 2026-10-16. Facts with citations are in [core-dev/README.md](core-dev/README.md) (§ numbers below refer to it). Questions are numbered Q1–Q12 as in its §5.

## Starting point

- **CPU:** DSPPC604 in `../MacPPC7300_MiSTer` is a working 32-bit PowerPC with FPU, MMU and caches. Its author reports it is close to closing timing at 70 MHz; the Pippin needs 66 MHz.
- **Peripherals already in RTL there:** Grand Central (interrupts, DBDMA), VIA + Cuda (68HC05 running 341S0060, the same part the Pippin uses), ESCC, AWACS, MESH, the SCSI CD target and CD audio, SWIM3, the SD-backed NVRAM save, and the SDRAM controller.
- **New for the Pippin:** the DSPPC603 CPU variant, Aspen (memory/PCI controller), Taos (video), the Athens and Bt856 I²C devices, the Am29F010 save flash, the AppleJack controller mapping, and the machine top level.
- **Test oracles:** MAME `pippin.cpp` (cycle-agnostic, but with a real 68HC05 Cuda and the 603's TLB-miss exceptions) and DingusPPC `machinepippin.cpp`. Neither emulator is ground truth; real hardware is.

## Phase 0: decisions (with the author, before code)

1. **Sharing code with MacPPC7300.** Options: a git submodule, a shared library repo, or copying files with a recorded upstream commit. The CPU and the shared peripherals will keep changing in MacPPC7300 (FPU work is under way), so a submodule pinned to a commit is the likely choice. Decide whether DSPPC603 lives in the MacPPC7300 tree (as its plan says) or here.
2. **Core name and CD support (Q6).** Main_MiSTer only turns on Mac SCSI CD support for `maclc`, `macplus`, `macquadra800` and `macppc7300`. Either send an upstream PR adding the Pippin core's name to `is_mac_scsi_family()`, or pick a name that matches. Prefer the upstream PR and keep the hps_io slot layout the same as the other Mac cores (CD on slot 4).
3. **License (Q12):** GPL-2.0, matching MacPPC7300 and Template_MiSTer. DingusPPC (GPL-3.0) is used only as a test oracle, never copied into RTL.
4. **Defaults (Q3):** RAM 5 MB DRAM (retail), with options of 13 and 21 MB. Video output VGA-style 640×480 (monitor ID 6), with NTSC as an option. ROM version 1.3 as the main target.

## Phase 1: oracle and trace setup

- Build MAME and DingusPPC with the Pippin ROMs (the user has them in `ROMs/`; never commit them).
- Add trace logging to the emulators: PC, MMIO accesses with address/value/size, interrupts, and TLB-miss exception entries. Use these to answer:
  - **Q2:** is the CD on MESH or on the 53C94? Log which SCSI registers the ROM touches.
  - **Q4:** where does VBL come from? Does the ROM or OS enable a Taos interrupt or rely on the VIA?
  - **Q7, first part:** with MAME's real 603 MMU, how often are 0x1000–0x1200 entered during boot?
  - **Q10:** does boot depend on Bt856 or the second Athens answering on I²C?
  - **Q5:** which Taos registers are actually written.
- If a real Pippin is available, read its PVR (Q7) and capture a serial/debug log of boot for comparison.
- **Done when:** the questions have answers written into core-dev/README.md, and a reference MMIO trace of a 1.3 ROM boot to the CD-insert screen is saved for comparison against the RTL.

## Phase 2: DSPPC603, minimal

Wait until the author finishes the FPU work in MacPPC7300.

- Copy or wrap DSPPC604 as DSPPC603. Parameters: PVR `0x0003xxxx` (exact value from Phase 1), I-cache and D-cache 8 KB, TLB size.
- Add the 603 SPRs (DMISS, DCMP, HASH1, HASH2, IMISS, ICMP, RPA, HID1) as plain registers. Decode `tlbld`/`tlbli` as no-ops. Map HID0 doze/nap/sleep and MSR[POW] to "wait for interrupt".
- Keep the hardware page-table walk for now (DingusPPC boots the Pippin this way).
- Time base = CPU/4 (16.5 MHz at 66 MHz).
- **Done when:** the CPU's existing golden vectors still pass, and Fmax is no worse than DSPPC604 at the same settings.

## Phase 3: machine skeleton and Aspen

- New top level from Template_MiSTer: clocks (CPU 66 MHz, memory 100 MHz as in MacPPC7300), SDRAM controller, ROM upload from the OSD into SDRAM, and the debug readout and UART reused from MacPPC7300.
- **Aspen (§1.2):**
  - RAM banks on 16 MB boundaries, with the mirror windows the ROM's memory sizing probes.
  - ROM at `0xFFC00000`.
  - Registers at `0xF8000000` (SYSTEM_ID, VERSION, MEM_CONFIG, GPIO).
  - PCI configuration at `0xF2800000`/`0xF2C00000`, enough to present Grand Central (`106b:0002`) and let firmware place its BAR at `0xF3000000`.
- **Done when:** the ROM runs from reset and passes memory sizing, matching the MAME trace up to the first Cuda access.

## Phase 4: Grand Central, Cuda, VIA, SCC

- Reuse MacPPC7300's Grand Central, VIA and Cuda (hc05 + 341S0060, Q9), and the ESCC. Adjust for the Pippin's Grand Central placement and interrupt wiring (§1.3), including the PCI slot interrupts on EXT9/EXT10 if they are used.
- At reset the CPU is held until Cuda releases it (§1.6).
- **Done when:** Cuda releases the CPU, the ROM gets through its Cuda/PRAM/RTC traffic, and the RTL trace matches MAME's through video setup.

## Phase 5: Taos video, Athens, Bt856

- Taos (§1.5):
  - 1 MB VRAM at `0xF0000000`, kept in SDRAM or a dedicated buffer.
  - Registers at `0xF0800000` and the 256-entry CLUT at `0xF1000000`.
  - 8 bpp CLUT and 16 bpp xRGB555 modes, `FB_BASE` and `ROW_WORDS`.
  - GPIO_IN carrying the monitor ID and the CD-tray-closed bit.
  - The VBL source, as found in Phase 1.
- Video output through MiSTer's ascal, as MacPPC7300 does: 640×480 at about 60 Hz. NTSC 15 kHz is an option for later; the convolution filter comes after that.
- Athens Prime on I²C 0x29 (pixel clock register writes, then a pixel clock taken from a fixed PLL table). A Bt856 stub that acknowledges at 0x44.
- **Done when:** the Pippin startup screen appears and matches MAME pixel for pixel in both 8 and 16 bpp.

## Phase 6: SCSI and CD-ROM

- MESH at Grand Central +0x18000 with DBDMA channel 10 (or the 53C94, depending on Q2), reusing MacPPC7300's MESH and SCSI CD target.
- The CD answers at ID 3 with the inquiry `MATSHITA` / `CD-ROM CR-8005A` / `4.0i` (from the retrostuff article). Support Apple's vendor audio commands (MAME `nscsi/cd.h:156-196`, the Apple CD-ROM Handbook in `pdfs/cdrom/`).
- CD images: CUE/BIN and CHD through Main_MiSTer's Mac CD path, depending on Phase 0 decision 2. CD-DA frames are mixed into AWACS's output (Racing Days needs CD-DA to start at all).
- The eject button and the tray-closed GPIO bit, from the OSD.
- **Done when:** a Pippin disc boots to its title (Pippin Kickstart or a retail title), and the audio CD player works.

## Phase 7: input, audio, saves

- **AppleJack controller over ADB:** map a MiSTer gamepad to MAME's button bits (`adbhlepippin.cpp:15-24`) and the analog trackball to the controller's pointer. Optionally add an ADB keyboard and mouse (MacPPC7300 already has them).
- **AWACS** to MiSTer audio at 22.05 and 44.1 kHz, plus the CD-DA mix.
- **Save flash** (Am29F010, 128 KB at `0x40000000`, one byte per 32-bit word on lane D0–D7, bit-reversed), persisted to the SD card the way MacPPC7300's `nvsave.sv` saves NVRAM (Q8). Implement the flash's command sequences: program, sector erase, chip erase, autoselect.
- Front-panel power, reset and eject buttons as OSD actions.

## Phase 8: full 603 TLB reload

Follow [prompts/DSPPC603_tlb_reload.md](prompts/DSPPC603_tlb_reload.md): implement the exception-based reload faithfully and check it bit for bit against a real 603 machine, MAME and the RTL. Keep the hardware-walk build as an option until the real reload is proven across the title list.

## Phase 9: compatibility, speed, release

- A compatibility list of the retail Pippin titles, each tested on both MMU builds.
- **Speed:** DSPPC603 executes more per clock than a real 603. Add a throttle option if timing-sensitive titles misbehave, and measure against MAME and real hardware with the same benchmark disc.
- Timing closure on the full build, then ALM, RAM block and Fmax reporting as in the MacPPC7300 README tables.
- **Release:**
  - The `.rbf` goes in `releases/`.
  - A README covering the ROM file names and the CRC32s the core expects (§1.7) and the OSD options.
  - Docs for the CD image formats.
  - The Main_MiSTer PR, if one is needed.

## Risks

| Risk | Mitigation |
|---|---|
| The Pippin OS needs real 603 TLB-miss behaviour | Phase 1 measures it in MAME; Phase 8 implements it |
| Q2 is answered wrongly (MESH vs 53C94) | Phase 1 traces both buses; both controllers already exist in MacPPC7300 |
| Main_MiSTer CD support is gated by core name | Upstream PR early (Phase 0) |
| The VBL source is unknown | Phase 1 trace, then real hardware |
| Logic or timing margin | The Pippin machine is smaller than the 7300 (no Bandit L2, Control, MACE or 53C94, if Q2 allows); cache sizes drop to 8 KB |
| The shared CPU drifts while both cores are being developed | Pin the submodule; give DSPPC603 its own regression vectors |
