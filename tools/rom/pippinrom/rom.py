"""Parsers for the structures of an Old World (Pippin) 4 MB PowerPC ROM.

Everything here only *reads* bytes; no ROM code is executed.

Layout knowledge comes from:
  * the 68K "SuperMario" ROM header and ROM resource list format, as
    implemented in Elliot Nunn's tbxi (lowlevel.py, supermario_dump.py);
  * the ConfigInfo structure (tbxi lowlevel.py / PCCInfoRecordsPriv.h field
    names), whose component offsets are relative to the ConfigInfo page;
  * observation of these two ROMs (Pippin specific parts: embedded blob
    directory, XCOFF Open Firmware image, version1 FCode images).
"""
import struct

ROM_BASE = 0xFFC00000
ROM_SIZE = 0x400000


def u8(d, o): return d[o]
def u16(d, o): return struct.unpack_from('>H', d, o)[0]
def s16(d, o): return struct.unpack_from('>h', d, o)[0]
def u32(d, o): return struct.unpack_from('>I', d, o)[0]
def s32(d, o): return struct.unpack_from('>i', d, o)[0]


# ---------------------------------------------------------------- 68K header

HEADER_FIELDS = [
    # (offset, size, name)
    (0x00, 4, 'CheckSum'), (0x04, 4, 'ResetPC'), (0x08, 1, 'MachineNumber'),
    (0x09, 1, 'ROMVersion'), (0x0A, 4, 'ReStartJMP'), (0x0E, 4, 'BadDiskJMP'),
    (0x12, 2, 'ROMRelease'), (0x14, 1, 'PatchFlags'), (0x15, 1, 'unused1'),
    (0x16, 4, 'ForeignOSTbl'), (0x1A, 4, 'RomRsrc'), (0x1E, 4, 'EjectJMP'),
    (0x22, 4, 'DispTableOff'), (0x26, 4, 'CriticalJMP'), (0x2A, 4, 'ResetEntryJMP'),
    (0x2E, 1, 'RomLoc'), (0x2F, 1, 'unused2'), (0x30, 4, 'CheckSum0'),
    (0x34, 4, 'CheckSum1'), (0x38, 4, 'CheckSum2'), (0x3C, 4, 'CheckSum3'),
    (0x40, 4, 'RomSize'), (0x44, 4, 'EraseIconOff'), (0x48, 4, 'InitSys7ToolboxOff'),
    (0x4C, 4, 'SubVers'),
]
HEADER_END = 0x50
FOREIGN_OS_FIELDS = ['InitDispatcher', 'EMT1010', 'BadTrap', 'StartSDeclMgr',
                     'InitMemVect', 'SwitchMMU', 'InitRomVectors']
FOREIGN_OS_START = 0x50
FOREIGN_OS_END = 0x50 + 4 * 7


def parse_header(d):
    h = {}
    for off, size, name in HEADER_FIELDS:
        h[name] = int.from_bytes(d[off:off + size], 'big')
    h['ForeignOS'] = [(n, u32(d, FOREIGN_OS_START + 4 * i)) for i, n in enumerate(FOREIGN_OS_FIELDS)]
    return h


def checksums(d, rom68k_size):
    """Return dict of stored vs computed checksums.

    Main checksum: sum of big-endian 16-bit words from offset 4 to the end of
    the 68K ROM (the byte-lane sums at 0x30..0x3F are included).
    Byte-lane checksums: sum of every 4th byte over the 68K ROM with the
    main checksum and the four lane fields treated as zero.
    """
    words = struct.unpack('>%dH' % ((rom68k_size - 4) // 2), d[4:rom68k_size])
    main = sum(words) & 0xFFFFFFFF
    z = bytearray(d[:rom68k_size])
    z[0:4] = bytes(4)
    z[0x30:0x40] = bytes(16)
    lanes = [sum(z[i::4]) & 0xFFFFFFFF for i in range(4)]
    stored_lanes = [u32(d, 0x30 + 4 * i) for i in range(4)]
    return {'main_stored': u32(d, 0), 'main_calc': main,
            'lanes_stored': stored_lanes, 'lanes_calc': lanes}


# ------------------------------------------------------------ ROM resources

COMBO_NAMES = {0x78: 'AllCombos', 0x40: 'AppleTalk1', 0x20: 'AppleTalk2',
               0x30: 'AppleTalk2_NetBoot_FPU', 0x08: 'AppleTalk2_NetBoot_NoFPU',
               0x10: 'NetBoot'}


class Resource:
    __slots__ = ('index', 'entry_off', 'entry_len', 'data_off', 'size', 'type',
                 'id', 'attr', 'name', 'combo', 'next', 'mm_header')

    @property
    def mm_off(self):
        return self.data_off - 16

    def type_str(self):
        return self.type.decode('mac_roman')

    def name_str(self):
        return self.name.decode('mac_roman')

    def label(self):
        n = self.name_str()
        return "'%s' %d%s" % (self.type_str(), self.id, (' "%s"' % n) if n else '')


def parse_resources(d, rom_rsrc):
    """Walk the ROM resource linked list.  Returns (header_info, [Resource])
    in ROM-offset order of their entries (index = position in the list as
    the ROM chains them, 0 = first)."""
    first, max_idx, combo_sz, combo_ver, hdr_size = struct.unpack_from('>LBBHH', d, rom_rsrc)
    hdr = {'offset': rom_rsrc, 'offsetToFirst': first, 'maxValidIndex': max_idx,
           'comboFieldSize': combo_sz, 'comboVersion': combo_ver, 'headerSize': hdr_size}
    out = []
    link = first
    i = 0
    while link:
        r = Resource()
        combo, nxt, data, typ, rid, attr = struct.unpack_from('>QII4shB', d, link)
        nl = d[link + 23]
        r.index = i
        r.entry_off = link
        r.entry_len = (24 + nl + 15) // 16 * 16   # 23 fixed + len byte + name, padded to 16
        r.name = bytes(d[link + 24:link + 24 + nl])
        r.combo = combo >> 56
        r.next = nxt
        r.data_off = data
        r.type = bytes(typ)
        r.id = rid
        r.attr = attr
        r.mm_header = bytes(d[data - 16:data])
        r.size = u32(d, data - 8) - 12
        out.append(r)
        link = nxt
        i += 1
    return hdr, out


# ---------------------------------------------------------------- ConfigInfo

CONFIGINFO_FIELDS = [
    (0x28, 'l', 'ROMImageBaseOffset'), (0x2C, 'L', 'ROMImageSize'), (0x30, 'L', 'ROMImageVersion'),
    (0x34, 'l', 'Mac68KROMOffset'), (0x38, 'L', 'Mac68KROMSize'),
    (0x3C, 'l', 'ExceptionTableOffset'), (0x40, 'L', 'ExceptionTableSize'),
    (0x44, 'l', 'HWInitCodeOffset'), (0x48, 'L', 'HWInitCodeSize'),
    (0x4C, 'l', 'KernelCodeOffset'), (0x50, 'L', 'KernelCodeSize'),
    (0x54, 'l', 'EmulatorCodeOffset'), (0x58, 'L', 'EmulatorCodeSize'),
    (0x5C, 'l', 'OpcodeTableOffset'), (0x60, 'L', 'OpcodeTableSize'),
    (0x74, 'L', 'BootVersionOffset'), (0x78, 'L', 'ECBOffset'), (0x7C, 'L', 'IplValueOffset'),
    (0x80, 'L', 'EmulatorEntryOffset'), (0x84, 'L', 'KernelTrapTableOffset'),
    (0x88, 'L', 'TestIntMaskInit'), (0x8C, 'L', 'ClearIntMaskInit'), (0x90, 'L', 'PostIntMaskInit'),
    (0x94, 'L', 'LA_InterruptCtl'), (0x98, 'B', 'InterruptHandlerKind'),
    (0x9C, 'L', 'LA_InfoRecord'), (0xA0, 'L', 'LA_KernelData'), (0xA4, 'L', 'LA_EmulatorData'),
    (0xA8, 'L', 'LA_DispatchTable'), (0xAC, 'L', 'LA_EmulatorCode'),
    (0xB0, 'L', 'MacLowMemInitOffset'), (0xB4, 'L', 'PageAttributeInit'),
    (0x35C, 'L', 'SharedMemoryAddr'), (0x360, 'L', 'PA_RelocatedLowMemInit'),
    (0x364, 'l', 'OpenFWBundleOffset'), (0x368, 'L', 'OpenFWBundleSize'),
    (0x36C, 'L', 'LA_OpenFirmware'), (0x370, 'L', 'PA_OpenFirmware'), (0x374, 'L', 'LA_HardwarePriv'),
]


def find_configinfo(d):
    """ConfigInfo carries the 16-byte BootstrapVersion string at +0x64.  The
    Pippin's ConfigInfo checksum does not verify (tbxi notes the same), so we
    locate it by the 'Boot ' signature on a 4 KB boundary in the upper MB."""
    for i in range(0x300000, len(d), 0x1000):
        if d[i + 0x64:i + 0x69] == b'Boot ':
            return i
    return None


def parse_configinfo(d, off):
    c = {'offset': off}
    for o, fmt, name in CONFIGINFO_FIELDS:
        c[name] = struct.unpack_from('>' + fmt, d, off + o)[0]
    c['BootstrapVersion'] = bytes(d[off + 0x64:off + 0x74])
    # absolute ROM offsets of components
    for comp in ('Mac68KROM', 'ExceptionTable', 'HWInitCode', 'KernelCode',
                 'EmulatorCode', 'OpcodeTable', 'OpenFWBundle'):
        c[comp + '_rom'] = off + c[comp + 'Offset']
    c['ROMImageBase_rom'] = off + c['ROMImageBaseOffset']
    lm = []
    p = off + c['MacLowMemInitOffset']
    while any(d[p:p + 4]):
        lm.append((u32(d, p), u32(d, p + 4)))
        p += 8
    c['LowMemInit'] = lm
    c['LowMemInit_end'] = p + 4   # terminated by a zero long
    return c


# ------------------------------------------- Pippin embedded blob directory

def find_blob_directory(d, start, end):
    """The Pippin exception-table area contains a directory of 16-byte
    entries {OSType type; UInt16 id; UInt16 0; UInt32 romOffset; UInt32 size}
    describing blobs ('snd ', 'cTBL', 'fTBL', 'PICT') stored elsewhere in the
    upper megabyte.  Return (dir_start, dir_end, entries)."""
    ents = []
    first = None
    a = start
    while a + 16 <= end:
        t = d[a:a + 4]
        if all(0x20 <= c < 0x7F for c in t) and u16(d, a + 6) == 0:
            o, s = u32(d, a + 8), u32(d, a + 12)
            if 0 < o < ROM_SIZE and 0 < s < ROM_SIZE and o + s <= ROM_SIZE:
                if first is None:
                    first = a
                ents.append({'off': a, 'type': bytes(t), 'id': u16(d, a + 4), 'rom': o, 'size': s})
                a += 16
                continue
        if first is not None:
            break
        a += 16
    if first is None:
        return None
    return first, a, ents


# ------------------------------------------------------------------- XCOFF

def parse_xcoff(d, off):
    magic, nscns, timdat, symptr, nsyms, opthdr, flags = struct.unpack_from('>HHIIIHH', d, off)
    if magic != 0x01DF:
        return None
    x = {'offset': off, 'magic': magic, 'nscns': nscns, 'timdat': timdat,
         'symptr': symptr, 'nsyms': nsyms, 'opthdr': opthdr, 'flags': flags, 'sections': []}
    p = off + 20 + opthdr
    for i in range(nscns):
        name, paddr, vaddr, size, scnptr, relptr, lnnoptr, nreloc, nlnno, sflags = \
            struct.unpack_from('>8sIIIIIIHHI', d, p)
        x['sections'].append({'name': name.rstrip(b'\0').decode(), 'paddr': paddr, 'vaddr': vaddr,
                              'size': size, 'scnptr': scnptr, 'flags': sflags, 'hdr': p})
        p += 40
    x['headers_end'] = p
    x['symbols'] = []
    x['symtab_end'] = None
    if symptr and nsyms:
        sp = off + symptr
        strtab = sp + 18 * nsyms
        strlen = u32(d, strtab) if strtab + 4 <= len(d) else 0
        i = 0
        while i < nsyms:
            e = sp + 18 * i
            if d[e:e + 4] == b'\0\0\0\0':
                so = u32(d, e + 4)
                end = d.index(b'\0', strtab + so)
                name = d[strtab + so:end].decode('latin-1')
            else:
                name = d[e:e + 8].rstrip(b'\0').decode('latin-1')
            value, scnum, typ, sclass, naux = struct.unpack_from('>IhHBB', d, e + 8)
            x['symbols'].append({'name': name, 'value': value, 'scnum': scnum, 'type': typ,
                                 'sclass': sclass, 'naux': naux})
            i += 1 + naux
        x['strtab'] = strtab
        x['symtab_end'] = strtab + max(strlen, 4)
    return x


# ------------------------------------------- Open Firmware (Apple OF 1.0.5)

def scan_of_headers(d, lo, hi):
    """Native (subroutine-threaded PPC) Forth word headers in Apple's Open
    Firmware 1.0.5 image, observed layout:
        +0  s32  link  (relative to this field; points at previous header's link)
        +4  u8   flags (0x80 on every header; 0x20 set = headerless, no name)
        +5  u8   ?     (0xB7 on most words; probably the FCode "definer" type)
        +6  u16  FCode token number
        named:      +8 u8 name length, name, pad to 4, one 0 long, then code
        headerless: code starts at +8
    Candidates are only kept if their link lands on another candidate, so the
    result is the linked dictionary chain(s).  Returns dicts sorted by address."""
    cand = {}
    for a in range(lo, hi - 12, 4):
        w = s32(d, a)
        if not (-0x10000 < w < 0) or (a + w) % 4 or a + w < lo:
            continue
        fl = d[a + 4]
        if not fl & 0x80:
            continue
        if fl & 0x20:
            cand[a] = {'hdr': a, 'link': a + w, 'flags': fl, 'b5': d[a + 5], 'token': u16(d, a + 6),
                       'name': None, 'code': a + 8}
            continue
        n = d[a + 8]
        if not (1 <= n < 40):
            continue
        name = d[a + 9:a + 9 + n]
        if not all(0x20 < c < 0x7F for c in name):
            continue
        code = (a + 9 + n + 3) // 4 * 4 + 4
        cand[a] = {'hdr': a, 'link': a + w, 'flags': fl, 'b5': d[a + 5],
                   'token': u16(d, a + 6), 'name': name.decode('latin-1'), 'code': code}
    # keep candidates that are linked to (or link to) other candidates
    linked_to = {h['link'] for h in cand.values()}
    good = [h for a, h in sorted(cand.items()) if h['link'] in cand or a in linked_to]
    # headerless candidates are weaker: require both directions unless named
    good = [h for h in good if h['name'] is not None or (h['link'] in cand and h['hdr'] in linked_to)]
    return good


def scan_fcode_images(d, lo, hi):
    """FCode images in the OF area start with version1 (0xFD), format 0x08,
    a 16-bit checksum and a 32-bit length.  Only images whose checksum
    verifies are accepted."""
    out = []
    i = lo
    while i < hi - 8:
        if d[i] == 0xFD and d[i + 1] == 0x08:
            ck, ln = struct.unpack_from('>HI', d, i + 2)
            if 8 < ln < 0x40000 and i + ln <= hi and (sum(d[i + 8:i + ln]) & 0xFFFF) == ck:
                out.append({'off': i, 'len': ln, 'checksum': ck})
                i += ln
                continue
        i += 1
    return out
