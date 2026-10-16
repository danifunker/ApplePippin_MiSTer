# Pippin boot ROM map (Kinka 1.0 and Kinka Dev)

This is a byte-accurate map of the two 4 MB Pippin boot ROMs in `ROMs/`. It covers their structure, landmark checks, the
differences between the two ROMs, and the findings that matter for the FPGA core. It was produced by the static tools in
[`tools/rom/`](../tools/rom/README.md); no ROM code was executed. The full listings are in
[`disasm/kinka-1.0/index.md`](../disasm/kinka-1.0/index.md),
[`disasm/kinka-dev/index.md`](../disasm/kinka-dev/index.md) and
[`disasm/diff-1.0-vs-dev.md`](../disasm/diff-1.0-vs-dev.md). The per-ROM folders are committed as `disasm/disasm.tar.xz`: run `python3 tools/rom/pack.py unpack` first. Regenerate them with `tools/rom/disassemble.sh`.

Labels used here:

- **Verified** means checked against the bytes by the tools: parsed structures with consistent links, recomputed
  checksums, or matching patterns.
- **[inference]** means an interpretation that the bytes do not prove.

## 1. Inputs

| ROM | File | SHA-1 | 68K checksum @0 | Version word / release | DingusPPC id |
|---|---|---|---|---|---|
| Kinka 1.0 | `2BEF21B7 - Bandai Pippin (Kinka 1.0).ROM` | `6478ee9e8d5cfe3b00f699f7072482210e00c5cc` | 0x2BEF21B7 | 0x077D / 0x2CF2 | 077d2cf2, 2bef21b7 |
| Kinka Dev | `2BF65931 - Bandai Pippin (Kinka Dev).ROM` | `eb8739cab1807c6c7c51acc7f4a3afc1f9c6ddbb` | 0x2BF65931 | 0x077D / 0x2CC6 | 077d2cc6, 2bf65931 |

**Verified:** the MAME/DingusPPC ids are the 68K ROM checksum stored at offset 0. It is the sum of the big-endian 16-bit
words from offset 4 to 0x300000. The four byte-lane sums at 0x30-0x3F also recompute correctly. They sum every 4th byte
over the 68K ROM, with the checksum fields taken as zero.

## 2. Structure (verified for both ROMs)

The ROM is mapped at CPU address 0xFFC00000 (CPU address = 0xFFC00000 + ROM offset). The 603 resets to 0xFFF00100,
which is ROM offset 0x300100.

The first 3 MB hold a classic "SuperMario"-style 68K Mac ROM. Its parts are:

- the header, with ResetPC 0x2A
- the 68K Toolbox/OS code
- a linked ROM resource list of 300 resources. Each resource body is preceded by a 16-byte fake Memory Manager header
  (`Kurt`, 0xC0A00000, size+12).
- `kc` fill
- DeclData at the very end. It contains a format block with the board name "Macintosh 4A".

The resources split into three classes:

| Class | Count | Bytes |
|---|---:|---:|
| PEF containers (PowerPC) | 45 | 1,448,315 |
| 68K code resources | 78 | 502,901 |
| Data resources | 177 | 293,735 |

The PEF types are `nlib`, `ncod`, `ndrv`, `nift`, `nint`, `nitt`, `ncmp`, `nsnd` and `slib`. The 68K code types are
DRVR, PACK, xDEF, `proc`, `iNiT`, `rvpr`, `scod`, `sl0x` and others.

The last megabyte holds the PowerPC parts. They are located through ConfigInfo at 0x30D000, whose component offsets are
relative to that page. ConfigInfo's own checksum does not verify on either ROM; tbxi notes the same.

| Region | 1.0 offset | 1.0 size | Dev offset | Dev size | ISA | Same bytes? | SHA-1 (1.0, 12 hex) |
|---|---|---:|---|---:|---|---|---|
| 68K ROM header + ForeignOS table | 0x000000 | 108 | 0x000000 | 108 | data | no | e746852e245b |
| 68K main code | 0x00006C | 870260 | 0x00006C | 869956 | 68K | no | eb15e953a2d6 |
| ROM resources (list header, 300 entries, bodies, alignment) | 0x0D47E0 | 2262272 | 0x0D46B0 | 2262272 | mixed | no (moved -0x130) | 97579469f6bd |
| `kc` fill | 0x2FCCE0 | 12786 | 0x2FCBB0 | 13090 | - | no | 9e719449b256 |
| DeclData | 0x2FFED2 | 302 | 0x2FFED2 | 302 | data | no | e5a92cfc468e |
| Exception vectors + low-level startup (reset at +0x100, cold start at +0x3000) | 0x300000 | 21456 | 0x300000 | 21456 | PPC | yes | bb40c0075726 |
| Pippin blob directory (83 x 16-byte entries) | 0x3053D0 | 1328 | same | 1328 | data | yes | 656ad6a9849a |
| padding | 0x305900 | 30464 | same | 30464 | - | yes | cf188f75730e |
| ConfigInfo page | 0x30D000 | 4096 | same | 4096 | data | no (checksum fields) | 5af1ec361e6d |
| padding | 0x30E000 | 8192 | same | 8192 | - | yes | 0631457264ff |
| NanoKernel (v01.01) | 0x310000 | 23104 | same | 23104 | PPC | yes | 2dc8bf3aa578 |
| padding | 0x315A40 | 42432 | same | 42432 | - | yes | 1001b6fea512 |
| HWInit XCOFF header | 0x320000 | 60 | same | 60 | data | no (timestamp) | f94be79bbcdb |
| HWInit .text (`.POST`, `.L2DataCacheTest`, `.SerialTestManager`) | 0x32003C | 7272 | same | 7272 | PPC | yes | 1ce8b7abfdf0 |
| HWInit XCOFF symbol/string table | 0x321CA4 | 284 | same | 284 | data | no | 6be6af34a336 |
| Blobs inside the HWInit slot (PICT 0xC7-0xCA) | 0x321DC0 | 54832 | same | 54832 | data | yes | 7e5371648845 |
| padding | 0x32F3F0 | 3088 | same | 3088 | - | yes | 69cfb31f4c12 |
| Open Firmware XCOFF header | 0x330000 | 60 | same | 60 | data | yes | b231e66c1485 |
| OF native kernel (PPC subroutine-threaded Forth, 501 words, 235 named) | 0x33003C | 26600 | same | 26600 | PPC | yes | 3a1c66da4017 |
| OF FCode images 0-9 (version1, checksums verified) + descriptors | 0x336824 | 70396 | same | 70396 | FCode | yes | c5ca89ff4e96 |
| end of XCOFF .text (0xFF fill) + 4 zero bytes | 0x347B20 | 16 | same | 16 | - | yes | - |
| Blobs after OF (`snd ` boot sound, `cTBL`, 6 `fTBL`, 71 `PICT`) | 0x347B30 | 96635 | same | 96635 | data | yes | b0acc789915e |
| padding | 0x35F4AB | 2901 | same | 2901 | - | yes | a33b9cfbc031 |
| 68K emulator ("680x0 Emulation written by Gary Davidian") | 0x360000 | 95104 | same | 95104 | PPC | yes | 8924126232e0 |
| padding | 0x377380 | 35968 | same | 35968 | - | yes | 070a0956e779 |
| 68K emulator opcode table (65536 x 8 bytes) | 0x380000 | 524288 | same | 524288 | PPC | yes | b3e2f384297c |

### Coverage

Every byte belongs to exactly one leaf region. Each index has 1166 contiguous rows, asserted by the tool.

| Kind | 1.0 bytes | % |
|---|---:|---:|
| PPC code | 1,933,058 | 46.1 |
| 68K code | 1,374,409 | 32.8 |
| Data | 495,499 | 11.8 |
| Tables | 176,126 | 4.2 |
| Padding | 138,343 | 3.3 |
| FCode | 70,237 | 1.7 |
| Headers | 6,632 | 0.2 |
| **Unidentified** | **0** | **0** |

"Padding" includes 240 bytes of non-zero alignment slack between PEF sections, which are stale bytes from the build
tool. The Dev ROM has the same coverage, with 304 more padding bytes and 304 fewer 68K code bytes.

### What is disassembled and what is data-only

Disassembled:

- **68K:** the main code (linear sweep, A-line traps named from multiversal, low-memory globals named) and the 78 68K
  code resources.
- **PPC:** every PEF code section (45), the exception table and startup code, the NanoKernel, HWInit, the native OF
  kernel, the 68K emulator, and the opcode table (one line per 68K opcode).
- **FCode:** the 10 Open Firmware images, through OpenBIOS `detok`. Native Forth words are supplied to it as vendor
  tokens.

Data-only (hex dump plus decoded header):

- data resources
- the PEF data sections (raw bytes, plus the unpacked pidata with symbolic relocations) and the loader sections
  (imports, exports and relocations are decoded)
- ConfigInfo
- the blob directory and its blobs
- DeclData

### Pippin-specific structures (observed, not documented elsewhere)

- **Blob directory at 0x3053D0.** It is made of 16-byte entries `{OSType type; u16 id; u16 0; u32 romOffset; u32 size}`:
  1 `snd `, 1 `cTBL`, 6 `fTBL` and 75 `PICT`.
  - The `snd ` entry is format 1, 46,553 samples, 8-bit at 22,050 Hz. **[inference]** It is the boot chime.
  - Most "PICT" entries are 128-byte blobs with no QuickDraw header. **[inference]** They are glyphs or bitmaps for a
    PPC-side display.
  - Four PICTs (0xC7-0xCA) sit inside the HWInit slot. The first of them overwrites the last bytes of the HWInit XCOFF
    string table, so the symbol name `.SerialTestManager` is truncated in 1.0.
- **OF native word header.** The layout is `s32 link (relative); u8 flags (0x80; 0x20 = headerless); u8 type; u16 FCode
  token; [u8 len, name, pad, 0 long]`, and the code follows. **[inference]** The type byte equals the FCode definer token
  (0xB7 `b(:)`, 0xBA `b(constant)`, ...).
- **FCode image descriptors.** Images 1-9 are each preceded by 16 bytes `{s32 link; u16; u16; u32; u32 0}`. The links
  chain the images together.
  - **[inference]** The u16 pair is a PCI (device, vendor) match. Examples: (0x0001, 0x106B) → the `aspen` image;
    (0x0003, 0x106B) → `chaos` and `control`; (0x0004, 0x106B) → `planb`.
  - The u32 is a class code or package selector. Examples: 0x060400 → `pci-bridge`; 1 → `mesh` (AAPL,343S1146);
    3 → `sd`; 4 → `st`.
  - The chaos, control and planb images are Power Mac 7500-family drivers carried along unused.

## 3. Landmark checks

| Check | 1.0 | Dev |
|---|---|---|
| PPC reset vector: ROM 0x300100 = `b +8`; the cold-start path reaches 0xFFF03000 (`mfpvr r4`) | PASS | PASS |
| 68K ResetPC 0x2A, and ConfigInfo LowMemInit [4] = 0xFFC0002A | PASS | PASS |
| 68K header version 0x077D; release matches the DingusPPC id (077d2cf2 / 077d2cc6) | PASS | PASS |
| Offset-0 checksum = file name / MAME / DingusPPC id, recomputed; byte-lane sums | PASS | PASS |
| `'rvpr' 0` present (1.0 at 0x2A2EB0, 36,201 bytes); bytes at +0x14, +0x104 (`lea`/`adda.l #$106A2`/`_StripAddress`), +0x108A, +0x1C64 match Kaisershot parts 3/6 | PASS | PASS (resource present, moved -0x130) |
| FindStartupDevice internal-CD check at 0x1592 (`move #-36,d0 ...`) and the rvpr caller at 0x3230 (Kaisershot part 2, byte-exact) | PASS | Expected difference: both are absent in Dev (see §4) |
| `PICT` -20137 "Pippin Logo" (125x125, PICT v2); 1.0 at 0x2ABC50 | PASS | PASS |
| Logo routine at 0xE3C pushes #-20137 and calls `_GetPicture` (Pippin Kickstart 1.1) | PASS | PASS |
| Native SCSI Manager = `'nitt' 43 "Native 4.3"`: code offset 0xB854 is a function start (after a `blr`); a data-section transition vector targets code+0xBAD4; code size - 0xB854 = 35,536 bytes, exactly Kickstart's "35K block" | PASS | PASS |
| "PipPCI" string | Not present: the model string is "Open Firmware, 1.0.5" (0x340F94). Kaisershot's "PipPCI" came from a ROM 1.2 console. | same |
| `'iNiT'` 1 and `'iNiT'` "Install XFS" exist; the `'nint'` 43 PEF exports `InitAnimation` (Kaisershot part 2) | PASS | PASS |
| ConfigInfo BootstrapVersion "Boot Pip 0.1"; emulator signature string at 0x36E7C0 | PASS | PASS |

## 4. Kinka 1.0 vs Kinka Dev

Full report: [`disasm/diff-1.0-vs-dev.md`](../disasm/diff-1.0-vs-dev.md). All of the following is verified.

**The upper megabyte is identical.** The PPC startup code, NanoKernel, HWInit .text, Open Firmware (native and FCode),
emulator, opcode table and blobs are the same in both ROMs. Only ConfigInfo's checksum words, the HWInit XCOFF timestamp
and the HWInit string-table tail differ.

**The 68K main code is 304 bytes shorter in Dev.** That shifts all 300 resources by -0x130. Of 850 non-padding regions:

- 110 are identical at the same offset.
- 424 are identical but moved.
- 301 resource entries and the list header differ only in their absolute offsets.
- 15 regions really differ.

**Substantive 68K changes.** Only three hunks remain after filtering out pure address/displacement shifts:

1. **0x1556-0x15E6, FindStartupDevice.** 1.0 boots only from the internal CD. It checks for refNum -36 (.AppleCD), calls
   the rvpr authentication through 0x3230, and on failure ejects and restarts. Dev drops the -36 check and the
   authentication call. It goes straight to `_HideCursor` and boot, so the Dev ROM boots unsigned media from any drive.
2. **0x20B0, branch-island table.** It holds one fewer `bra.l` stub; this is the 1.0 trampoline used by the auth path
   (Kaisershot's "mysterySub1/3").
3. **0x31D0-0x32BA.** 1.0's authentication parameter block (`$4B` at 0x31D0, data at 0x31E0) and the
   `'rvpr'`-loading routine at 0x3230 are absent in Dev. There, a small Gestalt-style function testing `'pipn'` sits at
   0x3180. No `'rvpr'` OSType literal remains in Dev's 68K code; the resource is still in the map but nothing visible
   loads it.

**PEF resources.** Six PEF resources differ: `ndrv` 505, `nitt` 43, `nint` 43, `ndrv` 110, `nsnd` -16501 and `nift`
-16572. For most of them only the container timestamp/version words differ. Code changes:

- **`nitt` 43, the SCSI Manager: 9 bytes in 4 places** (code +0xC1F0, +0xC394, +0xC3A0, +0xCEDC). 1.0 does
  `cmpwi rX,3; beq ok` and otherwise errors with -0x1EBC, so it only talks to SCSI ID 3, the internal CD. Dev does
  `cmpwi rX,7; ble ok`, so any ID 0-7 is accepted. This is exactly the "nine bytes in four locations" that Pippin
  Kickstart 1.1 patches to "behave identically to the version in the Pippin GM Flash ROM". It also places the Pippin's
  CD at **SCSI ID 3**, consistent with MAME and retrostuff.
- **`ndrv` 110: 31 bytes in 4 functions** (code +0x4818-0x48C7, +0x4F4C-0x4F76, +0x59A0-0x59AB). It is not yet
  analysed.

The DeclData format block differs in 5 bytes (CRC/date).

## 5. Notes for the FPGA core

Everything in this section was read from `disasm/kinka-1.0/ppc_exception_table.s` (0xFFF0xxxx) and is identical in Dev.
Interpretations are marked **[inference]**.

### Startup sequence

1. **Reset.** The 0x100 vector branches to the cold start at **0xFFF03000** when SRR1 says so. The cold start reads
   **PVR** and has separate HID0 setups for PVR 1 (601), 3/6/7 (603/603e/603ev) and 4 (604). The core's CPU must return a
   valid 603-family PVR. The 604 path writes 604-only performance SPRs (952/953/954/959).
2. **0xFFF03148 clears all BATs.** It then builds new BAT values. The constants such as 0xF0000000 seen there are BAT
   values, not VRAM accesses.
3. **First device MMIO, at 0xFFF03694: PCI configuration of Grand Central through Aspen.**
   - It writes 0x00002810 to **0xF2800000** (CONFIG_ADDR, plain `stwx`).
   - It writes **0xF3000000** to **0xF2C00000** (CONFIG_DATA, byte-reversed `stwbrx`), which sets GC's BAR0.
   - It then selects 0x2804 (command register) and writes 0x16.
   - It writes 0x80000000 byte-reversed to GC InterruptMask (0xF3000024).

   This confirms that the ROM itself places GC at 0xF3000000, as README §1.2 assumes. **[inference]** 0x2810/0x2804 are
   Bandit-style config addresses (IDSEL bit 13 → GC, register 0x10 = BAR0, register 0x04 = command).
4. **Taos GPIO.** It writes GPIO_OUT (0xF0800070) = 0 and GPIO_CONFIG (0xF080006C) = 0x10000000. Later GPIO_OUT is set
   to 0x10000000.
5. **0xFFF05344: save flash probe at 0x40000000.** It issues the Am29F010 command sequence at offsets **0x15554** and
   **0xAAA8**, which are 0x5555 and 0x2AAA times 4, so there is one flash byte per 32-bit word. The data values are
   **bit-reversed**: 0x55 for 0xAA, 0xAA for 0x55, 0x09 for 0x90. This confirms MAME's model (byte lane D0-D7,
   bit-reversed).
6. **0xFFF03E98: memory sizing through Aspen.**
   - It writes **MEM_CONFIG (0xF8000018) = 0xAA000000** first.
   - It probes banks at **0x00000000, 0x01000000, 0x02000000 and 0x03000000** (16 MB spacing, as in DingusPPC).
   - It reads and modifies **GPIO_ENABLE/GPIO_OUT** (it sets bit 0x20000000) and tests **GPIO_IN bit 0x10000000**. That
     bit adds 0x00800000 to the final MEM_CONFIG value.
7. **0xFFF04804: VIA/Cuda at 0xF3016000.** It accesses vBufB, vDirB, vDirA, vACR, vPCR, vIER, vT1CH, vT1L and vBufA,
   with the 0x200 register stride. ConfigInfo LowMemInit also sets low-memory 0x1D4 = 0xF3016000 (the VIA base).

### NVRAM

NVRAM sits behind GC's IOBus with an **address latch at 0xF301D000** (`stwbrx` of addr>>5) and **data at
0xF301F000 + (addr & 0x1F) << 4** (byte stride 16). The routines are at 0xFFF050B4-0xFFF05160. HWInit and the native OF
use the same pattern.

### Registers the emulators do not model

**Aspen** registers accessed but absent from DingusPPC's `aspen.h` enum:

- reads at +0x00
- +0x20, +0x40, +0x50, +0x60, +0x70
- byte accesses at **+0xE0/+0xF0**
- +0x150, +0x1B0, +0x1C0, +0x500

A pointer to **0xF8100000** is also built. The core needs at least benign read/write behaviour for these.
**[inference]** They are memory/arbiter configuration registers.

### VRAM used as boot-state scratch

**[inference]** The PPC code writes halfword 0xE2, and later 0xE1, to **0xF00DFFFA**. The 68K boot path tests and
writes the byte at **0xF00DFFF8**. In 1.0, FindStartupDevice loops while that byte is 0. VRAM must therefore exist and
retain these values at least up to 0xF00DFFFF, so Taos VRAM needs ≥ 0xE0000 bytes at 0xF0000000.

### SCSI

The 1.0 SCSI Manager only accepts target **ID 3** (see §4). The ROM contains SIMs for both "NCR 53c96" (Curio, at GC
+0x10000) and "MESH". Open Firmware has a `mesh` FCode driver (AAPL,343S1146) and no 53C94/Curio FCode. **[inference]**
This favours MAME's choice of the CD on MESH for the D2 question, but it does not settle it, because the Mac OS SIM
supports both.

### ConfigInfo values (both ROMs)

| Field | Value |
|---|---|
| LA_InterruptCtl | 0xF3000000 |
| InterruptHandlerKind | 6 |
| Emulator code / dispatch table logical addresses | 0x68060000 / 0x68080000 (BAT 0x68000000 → ROM+0x300000) |
| LA_OpenFirmware | 0xFF800000 |
| PA_OpenFirmware | 0x00200000 |
| LA_HardwarePriv | 0xFFF0C000 |
| LowMemInit | [0x4] = 0xFFC0002A, [0xC20] = 0x028001E0, [0x104] = 0x50, [0x824] = 0, [0x1D4] = 0xF3016000 |

The Open Firmware node addresses FF8xxxxx in Kaisershot's dump fit the LA_OpenFirmware mapping.

### Relation to docs/core-dev/README.md

No contradictions were found. The ROM confirms:

- GC at 0xF3000000, assigned by the ROM itself
- Aspen at 0xF8000000 with MEM_CONFIG at +0x18 and GPIO at +0x30/+0x34/+0x38
- PCI config at 0xF2800000/0xF2C00000
- Taos registers at 0xF0800000
- flash at 0x40000000, byte lane D0-D7 and bit-reversed
- RAM banks on 16 MB boundaries
- CD at SCSI ID 3

Additions: the extra Aspen registers listed above, the use of VRAM as scratch, and the fact that the ROM checks PVR.
"PipPCI" (§1.7 by way of part 5) is a ROM 1.2 string, not 1.0.

## 6. Gaps

- The 68K and PPC listings are linear sweeps. Data islands decode as junk; there is no control-flow-based code/data
  separation.
- Function names are available only where the ROM carries them:
  - PEF exports, internal transition vectors and CFM glue stubs
  - HWInit XCOFF symbols
  - OF Forth headers
  - traceback tables (the ROM PEFs appear to have none)

  The 68K main code, the NanoKernel and the emulator have no symbols.
- The trap-name table (multiversal) lacks some private traps, for example $A085. These are flagged, not guessed.
- Open Firmware is decoded. The native kernel is disassembled with word labels and the FCode is detokenised. FCode
  tokens defined headerless (`new-token`) remain unnamed, as in the ROM.
- These parts are only partly interpreted: the PCI-match fields of the FCode descriptors, the `fTBL`/`cTBL`/128-byte
  `PICT` blobs and their consumer, and the `ndrv` 110 differences.
