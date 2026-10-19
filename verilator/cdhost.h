// The Main's Mac CD layer for the machine bench: a disc image on block slot 4, served by
// Main_MiSTer's own support/mac/mac_cdrom.cpp (built from the MAIN_MISTER checkout into
// libmaincd.a, verilator/maincd), as mac.cpp's mac_sd_service and user_io.cpp hand it the
// core's requests on the board:
//
//   lba < 40000000          the data track as a flat disc of 2048-byte sectors, in
//                           512-byte blocks (mac_cdrom_fill)
//   40000000 + disc lba     CD-DA, a whole 2352-byte frame a block (user_io's blksz)
//   7C000000                the next audio frame of a PLAY, 2352 bytes and its status
//   7D000000 + op << 16     the command window (writes): the CDB at byte 496
//   7E000000 + op << 16     the response window: INQUIRY, MODE SENSE, the READ TOCs,
//   + cdb bytes             the sub-channel, AUDIO STATUS (mac_cdrom_window_fill)
//   7FFF0000                the "MCDA" TOC blob, two blocks
//
// CUE/BIN, CHD and raw 2352-byte images are translated (MAC_CDROM_HANDLED); a flat
// 2048-byte image (ISO, Toast) takes the Main's generic path, which serves the file's
// blocks as they are. A transfer of more than 4096 bytes leaves the Main's Mac path on
// the board (mac_sd_service's buffer); the bench says so if the core ever asks for one.

#pragma once

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>

extern "C++" {
#include "mac_cdrom.h"
}

struct CdHost {
	bool active = false;             // the Main translates the image
	FILE* flat = nullptr;            // ... or serves it as it is
	uint64_t bytes = 0;
	uint64_t data_reads = 0, cmds = 0, too_big = 0;

	bool mounted() const { return active || flat; }
	uint64_t size() const { return bytes; }

	bool mount(const std::string& path) {
		int r = mac_cdrom_mount(MAC_CDROM_SLOT, path.c_str());
		if (r == MAC_CDROM_REJECT) { std::fprintf(stderr, "the Main rejects %s\n", path.c_str()); return false; }
		if (r == MAC_CDROM_HANDLED) {
			active = true;
			bytes = mac_cdrom_size(MAC_CDROM_SLOT);
		} else {
			flat = std::fopen(path.c_str(), "rb");
			if (!flat) { std::fprintf(stderr, "cannot open %s\n", path.c_str()); return false; }
			std::fseek(flat, 0, SEEK_END);
			bytes = (uint64_t)std::ftell(flat);
		}
		std::printf("CD: %s, %s, %llu bytes\n", path.c_str(), active ? "translated by the Main" : "a flat image",
		            (unsigned long long)bytes);
		return true;
	}

	// the bytes a transfer of cnt blocks at lba moves (user_io.cpp: blksz)
	static int xfer_bytes(uint32_t lba, unsigned cnt) {
		bool cdda = lba >= MAC_CDROM_AUDIO_BLK && lba < MAC_CDROM_WIN_BASE;
		return (cdda ? 2352 : 512) * (int)cnt;
	}

	bool board_serves(int n) {
		if (n <= 4096) return true;
		if (too_big++ < 5) std::printf("note: a slot-4 transfer of %d bytes, which the board's Main does not serve\n", n);
		return false;
	}

	void fill(uint32_t lba, uint8_t* buf, int n) {
		std::memset(buf, 0, n);
		if (!board_serves(n)) return;
		if (flat) {
			std::fseek(flat, (long)((uint64_t)lba * 512), SEEK_SET);
			if (std::fread(buf, 1, n, flat) != (size_t)n) {}
			data_reads++;
			return;
		}
		if (lba >= MAC_CDROM_WIN_BASE && lba < MAC_CDROM_TOC_BLK) mac_cdrom_window_fill(lba, buf, n);
		else {
			mac_cdrom_fill(MAC_CDROM_SLOT, lba, buf, n);
			if (lba < MAC_CDROM_AUDIO_BLK) data_reads++;
		}
	}

	void command(uint32_t lba, const uint8_t* buf, int n) {
		if (!board_serves(n) || flat) return;
		if (lba >= MAC_CDROM_WIN_BASE && lba < MAC_CDROM_TOC_BLK) { mac_cdrom_command(lba, buf, n); cmds++; }
	}
};
