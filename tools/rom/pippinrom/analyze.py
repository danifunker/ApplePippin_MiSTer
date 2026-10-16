"""Build a byte-accurate region map of a Pippin ROM.

Every byte of the 4 MB image ends up in exactly one *leaf* region.  Regions
are plain dicts:
    start, end      ROM offsets [start, end)
    kind            code68k | codeppc | fcode | header | table | data | padding | unknown
    isa             '68K', 'PPC', 'FCode', or '-' for data
    name            short description
    group           section of index.md the row belongs to
    file            output file (relative to the output directory), may be None
    plus kind-specific keys used by emit.py
"""
import hashlib
import re

from . import rom as R
from .pef import PEF

CODE68K_TYPES = {b'DRVR', b'CDEF', b'MDEF', b'WDEF', b'LDEF', b'MBDF', b'PACK', b'proc', b'dimg',
                 b'iNiT', b'rvpr', b'CODX', b'ASPT', b'ascd', b'NCOD', b'FTIN', b'GARY', b'sift',
                 b'daud', b'scod', b'sl00', b'sl01', b'sl02', b'sl03', b'sl04', b'sl05', b'sl06',
                 b'sl07', b'INIT', b'ptch', b'PTCH', b'lpch', b'CODE'}

PAD_KC = b'kc'


def safe(s):
    s = re.sub(r'[^A-Za-z0-9_.+-]+', '_', s).strip('_')
    return s or 'x'


def rsrc_basename(r):
    t = safe(r.type.decode('mac_roman').strip()) or 'type'
    n = safe(r.name.decode('mac_roman')) if r.name else ''
    return '%s_%d%s' % (t, r.id, ('_' + n) if n else '')


def fill_kind(b):
    if not b:
        return 'empty'
    if b.count(b[0:1]) == len(b):
        return 'fill 0x%02X' % b[0]
    if len(b) >= 2:
        # 'kc' pattern, possibly starting on the 'c'
        ph = b[0:1] == b'c'
        pat = (b'ck' if ph else b'kc')
        if (pat * (len(b) // 2 + 1))[:len(b)] == b:
            return "'kc' fill"
    return None


class ROMAnalysis:
    def __init__(self, d, label):
        assert len(d) == R.ROM_SIZE, 'expected a 4 MB ROM image'
        self.d = d
        self.label = label
        self.regions = []
        self.notes = []
        self.pefs = {}
        self._build()

    # --------------------------------------------------------------- helpers
    def add(self, start, end, kind, name, group, file=None, isa='-', **kw):
        if end <= start:
            return None
        r = dict(start=start, end=end, kind=kind, name=name, group=group, file=file, isa=isa)
        r.update(kw)
        self.regions.append(r)
        return r

    def trailing_fill(self, start, end, fill=0):
        """Return the offset where a trailing run of `fill` bytes starts."""
        e = end
        while e > start and self.d[e - 1] == fill:
            e -= 1
        return (e + 3) & ~3 if e < end else end

    # ----------------------------------------------------------------- build
    def _build(self):
        d = self.d
        self.header = R.parse_header(d)
        h = self.header
        self.ci_off = R.find_configinfo(d)
        self.ci = R.parse_configinfo(d, self.ci_off)
        ci = self.ci
        m68k_end = ci['Mac68KROM_rom'] + ci['Mac68KROMSize']
        self.m68k_end = m68k_end
        self.cks = R.checksums(d, h['RomSize'] if h['RomSize'] else m68k_end)

        # ---------------- 68K ROM
        self.add(0, R.HEADER_END, 'header', '68K ROM header (SuperMario layout)', '68K ROM',
                 '00_rom_header.txt')
        self.add(R.FOREIGN_OS_START, R.FOREIGN_OS_END, 'table', 'ForeignOS vector table (7 longs)', '68K ROM',
                 '00_rom_header.txt')
        rr = h['RomRsrc']
        self.add(R.FOREIGN_OS_END, rr, 'code68k', '68K main code (Toolbox/OS, linear sweep)', '68K ROM',
                 'm68k_main/', isa='68K', split=0x10000)
        self.rsrc_hdr, self.resources = R.parse_resources(d, rr)
        self.add(rr, rr + 16, 'header', 'ROM resource list header', '68K ROM', 'resources.txt')
        for r in self.resources:
            self.add(r.entry_off, r.entry_off + r.entry_len, 'table',
                     'resource entry for %s' % r.label(), 'resource entries', 'resources.txt', rsrc=r)
            base = rsrc_basename(r)
            dend = r.data_off + r.size
            if d[r.data_off:r.data_off + 8] == b'Joy!peff':
                self._add_pef(r, base)
            elif r.type in CODE68K_TYPES:
                self.add(r.mm_off, dend, 'code68k', '%s (+16-byte MM header)' % r.label(), 'resources',
                         'rsrc/%s.s' % base, isa='68K', rsrc=r)
            else:
                self.add(r.mm_off, dend, 'data', '%s (+16-byte MM header)' % r.label(), 'resources',
                         'rsrc/%s.hex.txt' % base, rsrc=r)
        # DeclData at the very end of the 68K ROM (after the 'kc' padding)
        pad = d.rfind(PAD_KC * 100, 0, m68k_end)
        if pad >= 0:
            dd = pad + 200
            while d[dd:dd + 2] == PAD_KC:
                dd += 2
            self.add(dd, m68k_end, 'data', 'DeclData (NuBus-style declaration ROM / format block)', '68K ROM',
                     'decldata.hex.txt')

        # ---------------- PowerPC megabyte
        et = ci['ExceptionTable_rom']
        bd = R.find_blob_directory(d, et, et + ci['ExceptionTableSize'])
        self.blobdir = bd
        et_code_end = bd[0] if bd else self.trailing_fill(et, et + ci['ExceptionTableSize'])
        self.add(et, et_code_end, 'codeppc', 'PowerPC exception vectors + low-level startup (reset at +0x100)',
                 'PowerPC', 'ppc_exception_table.s', isa='PPC', vaddr=R.ROM_BASE + et)
        if bd:
            self.add(bd[0], bd[1], 'table', 'Pippin blob directory (%d entries: snd/cTBL/fTBL/PICT)' % len(bd[2]),
                     'PowerPC', 'blob_directory.txt')
            for i, e in enumerate(bd[2]):
                t = e['type'].decode('latin-1')
                self.add(e['rom'], e['rom'] + e['size'], 'data', "blob '%s' 0x%X" % (t, e['id']), 'blobs',
                         'blobs/%02d_%s_%02X.hex.txt' % (i, safe(t), e['id']), blob=e)
        self.add(self.ci_off, self.ci_off + 0x1000, 'table', 'ConfigInfo page (boot info for the NanoKernel)',
                 'PowerPC', 'configinfo.txt')
        k = ci['KernelCode_rom']
        self.add(k, self.trailing_fill(k, k + ci['KernelCodeSize']), 'codeppc', 'NanoKernel', 'PowerPC',
                 'nanokernel.s', isa='PPC', vaddr=R.ROM_BASE + k)
        # HWInit is an XCOFF image
        hw = ci['HWInitCode_rom']
        self._add_xcoff(hw, hw + ci['HWInitCodeSize'], 'HWInit (POST diagnostics, Serial Test Manager)', 'hwinit')
        # Open Firmware XCOFF
        of = ci['OpenFWBundle_rom']
        self._add_xcoff(of, of + 0x30000, 'Open Firmware 1.0.5', 'openfirmware')
        em = ci['EmulatorCode_rom']
        self.add(em, self.trailing_fill(em, em + ci['EmulatorCodeSize']), 'codeppc',
                 '68K emulator (Gary Davidian)', 'PowerPC', 'emulator.s', isa='PPC', vaddr=R.ROM_BASE + em)
        op = ci['OpcodeTableOffset'] + self.ci_off
        self.add(op, op + ci['OpcodeTableSize'], 'codeppc',
                 '68K emulator opcode dispatch table (65536 x 2 instructions)', 'PowerPC', 'emulator_opcode_table.s',
                 isa='PPC', vaddr=R.ROM_BASE + op, opcode_table=True)
        self._resolve()

    def _add_pef(self, r, base):
        d = self.d
        p = PEF(d, r.data_off)
        self.pefs[r.data_off] = (r, p, base)
        dend = r.data_off + r.size
        secs = sorted(p.sections, key=lambda s: s['rom'])
        first = min([s['rom'] for s in secs if s['raw_size']] + [dend])
        self.add(r.mm_off, first, 'header', '%s PEF container header (+MM header)' % r.label(), 'resources',
                 'pef/%s/container.txt' % base, rsrc=r, pef=p)
        for s in secs:
            if not s['raw_size']:
                continue
            e = min(s['rom'] + s['raw_size'], dend)
            if s['kind'] == 0:
                self.add(s['rom'], e, 'codeppc', '%s PEF code section %d' % (r.label(), s['index']), 'resources',
                         'pef/%s/code_s%d.s' % (base, s['index']), isa='PPC', rsrc=r, pef=p, sec=s)
            elif s['kind'] == 4:
                self.add(s['rom'], e, 'table', '%s PEF loader section %d' % (r.label(), s['index']), 'resources',
                         'pef/%s/container.txt' % base, rsrc=r, pef=p, sec=s)
            else:
                self.add(s['rom'], e, 'data', '%s PEF %s section %d' % (r.label(), s['kind_name'], s['index']),
                         'resources', 'pef/%s/data_s%d.hex.txt' % (base, s['index']), rsrc=r, pef=p, sec=s)
            if s['rom'] + s['raw_size'] > dend:
                self.notes.append('%s: PEF section %d extends %d bytes past the resource size' %
                                  (r.label(), s['index'], s['rom'] + s['raw_size'] - dend))

    def _add_xcoff(self, lo, hi, title, stem):
        d = self.d
        x = R.parse_xcoff(d, lo)
        if not x:
            self.add(lo, self.trailing_fill(lo, hi), 'codeppc', title, 'PowerPC', stem + '.s', isa='PPC',
                     vaddr=R.ROM_BASE + lo)
            return
        txt = x['sections'][0]
        t0 = lo + txt['scnptr']
        t1 = t0 + txt['size']
        self.add(lo, t0, 'header', title + ': XCOFF file/section headers', 'PowerPC', stem + '/xcoff.txt', xcoff=x)
        if stem == 'openfirmware':
            self.of_headers = R.scan_of_headers(d, t0, t1)
            self.fcode = R.scan_fcode_images(d, t0, t1)
            native_end = self.fcode[0]['off'] if self.fcode else t1
            self.add(t0, native_end, 'codeppc', 'Open Firmware native kernel (PPC, subroutine-threaded Forth)',
                     'Open Firmware', stem + '/of_native.s', isa='PPC', vaddr=R.ROM_BASE + t0, xcoff=x, text0=t0)
            prev_end = native_end
            for i, f in enumerate(self.fcode):
                o = f['off']
                if R.u16(d, o - 10) in (0x106B, 0xFFFF) and o - 16 >= prev_end and R.u32(d, o - 4) == 0:
                    self.add(o - 16, o, 'table', 'FCode image %d descriptor (link, device/vendor id, class)' % i,
                             'Open Firmware', stem + '/fcode_%02d.fth' % i, fcode_desc=True)
                self.add(o, o + f['len'], 'fcode', 'FCode image %d (version1, %d bytes)' % (i, f['len']),
                         'Open Firmware', stem + '/fcode_%02d.fth' % i, isa='FCode', fcode=f, index=i)
                prev_end = o + f['len']
            self.add(prev_end, t1, 'padding', 'end of XCOFF .text', 'Open Firmware', None)
        else:
            syms = {lo + txt['scnptr'] + s['value']: s['name'] for s in x['symbols']
                    if s['scnum'] == 1 and s['name'] and s['sclass'] == 2}
            self.add(t0, t1, 'codeppc', title + ': .text', 'PowerPC', stem + '/text.s', isa='PPC',
                     vaddr=R.ROM_BASE + t0, symbols=syms, text0=t0)
        if x.get('symtab_end'):
            self.add(lo + x['symptr'], x['symtab_end'], 'table',
                     title + ': XCOFF symbol + string table', 'PowerPC', stem + '/xcoff.txt', xcoff_sym=True)

    # ------------------------------------------------- overlaps, gaps, cover
    def _resolve(self):
        d = self.d
        regs = sorted(self.regions, key=lambda r: (r['start'], -(r['end'] - r['start'])))
        out = []
        for r in regs:
            if out and r['start'] < out[-1]['end']:
                prev = out[-1]
                # blobs and resources win over XCOFF/table tails; clip the earlier region
                if prev.get('xcoff_sym') or prev['kind'] in ('padding',):
                    self.notes.append('%s [%06X-%06X) clipped at %06X by %s' % (
                        prev['name'], prev['start'], prev['end'], r['start'], r['name']))
                    prev['clipped_from'] = prev['end']
                    prev['end'] = r['start']
                    if prev['end'] <= prev['start']:
                        out.pop()
                elif r.get('xcoff_sym'):
                    r['clipped_from_start'] = r['start']
                    r['start'] = out[-1]['end']
                    if r['end'] <= r['start']:
                        continue
                else:
                    raise RuntimeError('overlap: %r vs %r' % (
                        (prev['name'], hex(prev['start']), hex(prev['end'])), (r['name'], hex(r['start']), hex(r['end']))))
            out.append(r)
        # fill gaps
        full = []
        pos = 0
        for r in out + [None]:
            nxt = r['start'] if r else R.ROM_SIZE
            if nxt > pos:
                full.extend(self._gap(pos, nxt))
            if r:
                full.append(r)
                pos = r['end']
        for i, r in enumerate(full):
            if r['kind'] == 'unknown' and 0 < i < len(full) - 1:
                a, b = full[i - 1], full[i + 1]
                if a.get('pef') is not None and a.get('pef') is b.get('pef'):
                    r.update(kind='padding', file=None,
                             name='PEF section alignment slack (stale non-zero bytes left by the build tool)')
        self.regions = full
        tot = sum(r['end'] - r['start'] for r in full)
        assert tot == R.ROM_SIZE, tot
        for a, b in zip(full, full[1:]):
            assert a['end'] == b['start'], (a, b)
        for r in full:
            r['sha1'] = hashlib.sha1(d[r['start']:r['end']]).hexdigest()

    def _gap(self, lo, hi):
        """Classify a gap: fill runs become padding, anything else 'unknown'."""
        d = self.d
        out = []
        b = bytes(d[lo:hi])
        fk = fill_kind(b)
        group = '68K ROM' if lo < self.m68k_end else 'PowerPC'
        if fk:
            return [dict(start=lo, end=hi, kind='padding', name='padding (%s)' % fk, group=group, file=None, isa='-')]
        # split into runs of 16-byte chunks that are fill / non-fill
        def key(chunk):
            k = fill_kind(chunk)
            return k.split(' ')[0] + (chunk[:1].hex() if k and k.startswith('fill') else '') if k else None
        a = lo
        while a < hi:
            k = key(b[a - lo:min(a - lo + 16, hi - lo)])
            e = min(a + 16, hi)
            while e < hi and key(b[e - lo:min(e - lo + 16, hi - lo)]) == k:
                e = min(e + 16, hi)
            if k:
                out.append(dict(start=a, end=e, kind='padding', name='padding (%s)' % fill_kind(b[a - lo:e - lo]),
                                group=group, file=None, isa='-'))
            else:
                out.append(dict(start=a, end=e, kind='unknown', name='unidentified data', group=group,
                                file='unknown/%06X.hex.txt' % a, isa='-'))
            a = e
        # merge adjacent same-kind
        merged = []
        for r in out:
            if merged and merged[-1]['kind'] == r['kind'] == 'unknown':
                merged[-1]['end'] = r['end']
            else:
                merged.append(r)
        return merged

    # ----------------------------------------------------------------- stats
    def coverage(self):
        by = {}
        for r in self.regions:
            by[r['kind']] = by.get(r['kind'], 0) + r['end'] - r['start']
        return by
