/*
 * PPC603Test: run ppctest's single-instruction vectors under Mac OS.
 *
 * The Mac OS route of the 603 CPU test suite (../README.md). On a Mac with
 * no Open Firmware (Performa 52xx/62xx) the only way to run code is as an
 * application, in user mode. This one reads `ppc603.vec` from its own
 * folder, runs every vector exactly as ppctest's harness.py does (the
 * instruction is written into a two-word slot, the state loaded, the slot
 * called, the state stored), and writes `ppc603.res` beside it. The host
 * tool ppc603test.py decodes that into ppctest's CSV format.
 *
 * Record layouts are ppctest's (layout.py I_* and O_*); file layouts are
 * vec603.py's. Built with Retro68 for powerpc-apple-macos (CFM/PEF).
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <MacTypes.h>
#include <Gestalt.h>
#include <Events.h>
#include <Files.h>
#include <Multiverse.h>        /* FindFolder (Multiversal interfaces) */
#ifndef kOnSystemDisk
#define kOnSystemDisk (-32768)
#endif
#ifndef kCreateFolder
#define kCreateFolder 1
#endif

#define VEC_MAGIC "P603VEC1"
#define RES_MAGIC "P603RES1"
#define HDR 64
#define REC 64
#define ENTRY (2 * REC)
#define CHUNK 64

/* vector-file header */
#define V_BUILD 12
#define V_NVEC 16
#define V_FLAGS 20
/* results-file header */
#define R_BUILD 8
#define R_NVEC 12
#define R_NDONE 16
#define R_SUM 20
#define R_NMISS 24
#define R_CPU 28
#define R_MACHINE 32
#define R_SYSV 36
#define R_STATUS 40
#define R_TICKS 44
#define R_MISS 48
#define R_MISS_MAX 4
#define RS_RUNNING 0x52554E47UL
#define RS_DONE 0x444F4E45UL
#define RS_ABORTED 0x41424F52UL

#define F_HAS_EXPECTED 1
#define F_MEM 2

/* in-record offsets (layout.py I_*) */
#define I_INSN 0x00
#define I_FLAGS 0x04

typedef unsigned long u32;

static u32 get32(const unsigned char *p) {
    return ((u32)p[0] << 24) | ((u32)p[1] << 16) | ((u32)p[2] << 8) | p[3];
}
static void put32(unsigned char *p, u32 v) {
    p[0] = v >> 24; p[1] = v >> 16; p[2] = v >> 8; p[3] = v;
}

/*
 * The scratch area the vector sequence uses (offsets from r29):
 *   0x00  +0.0, loaded into f3 before every vector
 *   0x08  the caller's FPSCR, put back afterwards
 *   0x20  the 8-byte memory buffer of an F_MEM vector (spare bytes either side)
 * The slot: the instruction under test followed by blr, called with blrl.
 */
static double scratch[8] __attribute__((aligned(32)));
static u32 slot[8] __attribute__((aligned(32)));

static void run_vector(const unsigned char *in, unsigned char *out)
{
    register const unsigned char *rin asm("r31") = in;
    register unsigned char *rout asm("r30") = out;
    register double *rscr asm("r29") = scratch;
    register u32 *rslot asm("r28") = slot;

    __asm__ __volatile__(
        "mffs 0\n\t"  "stfd 0, 8(29)\n\t"               /* save FPSCR */
        "lwz 0, 0(31)\n\t" "stw 0, 0(28)\n\t"             /* the instruction into the slot */
        "dcbst 0, 28\n\t" "sync\n\t" "icbi 0, 28\n\t" "sync\n\t" "isync\n\t"
        "lfd 0, 0x20(31)\n\t" "mtfsf 0xff, 0\n\t"         /* low word of the CTR/FPSCR pair */
        "lfd 3, 0(29)\n\t"
        "lfd 4, 0x28(31)\n\t" "lfd 5, 0x30(31)\n\t" "lfd 6, 0x38(31)\n\t"
        "stfd 6, 0x20(29)\n\t"                            /* buffer starts as the f6 pattern */
        "lwz 0, 4(31)\n\t" "andi. 7, 0, 2\n\t" "beq 1f\n\t" "addi 7, 29, 0x20\n"
        "1:\n\t"
        "lwz 0, 0x18(31)\n\t" "mtcrf 0xff, 0\n\t"
        "lwz 0, 0x1c(31)\n\t" "mtxer 0\n\t"
        "lwz 0, 0x20(31)\n\t" "mtctr 0\n\t"
        "lwz 3, 8(31)\n\t" "lwz 4, 12(31)\n\t" "lwz 5, 16(31)\n\t" "lwz 6, 20(31)\n\t"
        "add 6, 6, 7\n\t"
        "mtlr 28\n\t" "blrl\n\t"                          /* the slot: insn; blr */
        "stw 3, 0(30)\n\t" "stw 4, 4(30)\n\t" "stw 5, 8(30)\n\t"
        "subf 0, 7, 6\n\t" "stw 0, 12(30)\n\t"            /* r6 less the buffer address */
        "mfcr 0\n\t" "stw 0, 0x10(30)\n\t" "mfxer 0\n\t" "stw 0, 0x14(30)\n\t"
        "stfd 3, 0x20(30)\n\t" "stfd 4, 0x28(30)\n\t" "stfd 5, 0x30(30)\n\t" "stfd 6, 0x38(30)\n\t"
        "mffs 0\n\t" "stfd 0, 0x18(30)\n\t"               /* FPSCR lands at 0x1C */
        "mfctr 0\n\t" "stw 0, 0x18(30)\n\t"
        "cmpwi 7, 0\n\t" "beq 2f\n\t"
        "lfd 0, 0x20(29)\n\t" "stfd 0, 0x38(30)\n"        /* the buffer, in place of f6 */
        "2:\n\t"
        "lfd 0, 8(29)\n\t" "mtfsf 0xff, 0\n\t"            /* the caller's FPSCR back */
        : "+r"(rin), "+r"(rout), "+r"(rscr), "+r"(rslot)
        :
        : "r0", "r3", "r4", "r5", "r6", "r7", "fr0", "fr3", "fr4", "fr5", "fr6",
          "cr0", "cr1", "cr2", "cr3", "cr4", "cr5", "cr6", "cr7", "xer", "ctr", "lr", "memory");
}

/*
 * The results file is written with the File Manager so that it can go
 * somewhere other than the application's folder: first beside the
 * application (the BlueSCSI volume, which is what we want), and if that
 * volume is locked (a CD) on the desktop of the startup disk.
 */
static short res_ref = 0;
static long res_pos = 0;

static OSErr res_create(short vRefNum, long dirID)
{
    static unsigned char name[] = "\pppc603.res";
    OSErr err;
    HDelete(vRefNum, dirID, name);
    err = HCreate(vRefNum, dirID, name, 'R68K', 'BINA');
    if (err != noErr) return err;
    return HOpenDF(vRefNum, dirID, name, fsRdWrPerm, &res_ref);
}

static const char *res_open(void)
{
    short vRefNum;
    long dirID;
    if (res_create(0, 0) == noErr) return "beside the application";
    if (FindFolder(kOnSystemDisk, kDesktopFolderType, kCreateFolder, &vRefNum, &dirID) == noErr
        && res_create(vRefNum, dirID) == noErr)
        return "on the desktop of the startup disk";
    return NULL;
}

static int res_write(const void *buf, long len)
{
    long n = len;
    if (SetFPos(res_ref, fsFromStart, res_pos) != noErr) return -1;
    if (FSWrite(res_ref, &n, buf) != noErr || n != len) return -1;
    res_pos += len;
    return 0;
}

static int write_header(unsigned char *hdr)
{
    long keep = res_pos;
    res_pos = 0;
    if (res_write(hdr, HDR) != 0) return -1;
    res_pos = keep;
    return 0;
}

int main(void)
{
    static unsigned char entries[CHUNK * ENTRY];
    static unsigned char results[CHUNK * REC];
    unsigned char vhdr[HDR], rhdr[HDR];
    FILE *vec;
    const char *where;
    u32 nvec, build, ndone = 0, sum = 0, nmiss = 0, i, n;
    long cpu = 0, machine = 0, sysv = 0, t0;
    int fail = 0;

    printf("PPC603Test v1: ppctest's vectors under Mac OS\n");
    Gestalt(gestaltNativeCPUtype, &cpu);
    Gestalt(gestaltMachineType, &machine);
    Gestalt(gestaltSystemVersion, &sysv);
    printf("Gestalt: cpu %04lX  machine %ld  system %04lX\n", cpu, machine, sysv);

    slot[1] = 0x4E800020UL;                       /* blr after the instruction */
    memset(scratch, 0, sizeof scratch);

    vec = fopen("ppc603.vec", "rb");
    if (!vec) {
        printf("ERR: cannot open ppc603.vec (put it in this application's folder)\n");
        goto wait;
    }
    if (fread(vhdr, HDR, 1, vec) != 1 || memcmp(vhdr, VEC_MAGIC, 8) != 0) {
        printf("ERR: ppc603.vec is not a ppc603 vector file\n");
        goto wait;
    }
    build = get32(vhdr + V_BUILD);
    nvec = get32(vhdr + V_NVEC);
    printf("vectors: %lu, build %08lX\n", nvec, build);

    where = res_open();
    if (!where) {
        printf("ERR: cannot create ppc603.res anywhere\n");
        goto wait;
    }
    printf("results: ppc603.res %s\n", where);
    res_pos = HDR;
    memset(rhdr, 0, HDR);
    memcpy(rhdr, RES_MAGIC, 8);
    put32(rhdr + R_BUILD, build);
    put32(rhdr + R_NVEC, nvec);
    put32(rhdr + R_CPU, cpu);
    put32(rhdr + R_MACHINE, machine);
    put32(rhdr + R_SYSV, sysv);
    put32(rhdr + R_STATUS, RS_RUNNING);
    if (write_header(rhdr) != 0) {
        printf("ERR: cannot write ppc603.res\n");
        goto wait;
    }
    t0 = TickCount();
    printf("one dot per %d vectors:\n", CHUNK);

    while (ndone < nvec) {
        n = nvec - ndone;
        if (n > CHUNK) n = CHUNK;
        if (fread(entries, ENTRY, n, vec) != n) {
            printf("\nERR: short read of ppc603.vec at vector %lu\n", ndone);
            fail = 1;
            break;
        }
        for (i = 0; i < n; i++) {
            const unsigned char *in = entries + i * ENTRY;
            const unsigned char *exp = in + REC;
            unsigned char *out = results + i * REC;
            u32 w;
            run_vector(in, out);
            for (w = 0; w < REC; w += 4) {
                sum = ((sum << 1) | (sum >> 31)) + get32(out + w);
            }
            if ((get32(in + I_FLAGS) & F_HAS_EXPECTED) && memcmp(out, exp, REC) != 0) {
                if (nmiss < R_MISS_MAX)
                    put32(rhdr + R_MISS + 4 * nmiss, ndone + i);
                nmiss++;
            }
        }
        if (res_write(results, (long)REC * n) != 0) {
            printf("\nERR: write to ppc603.res failed at vector %lu\n", ndone);
            fail = 1;
            break;
        }
        ndone += n;
        put32(rhdr + R_NDONE, ndone);
        put32(rhdr + R_SUM, sum);
        put32(rhdr + R_NMISS, nmiss);
        put32(rhdr + R_TICKS, TickCount() - t0);
        if (write_header(rhdr) != 0) {
            printf("\nERR: header write failed at vector %lu\n", ndone);
            fail = 1;
            break;
        }
        putchar('.');
        if ((ndone / CHUNK) % 64 == 0) putchar('\n');
        fflush(stdout);
    }
    put32(rhdr + R_STATUS, fail ? RS_ABORTED : RS_DONE);
    put32(rhdr + R_TICKS, TickCount() - t0);
    write_header(rhdr);
    FSClose(res_ref);
    FlushVol(NULL, 0);
    fclose(vec);
    printf("\nn=%08lX sum=%08lX miss=%08lX ticks=%lu %s\n", ndone, sum, nmiss,
           (unsigned long)(TickCount() - t0), fail ? "ABORTED" : "write=ok");
    if (nmiss) {
        printf("first mismatches:");
        for (i = 0; i < nmiss && i < R_MISS_MAX; i++)
            printf(" #%lX", get32(rhdr + R_MISS + 4 * i));
        printf("\n");
    }
    printf("ppc603.res is %s. Decode it with ppc603test.py.\n", where);
wait:
    printf("(press Return to quit)\n");
    getchar();
    return 0;
}
