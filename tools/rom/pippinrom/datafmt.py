"""Hex dumps and header decoders for data resources/blobs.  Only headers are
decoded; pixel/sample payloads are left as hex."""
import struct


def hexdump(d, lo, hi, vaddr=None, relbase=None, max_bytes=None):
    out = []
    end = hi if max_bytes is None else min(hi, lo + max_bytes)
    prev = None
    rep = 0
    a = lo
    while a < end:
        b = bytes(d[a:min(a + 16, end)])
        if b == prev and len(b) == 16 and a + 16 < end:
            rep += 1
            a += 16
            continue
        if rep:
            out.append('*  (%d identical lines)' % rep)
            rep = 0
        prev = b
        cols = ''
        if vaddr is not None:
            cols += '%08X ' % (vaddr + a - lo)
        cols += '%06X ' % a
        if relbase is not None:
            cols += '%06X ' % (a - relbase)
        hx = ' '.join(b[i:i + 4].hex() for i in range(0, len(b), 4))
        asc = ''.join(chr(c) if 0x20 <= c < 0x7F else '.' for c in b)
        out.append('%s %-35s |%s|' % (cols, hx, asc))
        a += 16
    if rep:
        out.append('*  (%d identical lines)' % rep)
    if end < hi:
        out.append('... (%d more bytes not shown)' % (hi - end))
    return out


def _pstr(b, p):
    n = b[p]
    return b[p + 1:p + 1 + n].decode('mac_roman', 'replace'), p + 1 + n


def _rect(b, p):
    t, l, bo, r = struct.unpack_from('>hhhh', b, p)
    return '(top %d, left %d, bottom %d, right %d) = %dx%d' % (t, l, bo, r, r - l, bo - t)


def decode(typ, b):
    """Return list of human-readable header lines for resource/blob bytes b."""
    L = []
    try:
        if typ == b'PICT' and len(b) >= 12:
            size = struct.unpack_from('>H', b, 0)[0]
            L.append('picSize (low 16 bits): %d; actual %d bytes' % (size, len(b)))
            L.append('picFrame: ' + _rect(b, 2))
            if b[10:12] == b'\x00\x11' and b[12:14] == b'\x02\xff':
                L.append('version: 2 (opcode $0011 $02FF)')
            elif b[10:12] == b'\x11\x01':
                L.append('version: 1')
            else:
                L.append('version opcode bytes: %s (not a standard PICT header?)' % b[10:16].hex())
        elif typ == b'snd ' and len(b) >= 20:
            fmt = struct.unpack_from('>H', b, 0)[0]
            L.append("'snd ' format %d" % fmt)
            p = 2
            if fmt == 1:
                nmods = struct.unpack_from('>H', b, p)[0]; p += 2
                for i in range(nmods):
                    mid, init = struct.unpack_from('>HI', b, p); p += 6
                    L.append('  synth/modifier id %d init 0x%08X' % (mid, init))
            else:
                p += 2
            ncmd = struct.unpack_from('>H', b, p)[0]; p += 2
            for i in range(ncmd):
                cmd, p1, p2 = struct.unpack_from('>HhI', b, p); p += 8
                L.append('  command 0x%04X param1 %d param2 0x%X' % (cmd, p1, p2))
                if cmd & 0x7FFF in (80, 81) and p2 < len(b):
                    sp, ln, rate, ls, le, enc, base = struct.unpack_from('>IIIIIBB', b, p2)
                    L.append('  sound header @+0x%X: samplePtr %d, length %d, rate %.2f Hz, loop %d-%d, encode %d, baseFreq %d'
                             % (p2, sp, ln, rate / 65536.0, ls, le, enc, base))
                    L.append('  sample data @+0x%X .. +0x%X (8-bit offset binary)' % (p2 + 22, p2 + 22 + ln))
        elif typ == b'vers' and len(b) >= 8:
            maj, mnr, stage, rel, country = struct.unpack_from('>BBBBH', b, 0)
            s1, p = _pstr(b, 6)
            s2, p = _pstr(b, p)
            L.append('version %x.%x.%x stage 0x%02X release %d country %d' % (maj, mnr >> 4, mnr & 15, stage, rel, country))
            L.append('short: %r' % s1)
            L.append('long:  %r' % s2)
        elif typ == b'STR#' and len(b) >= 2:
            n = struct.unpack_from('>H', b, 0)[0]
            p = 2
            L.append('%d strings' % n)
            for i in range(n):
                s, p = _pstr(b, p)
                L.append('  [%d] %r' % (i + 1, s))
        elif typ == b'STR ' and len(b) >= 1:
            L.append('string: %r' % _pstr(b, 0)[0])
        elif typ in (b'clut', b'cTBL') and len(b) >= 8:
            seed, flags, n = struct.unpack_from('>IHH', b, 0)
            L.append('ctSeed 0x%08X ctFlags 0x%04X ctSize %d (%d entries)' % (seed, flags, n, n + 1))
        elif typ == b'FONT' and len(b) >= 26:
            f = struct.unpack_from('>13h', b, 0)
            L.append('fontType 0x%04X firstChar %d lastChar %d widMax %d kernMax %d nDescent %d fRectWidth %d '
                     'fRectHeight %d owTLoc %d ascent %d descent %d leading %d rowWords %d' %
                     tuple([f[0] & 0xFFFF] + list(f[1:])))
        elif typ == b'thng' and len(b) >= 20:
            t, st, mf, fl, fm = struct.unpack_from('>4s4s4sII', b, 0)
            L.append('component type %r subType %r manufacturer %r flags 0x%X mask 0x%X' % (t, st, mf, fl, fm))
            if len(b) >= 40:
                L.append("  code rsrc %r %d, name rsrc %r %d, info rsrc %r %d, icon rsrc %r %d" %
                         struct.unpack_from('>4sh4sh4sh4sh', b, 20))
        elif typ == b'DRVR' and len(b) >= 19:
            fl, dl, emask, menu, o_open, o_prime, o_ctl, o_stat, o_close = struct.unpack_from('>HHHhHHHHH', b, 0)
            name, _ = _pstr(b, 18)
            L.append('drvrFlags 0x%04X delay %d eMask 0x%04X menu %d open +0x%X prime +0x%X control +0x%X '
                     'status +0x%X close +0x%X name %r' % (fl, dl, emask, menu, o_open, o_prime, o_ctl, o_stat, o_close, name))
        elif typ in (b'ICON', b'ICN#', b'ics#', b'ics4', b'ics8', b'CURS'):
            L.append('icon/cursor bitmap data, %d bytes' % len(b))
        elif typ == b'cicn' and len(b) >= 50:
            L.append('color icon: PixMap bounds ' + _rect(b, 6))
        elif typ == b'KCHR' and len(b) >= 2:
            L.append('KCHR version %d' % struct.unpack_from('>H', b, 0)[0])
        elif typ in (b'libr',):
            L.append('ASLM library registration; name %r' % b.split(b'\0')[0].decode('mac_roman', 'replace'))
    except (struct.error, IndexError, ValueError) as e:
        L.append('(header decode stopped: %s)' % e)
    return L
