# Apple Pippin technical documents: index

These are reference documents collected for the Apple/Bandai Pippin (@WORLD / Atmark) MiSTer FPGA core.
Every `.pdf` file was checked for a `%PDF` header and opened with `pdfinfo`. Page counts come from `pdfinfo`.
Total size is about 190 MB. The files are in the git-ignored `scratch/pdfs/` folder; paths below are relative to it.

**Chip list.** The authoritative source is MAME `src/mame/apple/pippin.cpp`, saved as `emulator_notes/MAME_pippin_driver_src.cpp.txt`:

- **Apple ASICs**
  - 343S0152 **Aspen**: Bandit-derived PCI host bridge and RAM controller.
  - 343S0153 **Taos**: 640x480 framebuffer and CRTC, with convolution for NTSC/PAL. MAME notes it resembles the Quadra **DAFB**.
  - 343S1125 **Grand Central**: SWIM III, sound (AWACS), VIA, SCC, and DBDMA.
  - 341S0060 **Cuda**: a 68HC05E1-based ADB/PRAM/RTC/power MCU.
  - 343S1146 **MESH**: customized 53C9x SCSI controller.
  - 2x **Athens Prime**: PLL clock generator.
- **Other chips:** Z8530 SCC, Crystal CS4217 audio codec/DAC, Bt856 composite/S-video encoder (I2C), and AMD Am29F010 flash for game saves (bit-reversed bus).
- **Closest documented relatives.** Pippin's architecture comes from the first-generation PCI Power Macs (7200, 7500, 8500 and 9500), which use Bandit + Grand Central + MESH + Cuda + AWACS. It does not derive from the 5200/6200 "PDM/Capella" line. That is why the `related_macs/` folder holds the 7200, 7500/8500 and 9500 documents.

## apple/: Apple Pippin documents

| File | Title | Size | Pages | Source | FPGA relevance |
|---|---|---|---|---|---|
| `apple/PPDV-ES001-DM_The_66_Most_Asked_Questions_Regarding_Pippin_Mar95.pdf` | The 66 Most Asked Questions Regarding Pippin (Mar 1995) | 2.2M | 22 | http://www.bitsavers.org/pdf/apple/mac/pippin/PPDV-ES001-DM_The_66_Most_Asked_Questions_Regarding_Pippin_Mar95.pdf | Early platform overview: CPU, memory, video, CD, and expansion goals. |
| `apple/tech_info_library/TIL_Pippin_Tech_Specs.pdf` | Pippin: Technical Specifications (TIL, 9/95) | 8K | 2 | https://discmaster.textfiles.com/file/30834/Service%20Source%202.0%201996%20Companion.iso/Technical%20Info%20Library/Tech%20Info%20Library/Pippin/Pippin%20%20Tech%20Specs | Official spec sheet: 6 MB shared RAM, 64 KB backup SRAM, dual framebuffers, 8/16-bit video, NTSC/PAL/VGA. |
| `apple/tech_info_library/TIL_Pippin_QA_Part1of2.pdf` | Pippin: Questions and Answers part 1 (TIL, 1/96) | 12K | 5 | same dir, `Pippin  Q - A (1 of 1)` | Background and platform positioning. |
| `apple/tech_info_library/TIL_Pippin_QA_Part2of2.pdf` | Pippin: Questions and Answers part 2 (TIL, 9/95) | 8K | 3 | same dir, `Pippin  Q - A (2 of 2)` | Background. |
| `apple/pippin_technotes/Pippin_Startup_Process.pdf` | Pippin Startup Process | 28K | 3 | https://discmaster.textfiles.com/browse/32723/Dev.CD%20Dec%2096%20RL/Dev.CD%20Dec%2096%20RL.toast/Technical%20Documentation/Pippin%20Technical%20Notes (all technotes below come from this Dec 1996 Dev CD dir) | The boot sequence from ROM to CD. Needed to understand what the ROM expects at boot. |
| `apple/pippin_technotes/Pippin_Authentication.pdf` | Pippin Authentication | 32K | 3 | Dev CD Dec 96 | The CD authentication scheme that the ROM enforces. |
| `apple/pippin_technotes/Creating_Pippin_CDROMs.pdf` | Creating Pippin CD-ROMs | 156K | 13 | Dev CD Dec 96 | Boot CD layout, useful for testing boot media. |
| `apple/pippin_technotes/Pippin_Video.pdf` | Pippin Video (PPBD-JSEF002) | 60K | 8 | Dev CD Dec 96 | PippinVideo.h: Taos video modes, convolution/flicker, NTSC/PAL, double buffering, from the software side. |
| `apple/pippin_technotes/Pippin_Flash_Access.pdf` | Pippin Flash Access | 20K | 2 | Dev CD Dec 96 | API for the save-game flash (Am29F010). |
| `apple/pippin_technotes/Applejack_Tech_Note.pdf` | AppleJack Tech Note | 120K | 10 | Dev CD Dec 96 | AppleJack ADB controller protocol and behaviour. |
| `apple/pippin_technotes/Pippin_Launch.pdf` | Pippin Launch | 64K | 7 | Dev CD Dec 96 | Software (app launch). Low relevance. |
| `apple/pippin_technotes/Pippin_Standard_File.pdf` | Pippin Standard File | 28K | 3 | Dev CD Dec 96 | Software API. Low relevance. |
| `apple/pippin_technotes/PippinFinder.pdf` | PippinFinder | 20K | 2 | Dev CD Dec 96 | Software. Low relevance. |
| `apple/pippin_technotes/Pippin_Q_and_A.pdf` | Pippin Q & A (developer) | 112K | 21 | Dev CD Dec 96 | Developer Q&A, with some hardware notes (RAM, video, ADB). |
| `apple/pippin_technotes/Stopping_INIT_Icons.pdf` | Stopping INIT Icons (original filename typo "Stoppinf") | 44K | 2 | Dev CD Dec 96 | Software. Low relevance. |

## bandai/: Bandai consumer documents

| File | Title | Size | Pages | Source | FPGA relevance |
|---|---|---|---|---|---|
| `bandai/Pippin_atWORLD_Atmark_User_Manual.pdf` | Pippin @WORLD User's Manual (also applies to Atmark) | 14M | 51 | https://archive.org/download/apple-pippin-bandai-atmark/apple-pippin-bandai-atmark.pdf | Ports, controller, video outputs and user-visible boot behaviour. |
| `bandai/Bandai_Pippin_atWORLD_Quick_Setup_Guide.pdf` | @WORLD Quick Setup Guide | 172K | 1 | https://archive.org/details/bandai-pippin-world-qsg | Connections overview. |

## related_macs/: Power Macintosh relatives (Bandit / Grand Central / MESH generation)

| File | Title | Size | Pages | Source | FPGA relevance |
|---|---|---|---|---|---|
| `related_macs/DevNote_Power_Macintosh_7500_8500.pdf` | Developer Note: Power Macintosh 7500 & 8500 | 676K | 110 | Dev CD Dec 96 `Developer Notes/Macintosh CPUs - PPC Desktop/Power Macintosh 7500 & 8500` (discmaster id 32723) | **Key document.** Bandit, Grand Central (I/O map, DBDMA, interrupts), MESH, Cuda, AWACS and SWIM III. This is Pippin's I/O architecture. |
| `related_macs/DevNote_Power_Macintosh_7200.pdf` | Developer Note: Power Macintosh 7200 | 568K | 90 | Dev CD Dec 96 (same dir) | Bandit + Grand Central with 53C94 SCSI and Cuda. A close relative. |
| `related_macs/DevNote_Power_Macintosh_9500.pdf` | Developer Note: Power Macintosh 9500 | 464K | 82 | Dev CD Dec 96 (same dir) | Bandit/Grand Central/MESH, with a different emphasis. |
| `related_macs/DevNote_Power_Macintosh_6100_7100_8100.pdf` | Developer Note: Power Macintosh Computers (6100/7100/8100) | 948K | 100 | Dev CD Dec 96 (same dir) | First-generation (NuBus/AMIC) machines. Has Cuda, AWACS and SWIM III background, plus 601 bus details. |
| `related_macs/TNT_8500_7500_ERS_19950705.pdf` | Power Macintosh 8500/7500 ("TNT") System ERS, 062-1457 Rev A, 1995-07-05 (Apple internal) | 8.3M | 87 | https://tinkerdifferent.com/attachments/tnt_8500_7500_ers_19950705-pdf.29037/ | **Very high value.** The internal engineering spec, with detailed Bandit, Grand Central and DBDMA register-level material. |
| `related_macs/Designing_PCI_Cards_and_Drivers_for_Power_Macintosh.pdf` | Designing PCI Cards and Drivers for Power Macintosh Computers (PCI DDK 3.0 edition) | 2.9M | 616 | https://discmaster.textfiles.com/browse/32816/Dev.CD%20Apr%2000%20SDK1.toast/Development%20Kits/Hardware/PCI%20DDK%203.0/PCI%20DDK%203.0/%E2%80%A2%20Documentation/Designing%20PCI%20Cards%26Drivers | Bandit PCI bridge behaviour, Mac PCI address map, endianness/byte swapping and the Open Firmware device tree. Relevant to the Aspen PCI side. |
| `related_macs/Display_Device_Driver_Guide.pdf` | Display Device Driver Guide | 272K | 42 | Dev CD Dec 96 `Developer Notes/System Software` | How MacOS drives the framebuffer (cscSetEntries, gamma). Helps when reasoning about Taos driver behaviour. |

## chips/: datasheets and manuals

| File | Title | Size | Pages | Source | FPGA relevance |
|---|---|---|---|---|---|
| `chips/1997_MPC603EUM_MPC603e_EC603e_Users_Manual_Rev_1.pdf` | MPC603e/EC603e RISC Microprocessor User's Manual (Rev 1, 1997) | 34M | 462 | http://www.bitsavers.org/components/motorola/PowerPC/1997_MPC603EUM_MPC603e_EC603e_Users_Manual_Rev_1.pdf | **CPU core reference.** Covers the 603 too; Appendix C lists the 603-vs-603e differences. Includes the pipeline, MMU/TLB, caches and the 60x bus. |
| `chips/MPCFPE32B_PowerPC_Programming_Environments_for_32-Bit_Microprocessors_Jan97.pdf` | PowerPC Programming Environments Manual (32-bit) | 38M | 702 | http://www.bitsavers.org/components/motorola/PowerPC/MPCFPE32B_PowerPC_Programming_Environments_for_32-Bit_Microprocessors_Jan97.pdf | ISA reference: instruction encodings, exceptions and the BAT/segment MMU. |
| `chips/1997_MPCBUSIF_The_Bus_Interface_for_32-Bit_Microprocessors.pdf` | The Bus Interface for 32-Bit Microprocessors (60x bus) | 16M | 264 | http://www.bitsavers.org/components/motorola/PowerPC/1997_MPCBUSIF_The_Bus_Interface_for_32-Bit_Microprocessors.pdf | 60x bus protocol (address/data tenures, ARTRY, burst). Needed for the CPU-to-Aspen interface. |
| `chips/Motorola_MPC603_Technical_Summary_1994.pdf` | MPC603 Technical Summary (MPC603/D, 6/94) | 520K | 28 | https://docs.ampnuts.ru/nxp.com.datasheet/MPC603.pdf | The original (non-e) 603 overview. |
| `chips/Motorola_MPC603e_Hardware_Specifications_Rev3_1997.pdf` | MPC603e Hardware Specifications (MPC603EC/D Rev 3) | 264K | 31 | https://docs.ampnuts.ru/nxp.com.datasheet/MPC603EC.pdf | Pinout and bus timing (603e). |
| `chips/00-2057-03_Z8030_Z-BUS_SCC_Z8530_SCC_Serial_Communications_Controller_Technical_Manual_Sep1986.pdf` | Zilog Z8030/Z8530 SCC Technical Manual (1986) | 12M | 114 | http://www.bitsavers.org/components/zilog/_dataBooks/00-2057-03_Z8030_Z-BUS_SCC_Z8530_SCC_Serial_Communications_Controller_Technical_Manual_Sep1986.pdf | The SCC inside Grand Central (serial/GeoPort; Open Firmware console). |
| `chips/MC68HC05E1_General_Release_Specification.pdf` | MC68HC05E1 General Release Specification | 1.0M | 86 | http://www.bitsavers.org/components/motorola/6805/_dataSheets/MC68HC05E1_General_Release_Specification.pdf | **Cuda** is a 68HC05E1 with mask ROM. Needed to run the real Cuda firmware in an HC05 soft core. |
| `chips/MC68HC05E5GRS_199702.pdf` | MC68HC05E5 General Release Specification | 1.4M | 140 | http://www.bitsavers.org/components/motorola/6805/_dataSheets/MC68HC05E5GRS_199702.pdf | The Cuda Lite / Cuda 3.x variant. For reference. |
| `chips/6805_Users_Manual_2ed_1983.pdf` | M6805 Family User's Manual, 2nd ed. | 7.5M | 263 | http://www.bitsavers.org/components/motorola/6805/6805_Users_Manual_2ed_1983.pdf | HC05 CPU core instruction set and timing. |
| `chips/NCR_53C94_53C95_53C96_Data_Sheet_Feb90.pdf` | NCR 53C94/95/96 Data Sheet (1990) | 2.9M | 64 | https://cdn.hackaday.io/files/18974811783616/NCR_53C94_53C95_53C96_Data_Sheet_Feb90.pdf | MESH is a heavily customized 53C9x. Base register and command semantics. |
| `chips/NCR_53CF94_96-2_Fast_SCSI_Controller_Data_Manual_Apr1993.pdf` | NCR 53CF94/96-2 Fast SCSI Controller Data Manual | 7.8M | 130 | http://www.bitsavers.org/components/ncr_symbios/scsi/53CF94/53CF94_96-2_Fast_SCSI_Controller_Data_Manual_Apr1993.pdf | Same as above, a later variant. |
| `chips/Brooktree_Bt856_Bt857_Video_Encoder_Datasheet.pdf` | Bt856/Bt857 YCrCb to NTSC/PAL Digital Video Encoder | 640K | 54 | http://mjpeg.sourceforge.net/driver-zoran/datasheets/bt856.pdf (via web.archive.org) | The composite/S-video encoder after Taos. Its I2C registers are programmed by the ROM through Cuda. |
| `chips/AMD_Am29F010_Flash_Datasheet.pdf` | AMD Am29F010 1 Mbit Flash | 112K | 29 | https://elby-designs.com/webtek/datasheets/am29f010.pdf | The save-game flash at 0x40000000. The command set (autoselect/program/erase) must be emulated. |
| `chips/Crystal_CS4215_CS4216_Audio_Codecs_1994_Databook_excerpt.pdf` | Crystal CS4215/CS4216 serial codecs, an excerpt (pp. 265-398) of the 1994 Crystal Audio Databook | 30M | 134 | http://www.bitsavers.org/components/crystalSemiconductor/_dataBooks/1994_Crystal_Semiconductor_Audio_Databook.pdf | The CS4217 itself has no public datasheet. The CS4215/4216 are the closest documented family members (serial codec framing). The AWACS-side framing is in the DingusPPC/MAME notes. |

## cdrom/: CD-ROM drive

| File | Title | Size | Pages | Source | FPGA relevance |
|---|---|---|---|---|---|
| `cdrom/Apple_CD-ROM_Handbook.pdf` | Apple CD-ROM Handbook | 768K | 158 | Dev CD Dec 96 `Technical Documentation/Peripherals Documentation/Apple CD-ROM Handbook` | **Key document for the CD path.** Apple's SCSI CD-ROM command set, including the vendor-specific audio commands that AppleCD drivers use. |
| `cdrom/Panasonic_CR-501_Product_Specification_Dec90.pdf` | Panasonic CR-501 Product Specification (1990) | 4.8M | 93 | http://www.bitsavers.org/pdf/panasonic/cdrom/CR-501_Product_Specification_Dec90.pdf | An earlier member of the Matsushita CR-50x SCSI family (Pippin uses a CR-504-L). Covers the SCSI command set and mode pages. |
| `cdrom/Sony_CDU75S_PCM-1715U_Datasheet.pdf` | Burr-Brown PCM1715U audio DAC datasheet (from the Sony CDU75S dir) | 128K | 10 | http://www.bitsavers.org/pdf/sony/cdrom/CDU75S/PCM-1715U_Datasheet.pdf | CD audio DAC on the CDU75S drive. Low relevance. |

The three bitsavers directories named in the article contain **only one PDF**, the PCM-1715U file above. The rest is firmware dumps and photos, which were not downloaded:

- `CR-504-J_4X_SCSI/CR-504-J_SS1704-0_dump+readme.zip`
- `CR-504-K_.../firmware/504par4.0i.bin`
- `CDU75S/firmware/*.bin|*.hex`
- PCB photos

The firmware dumps could matter later if the drive MCU is emulated. MAME's Pippin driver contains a Panasonic MN1880 "cdmcu" map.

## components/: passives and EPROM (repair/board-level)

| File | Title | Size | Pages | Source | Note |
|---|---|---|---|---|---|
| `components/UCC_SXE_Electrolytic_Capacitors.pdf` | Nippon Chemi-Con/UCC SXE series | 120K | 4 | https://media.it-tronics.de/Datasheets/Capacitors/E-Caps/UCC/SXE.pdf | Recap reference (board repair, not core logic). |
| `components/ChemiCon_KME_Electrolytic_Capacitors.pdf` | Nippon Chemi-Con KME series | 64K | 3 | https://www.chemi-con.co.jp/catalog/pdf/bulletin/al-kme-bulleti512e-e-050712.pdf (live URL returns an error page; fetched via `https://web.archive.org/web/2020id_/...`) | Recap reference. |
| `components/National_NM27C512_EPROM_Datasheet.pdf` | National NM27C512 64Kx8 CMOS EPROM | 184K | 10 | https://deramp.com/downloads/mfe_archive/050-Component%20Specifications/National%20Semiconductor/Memory%20Components/National%20NM27C512.pdf | EPROM referenced by the retrostuff article. |

## emulator_notes/: non-PDF reference text

| File | Content | Source | FPGA relevance |
|---|---|---|---|
| `emulator_notes/MAME_pippin_driver_src.cpp.txt` | MAME `pippin.cpp` (BSD-3), snapshot | https://github.com/mamedev/mame/blob/master/src/mame/apple/pippin.cpp | The authoritative chip list, memory map, RAM mirroring quirks and flash wiring. Companion files are in the same dir upstream: `bandit.cpp` (Aspen), `taos.cpp`, `heathrow.cpp` (Grand Central), `cuda.cpp`, `mesh.cpp`, `athensprime.cpp`, `awacs_macrisc.cpp`. |
| `emulator_notes/dingusppc_zdocs/*.md` | DingusPPC developer notes: adb, awacs, dbdma, heathrow, memorymaps, mesh, misc, swim3, viacuda, openfirmware, powerpc, mmu | https://github.com/dingusdev/dingusppc/tree/master/zdocs/developers | Register-level notes for the Grand Central-family blocks. DingusPPC also has `machines/machinepippin.cpp`, `devices/memctrl/aspen.cpp` and `devices/video/taos.cpp`. |
| `emulator_notes/blitter_net/*.txt` | Keith Kaisershot (blitter), "Exploring the Pippin ROM(s)" parts 2-9, plus "Pippin Kickstart 1.1", as plain-text captures | https://blitter.net/blog/ (fetched via Wayback; blitter.net timed out directly) | ROM internals, boot/authentication flow, SCSI Manager, Open Firmware device tree (Aspen @F2000000, Taos @F0800000, Grand Central offsets: SCC 0x13000, AWACS 0x14000, SWIM3 0x15000, VIA-Cuda 0x16000, MESH 0x18000, NVRAM 0x1D000) and the ROM 1.2 vs 1.3 differences. |

## Not downloaded / worth finding

| Item | Status / where referenced |
|---|---|
| Apple **Service Source for Pippin @WORLD** / Bandai **Atmark service manual** / **schematics** | No public copy found (searched archive.org, bitsavers, discmaster, macintoshrepository and web). Probably never released. retrostuff.org (handled separately) is the best repair reference. |
| Any Apple **Pippin hardware ERS / developer note** (Aspen, Taos, Pippin board) | Not found publicly. The TNT (7500/8500) ERS on tinkerdifferent suggests other Apple ERS leaks exist; a "Pippin ERS" or "Taos ERS" would be the single most valuable find. Worth asking on tinkerdifferent / 68kmla. |
| **Taos video** register docs | None public. Use MAME `taos.cpp` and DingusPPC `taos.cpp`. MAME notes Taos resembles **DAFB**, so the Quadra 700/900 developer notes or DAFB documents could help. |
| **Grand Central / Bandit / Aspen / Athens Prime / CS4217** datasheets | Apple-custom (or Apple-specific) parts with no public datasheets. Covered indirectly by the TNT ERS, the dev notes and the emulator sources. |
| **Macintosh Technology in the Common Hardware Reference Platform** (Apple/Morgan Kaufmann, 1995) | Documents Mac I/O devices (MESH, SWIM3, DBDMA, Cuda-era interfaces). No free PDF located. Cited in CHRP 1.0: https://public.dhe.ibm.com/rs6000/technology/spec/chrp/CHNG_C10.html |
| Original **MPC603UM** (1994, non-e 603 user's manual) | Not found online (68kmla thread asking: https://68kmla.org/bb/threads/looking-for-the-original-powerpc-603-user-manual-not-603e.47599). The 603e manual covers the 603 via Appendix C. |
| Pippin @WORLD user manual on macintoshrepository | https://www.macintoshrepository.org/44515-apple-pippin-world-user-manual- returns "file could not be found". The same 13.96 MB PDF was obtained from archive.org instead. |
| blitter.net "Exploring the Pippin ROM(s)" **part 1** | https://blitter.net/blog/2018/06/07/exploring-the-pippin-roms/ failed on both direct and Wayback fetch. |
| Pippin SDK CDs (DR0, 1.0, 1.1, DR1, Nov 96) | Software. Only the tech notes were extracted. The SDK is on macintoshrepository (https://www.macintoshrepository.org/627-apple-pippin-sdk) and in discmaster "HolyGrail 5/Apple/Pippin SDK.sit". It includes "Pippin Video Sources" (Pippin.h, sample code): https://discmaster.textfiles.com/browse/5527/WWDC96_1996%20(CD).toast/Technology%20Materials/Pippin |
| Atmark Channel Pippin Developer FAQ / Newsletters (Japanese) | https://web.archive.org/web/19980508025046/http://www.channel.or.jp/faq/develop/faq.html |
| incog Pippin scans (archive.org, 87 MB 7z) | https://archive.org/details/incog-pippin-scans. Box/manual scans of titles, not hardware. Skipped. |
| Panasonic **CR-504-L** (the Pippin's drive) manual | Not found. Only firmware dumps exist for CR-504-J/K/C on bitsavers. |
| Sony / Panasonic CD firmware dumps | Listed in the cdrom section; not downloaded (not documents). |
