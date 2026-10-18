| probe_boot.s — HFS boot block that asks one question of a PowerPC Mac:
| does code reached from the boot blocks run in supervisor mode?
|
| The ROM boots this partition exactly as it boots the 040 bench disks
| (bbVersion $D000: the ROM jumps to bbEntry with the Apple_Driver43
| loaded and our drive in BootDrive). We are 68k code under the ROM's
| 68k emulator. We build a Mixed Mode routine descriptor around a
| PowerPC routine held in this block and call it through the emulator's
| $AAFE trap, the way every native routine is called on a PowerPC Mac.
| The PowerPC routine executes mfmsr (and, in a second call, mfspr PVR):
| privileged instructions. Before and after each call a record is
| written to /Results on this partition with the driver's _Write:
|
|   word 0  'PRB1'            the boot block ran
|   word 1  'CAL0'            about to call a harmless PowerPC routine (li r3,$5050)
|   word 2  $00005050         Mixed Mode works from a boot block
|   word 3  'CAL1'            about to call the PowerPC routine (mfmsr)
|   word 4  MSR as returned   the call came back: this word is the MSR
|   word 5  'CAL2'            about to call again (mfspr PVR)
|   word 6  PVR as returned
|   word 7  'DONE'
|
| Words 0-1 only: the Mixed Mode call itself failed (no PowerPC code can
| be reached this way). Words 0-3 only: the PowerPC code did not return
| from mfmsr: the privileged instruction trapped, so emulated code runs
| in user mode and the supervisor tier needs another way in. Word 4
| present with MSR[PR] (value $4000) clear: boot blocks ARE a
| supervisor-mode route, and super603's blob can be loaded and run from
| here (the next step).
|
| Assemble: m68k-apple-macos-as -m68020 -o probe_boot.o probe_boot.s
| The PowerPC words are hand-assembled: mfmsr r3 = 7C6000A6,
| mfspr r3,PVR = 7C7F42A6, blr = 4E800020.
|
| Layout rule: everything is PC-relative, nothing is relocated; the
| block is written to the first two sectors of the HFS partition
| (1024 bytes). RESOFF is patched by build_probe.py with /Results'
| byte offset in the partition.

    .text
    .global _start
_start:
    .ascii  "LK"
bbEntry:
    bra.w   startup
bbVersion:    .word 0xD000
bbPageFlags:  .word 0
bbSysName:    .byte 6;  .ascii "System";          .space 9
bbShellName:  .byte 6;  .ascii "Finder";          .space 9
bbDbg1Name:   .byte 7;  .ascii "Macsbug";         .space 8
bbDbg2Name:   .byte 12; .ascii "Disassembler";    .space 3
bbScreenName: .byte 13; .ascii "StartUpScreen";   .space 2
bbHelloName:  .byte 6;  .ascii "Finder";          .space 9
bbScrapName:  .byte 14; .ascii "Clipboard File";  .space 1
bbCntFCBs:        .word 10
bbCntEvts:        .word 20
bbHeapSize128K:   .long 0x00004300
bbHeapSize256K:   .long 0x00008000
bbHeapSize:       .long 0x00020000

PB_OFF_IORESULT     = 16
PB_OFF_IOVREFNUM    = 22
PB_OFF_IOREFNUM     = 24
PB_OFF_IOBUFFER     = 32
PB_OFF_IOREQCOUNT   = 36
PB_OFF_IOPOSMODE    = 44
PB_OFF_IOPOSOFFSET  = 46
PB_SIZE             = 80
DRVQHDR_QHEAD       = 0x0000030A
BOOTDRIVE           = 0x00000210
DRVQEL_OFF_QLINK    = 0
DRVQEL_OFF_DQDRIVE  = 6
DRVQEL_OFF_DQREFNUM = 8
WORK                = 0x00080000        | scratch RAM: record (512 B) at +0, pb at +512, TVector at +1024

startup:
    move.w  #0x2700, %sr
    | our drive's driver refnum, from the drive queue
    move.w  BOOTDRIVE.l, %d4
    moveal  DRVQHDR_QHEAD.l, %a1
    moveq   #0, %d5
.scan:
    cmp.l   #0, %a1
    beq     halt
    cmp.w   DRVQEL_OFF_DQDRIVE(%a1), %d4
    beq.s   .found
    moveal  DRVQEL_OFF_QLINK(%a1), %a1
    addq.l  #1, %d5
    cmpi.l  #32, %d5
    blt.s   .scan
    bra     halt
.found:
    move.w  DRVQEL_OFF_DQREFNUM(%a1), %d6
    | the record: zero it, word 0 = 'PRB1'
    lea     WORK, %a2
    move.l  %a2, %a0
    move.w  #127, %d0
1:  clr.l   (%a0)+
    dbra    %d0, 1b
    move.l  #0x50524231, (%a2)              | 'PRB1'
    bsr.w   write_record
    | the TVector: code address, TOC (unused)
    lea     ppc_echo(%pc), %a0
    move.l  %a0, WORK+1024
    clr.l   WORK+1028
    lea     desc(%pc), %a0
    move.l  #WORK+1024, 20(%a0)             | routineRecords[0].procDescriptor (12 + 8)
    moveq   #1, %d0
    .word   0xA198                          | _HwPriv FlushInstructionCache: the PowerPC code is data the ROM just loaded
    move.l  #0x43414C30, 4(%a2)             | 'CAL0'
    bsr.w   write_record
    lea     desc(%pc), %a0
    jsr     (%a0)                           | $AAFE: Mixed Mode switches to the PowerPC routine
    move.l  %d0, 8(%a2)                     | $5050 if it came back
    bsr.w   write_record
    lea     ppc_mfmsr(%pc), %a0
    move.l  %a0, WORK+1024
    move.l  #0x43414C31, 12(%a2)            | 'CAL1'
    bsr.w   write_record
    lea     desc(%pc), %a0
    jsr     (%a0)
    move.l  %d0, 16(%a2)                    | the MSR
    bsr.w   write_record
    lea     ppc_mfpvr(%pc), %a0
    move.l  %a0, WORK+1024
    move.l  #0x43414C32, 20(%a2)            | 'CAL2'
    bsr.w   write_record
    lea     desc(%pc), %a0
    jsr     (%a0)
    move.l  %d0, 24(%a2)                    | the PVR
    move.l  #0x444F4E45, 28(%a2)            | 'DONE'
    bsr.w   write_record
halt:
    bra.s   halt

| write the 512-byte record at WORK to /Results (partition offset RESOFF)
write_record:
    lea     WORK+512, %a0
    moveq   #(PB_SIZE/4)-1, %d0
1:  clr.l   (%a0)+
    dbra    %d0, 1b
    lea     WORK+512, %a0
    move.w  %d6, PB_OFF_IOREFNUM(%a0)
    move.w  %d4, PB_OFF_IOVREFNUM(%a0)
    move.l  #WORK, PB_OFF_IOBUFFER(%a0)
    move.l  #512, PB_OFF_IOREQCOUNT(%a0)
    move.w  #1, PB_OFF_IOPOSMODE(%a0)
    move.l  resoff(%pc), PB_OFF_IOPOSOFFSET(%a0)
    .word   0xA003                          | _Write (synchronous)
    rts

    .align 4
    .ascii  "RESOFF__"
resoff: .long   0xDEADBEEF

| the Mixed Mode routine descriptor (version 7, one register-based
| PowerPC routine returning a long in D0: procInfo = kRegisterBased |
| RESULT_SIZE(kFourByteCode) | REGISTER_RESULT_LOCATION(kRegisterD0))
    .align 4
desc:
    .word   0xAAFE                          | goMixedModeTrap
    .byte   7                               | version
    .byte   0                               | routineDescriptorFlags
    .long   0                               | reserved1
    .byte   0                               | reserved2
    .byte   0                               | selectorInfo
    .word   0                               | routineCount (one routine: count - 1)
    | RoutineRecord
    .long   0x00000032                      | procInfo
    .byte   0                               | reserved1
    .byte   1                               | ISA = kPowerPCISA
    .word   0                               | routineFlags
    .long   0                               | procDescriptor (patched at run time)
    .long   0                               | reserved2
    .long   0                               | selector

| the PowerPC routines (big-endian words; r3 is the result)
    .align 4
ppc_echo:
    .long   0x38605050                      | li r3, 0x5050
    .long   0x4E800020                      | blr
ppc_mfmsr:
    .long   0x7C6000A6                      | mfmsr r3
    .long   0x4E800020                      | blr
ppc_mfpvr:
    .long   0x7C7F42A6                      | mfspr r3, PVR
    .long   0x4E800020                      | blr
