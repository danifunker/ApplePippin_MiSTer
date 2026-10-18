"""File formats shared by the host tool and the Mac OS runner (macapp/).

The vector file `ppc603.vec` is ppctest's vector set in a plain file instead
of a disk image: one 128-byte entry per vector, the 64-byte input record
(layout.py I_*) followed by the 64-byte expected record (O_* order, zeros
when there is no expectation). The runner writes `ppc603.res`: a 64-byte
header, then one 64-byte output record per vector in the same O_* layout as
the Open Firmware and Linux routes write, so ppctest's decoder reads them
unchanged. Everything is big-endian.
"""

import struct
import zlib

VEC_MAGIC = b"P603VEC1"
RES_MAGIC = b"P603RES1"
HDR = 64
REC = 64
ENTRY = 2 * REC
CHUNK = 64                   # vectors the runner reads and writes at a time

# vector-file header
V_MAGIC, V_VERSION, V_BUILD, V_NVEC, V_FLAGS = 0, 8, 12, 16, 20
V_NEXP = 24                  # vectors that carry an expected record
VF_HAS_MEM = 1               # some vectors use the memory buffer

# results-file header, written by the runner
R_MAGIC, R_BUILD, R_NVEC, R_NDONE, R_SUM, R_NMISS = 0, 8, 12, 16, 20, 24
R_CPU, R_MACHINE, R_SYSV, R_STATUS, R_TICKS = 28, 32, 36, 40, 44
R_MISS, R_MISS_MAX = 48, 4   # the first four mismatching vector numbers
RS_RUNNING, RS_DONE, RS_ABORTED = 0x52554E47, 0x444F4E45, 0x41424F52   # 'RUNG' 'DONE' 'ABOR'

# Gestalt 'cput' values (gestaltNativeCPUtype); the low byte is the PVR's
# high half for every PowerPC
GESTALT_CPU = {0x101: "601", 0x103: "603", 0x104: "604", 0x106: "603e",
               0x107: "603ev", 0x108: "750", 0x109: "604e", 0x10A: "604ev"}


def build_id(vectors):
    """CRC32 of every input record: what ties a results file to its vectors."""
    crc = 0
    for v in vectors:
        crc = zlib.crc32(v.pack_input(), crc)
    return crc & 0xFFFFFFFF


def pack_vector_file(vectors):
    body = bytearray()
    nexp = 0
    has_mem = False
    for v in vectors:
        body += v.pack_input()
        body += v.pack_expected()
        nexp += v.exp is not None
        has_mem |= v.mem
    hdr = bytearray(HDR)
    hdr[V_MAGIC:V_MAGIC + 8] = VEC_MAGIC
    struct.pack_into(">IIIII", hdr, V_VERSION, 1, build_id(vectors), len(vectors),
                     VF_HAS_MEM if has_mem else 0, nexp)
    return bytes(hdr) + bytes(body)


class Results:
    """A results file as the runner left it."""

    def __init__(self, data):
        if data[R_MAGIC:R_MAGIC + 8] != RES_MAGIC:
            raise ValueError("not a ppc603 results file")
        (self.build, self.nvec, self.ndone, self.sum, self.nmiss, self.cpu, self.machine,
         self.sysv, self.status, self.ticks) = struct.unpack_from(">10I", data, R_BUILD)
        self.miss = list(struct.unpack_from(">%dI" % R_MISS_MAX, data, R_MISS))
        self.records = data[HDR:HDR + self.nvec * REC]

    def record(self, i):
        return self.records[i * REC:(i + 1) * REC]

    @property
    def done(self):
        return self.status == RS_DONE

    def cpu_name(self):
        return GESTALT_CPU.get(self.cpu, "cput %04X" % self.cpu)


def checksum(records, n):
    """The runner's running checksum: sum = rotl(sum, 1) + word over every
    output word, in order."""
    s = 0
    for i in range(n * REC // 4):
        w = struct.unpack_from(">I", records, i * 4)[0]
        s = (((s << 1) | (s >> 31)) + w) & 0xFFFFFFFF
    return s
