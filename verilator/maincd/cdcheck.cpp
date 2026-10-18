// cdcheck: a disc image through the Main's Mac CD layer, as the core reads it on block
// slot 4, summarised; with two images, whether the core would see the same disc in both
// (a CHD made from a CUE/BIN, say).
//
//   cdcheck IMAGE              its mount, size, TOC and a digest of each part
//   cdcheck IMAGE_A IMAGE_B    ... both, and exit 1 if any part differs
//
// The parts: every 512-byte block of the flat data disc, the "MCDA" TOC blob
// (7FFF0000), the READ TOC answers (7E43xxxx, formats 0-2), and every CD-DA frame of
// the audio tracks (40000000 + disc LBA, whole 2352-byte frames).

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

#include "support/mac/mac_cdrom.h"

namespace {

struct Digest {
	uint64_t h = 1469598103934665603ull;
	uint64_t n = 0;
	void add(const uint8_t* p, size_t len)
	{
		for (size_t i = 0; i < len; i++) { h ^= p[i]; h *= 1099511628211ull; }
		n += len;
	}
};

struct Summary {
	int mount = -1;
	uint64_t size = 0;
	Digest data, blob, toc, audio;
	uint64_t audio_frames = 0;
};

Summary check(const char* path)
{
	Summary s;
	s.mount = mac_cdrom_mount(MAC_CDROM_SLOT, path);
	std::printf("%s\n  mount: %s\n", path,
	            s.mount == MAC_CDROM_HANDLED ? "translated (the Main serves it)" :
	            s.mount == MAC_CDROM_PASSTHRU ? "flat 2048-byte image (the generic path)" : "REJECTED");
	if (s.mount != MAC_CDROM_HANDLED) return s;
	s.size = mac_cdrom_size(MAC_CDROM_SLOT);
	std::vector<uint8_t> buf(4096);
	for (uint64_t lba = 0; lba < s.size / 512; lba++)
	{
		mac_cdrom_fill(MAC_CDROM_SLOT, lba, buf.data(), 512);
		s.data.add(buf.data(), 512);
	}
	for (uint32_t k = 0; k < MAC_CDROM_TOC_BLKS; k++)
	{
		mac_cdrom_fill(MAC_CDROM_SLOT, MAC_CDROM_TOC_BLK + k, buf.data(), 512);
		s.blob.add(buf.data(), 512);
	}
	// the blob: "MCDA", then the tracks (see build_toc_blob); its first bytes printed
	std::printf("  data disc: %llu bytes (%llu sectors of 2048)\n  TOC blob:",
	            (unsigned long long)s.size, (unsigned long long)(s.size / 2048));
	mac_cdrom_fill(MAC_CDROM_SLOT, MAC_CDROM_TOC_BLK, buf.data(), 512);
	for (int i = 0; i < 32; i++) std::printf(" %02X", buf[i]);
	std::printf("\n");
	// the lead-out, from the blob (bytes 8-11, little-endian: mac_cd_build_blob)
	uint32_t leadout = (uint32_t)buf[8] | (uint32_t)buf[9] << 8 | (uint32_t)buf[10] << 16 | (uint32_t)buf[11] << 24;
	// READ TOC (43; the window's address carries CDB byte 9, the format in its bits 7-6,
	// and CDB byte 6, the first track): formats 0 from track 1 and from the lead-out, 1, 2
	static const uint8_t asks[][2] = {{0x00, 0x01}, {0x00, 0xAA}, {0x40, 0x00}, {0x80, 0x00}};
	for (auto& q : asks)
	{
		uint32_t lba = MAC_CDROM_RESP_BLK | (0x43u << 16) | ((uint32_t)q[0] << 8) | q[1];
		mac_cdrom_window_fill(lba, buf.data(), 512);
		s.toc.add(buf.data(), 512);
	}
	// CD-DA: every frame the Main would hand the player, 0 to the lead-out
	std::vector<uint8_t> fr(2352), zero(2352, 0);
	for (uint32_t d = 0; d < leadout; d++)
	{
		mac_cdrom_fill(MAC_CDROM_SLOT, MAC_CDROM_AUDIO_BLK + d, fr.data(), 2352);
		if (std::memcmp(fr.data(), zero.data(), 2352)) s.audio_frames++;
		s.audio.add(fr.data(), 2352);
	}
	std::printf("  lead-out %u; %llu CD-DA frames with sound\n", leadout, (unsigned long long)s.audio_frames);
	std::printf("  digests: data %016llX  blob %016llX  toc %016llX  audio %016llX\n",
	            (unsigned long long)s.data.h, (unsigned long long)s.blob.h, (unsigned long long)s.toc.h,
	            (unsigned long long)s.audio.h);
	mac_cdrom_unmount(MAC_CDROM_SLOT);
	return s;
}

} // namespace

int main(int argc, char** argv)
{
	if (argc < 2 || argc > 3)
	{
		std::fprintf(stderr, "usage: cdcheck IMAGE [IMAGE_B]\n");
		return 2;
	}
	Summary a = check(argv[1]);
	if (argc == 2) return a.mount == MAC_CDROM_HANDLED ? 0 : 1;
	Summary b = check(argv[2]);
	bool same = a.mount == b.mount && a.size == b.size && a.data.h == b.data.h && a.blob.h == b.blob.h &&
	            a.toc.h == b.toc.h && a.audio.h == b.audio.h;
	std::printf("%s\n", same ? "SAME: the core sees one disc in both" : "DIFFERENT");
	if (!same)
	{
		if (a.size != b.size) std::printf("  sizes differ\n");
		if (a.data.h != b.data.h) std::printf("  data differs\n");
		if (a.blob.h != b.blob.h) std::printf("  TOC blob differs\n");
		if (a.toc.h != b.toc.h) std::printf("  READ TOC differs\n");
		if (a.audio.h != b.audio.h) std::printf("  audio differs\n");
	}
	return same ? 0 : 1;
}
