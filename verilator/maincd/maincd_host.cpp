// The Main's Mac CD layer on the host: what Main_MiSTer's support/mac/mac_cdrom.cpp,
// support/chd/mister_chd.cpp and lib/libchdr need from the rest of the Main, on stdio.
//
// With these the bench (and cdcheck) run the Main's own CD code, unchanged from the
// MAIN_MISTER checkout: CUE/BIN, CHD and raw images become the flat 2048-byte disc and
// the windows above it exactly as the board's Main serves them on block slot 4.
// Everything else of the Main (the SPI link to the FPGA, menus, the remount after the
// boot repulse, which the Pippin's "optimized" Mac SCSI path does not use) is left out.

#include <cstdio>
#include <cstring>
#include <ctime>

#include "file_io.h"
#include "hardware.h"
#include "user_io.h"

fileTYPE::fileTYPE() : filp(nullptr), mode(0), type(0), zip(nullptr), size(0), offset(0) { path[0] = 0; name[0] = 0; }
fileTYPE::~fileTYPE() { FileClose(this); }
int fileTYPE::opened() { return filp != nullptr; }

int FileOpen(fileTYPE* f, const char* name, char mute)
{
	FileClose(f);
	f->filp = std::fopen(name, "rb");
	if (!f->filp)
	{
		if (!mute) std::printf("FileOpen: cannot open %s\n", name);
		return 0;
	}
	std::fseek(f->filp, 0, SEEK_END);
	f->size = ftello(f->filp);
	std::fseek(f->filp, 0, SEEK_SET);
	f->offset = 0;
	std::snprintf(f->path, sizeof(f->path), "%s", name);
	const char* b = std::strrchr(name, '/');
	std::snprintf(f->name, sizeof(f->name), "%s", b ? b + 1 : name);
	return 1;
}

int FileClose(fileTYPE* f)
{
	if (f->filp) std::fclose(f->filp);
	f->filp = nullptr;
	f->size = 0;
	f->offset = 0;
	return 1;
}

int FileSeek(fileTYPE* f, __off64_t offset, int origin)
{
	if (!f->filp || fseeko(f->filp, offset, origin) != 0) return 0;
	f->offset = ftello(f->filp);
	return 1;
}

int FileReadAdv(fileTYPE* f, void* buf, int length, int failres)
{
	if (!f->filp) return failres;
	size_t n = std::fread(buf, 1, length, f->filp);
	if (n != (size_t)length && std::ferror(f->filp)) { std::clearerr(f->filp); return failres; }
	f->offset += n;
	return (int)n;
}

// paths are given whole here
const char* getFullPath(const char* name) { return name; }

static unsigned long now_ms()
{
	timespec t;
	clock_gettime(CLOCK_MONOTONIC, &t);
	return (unsigned long)(t.tv_sec * 1000 + t.tv_nsec / 1000000);
}
unsigned long GetTimer(unsigned long offset) { return now_ms() + offset; }
unsigned long CheckTimer(unsigned long t) { return (long)(now_ms() - t) >= 0; }

void diskled_on() {}

// the Pippin's CD: block slot 4, the "optimized" Mac SCSI path (the core's own CD target)
int mac_cdrom_slot() { return 4; }
char is_mac_scsi_optimized() { return 1; }
char mac_cd_read_keeps_audio() { return 1; }   // the Pippin: a data read leaves the CD audio playing

int user_io_file_mount(const char* name, unsigned char index, char, int)
{
	std::printf("maincd: the Main would remount %s on slot %u (not on the bench)\n", name, index);
	return 0;
}
