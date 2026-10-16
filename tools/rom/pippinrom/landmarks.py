"""Sanity checks against published landmarks (Kaisershot's "Exploring the
Pippin ROM(s)" series and "Pippin Kickstart 1.1", MAME/DingusPPC ROM ids).
Each check returns (name, status, detail) with status PASS / FAIL / INFO."""
import struct

from . import rom as R

DINGUS_IDS = {0x2BEF21B7: '077d2cf2', 0x2BF65931: '077d2cc6'}   # docs/core-dev/README.md 1.7


def _bytes_at(d, off, hexstr):
    b = bytes.fromhex(hexstr.replace(' ', ''))
    return d[off:off + len(b)] == b


def check(A, rom_path=None):
    d = A.d
    h = A.header
    out = []

    is_dev = h['CheckSum'] == 0x2BF65931

    def add(name, ok, detail, info=False, expected_fail=None):
        st = 'INFO' if info else ('PASS' if ok else 'FAIL')
        if not ok and expected_fail:
            st = 'EXPECTED-DIFF'
            detail += ' -- ' + expected_fail
        out.append((name, st, detail))

    # 1. reset vector
    ok = _bytes_at(d, 0x300100, '48000008') and _bytes_at(d, 0x303000, '7c9f42a6')
    add('PPC reset vector 0xFFF00100 (ROM 0x300100)', ok,
        'ROM 0x300100 = %s (b +8); cold-start path reaches 0xFFF03000 = %s (mfpvr r4)' % (
            d[0x300100:0x300104].hex(), d[0x303000:0x303004].hex()))
    lm = dict(A.ci['LowMemInit'])
    add('68K reset PC', h['ResetPC'] == 0x2A and lm.get(4) == 0xFFC0002A,
        'header ResetPC 0x%X; ConfigInfo LowMemInit [4] = 0x%08X' % (h['ResetPC'], lm.get(4, 0)))
    # 2. version
    vid = '%02x%02x%04x' % (h['MachineNumber'], h['ROMVersion'], h['ROMRelease'])
    exp = DINGUS_IDS.get(h['CheckSum'])
    add('68K ROM header version 0x077D', h['MachineNumber'] == 0x07 and h['ROMVersion'] == 0x7D,
        'version word 0x%02X%02X, release 0x%04X -> id %s (DingusPPC romidentity: %s)' % (
            h['MachineNumber'], h['ROMVersion'], h['ROMRelease'], vid, exp or 'n/a'))
    if exp:
        add('DingusPPC ROM version id', vid == exp, '%s vs %s' % (vid, exp))
    # 3. checksum
    c = A.cks
    name_id = None
    if rom_path:
        import os
        base = os.path.basename(rom_path)
        try:
            name_id = int(base[:8], 16)
        except ValueError:
            pass
    add('68K checksum at offset 0 = MAME/DingusPPC id', c['main_stored'] == c['main_calc'] and
        (name_id is None or name_id == c['main_stored']),
        'stored 0x%08X, recomputed 0x%08X (16-bit word sum 4..0x%X), file-name id %s; byte-lane sums %s' % (
            c['main_stored'], c['main_calc'], h['RomSize'], ('0x%08X' % name_id) if name_id is not None else '-',
            'OK' if c['lanes_stored'] == c['lanes_calc'] else 'MISMATCH'))
    # 4. 'rvpr' 0
    rv = [r for r in A.resources if r.type == b'rvpr' and r.id == 0]
    if rv:
        r = rv[0]
        b = r.data_off
        checks = [(0x14, '41FAFFEA'), (0x104, '41FAFEFA D1FC000106A2 2008 A055 C18C'),
                  (0x108A, '4E560000 2F2E0008 206E0008 20680004 2050 4E90 4E5E 4E75'),
                  (0x1C64, '4E560000 206E0008 20AE000C 216E00100004')]
        res = ['+0x%X %s' % (o, 'ok' if _bytes_at(d, b + o, hx) else 'differs') for o, hx in checks]
        add("'rvpr' 0 present, code matches Kaisershot parts 3/6 listings", all('ok' in x for x in res),
            'data at ROM 0x%06X, %d bytes; %s' % (b, r.size, '; '.join(res)))
    else:
        add("'rvpr' 0 present", False, 'no rvpr resource')
    # caller (part 2 listing)
    ok2 = _bytes_at(d, 0x3230, '48E73030 20780DDC 41E8FF7E 20B8020C 594F 2F3C72767072 4267 A9A0')
    ok1 = _bytes_at(d, 0x1592, '303CFFDC 322A0008 B240 66C0')
    add('FindStartupDevice CD-only check (0x1592) and rvpr caller (0x3230), Kaisershot part 2', ok1 and ok2,
        '0x1592: %s, 0x3230: %s' % ('match' if ok1 else 'differs', 'match' if ok2 else 'differs'),
        expected_fail='the Dev ROM has neither the internal-CD check nor the rvpr authentication call '
                      '(see disasm/diff-1.0-vs-dev.md)' if is_dev else None)
    # 5. logo
    pict = [r for r in A.resources if r.type == b'PICT' and r.id == -20137]
    if pict:
        r = pict[0]
        add('PICT -20137 (Pippin logo)', True, "resource '%s' at ROM 0x%06X, %d bytes, frame %s" % (
            r.name_str(), r.data_off, r.size, struct.unpack_from('>4h', d, r.data_off + 2)))
    else:
        add('PICT -20137 (Pippin logo)', False, 'not found')
    seg = d[0xE3C:0xE3C + 0x40]
    i = seg.find(b'\x3f\x3c\xb1\x57')
    ok = i >= 0 and seg.find(b'\xa9\xbc', i) >= 0
    add('Logo routine at 0xE3C pushes -20137 then _GetPicture (Kickstart 1.1)', ok,
        'pattern 3F3C B157 at 0x%X, A9BC after it: %s' % (0xE3C + i if i >= 0 else -1, 'yes' if ok else 'no'))
    # 6. SCSI Manager PEF
    nitt = [(r, p) for (r, p, base) in A.pefs.values() if r.type == b'nitt' and r.id == 43]
    if nitt:
        r, p = nitt[0]
        code = [s for s in p.sections if s['kind'] == 0][0]
        cb = code['rom']
        ok_fn = _bytes_at(d, cb + 0xB850, '4e800020') and _bytes_at(d, cb + 0xB854, '7c0802a6')
        tv = any(t[0] == 'sect' and t[1] == code['index'] and t[2] == 0xBAD4 for t in p.slot.values())
        span = code['raw_size'] - 0xB854
        add("SCSI Manager PEF ('nitt' 43 \"Native 4.3\"): code offset 0xB854 / TV to 0xBAD4 / 35536-byte block",
            ok_fn and tv and span == 35536,
            'code section at ROM 0x%06X (%d bytes); +0xB850 blr / +0xB854 mflr r0: %s; data TV -> code+0xBAD4: %s; '
            'code size - 0xB854 = %d' % (cb, code['raw_size'], 'yes' if ok_fn else 'no', 'yes' if tv else 'no', span))
    else:
        add('SCSI Manager PEF', False, "'nitt' 43 not found")
    # 7. strings
    i = d.find(b'PipPCI')
    j = d.find(b'Open Firmware, ')
    add('"PipPCI" OF model string', i >= 0,
        ('found at 0x%06X' % i) if i >= 0 else
        'absent; this ROM\'s OF model string is %r at 0x%06X (Kaisershot saw "PipPCI" on ROM 1.2)' % (
            d[j:j + 20].split(b'\x01')[0].decode('latin-1'), j),
        expected_fail='the landmark was observed on a ROM 1.2 console; this ROM identifies its OF by the string shown')
    add('ConfigInfo BootstrapVersion', A.ci['BootstrapVersion'].startswith(b'Boot Pip'),
        '%r (16-byte field; printable prefix shown)' % A.ci['BootstrapVersion'].split(b'\x01')[0].decode('mac_roman'))
    i = d.find(b'680x0 Emulation written by Gary Davidian')
    add('68K emulator signature string', i >= 0, 'at ROM 0x%06X' % i)
    inits = [r.label() for r in A.resources if r.type == b'iNiT']
    add("'iNiT' 1 and 'iNiT' \"Install XFS\" (Kaisershot part 2)", len(inits) == 2, ', '.join(inits))
    nint = [(r, p) for (r, p, base) in A.pefs.values() if r.type == b'nint' and r.id == 43]
    if nint:
        names = [e['name'] for e in nint[0][1].exports]
        add("'nint' 43 PEF exports InitAnimation", 'InitAnimation' in names, 'exports: %s' % ', '.join(names))
    return out
