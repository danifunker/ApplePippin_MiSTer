"""PowerPC (32-bit, big-endian) linear-sweep disassembler built on Capstone,
with Pippin-specific annotations:
  * SPR numbers -> names (603 set)
  * lis/addi/ori constant tracking -> MMIO / ROM region names
  * branch targets -> labels; caller-supplied symbols (exports, Forth words)
  * AIX/MrC traceback tables recognised, decoded and used to name functions
"""
import re
import struct
import capstone

from .annot import SPR, mmio_name

_md = capstone.Cs(capstone.CS_ARCH_PPC, capstone.CS_MODE_32 | capstone.CS_MODE_BIG_ENDIAN)

LANGS = ['C', 'Fortran', 'Pascal', 'Ada', 'PL/1', 'Basic', 'Lisp', 'Cobol', 'Modula2', 'C++',
         'RPG', 'PL.8', 'Assembler']


def parse_tbtable(d, a, end):
    """Parse a traceback table whose leading zero word is at d[a].  Returns
    dict(start, end, name, ...) or None.  Requires has_tboff so that the
    function start can be computed (and as a sanity check)."""
    if a + 12 > end or d[a:a + 4] != b'\0\0\0\0':
        return None
    p = a + 4
    version, lang, f1, f2, f3, f4, fixedparms, f5 = d[p:p + 8]
    if version != 0 or lang > 12 or not (f1 & 0x20):
        return None
    q = p + 8
    floatparms = f5 >> 1
    try:
        if fixedparms or floatparms:
            q += 4
        tboff = struct.unpack_from('>I', d, q)[0]; q += 4
        if f2 & 0x80:
            q += 4
        if f1 & 0x08:
            n = struct.unpack_from('>I', d, q)[0]
            if n > 64:
                return None
            q += 4 + 4 * n
        name = None
        if f2 & 0x40:
            nl = struct.unpack_from('>H', d, q)[0]
            if not 0 < nl < 256:
                return None
            raw = d[q + 2:q + 2 + nl]
            if not all(0x20 <= c < 0x7F for c in raw):
                return None
            name = raw.decode('latin-1')
            q += 2 + nl
        if f2 & 0x20:
            q += 1
    except struct.error:
        return None
    if tboff == 0 or tboff % 4 or tboff > 0x100000:
        return None
    q = (q + 3) & ~3
    if q > end:
        return None
    return {'tb': a, 'start': a - tboff, 'end': q, 'name': name, 'lang': LANGS[lang] if lang < len(LANGS) else str(lang),
            'gpr_saved': f4 & 0x3F, 'fpr_saved': f3 & 0x3F, 'saves_lr': bool(f2 & 1), 'fixedparms': fixedparms}


def find_tbtables(d, lo, hi):
    out = {}
    for a in range(lo, hi - 12, 4):
        if d[a:a + 4] == b'\0\0\0\0' and d[a + 4] == 0 and d[a + 6] & 0x20:
            t = parse_tbtable(d, a, hi)
            if t and t['start'] >= lo:
                out[a] = t
    return out


_hexrx = re.compile(r'0x[0-9a-f]+')
_spr_rx = re.compile(r'^(mtspr|mfspr) (.*)$')
_mem_rx = re.compile(r'(-?0x[0-9a-f]+|-?\d+)\((r\d+)\)')


def _ival(s):
    return int(s, 16) if s.lstrip('-').startswith('0x') else int(s)


class PPCListing:
    """Disassemble [lo, hi) of byte array d, where d[lo] is at runtime
    address vaddr.  symbols: {rom_offset: name}; comments: {rom_offset: text};
    data_ranges: list of (lo, hi, label) ROM-offset ranges to emit as .long."""

    def __init__(self, d, lo, hi, vaddr, symbols=None, comments=None, data_ranges=None,
                 relcol=None, tbtables=True, collapse_zeros=True, toc_resolver=None):
        self.d, self.lo, self.hi, self.vaddr = d, lo, hi, vaddr
        self.sym = dict(symbols or {})
        self.cmt = dict(comments or {})
        self.data_ranges = sorted(data_ranges or [])
        self.relcol = relcol          # base offset for an extra "section-relative" column
        self.collapse = collapse_zeros
        self.toc_resolver = toc_resolver
        self.tbt = find_tbtables(d, lo, hi) if tbtables else {}
        for t in self.tbt.values():
            if t['name'] and t['start'] not in self.sym:
                self.sym[t['start']] = t['name']
        self.funcs = sorted((t['start'], t['name']) for t in self.tbt.values() if t['name'])

    def addr(self, off):
        return (self.vaddr + off - self.lo) & 0xFFFFFFFF

    def off_of(self, addr):
        o = addr - self.vaddr + self.lo
        return o if self.lo <= o < self.hi else None

    def _decode(self):
        """Yield (off, kind, payload): kind 'ins' (mnemonic, op_str), 'tb' (table dict),
        'data' (label), 'zeros' (count)."""
        d = self.d
        off = self.lo
        dr = list(self.data_ranges)
        while off < self.hi:
            while dr and dr[0][1] <= off:
                dr.pop(0)
            if dr and dr[0][0] <= off < dr[0][1]:
                yield off, 'data', dr[0][2]
                off += 4
                continue
            if off in self.tbt:
                t = self.tbt[off]
                yield off, 'tb', t
                off = t['end']
                continue
            if self.hi - off < 4:
                yield off, 'tail', None
                off = self.hi
                continue
            w = d[off:off + 4]
            if self.collapse and w == b'\0\0\0\0' and off + 8 <= self.hi and d[off + 4:off + 8] == b'\0\0\0\0':
                n = 0
                while off + n + 4 <= self.hi and d[off + n:off + n + 4] == b'\0\0\0\0' and (off + n) not in self.tbt:
                    n += 4
                yield off, 'zeros', n
                off += n
                continue
            ins = list(_md.disasm_lite(bytes(w), self.addr(off), 1))
            if ins:
                yield off, 'ins', (ins[0][2], ins[0][3])
            else:
                yield off, 'bad', None
            off += 4

    def lines(self):
        items = list(self._decode())
        # pass 1: branch targets
        targets = set()
        for off, kind, p in items:
            if kind == 'ins' and p[0].startswith('b') and not p[0].startswith(('bctr', 'blr')):
                m = _hexrx.findall(p[1])
                if m:
                    t = self.off_of(int(m[-1], 16))
                    if t is not None:
                        targets.add(t)
        for t in targets:
            if t not in self.sym:
                self.sym[t] = 'L_%08X' % self.addr(t)
        out = []
        regs = {}
        relw = self.relcol is not None
        for off, kind, p in items:
            if off in self.sym:
                regs = {}
                out.append('')
                out.append('%s:' % self.sym[off])
            a = self.addr(off)
            col = '%08X %06X ' % (a, off) + ('%06X ' % (off - self.relcol) if relw else '')
            c = self.cmt.get(off)
            if kind == 'zeros':
                out.append(col + '%-11s %-30s ; %d zero bytes' % ('00000000', '.long 0 (x%d)' % (p // 4), p))
                continue
            if kind == 'tail':
                b = self.d[off:self.hi]
                out.append(col + '%-11s .byte %s' % (b.hex(), ', '.join('0x%02x' % x for x in b)))
                continue
            w = self.d[off:off + 4]
            hx = w.hex()
            if kind == 'tb':
                t = p
                out.append(col + '%-11s %-30s ; traceback table for %s (%s, start %08X, gprs %d, fprs %d)' % (
                    hx, '.long 0', t['name'] or '<unnamed>', t['lang'], self.addr(t['start']), t['gpr_saved'], t['fpr_saved']))
                q = off + 4
                while q < t['end']:
                    ww = self.d[q:q + 4]
                    out.append('%08X %06X ' % (self.addr(q), q) + ('%06X ' % (q - self.relcol) if relw else '') +
                               '%-11s .long 0x%s%s' % (ww.hex(), ww.hex(), ('  ; "%s"' % ''.join(chr(x) if 0x20 <= x < 0x7f else '.' for x in ww))))
                    q += 4
                regs = {}
                continue
            if kind == 'data':
                v = struct.unpack('>I', w)[0]
                note = mmio_name(v) if v >= 0xF0000000 or 0x40000000 <= v < 0x40080000 else None
                out.append(col + '%-11s %-30s ; %s%s' % (hx, '.long 0x%08x' % v, p, (' -> ' + note) if note else ''))
                continue
            if kind == 'bad':
                out.append(col + '%-11s %-30s ; (not a valid instruction)' % (hx, '.long 0x' + hx))
                regs = {}
                continue
            mn, ops = p
            notes = []
            m = _spr_rx.match(mn + ' ' + ops)
            if m:
                parts = [x.strip() for x in ops.split(',')]
                idx = 0 if mn == 'mtspr' else 1
                try:
                    n = _ival(parts[idx])
                    nm = SPR.get(n)
                    if nm:
                        parts[idx] = nm
                        ops = ', '.join(parts)
                except (ValueError, IndexError):
                    pass
            # branch target labels
            if mn.startswith('b') and not mn.startswith(('bctr', 'blr')):
                hx_ = _hexrx.findall(ops)
                if hx_:
                    t = self.off_of(int(hx_[-1], 16))
                    if t is not None and t in self.sym:
                        ops = ops[:ops.rfind(hx_[-1])] + self.sym[t]
                    elif t is None:
                        notes.append('-> outside this region')
            # constant tracking
            parts = [x.strip() for x in ops.split(',')]
            try:
                if mn == 'lis' and len(parts) == 2:
                    regs[parts[0]] = (_ival(parts[1]) << 16) & 0xFFFFFFFF
                elif mn in ('addi', 'ori', 'addis', 'oris') and len(parts) == 3 and parts[1] in regs:
                    v = _ival(parts[2])
                    base = regs[parts[1]]
                    if mn == 'addi':
                        nv = (base + v) & 0xFFFFFFFF
                    elif mn == 'ori':
                        nv = base | (v & 0xFFFF)
                    elif mn == 'addis':
                        nv = (base + (v << 16)) & 0xFFFFFFFF
                    else:
                        nv = base | ((v & 0xFFFF) << 16)
                    regs[parts[0]] = nv
                    nm = mmio_name(nv)
                    notes.append('%s = 0x%08X%s' % (parts[0], nv, (' ' + nm) if nm else ''))
                elif mn == 'li' and len(parts) == 2:
                    regs[parts[0]] = _ival(parts[1]) & 0xFFFFFFFF
                else:
                    mm = _mem_rx.search(ops)
                    if mm and mm.group(2) == 'r2' and self.toc_resolver and mn.startswith(('l', 's')):
                        t = self.toc_resolver(_ival(mm.group(1)))
                        if t:
                            notes.append('TOC: ' + t)
                    if mm and mm.group(2) in regs and (mn.startswith(('l', 's')) or mn in ('dcbf', 'dcbi', 'dcbst', 'icbi')):
                        ea = (regs[mm.group(2)] + _ival(mm.group(1))) & 0xFFFFFFFF
                        nm = mmio_name(ea)
                        if nm or ea >= 0xF0000000:
                            notes.append('[0x%08X] %s' % (ea, nm or ''))
                    if parts and parts[0] in regs and not mn.startswith(('st', 'cmp', 'tw', 'mt', 'b', 'dcb', 'icb')):
                        del regs[parts[0]]
            except (ValueError, IndexError):
                pass
            if mn == 'lis' and parts:
                v = regs.get(parts[0])
                if v is not None:
                    nm = mmio_name(v)
                    if nm and not nm.startswith('ROM'):
                        notes.append('0x%08X %s' % (v, nm))
            if c:
                notes.append(c)
            line = col + '%-11s %-30s' % (hx, mn + (' ' + ops if ops else ''))
            if notes:
                line += ' ; ' + '; '.join(notes)
            out.append(line.rstrip())
            if mn in ('b', 'blr', 'bctr', 'rfi', 'ba'):
                regs = {}
        return out
