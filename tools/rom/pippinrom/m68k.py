"""68K linear-sweep disassembler (Capstone, 68040 mode) with Mac OS
annotations: A-line traps -> Toolbox/OS names, absolute short addresses ->
low-memory global names, branch targets -> labels, OSType immediates.

A linear sweep cannot tell code from embedded data; data inside code areas
will show up as odd instructions.  That is a known limitation."""
import re
import struct
import capstone

from .annot import trap_name, LOWMEM, mmio_name

_md = capstone.Cs(capstone.CS_ARCH_M68K, capstone.CS_MODE_BIG_ENDIAN | capstone.CS_MODE_M68K_040)

_target_rx = re.compile(r'^\$([0-9a-f]+)$')
_absw_rx = re.compile(r'\$([0-9a-f]+)\.w')
_absl_rx = re.compile(r'\$([0-9a-f]{5,8})(?:\.l)?(?![0-9a-f(])')
_imm_rx = re.compile(r'#\$([0-9a-f]{8})')
_BRANCH = ('bra', 'bsr', 'jmp', 'jsr', 'bhi', 'bls', 'bcc', 'bcs', 'bne', 'beq', 'bvc', 'bvs',
           'bpl', 'bmi', 'bge', 'blt', 'bgt', 'ble', 'bhs', 'blo', 'db')

F_LINE_NOTES = {
    0xFE0C: '68K emulator private F-line: flush PPC data cache for (A0, D0 bytes) [Kaisershot, Pippin Kickstart 1.1]',
}


def _ostype(v):
    b = struct.pack('>I', v)
    if all(0x20 <= c < 0x7F for c in b):
        return "'%s'" % b.decode('latin-1')
    return None


class M68KListing:
    def __init__(self, d, lo, hi, vaddr, symbols=None, comments=None, relcol=None, data_ranges=None):
        self.d, self.lo, self.hi, self.vaddr = d, lo, hi, vaddr
        self.sym = dict(symbols or {})
        self.cmt = dict(comments or {})
        self.relcol = relcol
        self.data_ranges = sorted(data_ranges or [])

    def addr(self, off):
        return (self.vaddr + off - self.lo) & 0xFFFFFFFF

    def off_of(self, a):
        o = a - self.vaddr + self.lo
        return o if self.lo <= o < self.hi else None

    def _decode(self):
        d = self.d
        off = self.lo
        dr = list(self.data_ranges)
        chunk = 4096
        while off < self.hi:
            while dr and dr[0][1] <= off:
                dr.pop(0)
            if dr and dr[0][0] <= off < dr[0][1]:
                n = min(dr[0][1], self.hi) - off
                yield off, 'data', (n, dr[0][2])
                off += n
                continue
            end = min(self.hi, off + chunk)
            if dr and dr[0][0] < end:
                end = dr[0][0]
            got = False
            for (a, size, mn, ops) in _md.disasm_lite(bytes(d[off:end]), self.addr(off)):
                got = True
                w = (d[off] << 8) | d[off + 1]
                if (w & 0xF000) == 0xA000:
                    yield off, 'trap', w
                    off += 2
                    break     # capstone treats A-line as 2-byte dc.w; resync after it
                yield off, 'ins', (size, mn, ops)
                off += size
                if off >= end:
                    break
            if not got:
                if self.hi - off >= 2:
                    w = (d[off] << 8) | d[off + 1]
                    yield off, ('trap' if (w & 0xF000) == 0xA000 else 'bad'), w
                    off += 2
                else:
                    yield off, 'byte', d[off]
                    off += 1

    def lines(self):
        items = list(self._decode())
        targets = set()
        for off, kind, p in items:
            if kind == 'ins' and p[1].startswith(_BRANCH):
                last = p[2].split(',')[-1].strip()
                m = _target_rx.match(last)
                if m:
                    t = self.off_of(int(m.group(1), 16))
                    if t is not None:
                        targets.add(t)
                m = re.match(r'^\$([0-9a-f]+)\(pc\)$', last)
                if m:
                    t = self.off_of(int(m.group(1), 16))
                    if t is not None:
                        targets.add(t)
        for t in targets:
            self.sym.setdefault(t, 'L_%08X' % self.addr(t))
        out = []
        relw = self.relcol is not None
        for off, kind, p in items:
            if off in self.sym:
                out.append('')
                out.append(self.sym[off] + ':')
            col = '%08X %06X ' % (self.addr(off), off) + ('%06X ' % (off - self.relcol) if relw else '')
            notes = []
            if off in self.cmt:
                notes.append(self.cmt[off])
            if kind == 'data':
                n, label = p
                out.append(col + '%-20s ; %s (%d bytes, see hex dump)' % ('', label, n))
                continue
            if kind == 'trap':
                nm = trap_name(p)
                text = (nm or 'dc.w $%04x' % p)
                if not nm:
                    notes.append('A-line trap $%04X (name unknown)' % p)
                out.append((col + '%-20s %-38s' % ('%04x' % p, text) + ((' ; ' + '; '.join(notes)) if notes else '')).rstrip())
                continue
            if kind in ('bad', 'byte'):
                if kind == 'bad' and p in F_LINE_NOTES:
                    notes.append(F_LINE_NOTES[p])
                out.append((col + '%-20s %-38s' % (('%04x' % p) if kind == 'bad' else '%02x' % p,
                                                    ('dc.w $%04x' % p) if kind == 'bad' else 'dc.b $%02x' % p) +
                            ((' ; ' + '; '.join(notes)) if notes else '')).rstrip())
                continue
            size, mn, ops = p
            raw = self.d[off:off + size].hex()
            hexs = ' '.join(raw[i:i + 4] for i in range(0, len(raw), 4))
            if mn.startswith(_BRANCH):
                last = ops.split(',')[-1].strip()
                m = _target_rx.match(last) or re.match(r'^\$([0-9a-f]+)\(pc\)$', last)
                if m:
                    t = self.off_of(int(m.group(1), 16))
                    if t is not None and t in self.sym:
                        ops = ops[:len(ops) - len(last)] + self.sym[t]
            for m in _absw_rx.finditer(ops):
                v = int(m.group(1), 16)
                if v < 0x8000 and v in LOWMEM:
                    notes.append('%s=$%X' % (LOWMEM[v], v))
            for m in _imm_rx.finditer(ops):
                v = int(m.group(1), 16)
                t = _ostype(v)
                if t:
                    notes.append(t)
                nm = mmio_name(v) if 0xF0000000 <= v < 0xFFFF0000 else None
                if nm:
                    notes.append(nm)
            out.append((col + '%-20s %-38s' % (hexs, mn + ' ' + ops) + ((' ; ' + '; '.join(notes)) if notes else '')).rstrip())
        return out
