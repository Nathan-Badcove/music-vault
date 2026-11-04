# ⬢ AudVault v3.0

**AudVault** is a high-performance, native Qt6 (`PySide6`) desktop application for managing large local audio libraries, enforcing strict acoustic fingerprint deduplication, maintaining an acoustic blacklist of discarded tracks, and keeping relative UTF-8 `.m3u8` playlists in sync across devices.

---

## ⚡ Core Architecture & Features

### 1. Automated Ingestion (`yt-dlp`)
* Pulls liked tracks or playlist queues directly using browser cookie authentication.
* Automatically extracts audio, embeds thumbnails/ID3 metadata, and tracks history via an archive ledger so tracks are never downloaded twice.

### 2. Strict 25-Second Acoustic Fingerprint Audit (`czkawka_cli` + `Chromaprint`)
* Cross-references incoming tracks in `_New_Arrivals` against all existing library folders using a strict **25.0-second continuous waveform segment** (`--maximum-difference 1.5`).
* Eliminates false positives caused by shared intro pads or short samples while catching re-encoded duplicates across different bitrates.
* Automatically isolates matches into `_Quarantined_Dupes` with side-by-side audition buttons (**▶ Dupe** vs **▶ Orig**), **↩ Restore**, and **✖ Delete**.

### 3. Acoustic Blacklist Engine (`_Discarded_Songs`)
* Discarding an unwanted track records its **32-bit raw Chromaprint sub-fingerprints**, normalized title, duration, timestamp, and discard reason into `discarded_db.json`.
* Background worker threads automatically scan `_New_Arrivals` upon load—even if a previously discarded song is re-downloaded under a completely different filename, AudVault flags and isolates it via acoustic bit-similarity matching.

### 4. Smart Artist & Album Cover Splicer (`.m3u8` Sync)
* Converts legacy `.m3u` files and broken absolute paths into clean, portable, relative UTF-8 `.m3u8` playlists (`../Folder/Track.mp3`) with `#EXTINF` display headers.
* **Smart Splicing:** Reads embedded ID3 tags (`Artist`, `Album`) and hashes embedded cover art (`APIC`/`covr`). Newly sorted tracks are automatically spliced directly after existing tracks from the **same Album/Cover Art**, or at the end of that **Artist's block**, preserving custom playlist ordering.

### 5. Delta Recovery & YouTube Music Matcher
* Scans `.m3u8` playlists against physical folders to detect missing files.
* **Local Auto-Healer:** Automatically locates and copies missing tracks if they exist elsewhere on disk.
* **Live YT Matcher & Stream Preview:** Searches YouTube Music for genuinely missing tracks, allows instant live audio streaming inside the bottom player deck before downloading, or lets you link custom local/phone remixes via a file picker.

---

## 🛠 Dependencies

* **Python 3.10+** (`PySide6`, `mutagen`, `yt-dlp`)
* **System CLI Tools:** `czkawka_cli`, `fpcalc` (`chromaprint`), `ffmpeg` / `ffprobe`

### Arch Linux Quick Install
```bash
sudo pacman -S python-pyside6 python-mutagen yt-dlp chromaprint ffmpeg
paru -S czkawka-cli-bin
```

---

## 🚀 Running & Building

**Run directly from source (Development Mode):**
```bash
python3 music_vault_manager.py
```

**Compile a standalone native binary locally:**
```bash
./build_local.sh
```
