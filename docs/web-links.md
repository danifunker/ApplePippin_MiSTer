# Pippin web sources: what they tell the core

Compiled 2026-10-21 from 31 links supplied by the user. Four agents read the links, plus about 15 sub-pages and articles they linked to. The archived pages, translations (Japanese and French) and images are in the git-ignored **`../scratch/web-links/<slug>/`**, one `README.md` per source. Paths below are relative to `scratch/web-links/`. Tags:

- **[photo]**: inferred from board photos.
- **[report]**: an owner's measurement, such as TattleTech or About This Mac.
- **[doc]**: an Apple document.

## Key facts for the core

1. **Main DRAM is two 32-bit banks of 5 V, 60 ns EDO with 11 address bits.**
   - Bank 0: 4 MB = 2 × 1M×16, KM416C1204AJ-6 at U21/U17.
   - Bank 1: 1 MB = 2 × 256K×16, KM416C254BJ-6 at U15/U31.
   - Two more 256K×16 chips are Taos's 1 MB VRAM, off the main bus.

   The 6 MB on the box is 5 MB DRAM + 1 MB VRAM. The 603 bus is 64 bits wide, but each DRAM bank is only 32 bits wide. Eight **74ABT574** octal registers (64 bits in all, 4 on each side) sit near the ROM slot and bus. They probably latch ROM data or assemble 64-bit beats from two DRAM accesses **[photo]**. Sources: `catkicking-lets2memory2/`, `retrostuff-pippins-images/`, `jdl-magazine-4/` (the annotated board scan `18.jpeg`).
2. **Expansion RAM sits on connector J18 and has no presence-detect pins.**
   - Same electrical spec as the onboard RAM. One RAS (U11 pin 203 → J18 pin 42), CAS0-3 as byte lanes (U11 pins 12/11/10/9), a shared WE, and multiplexed address A0-A10. U11 is the 208-pin ASIC, i.e. Aspen.
   - The ROM must size the card by probing; there are no PRD lines.
   - The Pippin needs **2048-cycle refresh**, which means 11 row bits. 4K- and 8K-refresh 64 Mbit parts don't work.
   - Real cards:

     | Card | Part | Organisation |
     |---|---|---|
     | 2 MB | PA-82011 | 4 × 256K×16 |
     | 4 MB | PA-82003-4 | prototype |
     | 8 MB | PA-82013 | 4 × 1M×16 |
     | 16 MB | third-party KMP2000 | 8 × 4M×4, also hand-wired from Micron MT8D432X or Samsung KMM5323041 SIMMs |

   - The full 72-pin SIMM ↔ J18 table is in `catkicking-lets2memory2/README.md`.
3. **Expected RAM sizes, as targets for the sizing code:**

   | Source | Configuration | Value shown |
   |---|---|---|
   | Kickstart | ROM 1.0, no card | 5040K |
   | Kickstart | 2 MB card | 7088K |
   | Kickstart | 4 MB card | 9132K |
   | Kickstart | 8 MB card | 13224K |
   | TattleTech | Kinka Dev ROM, 8 MB card | RAM Size 13,631,488 bytes (5 + 8 MB) |
   | About This Mac | 8 MB card | Total Memory 13,312K |
   | About This Mac | 16 MB card | Total Memory 21,504K |

   The Kickstart figures fall short of nominal by a near-constant 80-88 KB, which looks like a fixed reservation rather than a bank-mapping effect. Sources: `jdl-kickstart/`, `vintagemacworld-pip1/pip_tt.txt`, `jdl-link-16mo-ram/`.
4. **CPU identity from a real unit [report]:**
   - PVR **0x00030302**: 603, rev 3.2.
   - Clocks: 66.17 MHz core, 66.00 MHz bus, 16.5 MHz timebase (OF `timebase-frequency` 0x00FBC520).
   - Caches 8 KB I + 8 KB D. TLB: 32 sets, 64 entries.
   - Sources: `vintagemacworld-pip1/pip_tt.txt`, `jdl-open-firmware/`.
5. **The CD is on MESH.** A SCSIProbe screenshot shows a single bus, "Apple Computer MESH", with the CD (MATSHITA CR-8005A 4.0i, i.e. a CR-504-L) at **ID 3** and the host at ID 7 (`retrostuff-scsi-rom-dump/`). TattleTech reports MESH (AAPL,343S1146) at 50 MHz. This settles **D2** in [core-dev/README.md](core-dev/README.md) in MAME's favour.
6. **The repo's "Kinka Dev" ROM is the 1996-01-28 GM/"Monitoring" ROM.**
   - MD5 `318e40f6a1f47925876eb64cc18c9ede` matches `ROMs/2BF65931 …`. Version 077D/2CC6.
   - It boots from a SCSI hard disk without authentication.
   - Kinka 1.0 is 077D/2CF2, dated 1996-01-29, mask ROMs 341S0251-254 on board AP2777-01. It boots only from the internal CD at SCSI ID 3.
7. **Open Firmware 1.0.5 ("PipPCI2") is reachable over serial.**
   - Hold **Cmd-Opt-O-F** with an ADB keyboard; the SCC modem port runs at **38400 8N1, XON/XOFF**. Nothing shows on video.
   - The device tree from a ROM 1.3 unit is the address map to check the decode against (§4).

## 1. Memory

- **Onboard (catkicking, translated):** two x16 chips per 32-bit bank. U21 carries D0-15 and U17 carries D16-31. A8/A9 come only from U11 pins 176/175, and A10 only to J18 pin 34; the 256K×16 chips use 9 address bits. The schematic net names are ADDRESS(12)…ADDRESS(22) for DRAM A0…A10.
- **Card organisation:** genuine cards have 4 chips, i.e. two 32-bit halves. The 16 MB card is 8 × 4M×4 with one RAS and CAS0 = D0-7 … CAS3 = D24-31. A 32 MB design (8 chips per data line) was dropped as too much bus load.
- **The core's map against this:** our map (`rtl/machine/Pippin_machine.sv:17`, from MAME/DingusPPC) has bank 0 = 4 MB at 0, bank 1 = 1 MB at 0x0100_0000, and expansion banks 2/3. That fits two onboard banks plus one J18 card. A J18 card with two 32-bit halves could plausibly appear as banks 2 and 3; MAME's ">13 MB → bank 3" rule is consistent with a 16 MB card being two 8 MB halves **[inference]**.
- **No VM and no RAM disk** on any Pippin system (vintagemacworld). Thread Manager works only with Pippin System 7.5.2.
- **Save storage:** the board has an AM29F010-90JC, 128 KB **[photo]**. Apple's notes say 128 KB NVRAM with 8 KB for the system and 120 KB free; the Flash! volume shows 113 KB usable. The "64 KB SRAM backup" in the 1995 spec sheet is probably pre-production. OF reports NVRAM as 8192 bytes, which is the Grand Central nvram@1D000, a separate device.

## 2. ROM

The ROM board plugs into a 120-pin slot (Burndy CELP2X60, 50 mil, the same connector as X-PCI).

**Retail board**
- 4 × 512K×16 (29F800 pinout), **64 bits wide**.
- A0-A18 are shared by all four chips, so one chip address = one doubleword.
- Byte order in the big-endian image: bytes 0-1 come from U4, 2-3 from U3, 4-5 from U2, 6-7 from U1.
- Two /OE lines, one per chip pair. CE is grounded and BYTE# tied high.
- Pins 1-2 carry +12 V (Vpp on flash boards).
- Pin 44 /ROM is card-present: grounded on the card, it goes to the board's U1 pin 77.

**GM board**
- 16 × AM28F020-120JC plus a 74F86 XOR on A18, which selects the halves.
- The two halves have bit-reversed data lines.
- trag recommends 90 ns or faster flash for clones.

**Flash ROM boards** run about 1.5× slower and use about 250 KB more RAM than mask ROMs (fandom).

Unpopulated SOP-44 pads U31/U35/U15/U20 on the main board are onboard ROM sites.

Sources: `68kmla-flash-rom-board/` (full pinouts), `retrostuff-pippins-images/`, `fandom-pippin-roms/`.

| ROM | Version | Checksum | Board / chips | Boots from |
|---|---|---|---|---|
| Early developer | | | AP2660-02, 16 flash | FDD, HDD |
| Disco | 2CD1 | DEBFDAED | | |
| A1 | 2CA1 | 411628AB | | |
| C3 / C7 | 2CC3 / 2CC7 | — | | |
| **GM / Monitoring (= Kinka Dev)** | 077D/**2CC6** | **2BF65931** | AP2735-01, 341S0241-245, 247, 248, 250 (about 500 made) | HDD, Zip, any SCSI ID < 7 |
| **1.0 (Kinka 1.0)** | 077D/**2CF2** | **2BEF21B7** | AP2777-01, 341S0251-254 | internal CD at ID 3 only |
| 1.2 (JP and US) | 2CF5 | 3E10E14C | 820-0867-01, 341S0297-300 | adds MO and SCSI HDD; new CD driver |
| 1.3 | 2CF8 | 3E6B3EE4 | AP2777-01, 341S0328-331 | adds the PCI adapter; **no authentication** (Katz units) |

- The version word is at low-memory **$02AE**.
- TattleTech reports the ROM size as 3 MB (3,145,728 bytes) at **$FFC00000**. The chips hold 4 MB, and OF maps FFC00000 at 2 MB cacheable.
- ROM 1.2 with an 8x or faster drive loses CD audio and software eject; 1.3 fixes both (`jdl-link-24x-cdrom/`).
- The ROM contains traces of AppleTalk network boot (`jdl-rom-analyse/`).

## 3. Expansion connector (X-PCI)

- 120 pins, 2 × 60. A 32-bit, 5 V PCI subset plus +12 V:
  - Pins 1-44: GNT#, DEVSEL#, PAR, REQ#, FRAME#, IRDY#, TRDY#, STOP#, C/BE0-3#, AD0-1.
  - Then a key gap.
  - Pins 45-90: AD2-31, **IDSEL = pin 62**, CLK = 85, RST# = 87.
  - **INTA# = pin 98.**
- **IDSEL is tied to AD15 through R59.** Config cycles reach the slot device on AD bit 15; Grand Central is on bit 13 ([rom-map.md](rom-map.md):218).
- PCI clock is 33.33 MHz (TattleTech). Slot names are A1, B1 and C1.
- Pins 91-120 carry the **floppy** signals, and probably SCSI. Apple's passive floppy adapter AP2670-02 wires a 20-pin Apple floppy header to that end; there is an OSH Park reproduction that works with a Floppy Emu (`jdl-link-floppy/`). The exact assignment is in abzman's Google Sheet (sign-in needed) and on MAISON PiPPiN (not fetched).
- The source table has a typo: AD12 is listed on B47 but is really A47.
- The Katz "PIPPIN EXPANSION UNIT ISSUE 1" riser needs ROM 1.3. A Matrox Millennium II worked as a second display with it.
- Sources: `abzman-expansion-connector/` (full table), `catkicking-lets2memory2/related/` (pippinxpi), `vintagemacworld-pip1/`.

## 4. Open Firmware device tree (ROM 1.3 unit)

From `jdl-open-firmware/`:

```
/aspen@F2000000           PCI host (Aspen, AAPL,343S0152)
  /gc@10                  Grand Central (AAPL,343S1125)
    scc@13000 (ch-a@13020, ch-b@13000)   awacs@14000   swim3@15000
    via-cuda@16000 (adb, pram, rtc, power-mgt)   mesh@18000   nvram@1D000
  taos@F0800000           AAPL,343S0153: regs F0800000 size 0x800, FB F0000000 (16 MB), interrupt 0x1C
/aspenmemory@F8000000
/AAPL,ROM@FFC00000
```

**Translations**
- Cache-inhibited and guarded: F2000000/64K, F2800000/4K, F2C00000/4K, F3000000/16M, F8000000/4K.
- FF800000/1M maps to **physical 0x00200000**.
- ROM FFC00000/2M is cacheable.
- `existing` is 0-0x80000000.

There is no 53C94/Curio node, which agrees with fact 5.

## 5. Boot, SCSI and authentication

**SCSI**
- The internal CD is a CR-504-L at **ID 3** with parity and termination on.
- An external SCSI port can be added with a cable over the case lip.
- HDDs must be **HFS Standard**; HFS+ does not boot.
- SCSI2SD as IDs 4/5 works, but avoid ID 3. An Acard SCSI-to-IDE bridge stops the Pippin from booting.
- A BlueSCSI v1 inside the case fails to power up, probably for lack of TERMPWR. As an external drive with Kickstart it works.

**Authentication**
- Each disc carries a `PippinAuthenticationFile`: an RSA signature (about a 360-bit modulus) over MD5s of 128 KB chunks.
- Six chunks are checked: the first and five pseudo-random ones.
- Keith Kaisershot recovered the private key in 2019, so homebrew discs can be signed. No ROM patch is involved.

**Kickstart** (open-source boot CD)
- Shows the ROM version and RAM, ejects itself, then boots any unsigned disc or an external SCSI HDD.
- Kickstart 1.1 patches ROM 1.0's "ID 3 only" check.

**Startup**
- Discs are plain bootable HFS CDs with a blessed "System Folder". The app is launched by Startup Items or by "Pippin Launch" (`PCde`).
- Early discs patched the boot blocks.
- Dev units booted from an external SCSI HDD.
- **Newer technote:** `macgeek-pippin-museum/pdf/CreatPipCDs004.pdf` (PPBD-JBEF004, 5/10/96, 16 pp.) is newer than our v003. It adds only the ResEdit step: set the renamed Finder's Type/Creator to `FNDR`/`MACS`.

## 6. Input, video, misc

**Input**
- **P-ADB** is plain ADB on a Hosiden HGC0492 connector (the Game Gear link port). Pins: 1 data, 2 n.c. (no power-on line), 3 +5 V, 4 GND, 5-10 n.c. (`jdl-padb-gamegear/`).
- **AppleJack ADB report**, 4 bytes:
  - 7-bit two's-complement Y and X.
  - Buttons: b17 L-fire, b16 R-fire, b15 green, b14 red, b13 down, b12 right, b11 left, b10 up, b9 yellow, b8 blue.
  - b2/b1/b0 are the right/middle/left system buttons.
  - Source: `jdl-documentation/`.

**Video**
- Safe title area 512×384 and safe action area 576×432 on a 640×480 screen.
- Taos can shrink the picture by 12.5% under software control (640×480 → about 512×384 on TV).
- Scan modes: progressive (VGA only), interlace, interlace+convolution, and interlace+convolution+scale.
- TattleTech: 1 MB VRAM, 16 bpp maximum.

**Other**
- Serial hardware type "TntS"; sound type "awgc"; Gestalt machine type 73.
- The modem port is not GeoPort-powered.
- The main board is **820-0791-02 PVT-2**.
- Clock chips: 2 × 343S1191 (Athens Prime) and an MPC904 buffer.
- Other parts: Z85C30 SCC with DS8925 drivers, CS4217, Bt856, LM3940 3.3 V regulator (`retrostuff-pippins-images/`).

## 7. The current board stall (floppy driver init)

No source explains the board-only `tst.l 6(a0)` = 0 directly. Four facts are relevant:

- **A retail Pippin has no floppy drive.** SWIM3 is present, and a drive appears only through the X-PCI floppy adapter. So `.Sony` init on real hardware always takes the "no drives" path, and the 500 ms poll loop is normal behaviour. What is not normal is the TMTask field reading zero.
- **Real DRAM is 32 bits wide behind registered 64-bit latches.** Aspen therefore splits every 64-bit beat into two DRAM cycles. Nothing in these sources gives Aspen's write-buffer or read-after-write behaviour; that still needs to come from our own captures.
- **The memory sizing probe must see a plain 5 MB with no card.** No presence detect exists, so the ROM finds the card only by aliasing. A board-only difference in what the 4 KB probe windows return would change BufPtr and the low-memory layout, though not necessarily this field.
- **ROM 1.0 vs Dev:** the Dev (GM) ROM is the one TattleTech ran on an 8 MB unit, and it boots unauthenticated SCSI media. It remains the easier ROM for test discs.

## Source catalogue

| # | Link | Local | Content | Value |
|---|---|---|---|---|
| 1 | vintagemacworld.com/pip1.html (2014 and 2017 snapshots, identical) | `vintagemacworld-pip1/` | "Hacking the Pippin": ROM table, RAM, XPCI, OS 8, TattleTech report | **High** |
| 2 | catkicking lets2memory2 (JP) | `catkicking-lets2memory2/` (+`related/`: spec, 16 MB, XPCI table) | DRAM organisation, refresh, 72-pin↔J18 pinout | **High** |
| 3 | abzman2k expansion connector | `abzman-expansion-connector/` | X-PCI pinout (via catkicking) | **High** |
| 4 | retrostuff pippins_37/38.jpg | `retrostuff-pippins-images/` | Board chip markings | **High** |
| 5 | ato-net pippicon (JP) | `ato-net-pippicon/` | ADB plug for the IR controller | Low |
| 6 | 68kmla flash ROM board (pp. 1-2) | `68kmla-flash-rom-board/` | ROM card pinout, GM board, /ROM pin | **High** |
| 7 | hyperspin system setup | `hyperspin-system-setup/` | SheepShaver front-end pack | None |
| 8 | catkicking letspippin2hdd (JP; the live site is parked) | `catkicking-letspippin2hdd/` | Fitting an internal HDD | Low |
| 9 | macgeek museum: development, FAQ, index, information, photos | `macgeek-pippin-museum/` | 10 technotes (newer revisions), spec sheet, photos | Medium |
| 10 | CreatPipCDs004.pdf | `macgeek-pippin-museum/pdf/` | Technote v004 (newer than ours) | Medium |
| 11 | catkicking letspippin2 (JP) | `catkicking-letspippin2/` | LocalTalk → Ethernet bridging | None |
| 12 | retrostuff external SCSI and ROM dump | `retrostuff-scsi-rom-dump/` | MESH bus, ROM MD5s, SCSI2SD | **High** |
| 13 | pippin.fandom.com Pippin_ROMs | `fandom-pippin-roms/` | ROM versions and checksums | **High** |
| 14 | journaldulapin pippin-magazine-4 | `jdl-magazine-4/` | Annotated board, dev ROM boards, ADB and floppy mods | Medium |
| 15 | jdl ODE with a BlueSCSI | `jdl-ode-bluescsi/` | SCSI IDs, TERMPWR | Low |
| 16 | jdl ROM analysis | `jdl-rom-analyse/` | ROM versions, network boot | Medium |
| 17 | jdl Open Firmware | `jdl-open-firmware/` | Device tree, translations, serial access | **High** |
| 18 | jdl KeySpan serial | `jdl-keypasn-serial/` | USB-serial adapters for macOS | Low |
| 19 | jdl the Pippin has been cracked | `jdl-crack/`, `jdl-link-pippin-hack/` | Authentication scheme | Medium |
| 20 | jdl Kickstart | `jdl-kickstart/`, `jdl-link-kickstart-2021/` | RAM figures, boot rules | Medium |
| 21 | jdl P-ADB from a Game Gear | `jdl-padb-gamegear/` | P-ADB pinout | Medium |
| 22 | jdl documentation | `jdl-documentation/` | AppleJack report format, overscan | Medium |
| 23 | jdl 3D card (dated **April 1**) | `jdl-carte-3d/` | The PCI adapter is real; the 3D result is probably the joke | Do not rely on it |
| 24 | earthlink gamba os8_68030 | `gamba-os8-68030/` | OS 8 on 68030 Macs (ResEdit patches) | None |
| — | jdl linked articles | `jdl-link-*` | 16 MB RAM, RAM cards, GM ROM via HDD, CD drives, floppy adapter, Katz units | Medium |

**Not retrieved:**
- abzman's Google Sheet: needs sign-in; it has the floppy pins 91-120.
- MAISON PiPPiN (geocities): not fetched.
- 68kmla `CELP.pdf`: needs a forum login.
- catkicking `memory7.jpg` and `xpci_pci.pdf`: never archived.
- Kickstart ISOs, the GM ROM dump and the Gamba patch: software, skipped on purpose.
- PippinGuidelines.sit: packaging guidelines only.

**Copyright:** text and photos belong to their authors and stay in `scratch/` for internal reference.
