"""PEF (Preferred Executable Format, 'Joy!peff') container parser.

Format per Apple, "Mac OS Runtime Architectures", chapter 8 (PEF):
container header, section headers, section name table, loader section
(imports, relocations, export hash/key/symbol tables), pattern-initialised
data ('pidata').  Relocations are interpreted symbolically (we never
instantiate the fragment) so that TOC slots and transition vectors can be
labelled.
"""
import struct

SECTION_KINDS = {0: 'code', 1: 'unpackedData', 2: 'patternInitData', 3: 'constant',
                 4: 'loader', 5: 'debug', 6: 'executableData', 7: 'exception', 8: 'traceback'}
SYM_CLASSES = {0: 'code', 1: 'data', 2: 'tvect', 3: 'toc', 4: 'glue'}


class PEFError(Exception):
    pass


def read_varint(b, p):
    v = 0
    while True:
        c = b[p]; p += 1
        v = (v << 7) | (c & 0x7F)
        if not c & 0x80:
            return v, p


def unpack_pidata(b, total):
    out = bytearray()
    p = 0
    while p < len(b):
        op = b[p]; p += 1
        opc, cnt = op >> 5, op & 0x1F
        if cnt == 0:
            cnt, p = read_varint(b, p)
        if opc == 0:
            out += bytes(cnt)
        elif opc == 1:
            out += b[p:p + cnt]; p += cnt
        elif opc == 2:
            rep, p = read_varint(b, p)
            blk = b[p:p + cnt]; p += cnt
            out += blk * (rep + 1)
        elif opc in (3, 4):
            custom, p = read_varint(b, p)
            rep, p = read_varint(b, p)
            common = b"" if opc == 4 else b[p:p + cnt]
            if opc == 3:
                p += cnt
            else:
                common = bytes(cnt)
            for _ in range(rep):
                out += common
                out += b[p:p + custom]; p += custom
            out += common
        else:
            raise PEFError('bad pidata opcode %d' % opc)
    if total and len(out) < total:
        out += bytes(total - len(out))
    return bytes(out)


class PEF:
    def __init__(self, d, base):
        """d: whole ROM bytes; base: ROM offset of 'Joy!peff'."""
        self.base = base
        if d[base:base + 8] != b'Joy!peff':
            raise PEFError('no magic')
        (_, _, self.arch, self.fmt_version, self.timestamp, self.old_def_ver,
         self.old_imp_ver, self.cur_ver, self.nsec, self.ninst, _) = \
            struct.unpack_from('>4s4s4sIIIIIHHI', d, base)
        self.sections = []
        nametab = base + 40 + 28 * self.nsec
        for i in range(self.nsec):
            (nameoff, addr, exec_sz, init_sz, raw_sz, cont_off, kind, share, align, _) = \
                struct.unpack_from('>iIIIIIBBBB', d, base + 40 + 28 * i)
            name = ''
            if nameoff >= 0:
                e = d.index(b'\0', nametab + nameoff)
                name = d[nametab + nameoff:e].decode('latin-1')
            self.sections.append({'index': i, 'name': name, 'addr': addr, 'exec_size': exec_sz,
                                  'init_size': init_sz, 'raw_size': raw_sz, 'off': cont_off,
                                  'rom': base + cont_off, 'kind': kind,
                                  'kind_name': SECTION_KINDS.get(kind, '?%d' % kind),
                                  'share': share, 'align': align})
        self.header_end = nametab
        self.d = d
        self.imports = []
        self.libs = []
        self.exports = []
        self.relocs = {}
        self.main = self.init = self.term = None
        self.end = max([s['rom'] + s['raw_size'] for s in self.sections] + [nametab])
        ld = [s for s in self.sections if s['kind'] == 4]
        if ld:
            self._parse_loader(ld[0])
        self.unpacked = {}
        for s in self.sections:
            raw = d[s['rom']:s['rom'] + s['raw_size']]
            if s['kind'] == 2:
                try:
                    self.unpacked[s['index']] = unpack_pidata(raw, s['init_size'])
                except Exception:
                    self.unpacked[s['index']] = None
            elif s['kind'] in (0, 1, 3, 6):
                self.unpacked[s['index']] = bytes(raw) + bytes(max(0, s['init_size'] - s['raw_size']))
        self.slot = {}   # (section, offset) -> description from relocation
        try:
            self._run_relocs()
        except Exception as e:  # keep going; report later
            self.reloc_error = str(e)
        else:
            self.reloc_error = None

    # -------------------------------------------------------------- loader
    def _parse_loader(self, s):
        d, o = self.d, s['rom']
        (ms, mo, is_, io, ts, to, nlib, nimp, nrsec, relinstr, stroff, hashoff, hashpow, nexp) = \
            struct.unpack_from('>iIiIiIIIIIIIII', d, o)
        self.main = (ms, mo) if ms >= 0 else None
        self.init = (is_, io) if is_ >= 0 else None
        self.term = (ts, to) if ts >= 0 else None
        strs = o + stroff

        def cstr(off):
            e = d.index(b'\0', strs + off)
            return d[strs + off:e].decode('latin-1')
        p = o + 56
        for i in range(nlib):
            nameoff, oldimp, cur, cnt, first, opts, _, _ = struct.unpack_from('>IIIIIBBH', d, p)
            self.libs.append({'name': cstr(nameoff), 'count': cnt, 'first': first,
                              'weak': bool(opts & 0x40), 'oldImpVersion': oldimp, 'curVersion': cur})
            p += 24
        imp_lib = {}
        for li, lib in enumerate(self.libs):
            for k in range(lib['first'], lib['first'] + lib['count']):
                imp_lib[k] = lib['name']
        for i in range(nimp):
            w = struct.unpack_from('>I', d, p)[0]
            p += 4
            cls = (w >> 24) & 0xF
            self.imports.append({'name': cstr(w & 0xFFFFFF), 'class': SYM_CLASSES.get(cls, str(cls)),
                                 'weak': bool(w & 0x80000000), 'lib': imp_lib.get(i, '?')})
        self._reloc_hdrs = []
        for i in range(nrsec):
            sec, _, cnt, first = struct.unpack_from('>HHII', d, p)
            self._reloc_hdrs.append((sec, cnt, o + relinstr + first))
            p += 12
        # exports
        nhash = 1 << hashpow
        keys = o + hashoff + 4 * nhash
        syms = keys + 4 * nexp
        for i in range(nexp):
            key = struct.unpack_from('>I', d, keys + 4 * i)[0]
            ln = key >> 16
            cn, val, sec = struct.unpack_from('>IIh', d, syms + 10 * i)
            nameoff = cn & 0xFFFFFF
            name = d[strs + nameoff:strs + nameoff + ln].decode('latin-1')
            self.exports.append({'name': name, 'class': SYM_CLASSES.get(cn >> 24, str(cn >> 24)),
                                 'value': val, 'section': sec})

    # ---------------------------------------------------------- relocations
    def _run_relocs(self):
        nsec = len(self.sections)
        for sec, cnt, p in getattr(self, '_reloc_hdrs', []):
            data = self.unpacked.get(sec)
            if data is None:
                continue
            words = struct.unpack('>%dH' % cnt, self.d[p:p + 2 * cnt])
            pos = 0
            imp = 0
            sectC, sectD = 0, 1 if nsec > 1 else 0
            i = 0

            def tag(off, what):
                self.slot[(sec, off)] = what

            def val(off):
                return struct.unpack_from('>I', data, off)[0] if off + 4 <= len(data) else 0

            def by_sect(off, s):
                tag(off, ('sect', s, val(off)))

            history = []
            while i < len(words):
                w = words[i]
                two = (w >> 10) in (0b101000, 0b101001, 0b101100, 0b101101)
                ins = words[i:i + (2 if two else 1)]
                i += len(ins)
                if w >> 12 == 0b1001 or w >> 10 == 0b101100:   # RelocSmRepeat / RelocLgRepeat
                    if w >> 12 == 0b1001:
                        blocks, rep = ((w >> 8) & 0xF) + 1, (w & 0xFF) + 1
                    else:
                        blocks, rep = ((w >> 6) & 0xF) + 1, ((w & 0x3F) << 16) | ins[1]
                    seq = history[-blocks:]
                    for _ in range(rep):
                        for prev in seq:
                            pos, imp, sectC, sectD = self._exec1(prev, pos, imp, sectC, sectD, tag, val, by_sect)
                    continue
                pos, imp, sectC, sectD = self._exec1(ins, pos, imp, sectC, sectD, tag, val, by_sect)
                history.append(ins)

    def _exec1(self, ins, pos, imp, sectC, sectD, tag, val, by_sect):
        """Re-execute one already-decoded relocation instruction (for repeats)."""
        w = ins[0]
        if w >> 14 == 0:
            skip, run = (w >> 6) & 0xFF, w & 0x3F
            pos += 4 * skip
            for _ in range(run):
                by_sect(pos, sectD); pos += 4
        elif w >> 13 == 0b010:
            sub, run = (w >> 9) & 0xF, (w & 0x1FF) + 1
            for _ in range(run):
                if sub == 0:
                    by_sect(pos, sectC); pos += 4
                elif sub == 1:
                    by_sect(pos, sectD); pos += 4
                elif sub == 2:
                    by_sect(pos, sectC); by_sect(pos + 4, sectD); pos += 12
                elif sub == 3:
                    by_sect(pos, sectC); by_sect(pos + 4, sectD); pos += 8
                elif sub == 4:
                    by_sect(pos, sectD); pos += 8
                elif sub == 5:
                    tag(pos, ('import', imp, val(pos))); imp += 1; pos += 4
        elif w >> 13 == 0b011:
            sub, idx = (w >> 9) & 0xF, w & 0x1FF
            if sub == 0:
                tag(pos, ('import', idx, val(pos))); imp = idx + 1; pos += 4
            elif sub == 1:
                sectC = idx
            elif sub == 2:
                sectD = idx
            elif sub == 3:
                by_sect(pos, idx); pos += 4
        elif w >> 12 == 0b1000:
            pos += (w & 0xFFF) + 1
        elif w >> 10 == 0b101000:
            pos = ((w & 0x3FF) << 16) | ins[1]
        elif w >> 10 == 0b101001:
            idx = ((w & 0x3FF) << 16) | ins[1]
            tag(pos, ('import', idx, val(pos))); imp = idx + 1; pos += 4
        elif w >> 10 == 0b101101:
            sub = (w >> 6) & 0xF
            idx = ((w & 0x3F) << 16) | ins[1]
            if sub == 0:
                by_sect(pos, idx); pos += 4
            elif sub == 1:
                sectC = idx
            elif sub == 2:
                sectD = idx
        return pos, imp, sectC, sectD

    # ------------------------------------------------------------ helpers
    def describe_slot(self, sec, off):
        """Describe what the relocated word at (sec, off) refers to."""
        t = self.slot.get((sec, off))
        if not t:
            return None
        if t[0] == 'import':
            idx, addend = t[1], t[2]
            if idx < len(self.imports):
                im = self.imports[idx]
                s = '%s:%s' % (im['lib'], im['name'])
            else:
                s = 'import#%d' % idx
            return s + ('+0x%X' % addend if addend else '')
        _, s, v = t
        sname = self.sections[s]['kind_name'] if s < len(self.sections) else '?'
        return 'sect%d(%s)+0x%X' % (s, sname, v)

    def tvectors(self):
        """Exported transition vectors -> list of (name, code_section, code_off, toc_section, toc_off)."""
        out = []
        for e in self.exports:
            if e['class'] != 'tvect':
                continue
            sec, off = e['section'], e['value']
            data = self.unpacked.get(sec)
            if data is None or off + 8 > len(data):
                continue
            c0 = self.slot.get((sec, off))
            c1 = self.slot.get((sec, off + 4))
            cv, tv = struct.unpack_from('>II', data, off)
            cs = c0[1] if c0 and c0[0] == 'sect' else 0
            ts = c1[1] if c1 and c1[0] == 'sect' else sec
            out.append((e['name'], cs, cv, ts, tv))
        return out
