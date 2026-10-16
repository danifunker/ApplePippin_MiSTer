"""Name tables used to annotate disassembly: Mac OS traps and low-memory
globals (generated from multiversal, see data/*.tsv), PowerPC 603 SPRs, and
the Pippin physical memory map (docs/core-dev/README.md section 1.2, MAME
pippin.cpp/bandit.cpp/heathrow.cpp/taos.cpp, DingusPPC aspen.h/taos.h)."""
import os

_here = os.path.dirname(os.path.abspath(__file__))
_data = os.path.join(os.path.dirname(_here), 'data')


def _load_tsv(name):
    out = {}
    p = os.path.join(_data, name)
    if not os.path.exists(p):
        return out
    for line in open(p, encoding='utf-8'):
        if line.startswith('#') or not line.strip():
            continue
        k, v = line.rstrip('\n').split('\t')[:2]
        out[int(k, 16)] = v
    return out


TRAPS = _load_tsv('traps.tsv')
LOWMEM = _load_tsv('lowmem.tsv')

# OS traps whose bit 10 / bit 9 mean ,SYS / ,CLEAR (Memory Manager) rather
# than ,ASYNC / ,IMMED (File and Device Managers).
_MEMMGR_OS = set(range(0x19, 0x40)) | {0x4F, 0x62, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6A}


def trap_name(w):
    """Name for an A-line word, or None."""
    if (w & 0xF000) != 0xA000:
        return None
    if w & 0x0800:                          # Toolbox trap: 10-bit number, bit 10 = autopop
        base = 0xA800 | (w & 0x3FF)
        n = TRAPS.get(w) or TRAPS.get(base)
        if not n:
            return None
        return '_' + n + (' ,AUTOPOP' if (w & 0x400) and w not in TRAPS else '')
    # OS trap: 8-bit number, bits 8..10 are flags
    num = w & 0xFF
    n = TRAPS.get(w)
    flags = []
    if not n:
        for cand in (0xA000 | num, 0xA100 | num, 0xA200 | num, 0xA300 | num,
                     0xA400 | num, 0xA500 | num, 0xA600 | num, 0xA700 | num):
            if cand in TRAPS:
                n = TRAPS[cand]
                extra = (w ^ cand) & 0x600
                if num in _MEMMGR_OS:
                    if extra & 0x400 or (w & 0x400 and not cand & 0x400): flags.append('SYS')
                    if extra & 0x200 or (w & 0x200 and not cand & 0x200): flags.append('CLEAR')
                else:
                    if w & 0x400 and not cand & 0x400: flags.append('ASYNC')
                    if w & 0x200 and not cand & 0x200: flags.append('IMMED')
                break
    if not n:
        return None
    return '_' + n + (' ,' + ',' .join(flags) if flags else '')


SPR = {
    0: 'MQ', 1: 'XER', 4: 'RTCU', 5: 'RTCL', 8: 'LR', 9: 'CTR', 18: 'DSISR', 19: 'DAR',
    22: 'DEC', 25: 'SDR1', 26: 'SRR0', 27: 'SRR1', 268: 'TBL(r)', 269: 'TBU(r)',
    272: 'SPRG0', 273: 'SPRG1', 274: 'SPRG2', 275: 'SPRG3', 282: 'EAR', 284: 'TBL', 285: 'TBU',
    287: 'PVR',
    528: 'IBAT0U', 529: 'IBAT0L', 530: 'IBAT1U', 531: 'IBAT1L', 532: 'IBAT2U', 533: 'IBAT2L',
    534: 'IBAT3U', 535: 'IBAT3L', 536: 'DBAT0U', 537: 'DBAT0L', 538: 'DBAT1U', 539: 'DBAT1L',
    540: 'DBAT2U', 541: 'DBAT2L', 542: 'DBAT3U', 543: 'DBAT3L',
    # 603-specific (software table-walk) registers
    976: 'DMISS', 977: 'DCMP', 978: 'HASH1', 979: 'HASH2', 980: 'IMISS', 981: 'ICMP', 982: 'RPA',
    1008: 'HID0', 1009: 'HID1', 1010: 'IABR', 1013: 'DABR(601/604)', 1023: 'PIR(601/604)',
    952: 'MMCR0(604)', 953: 'PMC1(604)', 954: 'PMC2(604)', 955: 'SIA(604)', 959: 'SDA(604)',
}

# --------------------------------------------------------------- MMIO map
GC = 0xF3000000
GC_OFFS = [
    (0x00000, 0x00100, 'GC interrupt/ID regs',
     {0x20: 'InterruptEvents', 0x24: 'InterruptMask', 0x28: 'InterruptClear', 0x2C: 'InterruptLevels'}),
    (0x08000, 0x08B00, 'GC DBDMA', None),
    (0x10000, 0x11000, 'GC SCSI0 (53C94 "Curio")', None),
    (0x11000, 0x12000, 'GC Ethernet (MACE)', None),
    (0x12000, 0x13000, 'GC SCC (compat)', None),
    (0x13000, 0x14000, 'GC SCC', None),
    (0x14000, 0x15000, 'GC AWACS (audio)', None),
    (0x15000, 0x16000, 'GC SWIM3', None),
    (0x16000, 0x18000, 'GC VIA (Cuda)', None),
    (0x18000, 0x19000, 'GC SCSI1 (MESH)', None),
    (0x19000, 0x1A000, 'GC +0x19000', None),
    (0x1A000, 0x20000, 'GC IOBus devices (NVRAM at +0x1D000)', None),
]
DBDMA_CH = ['SCSI0', 'floppy', 'ENET-tx', 'ENET-rx', 'SCC-A-tx', 'SCC-A-rx', 'SCC-B-tx',
            'SCC-B-rx', 'audio-out', 'audio-in', 'SCSI1']
VIA_REGS = ['vBufB', 'vBufAH', 'vDirB', 'vDirA', 'vT1C', 'vT1CH', 'vT1L', 'vT1LH', 'vT2C', 'vT2CH',
            'vSR', 'vACR', 'vPCR', 'vIFR', 'vIER', 'vBufA']
TAOS_REGS = {0x00: 'FB_BASE', 0x04: 'ROW_WORDS', 0x08: 'COLOR_MODE', 0x0C: 'VIDEO_MODE', 0x10: 'VEFS',
             0x14: 'VOFS', 0x18: 'HSTART', 0x1C: 'VCONV_END', 0x20: 'CRT_CTRL', 0x24: 'CRT_TEST',
             0x2C: 'HEQ', 0x30: 'HBWAY', 0x34: 'HAL', 0x38: 'HSERR', 0x3C: 'HFP', 0x40: 'HPIX',
             0x44: 'HSP', 0x48: 'HLFLN', 0x4C: 'VBPEQ', 0x50: 'VBP', 0x54: 'VAL', 0x58: 'VFP',
             0x5C: 'VFPEQ', 0x60: 'VSYNC', 0x64: 'VHLINE', 0x68: 'GPIO_IN', 0x6C: 'GPIO_CONFIG',
             0x70: 'GPIO_OUT', 0x74: 'GPIO_INT_CTRL', 0x78: 'INT_LEVELS', 0x7C: 'INT_ENABLES',
             0x80: 'INT_CLEAR', 0x8C: 'TAOS_VERSION', 0x90: 'INT_SET', 0x94: 'HEB'}
ASPEN_REGS = {0x10: 'SYSTEM_ID', 0x14: 'CHIP_REV', 0x18: 'MEM_CONFIG', 0x30: 'GPIO_IN',
              0x34: 'GPIO_ENABLE', 0x38: 'GPIO_OUT'}


def mmio_name(a):
    """Return a short description for a physical address, or None."""
    a &= 0xFFFFFFFF
    if 0xFFC00000 <= a:
        return 'ROM+0x%06X' % (a - 0xFFC00000)
    if 0xF3000000 <= a < 0xF3020000:
        o = a - GC
        for lo, hi, name, regs in GC_OFFS:
            if lo <= o < hi:
                if regs and (o - lo) in regs:
                    return '%s.%s' % (name, regs[o - lo])
                if lo == 0x08000:
                    ch, r = divmod(o - lo, 0x100)
                    return 'GC DBDMA ch%d(%s)+0x%X' % (ch, DBDMA_CH[ch] if ch < len(DBDMA_CH) else '?', r)
                if lo == 0x16000 and (o - lo) % 0x200 == 0 and (o - lo) // 0x200 < 16:
                    return 'GC VIA.%s' % VIA_REGS[(o - lo) // 0x200]
                return '%s+0x%X' % (name, o - lo)
    if 0xF3000000 <= a < 0xF4000000:
        return 'PCI mem window 1 (GC BAR) +0x%X' % (a - GC)
    if 0xF0000000 <= a < 0xF0100000:
        return 'Taos VRAM+0x%X' % (a - 0xF0000000)
    if 0xF0800000 <= a < 0xF0800400:
        r = TAOS_REGS.get(a - 0xF0800000)
        return 'Taos.%s' % r if r else 'Taos reg+0x%X' % (a - 0xF0800000)
    if 0xF1000000 <= a < 0xF1000800:
        return 'Taos CLUT+0x%X' % (a - 0xF1000000)
    if 0xF2800000 <= a < 0xF2800010:
        return 'Aspen PCI CONFIG_ADDR'
    if 0xF2C00000 <= a < 0xF2C00010:
        return 'Aspen PCI CONFIG_DATA'
    if 0xF2000000 <= a < 0xF2800000:
        return 'PCI I/O space+0x%X' % (a - 0xF2000000)
    if 0xF8000000 <= a < 0xF8000800:
        r = ASPEN_REGS.get(a - 0xF8000000)
        return 'Aspen.%s' % r if r else 'Aspen reg+0x%X' % (a - 0xF8000000)
    if 0x40000000 <= a < 0x40080000:
        return 'save flash+0x%X' % (a - 0x40000000)
    if 0xF0000000 <= a < 0xFFC00000:
        return 'I/O space 0x%08X (unmapped in emulators?)' % a
    return None
