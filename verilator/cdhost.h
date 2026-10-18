// The Main's Mac CD layer for the machine bench: a CUE/BIN disc served on block slot 4 as
// Main_MiSTer's support/mac/mac_cdrom.cpp serves it to the "optimized" Mac SCSI cores
// (MacPPC7300's and the Pippin's CD target, Pippin_scsidisk):
//
//   lba < 40000000          the data track as a flat disc of 2048-byte sectors, in
//                           512-byte blocks (the sector's user data: offset 16 in a
//                           MODE1/2352 sector, 24 in MODE2/2352, 0 in a 2048-byte one)
//   40000000 + disc lba     CD-DA, five blocks a frame (2352 bytes and a pad)
//   7C000000                the next audio frame of a PLAY, 2352 bytes and its status
//   7D000000 + op << 16     the command window (writes): the CDB at byte 496
//   7E000000 + op << 16     the response window: INQUIRY, MODE SENSE, the READ TOCs,
//   + cdb bytes             the sub-channel, AUDIO STATUS
//   7FFF0000                the "MCDA" TOC blob, two blocks
//
// The responses and the audio player are the Main's own code (mac_cdrom_resp.cpp and
// mac_cdrom_play.cpp, compiled into the bench from the Main checkout: MAIN_MISTER in the
// Makefile), so the core sees what the board's Main answers. The image reading is this
// file's: single- or multi-file CUE sheets, MODE1/2352, MODE2/2352, MODE1/2048 and AUDIO
// tracks, INDEX 00 as the pregap inside the file.

#pragma once

#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

extern "C++" {
#include "mac_cdrom_resp.h"
#include "mac_cdrom_play.h"
}

struct CdHost {
	struct Track {
		std::string file;
		FILE* f = nullptr;
		int sector_size = 2352;
		bool audio = false;
		int data_soff = 16;          // the user data's offset in a sector
		uint32_t start = 0;          // the disc LBA of INDEX 01
		uint32_t pregap = 0;         // INDEX 01 less INDEX 00
		uint32_t file_frame = 0;     // the frame in its file where the track's INDEX 01 is
		uint32_t frames = 0;         // from INDEX 01 to the track's end
	};
	std::vector<Track> tracks;
	int data_trk = -1;
	uint32_t sectors = 0;            // the data track's length
	uint32_t leadout = 0;
	mac_cd_toc toc{};
	mac_cd_play play{};
	uint8_t blob[1024] = {};
	uint64_t data_reads = 0, cmds = 0;

	bool mounted() const { return data_trk >= 0 || !tracks.empty(); }
	uint64_t size() const { return (uint64_t)sectors * 2048; }

	static uint32_t msf(const std::string& s) {
		unsigned m = 0, sec = 0, f = 0;
		std::sscanf(s.c_str(), "%u:%u:%u", &m, &sec, &f);
		return (m * 60 + sec) * 75 + f;
	}

	bool mount(const std::string& cue) {
		std::ifstream in(cue);
		if (!in) { std::fprintf(stderr, "cannot open %s\n", cue.c_str()); return false; }
		std::string dir = cue.substr(0, cue.find_last_of('/') + 1);
		std::string line, cur_file;
		struct Pending { Track t; int idx0 = -1, idx1 = -1; };
		std::vector<Pending> pend;
		std::vector<std::string> pend_file;
		while (std::getline(in, line)) {
			if (!line.empty() && line.back() == '\r') line.pop_back();
			std::istringstream ss(line);
			std::string kw;
			ss >> kw;
			if (kw == "FILE") {
				size_t a = line.find('"'), b = line.rfind('"');
				cur_file = dir + line.substr(a + 1, b - a - 1);
			} else if (kw == "TRACK") {
				std::string num, mode;
				ss >> num >> mode;
				Pending p;
				p.t.file = cur_file;
				p.t.audio = mode == "AUDIO";
				p.t.sector_size = (mode == "MODE1/2048") ? 2048 : 2352;
				p.t.data_soff = (mode == "MODE1/2352") ? 16 : (mode == "MODE2/2352") ? 24 : 0;
				pend.push_back(p);
			} else if (kw == "INDEX" && !pend.empty()) {
				std::string n, t;
				ss >> n >> t;
				if (n == "00") pend.back().idx0 = (int)msf(t);
				if (n == "01") pend.back().idx1 = (int)msf(t);
			}
		}
		// the disc: the files in order, each track's INDEX 01 at the frames before it
		uint32_t disc = 0;
		for (size_t i = 0; i < pend.size(); i++) {
			Track t = pend[i].t;
			bool new_file = i == 0 || pend[i].t.file != pend[i - 1].t.file;
			if (new_file) {
				t.f = std::fopen(t.file.c_str(), "rb");
				if (!t.f) { std::fprintf(stderr, "cannot open %s\n", t.file.c_str()); return false; }
			} else t.f = tracks.back().f;
			std::fseek(t.f, 0, SEEK_END);
			uint32_t file_frames = (uint32_t)(std::ftell(t.f) / t.sector_size);
			int i1 = pend[i].idx1 < 0 ? 0 : pend[i].idx1;
			t.file_frame = (uint32_t)i1;
			t.pregap = pend[i].idx0 >= 0 ? (uint32_t)(i1 - pend[i].idx0) : 0;
			if (new_file && i > 0) disc += 0;                     // (files follow each other)
			uint32_t file_base = new_file ? disc : tracks.back().start - tracks.back().file_frame;
			t.start = file_base + t.file_frame;
			// the track ends at the next track's INDEX 00 (or 01) in the same file, else the file's end
			uint32_t end_in_file = file_frames;
			if (i + 1 < pend.size() && pend[i + 1].t.file == pend[i].t.file)
				end_in_file = (uint32_t)(pend[i + 1].idx0 >= 0 ? pend[i + 1].idx0 : pend[i + 1].idx1);
			t.frames = end_in_file - t.file_frame;
			if (new_file) disc = file_base + file_frames;
			tracks.push_back(t);
		}
		leadout = disc;
		for (size_t i = 0; i < tracks.size(); i++)
			if (!tracks[i].audio) { data_trk = (int)i; break; }
		sectors = data_trk >= 0 ? tracks[data_trk].frames : 0;
		std::memset(&toc, 0, sizeof(toc));
		toc.n = (int)tracks.size();
		for (int i = 0; i < toc.n && i < MAC_CD_MAX_TRACKS; i++) {
			toc.ctrl[i] = tracks[i].audio ? 0x10 : 0x14;
			toc.start[i] = tracks[i].start;
			toc.pregap[i] = tracks[i].pregap;
		}
		toc.leadout = leadout;
		toc.data_trk = data_trk;
		mac_cd_build_blob(&toc, blob);
		mac_cd_play_init(&play);
		mac_cd_play_set_toc(&play, &toc);
		std::printf("CD: %s: %zu tracks, data track %d of %u sectors, lead-out %u\n", cue.c_str(), tracks.size(),
		    data_trk + 1, sectors, leadout);
		return true;
	}

	// a raw 2352-byte frame at a disc LBA (zeros outside the audio tracks)
	bool audio_frame(uint32_t lba, uint8_t* out) {
		for (auto& t : tracks)
			if (t.audio && lba >= t.start && lba < t.start + t.frames) {
				std::fseek(t.f, (long)(t.file_frame + (lba - t.start)) * t.sector_size, SEEK_SET);
				return std::fread(out, 1, 2352, t.f) == 2352;
			}
		return false;
	}

	// a read of n bytes at lba from slot 4
	void fill(uint32_t lba, uint8_t* buf, int n) {
		std::memset(buf, 0, n);
		if (lba >= 0x7E000000u && lba < 0x7F000000u) {                       // the response window
			uint8_t op = (uint8_t)(lba >> 16), a = (uint8_t)(lba >> 8), b = (uint8_t)lba;
			const mac_cd_toc* t = mounted() ? &toc : nullptr;
			mac_cd_pos pos;
			switch (op) {
				case 0x12: mac_cd_resp_inquiry(buf); break;
				case 0x1A: mac_cd_resp_mode_sense(a & 0x3F, sectors - 1, play.ports, buf); break;
				case 0x43: if (t) mac_cd_resp_toc_43(t, a, b, buf); break;
				case 0xC1: if (t) mac_cd_resp_toc_c1(t, a, b, buf); break;
				case 0x42: mac_cd_play_pos(&play, &pos); mac_cd_resp_subch(&pos, a, b, buf); break;
				case 0xC2: mac_cd_play_pos(&play, &pos); mac_cd_resp_subq(&pos, buf); break;
				case 0xCC: mac_cd_play_pos(&play, &pos); mac_cd_resp_astat(&pos, a, buf); break;
				default: break;
			}
			return;
		}
		if (lba >= 0x7FFF0000u && lba < 0x7FFF0002u) { std::memcpy(buf, blob + (lba - 0x7FFF0000u) * 512, 512); return; }
		if (lba == 0x7C000000u) {                                              // the next PLAY frame
			if (n < 2358) return;
			uint32_t flba = 0;
			int have = mac_cd_play_frame(&play, &flba);
			if (have && audio_frame(flba, buf)) mac_cd_play_scale(&play, (int16_t*)buf, 588);
			buf[2352] = mac_cd_play_ast(&play);
			buf[2353] = (uint8_t)have;
			for (int k = 0; k < 4; k++) buf[2354 + k] = (uint8_t)(play.flush_gen >> (8 * k));
			return;
		}
		if (lba >= 0x40000000u && lba < 0x7C000000u) {                        // CD-DA, five blocks a frame
			uint32_t rel = lba - 0x40000000u, dlba = rel / 5, part = rel % 5;
			uint8_t fr[2352];
			if (audio_frame(dlba, fr) && part * 512 < 2352)
				std::memcpy(buf, fr + part * 512, std::min<uint32_t>(512, 2352 - part * 512));
			return;
		}
		if (lba < 0x40000000u && data_trk >= 0) {                              // the data track
			if (lba * 512ull < (uint64_t)sectors * 2048) mac_cd_play_stop(&play);
			Track& t = tracks[data_trk];
			for (int pos = 0; pos < n; pos += 512) {
				uint64_t byte_pos = (uint64_t)(lba + pos / 512) * 512;
				uint32_t cd_lba = (uint32_t)(byte_pos >> 11), off = (uint32_t)(byte_pos & 2047);
				if (cd_lba >= sectors) break;
				std::fseek(t.f, (long)((uint64_t)(t.file_frame + cd_lba) * t.sector_size + t.data_soff + off), SEEK_SET);
				if (std::fread(buf + pos, 1, 512, t.f) != 512) std::memset(buf + pos, 0, 512);
			}
			data_reads++;
		}
	}

	// a write of 512 bytes at lba to slot 4: the command window
	void command(uint32_t lba, const uint8_t* buf) {
		if ((lba & 0xFF000000u) != 0x7D000000u) return;
		cmds++;
		uint8_t op = (uint8_t)(lba >> 16);
		const uint8_t* cdb = buf + 496;
		switch (op) {
			case 0xFF: mac_cd_play_init(&play); break;
			case 0xFE: case 0x1B: case 0xC0: mac_cd_play_stop(&play); break;
			case 0x15: mac_cd_play_command(&play, cdb, buf, cdb[4]); break;
			case 0x1E: case 0xBB: case 0xCE: break;
			default: mac_cd_play_command(&play, cdb, nullptr, 0); break;
		}
	}
};
