import sys
import os
import re
import json
import shutil
import subprocess
import urllib.parse
import hashlib
import ctypes
import ctypes.util
from datetime import datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLabel, QFileDialog, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QSlider, QLineEdit,
    QSpinBox, QComboBox, QFrame, QDialog, QListWidget, QListWidgetItem,
    QInputDialog, QMessageBox, QCheckBox, QAbstractItemView, QProgressBar
)
from PySide6.QtCore import QProcess, QProcessEnvironment, Qt, QUrl, QTimer, QThread, Signal
from PySide6.QtGui import QColor, QBrush, QTextCursor
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QMediaDevices


REFINED_WIREFRAME_STYLE = """
QMainWindow, QWidget, QDialog {
    background-color: #090a0f;
    color: #c5c6c7;
    font-family: "JetBrains Mono", "Fira Code", monospace;
    font-size: 12px;
}
QTabWidget::pane {
    border: 1px solid #1f2833;
    background-color: #090a0f;
}
QTabBar::tab {
    background: #10131a;
    border: 1px solid #1f2833;
    border-bottom: none;
    padding: 8px 16px;
    color: #8892b0;
}
QTabBar::tab:hover {
    background: #161b26;
    color: #66fcf1;
    border-color: #45a29e;
}
QTabBar::tab:selected {
    background: #161b26;
    color: #66fcf1;
    border: 1px solid #45a29e;
    border-bottom: 2px solid #ff2a54;
    font-weight: bold;
}

/* Base Interactive Button (Cyan Wireframe -> Crimson/Cyan Hover) */
QPushButton {
    background-color: #10131a;
    border: 1px solid #2b3945;
    color: #66fcf1;
    padding: 6px 12px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #1b2230;
    border: 1px solid #66fcf1;
    color: #ffffff;
}
QPushButton:pressed {
    background-color: #66fcf1;
    color: #090a0f;
}

/* Danger / Delete Variant (Subtle Crimson -> Bright Interactive Red Hover) */
QPushButton[variant="danger"] {
    background-color: #140a0e;
    border: 1px solid #801b32;
    color: #ff2a54;
}
QPushButton[variant="danger"]:hover {
    background-color: #2e0c17;
    border: 1px solid #ff2a54;
    color: #ffffff;
}
QPushButton[variant="danger"]:pressed {
    background-color: #ff2a54;
    color: #090a0f;
}

/* Restore / Action Variant (Cyan base -> Crimson Red highlight on hover) */
QPushButton[variant="restore"] {
    background-color: #10131a;
    border: 1px solid #45a29e;
    color: #66fcf1;
}
QPushButton[variant="restore"]:hover {
    background-color: #210d15;
    border: 1px solid #ff2a54;
    color: #ff2a54;
}
QPushButton[variant="restore"]:pressed {
    background-color: #ff2a54;
    color: #090a0f;
}

/* Accent Action Variant (Cyan base -> Crimson border highlight on hover) */
QPushButton[variant="accent"] {
    background-color: #10131a;
    border: 1px solid #45a29e;
    color: #66fcf1;
}
QPushButton[variant="accent"]:hover {
    background-color: #210d15;
    border: 1px solid #ff2a54;
    color: #ff2a54;
}
QPushButton[variant="accent"]:pressed {
    background-color: #ff2a54;
    color: #090a0f;
}

QLineEdit, QSpinBox, QComboBox, QListWidget {
    background-color: #10131a;
    border: 1px solid #2b3945;
    color: #66fcf1;
    padding: 5px;
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
    border: 1px solid #66fcf1;
}
QTableWidget {
    background-color: #07080c;
    gridline-color: #161c24;
    border: 1px solid #1f2833;
    color: #c5c6c7;
    selection-background-color: #16242f;
    selection-color: #66fcf1;
}
QHeaderView::section {
    background-color: #10131a;
    color: #66fcf1;
    padding: 6px 12px;
    border: 1px solid #1f2833;
    border-bottom: 2px solid #45a29e;
    font-weight: bold;
}
QTextEdit {
    background-color: #06070a;
    border: 1px solid #1f2833;
    color: #45a29e;
}
QCheckBox {
    color: #c5c6c7;
    spacing: 6px;
}
QProgressBar {
    background-color: #0c0e14;
    border: 1px solid #2b3945;
    color: #ffffff;
    text-align: center;
    font-weight: bold;
    height: 20px;
}
QProgressBar::chunk {
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 #1b4d54, stop:0.75 #45a29e, stop:1 #ff2a54
    );
}
QSlider::groove:horizontal {
    height: 4px;
    background: #1f2833;
}
QSlider::sub-page:horizontal {
    background: #45a29e;
}
QSlider::handle:horizontal {
    background: #66fcf1;
    border: 1px solid #ff2a54;
    width: 12px;
    margin: -5px 0;
}
"""

SYSTEM_FOLDERS = {
    "Playlist masterfiles",
    "playlist M3U files",
    "_New_Arrivals",
    "_Quarantined_Dupes",
    "_Discarded_Songs",
    "_M3U_Safety_Backup"
}



def get_base_bundle_dir():
    """Returns PyInstaller/Nuitka temp bundle dir if frozen, or script directory if running raw .py."""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def get_bin(tool_name: str) -> str:
    """
    Dual-mode binary resolver:
      1. Checks bundled ./bin/<tool_name>(.exe) for standalone distributed builds.
      2. Falls back to system PATH (shutil.which) for local Arch Linux development.
    """
    ext = ".exe" if sys.platform.startswith("win") else ""
    bundle_dir = get_base_bundle_dir()
    for sub in ("bin", ""):
        candidate = os.path.join(bundle_dir, sub, f"{tool_name}{ext}")
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    found = shutil.which(f"{tool_name}{ext}") or shutil.which(tool_name)
    return found if found else f"{tool_name}{ext}"


def get_chromaprint_lib_path() -> str:
    """Resolves libchromaprint shared library across Linux (.so), Windows (.dll), and macOS (.dylib)."""
    bundle_dir = get_base_bundle_dir()
    if sys.platform.startswith("win"):
        names = ["chromaprint.dll", "libchromaprint.dll"]
    elif sys.platform == "darwin":
        names = ["libchromaprint.1.dylib", "libchromaprint.dylib"]
    else:
        names = ["libchromaprint.so.1", "libchromaprint.so"]

    for sub in ("bin", ""):
        for n in names:
            cand = os.path.join(bundle_dir, sub, n)
            if os.path.isfile(cand):
                return cand

    found = ctypes.util.find_library("chromaprint")
    return found if found else names[0]


def set_btn_variant(btn: QPushButton, variant: str):
    btn.setProperty("variant", variant)
    btn.style().unpolish(btn)
    btn.style().polish(btn)



class StagingFingerprintWorker(QThread):
    """Non-blocking background worker that computes Chromaprint raw & base64 fingerprints for _New_Arrivals."""
    file_scanned = Signal(str, dict)  # filepath, fp_data

    def __init__(self, filepaths):
        super().__init__()
        self.filepaths = filepaths
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        for fp in self.filepaths:
            if self._stop:
                break
            if not os.path.exists(fp):
                continue
            try:
                res_raw = subprocess.run(
                    [get_bin("fpcalc"), "-raw", "-length", "60", "-json", fp],
                    capture_output=True, text=True, timeout=10
                )
                if res_raw.returncode == 0 and res_raw.stdout:
                    d2 = json.loads(res_raw.stdout)
                    raw_ints = d2.get("fingerprint", [])[:120]
                    dur = float(d2.get("duration", 0.0))
                    fp_str = ",".join(str(x) for x in raw_ints[:24])
                    if raw_ints:
                        self.file_scanned.emit(fp, {
                            "fingerprint": fp_str,
                            "raw_fingerprint": raw_ints,
                            "duration": dur
                        })
            except Exception:
                pass


class MultiSortDialog(QDialog):
    """Popup dialog allowing multi-folder selection, new folder creation, or blacklisting."""
    def __init__(self, parent, track_names, available_folders):
        super().__init__(parent)
        self.setWindowTitle("AudVault v3.0 // Route or Discard Track(s)")
        self.resize(460, 520)
        self.available_folders = sorted(available_folders)
        self.selected_folders = []
        self.action_type = None

        layout = QVBoxLayout(self)

        title_text = (
            f"TARGET: {track_names[0]}" if len(track_names) == 1
            else f"TARGET: {len(track_names)} selected tracks"
        )
        lbl = QLabel(title_text)
        lbl.setStyleSheet("color: #66fcf1; font-weight: bold; font-size: 13px;")
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        layout.addWidget(QLabel("Check one or more destination playlist folders:"))

        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter folders...")
        self.filter_input.textChanged.connect(self.filter_folders)
        layout.addWidget(self.filter_input)

        self.folder_list = QListWidget()
        self.populate_list()
        layout.addWidget(self.folder_list)

        btn_new_folder = QPushButton("+ CREATE NEW PLAYLIST FOLDER...")
        set_btn_variant(btn_new_folder, "restore")
        btn_new_folder.clicked.connect(self.create_new_folder)
        layout.addWidget(btn_new_folder)

        action_row = QHBoxLayout()
        btn_sort = QPushButton("✔ MOVE / COPY TO SELECTED")
        set_btn_variant(btn_sort, "restore")
        btn_sort.clicked.connect(self.confirm_sort)

        btn_discard = QPushButton("✖ DISCARD & BLACKLIST...")
        set_btn_variant(btn_discard, "danger")
        btn_discard.clicked.connect(self.confirm_discard)

        action_row.addWidget(btn_sort)
        action_row.addWidget(btn_discard)
        layout.addLayout(action_row)

        btn_cancel = QPushButton("CANCEL")
        btn_cancel.clicked.connect(self.reject)
        layout.addWidget(btn_cancel)

    def populate_list(self, filter_str=""):
        checked_now = self.get_checked()
        self.folder_list.clear()
        for folder in self.available_folders:
            if filter_str.lower() in folder.lower():
                item = QListWidgetItem(folder)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked if folder in checked_now else Qt.Unchecked)
                self.folder_list.addItem(item)

    def filter_folders(self, text):
        self.populate_list(text)

    def get_checked(self):
        checked = set()
        for i in range(self.folder_list.count()):
            item = self.folder_list.item(i)
            if item.checkState() == Qt.Checked:
                checked.add(item.text())
        return checked

    def create_new_folder(self):
        name, ok = QInputDialog.getText(
            self, "Create New Playlist Folder", "Enter new playlist folder name:"
        )
        if ok and name.strip():
            clean_name = name.strip()
            if clean_name not in self.available_folders:
                self.available_folders.append(clean_name)
                self.available_folders.sort()
            self.populate_list(self.filter_input.text())
            for i in range(self.folder_list.count()):
                item = self.folder_list.item(i)
                if item.text() == clean_name:
                    item.setCheckState(Qt.Checked)

    def confirm_sort(self):
        self.selected_folders = list(self.get_checked())
        if not self.selected_folders:
            QMessageBox.warning(self, "No Folder Selected", "Please check at least one destination folder.")
            return
        self.action_type = "sort"
        self.accept()

    def confirm_discard(self):
        self.action_type = "discard"
        self.accept()


class MusicVaultApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AudVault v3.0")
        self.resize(1280, 800)
        self.setStyleSheet(REFINED_WIREFRAME_STYLE)

        default_vault = os.path.expanduser("~/Music/playlist backup")
        self.base_dir = default_vault if os.path.exists(default_vault) else os.path.expanduser("~/Music")
        self.process = None
        self.active_task_mode = None
        self.staging_fingerprint_cache = {}
        self.fp_worker = None
        self.metadata_cache = {}

        # Elapsed & percentage telemetry timer for acoustic scans
        self.task_timer = QTimer(self)
        self.task_timer.timeout.connect(self.update_elapsed_telemetry)
        self.task_start_ts = None
        self.total_library_files = 0
        self.total_staging_files = 0
        self.estimated_scan_secs = 120.0
        self.czkawka_reported_pct = 0
        self.ytdlp_current_idx = 0
        self.ytdlp_total_idx = 0

        # Internal Media Player Setup (Explicitly bound to system default audio sink)
        self.player = QMediaPlayer(self)
        default_device = QMediaDevices.defaultAudioOutput()
        self.audio_output = QAudioOutput(default_device, self)
        self.audio_output.setMuted(False)
        self.audio_output.setVolume(0.9)
        self.player.setAudioOutput(self.audio_output)

        self.player.positionChanged.connect(self.update_slider_position)
        self.player.durationChanged.connect(self.update_slider_duration)

        self.init_ui()
        self.refresh_staging_table()
        self.refresh_discarded_table()
        self.refresh_playlist_stats_table()

    def init_ui(self):
        root = QWidget()
        main_layout = QVBoxLayout(root)

        # --- Top Bar: Telemetry Header & Library Root ---
        top_bar = QHBoxLayout()
        brand_lbl = QLabel("⬢ AudVault v3.0")
        brand_lbl.setStyleSheet("color: #ff2a54; font-weight: bold; font-size: 13px; padding-right: 12px;")
        self.dir_label = QLabel(f"ROOT: {self.base_dir}")
        self.dir_label.setStyleSheet("color: #66fcf1; font-weight: bold;")
        btn_dir = QPushButton("SELECT LIBRARY ROOT")
        btn_dir.clicked.connect(self.select_directory)

        top_bar.addWidget(brand_lbl)
        top_bar.addWidget(self.dir_label)
        top_bar.addStretch()
        top_bar.addWidget(btn_dir)
        main_layout.addLayout(top_bar)

        # --- Controls Row ---
        ctrl_bar = QHBoxLayout()

        ctrl_bar.addWidget(QLabel("Cookies:"))
        self.browser_combo = QComboBox()
        self.browser_combo.addItems(["firefox", "chromium", "brave", "chrome"])
        ctrl_bar.addWidget(self.browser_combo)

        ctrl_bar.addWidget(QLabel("Max Fetch:"))
        self.max_spin = QSpinBox()
        self.max_spin.setRange(1, 5000)
        self.max_spin.setValue(350)
        ctrl_bar.addWidget(self.max_spin)

        self.btn_fetch = QPushButton("1. INGEST LIKED TRACKS")
        set_btn_variant(self.btn_fetch, "accent")
        self.btn_fetch.clicked.connect(self.run_ytdlp)

        self.btn_dedupe = QPushButton("2. ACOUSTIC FINGERPRINT AUDIT (25s STRICT)")
        set_btn_variant(self.btn_dedupe, "accent")
        self.btn_dedupe.clicked.connect(self.run_czkawka_audit)

        self.btn_m3u = QPushButton("3. CONSOLIDATE DUMPS & SYNC PLAYLISTS")
        set_btn_variant(self.btn_m3u, "accent")
        self.btn_m3u.clicked.connect(self.consolidate_and_rebuild_playlists)

        self.chk_recluster_existing = QCheckBox("Re-Cluster Existing M3U8s by Artist/Album")
        self.chk_recluster_existing.setToolTip(
            "When unchecked, preserves your exact existing M3U8 order and smartly splices ONLY new tracks into matching Artist/Album blocks.\n"
            "When checked, also groups existing tracks in every M3U8 by Artist & Album Cover."
        )
        self.chk_recluster_existing.setChecked(False)

        ctrl_bar.addSpacing(10)
        ctrl_bar.addWidget(self.btn_fetch)
        ctrl_bar.addWidget(self.btn_dedupe)
        ctrl_bar.addWidget(self.btn_m3u)
        ctrl_bar.addWidget(self.chk_recluster_existing)
        main_layout.addLayout(ctrl_bar)

        # --- Telemetry & Live Percentage Progress Bar Row ---
        prog_frame = QFrame()
        prog_frame.setStyleSheet("border: 1px solid #1f2833; background-color: #0c0e14; padding: 4px;")
        prog_layout = QHBoxLayout(prog_frame)
        prog_layout.setContentsMargins(8, 4, 8, 4)

        self.telemetry_label = QLabel("TELEMETRY // IDLE — READY FOR INGEST OR CHROMAPRINT SCAN")
        self.telemetry_label.setStyleSheet("color: #66fcf1; font-weight: bold; min-width: 480px;")

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("STANDBY — 0%")

        prog_layout.addWidget(self.telemetry_label)
        prog_layout.addWidget(self.progress_bar, stretch=1)
        main_layout.addWidget(prog_frame)

        # --- Main Tabs ---
        self.tabs = QTabWidget()

        # Tab 1: Interactive Staging & Sorter (_New_Arrivals)
        self.staging_tab = QWidget()
        staging_layout = QVBoxLayout(self.staging_tab)

        staging_top = QHBoxLayout()
        self.staging_status_lbl = QLabel("Staging Queue (_New_Arrivals):")
        self.chk_autoplay = QCheckBox("Auto-Play Next Track After Sorting/Discarding")
        self.chk_autoplay.setChecked(True)

        btn_bulk_sort = QPushButton("SORT / DISCARD SELECTED ROWS...")
        set_btn_variant(btn_bulk_sort, "accent")
        btn_bulk_sort.clicked.connect(self.sort_selected_staging_rows)

        btn_refresh_staging = QPushButton("REFRESH STAGING")
        btn_refresh_staging.clicked.connect(self.refresh_staging_table)

        staging_top.addWidget(self.staging_status_lbl)
        staging_top.addStretch()
        staging_top.addWidget(self.chk_autoplay)
        staging_top.addWidget(btn_bulk_sort)
        staging_top.addWidget(btn_refresh_staging)
        staging_layout.addLayout(staging_top)

        self.staging_table = QTableWidget(0, 5)
        self.staging_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.staging_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.staging_table.setHorizontalHeaderLabels([
            "Track Filename",
            "Blacklist / Status Audit",
            "Size",
            "Preview Audio",
            "Route / Discard Action"
        ])
        self.staging_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.staging_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        for col_idx in (2, 3, 4):
            self.staging_table.horizontalHeader().setSectionResizeMode(col_idx, QHeaderView.ResizeToContents)
        staging_layout.addWidget(self.staging_table)
        self.tabs.addTab(self.staging_tab, "1. STAGING & SORTER (_New_Arrivals)")

        # Tab 2: Duplicate Audit Report (With Interactive Per-Row Restore & Delete)
        self.audit_tab = QWidget()
        audit_layout = QVBoxLayout(self.audit_tab)

        audit_header = QHBoxLayout()
        self.audit_summary = QLabel(
            "Run '2. Acoustic Fingerprint Audit' to scan _New_Arrivals against your 26 folders."
        )
        btn_purge_quarantine = QPushButton("✖ WIPE ALL REMAINING QUARANTINED DUPES")
        set_btn_variant(btn_purge_quarantine, "danger")
        btn_purge_quarantine.clicked.connect(self.wipe_quarantine)
        audit_header.addWidget(self.audit_summary)
        audit_header.addStretch()
        audit_header.addWidget(btn_purge_quarantine)
        audit_layout.addLayout(audit_header)

        self.audit_table = QTableWidget(0, 8)
        self.audit_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.audit_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.audit_table.setHorizontalHeaderLabels([
            "Quarantined Track (_New_Arrivals)",
            "Matched Existing Track (Library)",
            "Playlist Folder",
            "Match Info",
            "Audition Dupe",
            "Audition Orig",
            "False Positive",
            "Confirm Dupe"
        ])
        self.audit_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.audit_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        for col_idx in range(2, 8):
            self.audit_table.horizontalHeader().setSectionResizeMode(col_idx, QHeaderView.ResizeToContents)
        audit_layout.addWidget(self.audit_table)
        self.tabs.addTab(self.audit_tab, "2. DUPLICATE AUDIT REPORT")

        # Tab 3: Discarded Songs Blacklist Ledger
        self.discard_tab = QWidget()
        discard_layout = QVBoxLayout(self.discard_tab)

        discard_header = QHBoxLayout()
        discard_header.addWidget(QLabel(
            "Discarded Songs Blacklist (_Discarded_Songs/discarded_songs_log.txt):"
        ))
        btn_refresh_discard = QPushButton("REFRESH BLACKLIST")
        btn_refresh_discard.clicked.connect(self.refresh_discarded_table)
        discard_header.addStretch()
        discard_header.addWidget(btn_refresh_discard)
        discard_layout.addLayout(discard_header)

        self.discard_table = QTableWidget(0, 4)
        self.discard_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.discard_table.setHorizontalHeaderLabels([
            "Date Discarded",
            "Original Filename",
            "Reason for Discarding",
            "Acoustic Fingerprint ID (Preview)"
        ])
        self.discard_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.discard_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.discard_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.discard_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        discard_layout.addWidget(self.discard_table)
        self.tabs.addTab(self.discard_tab, "3. DISCARDED SONGS BLACKLIST")

        # Tab 4: Local Playlists & Cross-Reference Overview
        self.stats_tab = QWidget()
        stats_layout = QVBoxLayout(self.stats_tab)

        stats_header = QHBoxLayout()
        self.stats_summary_lbl = QLabel("Library Cross-Reference Overview:")
        self.stats_summary_lbl.setStyleSheet("color: #66fcf1; font-weight: bold;")
        btn_refresh_stats = QPushButton("REFRESH COUNTS")
        set_btn_variant(btn_refresh_stats, "restore")
        btn_refresh_stats.clicked.connect(self.refresh_playlist_stats_table)
        stats_header.addWidget(self.stats_summary_lbl)
        stats_header.addStretch()
        stats_header.addWidget(btn_refresh_stats)
        stats_layout.addLayout(stats_header)

        self.stats_table = QTableWidget(0, 5)
        self.stats_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.stats_table.setHorizontalHeaderLabels([
            "Playlist / Folder Name",
            "Files in Folder (Disk)",
            "Tracks in .m3u8",
            "Sync / Cross-Ref Status",
            "Folder Size"
        ])
        self.stats_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for col_idx in (1, 2, 3, 4):
            self.stats_table.horizontalHeader().setSectionResizeMode(col_idx, QHeaderView.ResizeToContents)
        stats_layout.addWidget(self.stats_table)
        self.tabs.addTab(self.stats_tab, "4. PLAYLISTS & CROSS-REF")

        # Tab 5: Delta Recovery & YouTube Music Search/Preview/Heal
        self.delta_tab = QWidget()
        delta_layout = QVBoxLayout(self.delta_tab)

        delta_top = QHBoxLayout()
        self.delta_status_lbl = QLabel(
            "Delta Recovery: Scans .m3u8 files for missing tracks, auto-heals local cross-folder files, and searches YT Music."
        )
        self.delta_status_lbl.setStyleSheet("color: #66fcf1; font-weight: bold;")

        btn_scan_delta = QPushButton("1. SCAN & AUTO-HEAL LOCAL DELTAS")
        set_btn_variant(btn_scan_delta, "restore")
        btn_scan_delta.clicked.connect(self.scan_and_heal_deltas)

        btn_search_all = QPushButton("2. AUTO-SEARCH ALL MISSING ON YT")
        set_btn_variant(btn_search_all, "accent")
        btn_search_all.clicked.connect(self.batch_search_all_deltas)

        delta_top.addWidget(self.delta_status_lbl)
        delta_top.addStretch()
        delta_top.addWidget(btn_scan_delta)
        delta_top.addWidget(btn_search_all)
        delta_layout.addLayout(delta_top)

        self.delta_table = QTableWidget(0, 8)
        self.delta_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.delta_table.setHorizontalHeaderLabels([
            "Playlist (.m3u8)",
            "Missing Filename in .m3u8",
            "YT Music Match / Status",
            "1. Search YT",
            "2. Preview Match",
            "3. Download & Fix",
            "4. Pick File (Phone/Local)",
            "5. Remove Dead Line"
        ])
        self.delta_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.delta_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        for col_idx in (0, 3, 4, 5, 6, 7):
            self.delta_table.horizontalHeader().setSectionResizeMode(col_idx, QHeaderView.ResizeToContents)
        delta_layout.addWidget(self.delta_table)
        self.tabs.addTab(self.delta_tab, "5. DELTA RECOVERY & YT MATCHER")

        # Tab 6: Non-Corruptible Live Process Terminal
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setTextInteractionFlags(Qt.NoTextInteraction)
        self.tabs.addTab(self.console, "6. SYSTEM TERMINAL LOG")

        main_layout.addWidget(self.tabs)

        # --- Bottom Deck: Internal Audio Player ---
        player_frame = QFrame()
        player_frame.setStyleSheet("border-top: 1px solid #45a29e; background-color: #0c0e14; padding-top: 6px;")
        player_layout = QHBoxLayout(player_frame)

        self.btn_play_pause = QPushButton("▶ / ⏸ PLAY/PAUSE")
        set_btn_variant(self.btn_play_pause, "accent")
        self.btn_play_pause.clicked.connect(self.toggle_playback)

        self.btn_stop = QPushButton("■ STOP")
        self.btn_stop.clicked.connect(self.player.stop)

        self.now_playing_label = QLabel("AUDIO_LINK // IDLE — Select any track to audition")
        self.now_playing_label.setStyleSheet("color: #66fcf1; font-weight: bold; min-width: 360px;")

        self.seek_slider = QSlider(Qt.Horizontal)
        self.seek_slider.sliderMoved.connect(self.player.setPosition)

        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setStyleSheet("color: #66fcf1; font-weight: bold;")

        player_layout.addWidget(self.btn_play_pause)
        player_layout.addWidget(self.btn_stop)
        player_layout.addWidget(self.now_playing_label)
        player_layout.addWidget(self.seek_slider, stretch=1)
        player_layout.addWidget(self.time_label)

        main_layout.addWidget(player_frame)
        self.setCentralWidget(root)

    # =========================================================================
    # Visual Row Highlighting for Active Audio Playback
    # =========================================================================
    def highlight_playing_row(self, table: QTableWidget, active_row: int):
        """Highlights the currently playing row with a sleek dark cyan/crimson accent."""
        active_bg = QBrush(QColor("#1c111b"))
        active_fg = QBrush(QColor("#66fcf1"))
        default_bg = QBrush(QColor("#07080c"))
        default_fg = QBrush(QColor("#c5c6c7"))

        for r in range(table.rowCount()):
            is_active = (r == active_row)
            for c in range(table.columnCount()):
                item = table.item(r, c)
                if item:
                    item.setBackground(active_bg if is_active else default_bg)
                    if "⚠️" not in item.text():
                        item.setForeground(active_fg if is_active else default_fg)
        if 0 <= active_row < table.rowCount():
            table.selectRow(active_row)

    def find_row_by_widget(self, table: QTableWidget, widget) -> int:
        for r in range(table.rowCount()):
            for c in range(table.columnCount()):
                if table.cellWidget(r, c) == widget:
                    return r
        return -1

    # =========================================================================
    # Cursor-Safe Terminal Logging & Live Progress Percentage Parser
    # =========================================================================
    def log(self, text):
        self.append_stream(text + "\n")

    def append_stream(self, raw_text):
        """Always appends strictly at the very end of the console, regardless of user clicks."""
        if not raw_text:
            return
        cleaned = raw_text.replace("\r\n", "\n").replace("\r", "\n")
        cursor = self.console.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(cleaned)
        self.console.setTextCursor(cursor)
        self.console.ensureCursorVisible()

        self.parse_progress_from_output(cleaned)

    def parse_progress_from_output(self, text):
        if self.active_task_mode == "ytdlp":
            m_item = re.search(r'Downloading item (\d+) of (\d+)', text)
            if m_item:
                self.ytdlp_current_idx = int(m_item.group(1))
                self.ytdlp_total_idx = int(m_item.group(2))

            m_pct = re.search(r'\[download\]\s+(\d+(?:\.\d+)?)%', text)
            if m_pct:
                file_pct = float(m_pct.group(1))
                if self.ytdlp_total_idx > 0:
                    overall = ((self.ytdlp_current_idx - 1) + (file_pct / 100.0)) / self.ytdlp_total_idx * 100.0
                    self.progress_bar.setRange(0, 100)
                    self.progress_bar.setValue(int(overall))
                    self.progress_bar.setFormat(
                        f"INGESTING [{self.ytdlp_current_idx}/{self.ytdlp_total_idx}] — {file_pct:.1f}% (TOTAL: {overall:.1f}%)"
                    )
                    self.telemetry_label.setText(
                        f"TELEMETRY // YT-DLP TRACK {self.ytdlp_current_idx} OF {self.ytdlp_total_idx}"
                    )
                else:
                    self.progress_bar.setRange(0, 100)
                    self.progress_bar.setValue(int(file_pct))
                    self.progress_bar.setFormat(f"DOWNLOADING — {file_pct:.1f}%")

        elif self.active_task_mode == "czkawka":
            m_pct = re.search(r'(\d{1,3})%', text)
            if m_pct:
                self.czkawka_reported_pct = min(99, int(m_pct.group(1)))

    def update_elapsed_telemetry(self):
        if not self.task_start_ts or self.active_task_mode != "czkawka":
            return
        elapsed = (datetime.now() - self.task_start_ts).total_seconds()
        mins, secs = divmod(int(elapsed), 60)

        # Compute smooth percentage from 1% to 99% based on file count & CPU throughput
        # Uses asymptote after 85% so if uncached files take longer, it keeps advancing cleanly to 99%
        ratio = elapsed / max(10.0, self.estimated_scan_secs)
        if ratio <= 0.85:
            calc_pct = int(ratio * 100)
        else:
            extra = ratio - 0.85
            calc_pct = int(85 + 14 * (1.0 - (1.0 / (1.0 + extra * 1.5))))
        pct = max(1, min(99, max(calc_pct, self.czkawka_reported_pct)))

        if pct < 12:
            stage = "STAGE 1/3: Indexing 26 Folders & Audio Headers"
        elif pct < 82:
            stage = "STAGE 2/3: Computing 25s Chromaprint Waveforms"
        else:
            stage = "STAGE 3/3: Cross-Matching Acoustic Signatures"

        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(pct)
        self.progress_bar.setFormat(f"ACOUSTIC FINGERPRINT AUDIT — {pct}% ({mins:02d}m {secs:02d}s)")

        self.telemetry_label.setText(
            f"TELEMETRY // {stage} [{pct}%] | {self.total_staging_files} New vs {self.total_library_files} Lib Files"
        )

    # =========================================================================
    # Blacklist & Chromaprint Fingerprint Engine (_Discarded_Songs)
    # =========================================================================
    def get_discard_dir(self):
        d = os.path.join(self.base_dir, "_Discarded_Songs")
        os.makedirs(d, exist_ok=True)
        return d

    def get_discard_db_path(self):
        return os.path.join(self.get_discard_dir(), "discarded_db.json")

    def get_discard_log_path(self):
        return os.path.join(self.get_discard_dir(), "discarded_songs_log.txt")

    def load_discard_db(self):
        db_path = self.get_discard_db_path()
        if not os.path.exists(db_path):
            return []
        try:
            with open(db_path, "r", encoding="utf-8") as f:
                db = json.load(f)
            return db if isinstance(db, list) else []
        except Exception:
            return []

    def compute_fingerprint(self, filepath):
        if filepath in self.staging_fingerprint_cache:
            cached = self.staging_fingerprint_cache[filepath]
            return cached.get("fingerprint", ""), cached.get("duration", 0.0), cached.get("raw_fingerprint", [])
        try:
            res_raw = subprocess.run(
                [get_bin("fpcalc"), "-raw", "-length", "60", "-json", filepath],
                capture_output=True, text=True, timeout=8
            )
            if res_raw.returncode == 0 and res_raw.stdout:
                d2 = json.loads(res_raw.stdout)
                raw_ints = d2.get("fingerprint", [])[:120]
                dur = float(d2.get("duration", 0.0))
                fp_str = ",".join(str(x) for x in raw_ints[:24])
                if raw_ints:
                    self.staging_fingerprint_cache[filepath] = {
                        "fingerprint": fp_str,
                        "raw_fingerprint": raw_ints,
                        "duration": dur
                    }
                return fp_str, dur, raw_ints
        except Exception:
            pass
        return "", 0.0, []

    def decode_base64_fingerprint_to_raw(self, b64_fp: str):
        """Decodes a standard base64 Chromaprint string from discarded_db.json into raw 32-bit integers."""
        if not b64_fp:
            return []
        try:
            lib_name = get_chromaprint_lib_path()
            lib = ctypes.CDLL(lib_name)
            lib.chromaprint_decode_fingerprint.argtypes = [
                ctypes.c_char_p, ctypes.c_int,
                ctypes.POINTER(ctypes.POINTER(ctypes.c_uint32)),
                ctypes.POINTER(ctypes.c_int),
                ctypes.POINTER(ctypes.c_int),
                ctypes.c_int
            ]
            lib.chromaprint_decode_fingerprint.restype = ctypes.c_int
            lib.chromaprint_dealloc.argtypes = [ctypes.c_void_p]

            raw_ptr = ctypes.POINTER(ctypes.c_uint32)()
            size = ctypes.c_int(0)
            algo = ctypes.c_int(0)
            b_data = b64_fp.encode("ascii", errors="ignore")

            res = lib.chromaprint_decode_fingerprint(
                b_data, len(b_data),
                ctypes.byref(raw_ptr), ctypes.byref(size), ctypes.byref(algo), 1
            )
            if res == 1 and size.value > 0:
                ints = [int(raw_ptr[i]) for i in range(min(120, size.value))]
                lib.chromaprint_dealloc(raw_ptr)
                return ints
        except Exception:
            pass
        return []

    def raw_fingerprints_match(self, raw_a, raw_b):
        """Ultra-fast Chromaprint 32-bit comparison using int.bit_count() so UI never lags."""
        if not raw_a or not raw_b or len(raw_a) < 12 or len(raw_b) < 12:
            return False
        a = raw_a[:60]
        b = raw_b[:60]
        # Fast exact sub-fingerprint overlap check first
        if len(set(a) & set(b)) >= 8:
            return True
        min_len = min(len(a), len(b))
        for offset in range(-4, 5):
            diff_bits = 0
            compared = 0
            for i in range(min_len):
                j = i + offset
                if 0 <= j < len(b):
                    diff_bits += ((a[i] ^ b[j]) & 0xFFFFFFFF).bit_count()
                    compared += 32
            if compared >= 256 and (1.0 - (diff_bits / compared)) >= 0.82:
                return True
        return False

    def check_if_discarded(self, filepath, compute_if_missing=False):
        db = self.load_discard_db()
        if not db:
            return None

        fname = os.path.basename(filepath)
        norm_name = re.sub(r'[^\w]', '', os.path.splitext(fname)[0].lower())

        # 1. Fast normalized filename check
        for entry in db:
            saved_norm = re.sub(r'[^\w]', '', os.path.splitext(entry.get("filename", ""))[0].lower())
            if norm_name and saved_norm and norm_name == saved_norm:
                return entry

        # 2. Acoustic Chromaprint check (decodes legacy base64 entries on the fly if raw_fingerprint is missing!)
        if compute_if_missing or filepath in self.staging_fingerprint_cache:
            fp, dur, raw_ints = self.compute_fingerprint(filepath)
            if not raw_ints and fp:
                raw_ints = self.decode_base64_fingerprint_to_raw(fp)

            db_updated = False
            matched_entry = None
            for entry in db:
                saved_fp = entry.get("fingerprint", "")
                saved_raw = entry.get("raw_fingerprint", [])

                # Automatically backfill raw_fingerprint on older discarded_db.json entries!
                if not saved_raw and saved_fp:
                    saved_raw = self.decode_base64_fingerprint_to_raw(saved_fp)
                    if saved_raw:
                        entry["raw_fingerprint"] = saved_raw
                        db_updated = True

                if fp and saved_fp and (fp == saved_fp or (len(fp) > 40 and fp[:40] == saved_fp[:40])):
                    matched_entry = entry
                    break
                if raw_ints and saved_raw and self.raw_fingerprints_match(raw_ints, saved_raw):
                    matched_entry = entry
                    break

            if db_updated:
                try:
                    with open(self.get_discard_db_path(), "w", encoding="utf-8") as f:
                        json.dump(db, f, indent=2, ensure_ascii=False)
                except Exception:
                    pass
            if matched_entry:
                return matched_entry

        return None

    def record_and_delete_discarded(self, filepath, reason=None):
        """
        Deletes a discarded track. If it ALREADY exists in _Discarded_Songs (by fingerprint or name),
        it skips creating a duplicate JSON/log entry and deletes the file immediately!
        """
        fname = os.path.basename(filepath)
        existing_match = self.check_if_discarded(filepath, compute_if_missing=True)

        if existing_match:
            # Already blacklisted! Upgrade its stored raw_fingerprint if missing, then delete file without duplicating DB
            fp, dur, raw_ints = self.compute_fingerprint(filepath)
            if raw_ints and not existing_match.get("raw_fingerprint"):
                db = self.load_discard_db()
                for item in db:
                    if item.get("timestamp") == existing_match.get("timestamp") and item.get("filename") == existing_match.get("filename"):
                        item["raw_fingerprint"] = raw_ints
                with open(self.get_discard_db_path(), "w", encoding="utf-8") as f:
                    json.dump(db, f, indent=2, ensure_ascii=False)

            if self.player.source() == QUrl.fromLocalFile(filepath):
                self.player.stop()
            if os.path.exists(filepath):
                os.remove(filepath)

            orig_reason = existing_match.get("reason", "Previously blacklisted")
            self.log(
                f"[PURGED KNOWN BLACKLISTED TRACK] '{fname}' (Matched '{existing_match.get('filename')}' — "
                f"Reason: {orig_reason}). Deleted without creating duplicate DB entry."
            )
            return

        # Brand new discard: compute full fingerprint + raw sub-fingerprints and record once
        norm_name = re.sub(r'[^\w]', '', os.path.splitext(fname)[0].lower())
        fp, dur, raw_ints = self.compute_fingerprint(filepath)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        clean_reason = reason if reason else "Manually discarded by user"

        entry = {
            "timestamp": timestamp,
            "filename": fname,
            "normalized_name": norm_name,
            "duration": round(dur, 2),
            "reason": clean_reason,
            "fingerprint": fp,
            "raw_fingerprint": raw_ints
        }

        db = self.load_discard_db()
        db.append(entry)
        with open(self.get_discard_db_path(), "w", encoding="utf-8") as f:
            json.dump(db, f, indent=2, ensure_ascii=False)

        log_path = self.get_discard_log_path()
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("====================================================================\n")
            f.write(f"DATE DISCARDED : {timestamp}\n")
            f.write(f"TRACK FILENAME : {fname}\n")
            f.write(f"DURATION (SEC) : {dur:.2f}s\n")
            f.write(f"DISCARD REASON : {clean_reason}\n")
            f.write(f"FINGERPRINT ID : {fp}\n")
            f.write("====================================================================\n\n")

        safe_base = re.sub(r'[^\w\-\. ]', '_', fname)
        meta_file = os.path.join(self.get_discard_dir(), f"{safe_base}.discarded.txt")
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(entry, f, indent=2, ensure_ascii=False)

        if self.player.source() == QUrl.fromLocalFile(filepath):
            self.player.stop()

        if os.path.exists(filepath):
            os.remove(filepath)

        self.log(f"[BLACKLISTED & DELETED] '{fname}' -> Reason: {clean_reason}")

    def refresh_discarded_table(self):
        db = self.load_discard_db()
        # Automatically deduplicate any repeated entries in discarded_db.json from earlier tests
        deduped = []
        seen_fps = set()
        seen_names = set()
        modified = False
        for entry in db:
            fp_k = entry.get("fingerprint", "")[:48]
            nm_k = re.sub(r'[^\w]', '', os.path.splitext(entry.get("filename", ""))[0].lower())
            if (fp_k and fp_k in seen_fps) or (nm_k and nm_k in seen_names):
                modified = True
                continue
            if fp_k:
                seen_fps.add(fp_k)
            if nm_k:
                seen_names.add(nm_k)
            deduped.append(entry)

        if modified:
            with open(self.get_discard_db_path(), "w", encoding="utf-8") as f:
                json.dump(deduped, f, indent=2, ensure_ascii=False)
            db = deduped

        self.discard_table.setRowCount(0)
        for entry in reversed(db):
            row = self.discard_table.rowCount()
            self.discard_table.insertRow(row)
            self.discard_table.setItem(row, 0, QTableWidgetItem(entry.get("timestamp", "")))
            self.discard_table.setItem(row, 1, QTableWidgetItem(entry.get("filename", "")))
            self.discard_table.setItem(row, 2, QTableWidgetItem(entry.get("reason", "No reason specified")))
            fp_preview = entry.get("fingerprint", "N/A")
            if len(fp_preview) > 42:
                fp_preview = fp_preview[:42] + "..."
            self.discard_table.setItem(row, 3, QTableWidgetItem(fp_preview))

    # =========================================================================
    # Interactive Staging & Multi-Folder Sorter (_New_Arrivals)
    # =========================================================================
    def get_playlist_folders(self):
        if not os.path.exists(self.base_dir):
            return []
        return sorted([
            d for d in os.listdir(self.base_dir)
            if os.path.isdir(os.path.join(self.base_dir, d)) and d not in SYSTEM_FOLDERS
        ])

    def on_background_fp_scanned(self, filepath, fp_data):
        """Called asynchronously as the background thread fingerprints each file in _New_Arrivals."""
        self.staging_fingerprint_cache[filepath] = fp_data
        discard_match = self.check_if_discarded(filepath, compute_if_missing=False)
        if not discard_match:
            return

        # Update the row in real time if it matched a discarded fingerprint!
        for r in range(self.staging_table.rowCount()):
            item_name = self.staging_table.item(r, 0)
            if item_name and item_name.data(Qt.UserRole) == filepath:
                reason_txt = discard_match.get("reason", "Unspecified")
                orig_name = discard_match.get("filename", "")
                date_txt = discard_match.get("timestamp", "")
                status_str = f"⚠️ BLACKLIST FINGERPRINT MATCH ({orig_name} | {date_txt}): {reason_txt}"
                item_status = self.staging_table.item(r, 1)
                if item_status:
                    item_status.setText(status_str)
                    warn_color = QBrush(QColor("#ff2a54"))
                    item_name.setForeground(warn_color)
                    item_status.setForeground(warn_color)
                break

    def refresh_staging_table(self):
        staging = os.path.join(self.base_dir, "_New_Arrivals")
        self.staging_table.setRowCount(0)
        if not os.path.exists(staging):
            self.staging_status_lbl.setText("Staging Queue: _New_Arrivals folder not created yet.")
            return

        files = sorted([
            f for f in os.listdir(staging)
            if f.lower().endswith((".mp3", ".m4a", ".flac", ".opus", ".ogg", ".wav"))
        ])

        uncached_paths = []
        flagged_count = 0
        for fname in files:
            fpath = os.path.join(staging, fname)
            size_mb = os.path.getsize(fpath) / (1024 * 1024)
            discard_match = self.check_if_discarded(fpath, compute_if_missing=False)
            if fpath not in self.staging_fingerprint_cache:
                uncached_paths.append(fpath)

            row = self.staging_table.rowCount()
            self.staging_table.insertRow(row)

            item_name = QTableWidgetItem(fname)
            item_name.setData(Qt.UserRole, fpath)

            if discard_match:
                flagged_count += 1
                reason_txt = discard_match.get("reason", "Unspecified")
                date_txt = discard_match.get("timestamp", "")
                status_str = f"⚠️ PREVIOUSLY DISCARDED ({date_txt}): {reason_txt}"
                item_status = QTableWidgetItem(status_str)
                warn_color = QBrush(QColor("#ff2a54"))
                item_name.setForeground(warn_color)
                item_status.setForeground(warn_color)
            else:
                item_status = QTableWidgetItem("✔ Clean / Ready to Sort")
                item_status.setForeground(QBrush(QColor("#45a29e")))

            self.staging_table.setItem(row, 0, item_name)
            self.staging_table.setItem(row, 1, item_status)
            self.staging_table.setItem(row, 2, QTableWidgetItem(f"{size_mb:.2f} MB"))

            btn_play = QPushButton("▶ Preview")
            set_btn_variant(btn_play, "accent")
            btn_play.clicked.connect(
                lambda _, p=fpath, b=btn_play: self.play_from_table(self.staging_table, b, p, "[STAGING]")
            )
            self.staging_table.setCellWidget(row, 3, btn_play)

            btn_sort = QPushButton("SORT / DISCARD ▾")
            set_btn_variant(btn_sort, "restore")
            btn_sort.clicked.connect(lambda _, p=fpath: self.open_sort_modal([p]))
            self.staging_table.setCellWidget(row, 4, btn_sort)

        self.staging_status_lbl.setText(
            f"Staging Queue (_New_Arrivals): {len(files)} tracks remaining "
            f"({flagged_count} flagged as previously discarded)."
        )

        # Start non-blocking background fingerprinting for any new/renamed files in _New_Arrivals
        if uncached_paths and self.load_discard_db():
            if self.fp_worker and self.fp_worker.isRunning():
                self.fp_worker.stop()
                self.fp_worker.wait(500)
            self.fp_worker = StagingFingerprintWorker(uncached_paths)
            self.fp_worker.file_scanned.connect(self.on_background_fp_scanned)
            self.fp_worker.start()

    def sort_selected_staging_rows(self):
        selected_rows = sorted(set(idx.row() for idx in self.staging_table.selectedIndexes()))
        if not selected_rows:
            QMessageBox.information(
                self, "No Rows Selected",
                "Select one or more tracks in the table first (use Shift/Ctrl + Click), or click 'SORT / DISCARD ▾' on any row."
            )
            return
        filepaths = [
            self.staging_table.item(r, 0).data(Qt.UserRole)
            for r in selected_rows
        ]
        self.open_sort_modal(filepaths)

    def open_sort_modal(self, filepaths):
        track_names = [os.path.basename(p) for p in filepaths]
        folders = self.get_playlist_folders()

        dlg = MultiSortDialog(self, track_names, folders)
        if dlg.exec() != QDialog.Accepted:
            return

        if dlg.action_type == "discard":
            # Separate already-blacklisted files from brand-new discards!
            already_blacklisted = []
            brand_new_discards = []
            for fp in filepaths:
                if self.check_if_discarded(fp, compute_if_missing=True):
                    already_blacklisted.append(fp)
                else:
                    brand_new_discards.append(fp)

            clean_reason = None
            if brand_new_discards:
                reason, ok = QInputDialog.getText(
                    self,
                    "Discard & Blacklist Audio",
                    f"Enter reason for discarding ({len(brand_new_discards)} new track(s)):\n"
                    "(e.g., 'Meme song', 'Bad live version', 'Intro skit')",
                    text="Meme / Non-music track"
                )
                if not ok:
                    return
                clean_reason = reason.strip() if reason.strip() else "Manually discarded by user"

            # Purge already-blacklisted files immediately without re-prompting or duplicating DB!
            for fp in already_blacklisted:
                self.record_and_delete_discarded(fp, reason=None)

            # Record & delete brand-new discards
            for fp in brand_new_discards:
                self.record_and_delete_discarded(fp, reason=clean_reason)

            self.refresh_staging_table()
            self.refresh_discarded_table()
            self.trigger_autoplay_next()

        elif dlg.action_type == "sort":
            target_folders = dlg.selected_folders
            for fp in filepaths:
                if not os.path.exists(fp):
                    continue
                fname = os.path.basename(fp)

                discard_match = self.check_if_discarded(fp, compute_if_missing=True)
                if discard_match:
                    ans = QMessageBox.warning(
                        self,
                        "⚠️ Previously Discarded Track Detected!",
                        f"Track: {fname}\n\n\n"                        f"This audio matches a previously discarded file!\n\n"                        f"• Discarded On: {discard_match.get('timestamp')}\n\n"                        f"• Original Name: {discard_match.get('filename')}\n\n"                        f"• Reason: {discard_match.get('reason')}\n\n\n"                        f"Are you sure you want to proceed and add it to {target_folders}?",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.No
                    )
                    if ans != QMessageBox.Yes:
                        continue

                if self.player.source() == QUrl.fromLocalFile(fp):
                    self.player.stop()

                for i, folder_name in enumerate(target_folders):
                    dest_dir = os.path.join(self.base_dir, folder_name)
                    os.makedirs(dest_dir, exist_ok=True)
                    dest_path = os.path.join(dest_dir, fname)

                    if i < len(target_folders) - 1:
                        shutil.copy2(fp, dest_path)
                        self.log(f"[SORT COPY] '{fname}' -> '{folder_name}/'")
                    else:
                        shutil.move(fp, dest_path)
                        self.log(f"[SORT MOVE] '{fname}' -> '{folder_name}/'")

            self.refresh_staging_table()
            self.trigger_autoplay_next()

    def trigger_autoplay_next(self):
        if self.chk_autoplay.isChecked() and self.staging_table.rowCount() > 0:
            next_path = self.staging_table.item(0, 0).data(Qt.UserRole)
            self.highlight_playing_row(self.staging_table, 0)
            self.play_file(next_path, "[AUTO-NEXT STAGING]")

    # =========================================================================
    # Option B: Auto-Consolidate Telegram Dump & Rebuild Relative M3Us
    # =========================================================================
    def get_m3u_directory(self):
        master = os.path.join(self.base_dir, "Playlist masterfiles")
        if os.path.exists(master):
            return master
        return os.path.join(self.base_dir, "playlist M3U files")

    def refresh_playlist_stats_table(self):
        if not hasattr(self, "stats_table") or not os.path.exists(self.base_dir):
            return
        m3u_dir = self.get_m3u_directory()
        audio_exts = (".mp3", ".m4a", ".flac", ".opus", ".ogg", ".wav")

        folders = [
            d for d in os.listdir(self.base_dir)
            if os.path.isdir(os.path.join(self.base_dir, d)) and d not in SYSTEM_FOLDERS
        ]

        m3u8_map = {}
        if os.path.exists(m3u_dir):
            for f in os.listdir(m3u_dir):
                if f.lower().endswith(".m3u8"):
                    base = os.path.splitext(f)[0]
                    m3u8_map[base.lower()] = os.path.join(m3u_dir, f)

        all_keys = sorted(
            set(folders) | { os.path.splitext(f)[0] for f in (os.listdir(m3u_dir) if os.path.exists(m3u_dir) else []) if f.lower().endswith(".m3u8") },
            key=lambda s: s.lower()
        )

        self.stats_table.setRowCount(0)
        total_disk_tracks = 0
        total_m3u8_tracks = 0
        total_size_mb = 0.0

        for name in all_keys:
            folder_path = os.path.join(self.base_dir, name)
            disk_files = []
            folder_mb = 0.0
            if os.path.isdir(folder_path):
                for f in os.listdir(folder_path):
                    if f.lower().endswith(audio_exts):
                        disk_files.append(f)
                        try:
                            folder_mb += os.path.getsize(os.path.join(folder_path, f)) / (1024 * 1024)
                        except Exception:
                            pass

            m3u8_path = m3u8_map.get(name.lower())
            m3u8_count = 0
            if m3u8_path and os.path.exists(m3u8_path):
                try:
                    with open(m3u8_path, "r", encoding="utf-8", errors="ignore") as pf:
                        m3u8_count = sum(1 for line in pf if line.strip() and not line.strip().startswith("#"))
                except Exception:
                    pass

            is_dump = "dump" in name.lower() or name.lower() in {"telegram", "unsorted"}
            if not is_dump:
                total_disk_tracks += len(disk_files)
                total_m3u8_tracks += m3u8_count
                total_size_mb += folder_mb

            row = self.stats_table.rowCount()
            self.stats_table.insertRow(row)

            item_name = QTableWidgetItem(name)
            item_disk = QTableWidgetItem(str(len(disk_files)))
            item_m3u = QTableWidgetItem(str(m3u8_count) if m3u8_path else "No .m3u8")
            item_size = QTableWidgetItem(f"{folder_mb:.1f} MB")

            if is_dump:
                if len(disk_files) == 0:
                    status_txt = "✔ DUMP EMPTY (CLEAN)"
                    color = QBrush(QColor("#45a29e"))
                else:
                    status_txt = f"📦 {len(disk_files)} UNREFERENCED STRAGGLERS"
                    color = QBrush(QColor("#ff2a54"))
            elif len(disk_files) == m3u8_count and m3u8_path:
                status_txt = "✔ IN SYNC (100%)"
                color = QBrush(QColor("#66fcf1"))
            else:
                diff = len(disk_files) - m3u8_count
                status_txt = f"⚠️ MISMATCH (Δ {diff:+d} tracks)"
                color = QBrush(QColor("#ff2a54"))

            item_status = QTableWidgetItem(status_txt)
            item_status.setForeground(color)
            if is_dump and len(disk_files) > 0:
                item_name.setForeground(color)

            self.stats_table.setItem(row, 0, item_name)
            self.stats_table.setItem(row, 1, item_disk)
            self.stats_table.setItem(row, 2, item_m3u)
            self.stats_table.setItem(row, 3, item_status)
            self.stats_table.setItem(row, 4, item_size)

        self.stats_summary_lbl.setText(
            f"LIBRARY OVERVIEW // {len(all_keys)} Folders | "
            f"{total_disk_tracks} Tracks on Disk | {total_m3u8_tracks} Tracks Indexed in .m3u8 | "
            f"{total_size_mb / 1024:.2f} GB Total"
        )

    def load_metadata_cache(self):
        cache_p = os.path.join(self.base_dir, "_Discarded_Songs", "_metadata_cache.json")
        if not self.metadata_cache and os.path.exists(cache_p):
            try:
                with open(cache_p, "r", encoding="utf-8") as f:
                    self.metadata_cache = json.load(f)
            except Exception:
                self.metadata_cache = {}

    def save_metadata_cache(self):
        cache_p = os.path.join(self.get_discard_dir(), "_metadata_cache.json")
        try:
            with open(cache_p, "w", encoding="utf-8") as f:
                json.dump(self.metadata_cache, f, ensure_ascii=False)
        except Exception:
            pass

    def get_track_grouping_signature(self, filepath):
        """
        Extracts normalized (artist_key, album_key, cover_hash) for Smart Playlist Splicing.
        Uses persistent cache so 20k+ tracks only get probed once.
        """
        if not os.path.exists(filepath):
            return ("", "", "")
        try:
            mtime = int(os.path.getmtime(filepath))
        except Exception:
            mtime = 0
        cache_key = f"{filepath}::{mtime}"
        if cache_key in self.metadata_cache:
            c = self.metadata_cache[cache_key]
            return (c.get("artist", ""), c.get("album", ""), c.get("cover", ""))

        artist = ""
        album = ""
        cover_hash = ""

        # Try fast mutagen extraction if installed, otherwise ffprobe
        try:
            import mutagen
            audio = mutagen.File(filepath)
            if audio and audio.tags:
                tags = audio.tags
                # ID3 / MP4 / Vorbis tag lookups
                for k in ("TPE1", "TPE2", "©ART", "artist", "ARTIST", "Author"):
                    if k in tags and str(tags[k]).strip():
                        artist = str(tags[k][0] if isinstance(tags[k], list) else tags[k]).strip()
                        break
                for k in ("TALB", "©alb", "album", "ALBUM"):
                    if k in tags and str(tags[k]).strip():
                        album = str(tags[k][0] if isinstance(tags[k], list) else tags[k]).strip()
                        break
                # Check embedded cover art bytes for matching album covers
                for k in tags.keys():
                    if k.startswith("APIC") or k == "covr":
                        pic = tags[k]
                        raw_bytes = getattr(pic, "data", None) or (bytes(pic[0]) if isinstance(pic, list) and pic else None)
                        if raw_bytes:
                            cover_hash = hashlib.md5(raw_bytes[:4096]).hexdigest()[:12]
                            break
        except Exception:
            pass

        if not artist and not album:
            try:
                res = subprocess.run(
                    [get_bin("ffprobe"), "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", filepath],
                    capture_output=True, text=True, timeout=4
                )
                if res.returncode == 0 and res.stdout:
                    info = json.loads(res.stdout)
                    fmt_tags = info.get("format", {}).get("tags", {})
                    for k, v in fmt_tags.items():
                        kl = k.lower()
                        if kl in ("artist", "album_artist", "author") and not artist:
                            artist = str(v).strip()
                        elif kl == "album" and not album:
                            album = str(v).strip()
                    for st in info.get("streams", []):
                        if st.get("codec_type") == "video":
                            w = st.get("width", 0)
                            h = st.get("height", 0)
                            dur_ts = st.get("duration_ts", 0)
                            cover_hash = f"cov_{w}x{h}_{dur_ts}"
                            break
            except Exception:
                pass

        # Fallback: parse "Artist - Track" from filename if ID3 artist is missing or generic "YouTube"
        fname_stem = os.path.splitext(os.path.basename(filepath))[0]
        if (not artist or artist.lower() in {"unknown", "various artists"}) and " - " in fname_stem:
            artist = fname_stem.split(" - ", 1)[0].strip()

        # Normalize artist (take primary artist before feat./comma/semicolon)
        norm_artist = re.split(r'\s+(?:feat\.?|ft\.?|featuring|with)\s+|[,;&/]', artist.lower())[0]
        norm_artist = re.sub(r'[^\w]', '', norm_artist)
        norm_album = re.sub(r'[^\w]', '', album.lower())

        self.metadata_cache[cache_key] = {
            "artist": norm_artist,
            "album": norm_album,
            "cover": cover_hash
        }
        return (norm_artist, norm_album, cover_hash)

    def smart_splice_playlist_tracks(self, pl_name, pl_folder_path, existing_rel_lines, new_filenames, recluster_all=False):
        """
        Splices each newly added track into existing_rel_lines:
          1. Right after the last track sharing the SAME Artist + Album (or same Artist + Cover Hash).
          2. Otherwise, right after the last track sharing the SAME Artist.
          3. Otherwise, at the bottom of the playlist.
        If recluster_all=True, also groups existing blocks cleanly by Artist -> Album.
        """
        self.load_metadata_cache()

        def resolve_disk_path(rel_line):
            clean = rel_line.replace("\\", "/").lstrip("./")
            return os.path.normpath(os.path.join(self.base_dir, clean))

        working_lines = list(existing_rel_lines)

        if recluster_all and working_lines:
            # Group existing lines by first-seen Artist order, and within each Artist by Album/Cover
            artist_order = []
            artist_buckets = {}
            for line in working_lines:
                p = resolve_disk_path(line)
                art, alb, cov = self.get_track_grouping_signature(p)
                art_key = art if art else f"__untagged_{line}"
                if art_key not in artist_buckets:
                    artist_order.append(art_key)
                    artist_buckets[art_key] = []
                artist_buckets[art_key].append((alb or cov or "", line))

            rebuilt = []
            for art_key in artist_order:
                bucket = artist_buckets[art_key]
                # Keep relative album order within the artist chunk
                alb_order = []
                alb_map = {}
                for alb_k, l_str in bucket:
                    if alb_k not in alb_map:
                        alb_order.append(alb_k)
                        alb_map[alb_k] = []
                    alb_map[alb_k].append(l_str)
                for alb_k in alb_order:
                    rebuilt.extend(alb_map[alb_k])
            working_lines = rebuilt

        # Build signature list for working_lines
        line_sigs = [self.get_track_grouping_signature(resolve_disk_path(l)) for l in working_lines]

        for new_f in new_filenames:
            new_rel = f"../{pl_name}/{new_f}"
            new_full = os.path.join(pl_folder_path, new_f)
            n_art, n_alb, n_cov = self.get_track_grouping_signature(new_full)

            insert_idx = None

            if n_art:
                # Tier 1: Look for last track in playlist with SAME Artist AND SAME Album (or Cover Art)
                if n_alb or n_cov:
                    for i in range(len(line_sigs) - 1, -1, -1):
                        e_art, e_alb, e_cov = line_sigs[i]
                        if e_art == n_art:
                            if (n_alb and e_alb == n_alb) or (n_cov and e_cov == n_cov):
                                insert_idx = i + 1
                                self.log(
                                    f"  [Smart Splice: Album Match] Inserted '{new_f}' after '{os.path.basename(working_lines[i])}' in '{pl_name}.m3u8'"
                                )
                                break

                # Tier 2: Look for last track in playlist with SAME Artist (end of that Artist's chunk)
                if insert_idx is None:
                    for i in range(len(line_sigs) - 1, -1, -1):
                        e_art, e_alb, e_cov = line_sigs[i]
                        if e_art == n_art:
                            insert_idx = i + 1
                            self.log(
                                f"  [Smart Splice: Artist Block] Inserted '{new_f}' at end of '{n_art}' block after '{os.path.basename(working_lines[i])}' in '{pl_name}.m3u8'"
                            )
                            break

            if insert_idx is not None:
                working_lines.insert(insert_idx, new_rel)
                line_sigs.insert(insert_idx, (n_art, n_alb, n_cov))
            else:
                working_lines.append(new_rel)
                line_sigs.append((n_art, n_alb, n_cov))

        self.save_metadata_cache()
        return working_lines

    def consolidate_and_rebuild_playlists(self):
        m3u_dir = self.get_m3u_directory()
        backup_dir = os.path.join(self.base_dir, "_M3U_Safety_Backup")
        os.makedirs(m3u_dir, exist_ok=True)
        os.makedirs(backup_dir, exist_ok=True)

        self.tabs.setCurrentWidget(self.console)
        self.log(f"\n==> Starting Deep Consolidation & Pure .M3U8 Sync in '{os.path.basename(m3u_dir)}'...")

        audio_exts = (".mp3", ".m4a", ".flac", ".opus", ".ogg", ".wav")

        # 1. Identify all dump folders vs regular playlist folders
        dump_folders = {}
        regular_folders = {}
        for d in os.listdir(self.base_dir):
            full_d = os.path.join(self.base_dir, d)
            if os.path.isdir(full_d) and d not in SYSTEM_FOLDERS:
                if d.lower() in {"telegram dump", "telegram dumb", "telegram", "downloads dump", "download dump", "unsorted", "dump"} or "dump" in d.lower():
                    dump_folders[d.lower()] = d
                else:
                    regular_folders[d.lower()] = d

        # 2. Index files in regular folders AND dump folders separately so dump files aren't masked
        exact_index = {}         # (folder_lower, file_lower) -> (real_folder, real_file)
        dump_file_index = {}     # file_lower -> (dump_folder_real, real_file)
        dump_norm_index = {}     # norm_stem -> (dump_folder_real, real_file)
        regular_file_index = {}  # file_lower -> (reg_folder_real, real_file)
        regular_norm_index = {}  # norm_stem -> (reg_folder_real, real_file)

        def norm_stem(filename):
            stem = os.path.splitext(filename)[0].lower().strip()
            cleaned = re.sub(r'[^\w]', '', stem)
            return cleaned if len(cleaned) >= 3 else stem

        for d_low, d_real in dump_folders.items():
            f_path = os.path.join(self.base_dir, d_real)
            for f in os.listdir(f_path):
                if f.lower().endswith(audio_exts):
                    exact_index[(d_low, f.lower())] = (d_real, f)
                    dump_file_index[f.lower()] = (d_real, f)
                    dump_norm_index[norm_stem(f)] = (d_real, f)

        for r_low, r_real in regular_folders.items():
            f_path = os.path.join(self.base_dir, r_real)
            for f in os.listdir(f_path):
                if f.lower().endswith(audio_exts):
                    exact_index[(r_low, f.lower())] = (r_real, f)
                    regular_file_index[f.lower()] = (r_real, f)
                    regular_norm_index[norm_stem(f)] = (r_real, f)

        # 3. Backup ALL existing playlist files (.m3u and .m3u8) before merging & stripping .m3u
        existing_files = [
            f for f in os.listdir(m3u_dir)
            if f.lower().endswith((".m3u", ".m3u8", ".pls", ".xspf"))
        ]
        for pl_f in existing_files:
            shutil.copy2(os.path.join(m3u_dir, pl_f), os.path.join(backup_dir, pl_f))
        self.log(f"  [Safety Backup] Backed up {len(existing_files)} original playlist files to '_M3U_Safety_Backup/'")

        # 4. Group both .m3u and .m3u8 files by playlist name so NO references in legacy .m3u are lost!
        grouped_pl_files = {}  # pl_lower -> {"display_name": str, "files": [filenames]}
        for f in sorted(existing_files):
            base_name, ext = os.path.splitext(f)
            if base_name.lower() in dump_folders:
                continue
            key_low = base_name.lower()
            real_pl_name = regular_folders.get(key_low, base_name)
            grouped_pl_files.setdefault(key_low, {"display_name": real_pl_name, "files": []})
            grouped_pl_files[key_low]["files"].append(f)

        for r_low, r_real in regular_folders.items():
            if r_low not in grouped_pl_files:
                grouped_pl_files[r_low] = {"display_name": r_real, "files": []}

        # 5. Parse all playlist variants (.m3u8 first, then .m3u) to catch every single dump reference
        dump_usage_map = {}   # (dump_folder_real, dump_file_real) -> list of target_pl_real
        parsed_m3u_lines = {} # pl_real -> list of (resolved_folder, resolved_file)

        for key_low, info in sorted(grouped_pl_files.items()):
            pl_name = info["display_name"]
            # Read .m3u8 first, then .m3u so any extra tracks in either file are preserved
            pl_variants = sorted(info["files"], key=lambda x: 0 if x.lower().endswith(".m3u8") else 1)
            entries = []
            seen_in_pl = set()

            for variant_file in pl_variants:
                v_path = os.path.join(m3u_dir, variant_file)
                if not os.path.exists(v_path):
                    continue
                with open(v_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        stripped = line.strip()
                        if not stripped or stripped.startswith("#"):
                            continue
                        # Decode URL encodings like %20 if present
                        decoded = urllib.parse.unquote(stripped).replace("\\", "/")
                        parts = [p for p in decoded.split("/") if p and p != ".."]
                        if not parts:
                            continue

                        fname = parts[-1]
                        parent_folder = parts[-2] if len(parts) >= 2 else pl_name
                        f_low = fname.lower()
                        p_low = parent_folder.lower()
                        n_stem = norm_stem(fname)

                        # Priority 1: Did the line explicitly point to a dump folder, or does the file live in a dump folder?
                        if (p_low, f_low) in exact_index:
                            real_folder, real_file = exact_index[(p_low, f_low)]
                        elif f_low in dump_file_index:
                            real_folder, real_file = dump_file_index[f_low]
                        elif n_stem in dump_norm_index:
                            real_folder, real_file = dump_norm_index[n_stem]
                        elif f_low in regular_file_index:
                            real_folder, real_file = regular_file_index[f_low]
                        elif n_stem in regular_norm_index:
                            real_folder, real_file = regular_norm_index[n_stem]
                        else:
                            real_folder, real_file = pl_name, fname

                        dedupe_key = real_file.lower()
                        if dedupe_key not in seen_in_pl:
                            seen_in_pl.add(dedupe_key)
                            entries.append((real_folder, real_file))

                        # Also check if a copy of this track is sitting in any dump folder!
                        if real_folder.lower() in dump_folders:
                            dump_key = (real_folder, real_file)
                            dump_usage_map.setdefault(dump_key, [])
                            if pl_name not in dump_usage_map[dump_key]:
                                dump_usage_map[dump_key].append(pl_name)
                        elif f_low in dump_file_index:
                            dump_key = dump_file_index[f_low]
                            dump_usage_map.setdefault(dump_key, [])
                            if pl_name not in dump_usage_map[dump_key]:
                                dump_usage_map[dump_key].append(pl_name)

            parsed_m3u_lines[pl_name] = entries

        # 6. Move/Copy all referenced tracks out of Telegram dump & Downloads dump into target folders
        consolidated_count = 0
        for (dump_folder, dump_file), target_playlists in dump_usage_map.items():
            src_path = os.path.join(self.base_dir, dump_folder, dump_file)
            if not os.path.exists(src_path):
                continue

            for idx, target_pl in enumerate(target_playlists):
                dest_dir = os.path.join(self.base_dir, target_pl)
                os.makedirs(dest_dir, exist_ok=True)
                dest_path = os.path.join(dest_dir, dump_file)

                if idx < len(target_playlists) - 1:
                    if not os.path.exists(dest_path):
                        shutil.copy2(src_path, dest_path)
                    self.log(f"  [Consolidate Copy] '{dump_folder}/{dump_file}' -> '{target_pl}/{dump_file}'")
                else:
                    if not os.path.exists(dest_path):
                        shutil.move(src_path, dest_path)
                    else:
                        os.remove(src_path)
                    self.log(f"  [Consolidate Move] '{dump_folder}/{dump_file}' -> '{target_pl}/{dump_file}'")
                consolidated_count += 1

        # 7. Sweep Dump Folders for Redundant Stragglers (Files already present inside a regular playlist folder)
        # Rebuild regular folder index after moves
        current_regular_files = {}
        current_regular_norms = {}
        for r_low, r_real in regular_folders.items():
            f_path = os.path.join(self.base_dir, r_real)
            if os.path.isdir(f_path):
                for f in os.listdir(f_path):
                    if f.lower().endswith(audio_exts):
                        current_regular_files[f.lower()] = (r_real, f)
                        current_regular_norms[norm_stem(f)] = (r_real, f)

        purged_stragglers = 0
        for d_low, d_real in dump_folders.items():
            d_path = os.path.join(self.base_dir, d_real)
            if not os.path.isdir(d_path):
                continue
            for f in list(os.listdir(d_path)):
                if not f.lower().endswith(audio_exts):
                    continue
                f_low = f.lower()
                n_stem = norm_stem(f)
                if f_low in current_regular_files or (n_stem and n_stem in current_regular_norms):
                    matched_folder = current_regular_files.get(f_low, current_regular_norms.get(n_stem))[0]
                    os.remove(os.path.join(d_path, f))
                    purged_stragglers += 1
                    self.log(f"  [Straggler Purged] Removed '{d_real}/{f}' (Already inside '{matched_folder}/')")

        # 8. Strip legacy .m3u files and write clean UTF-8 .m3u8 files exclusively
        stripped_m3u_count = 0
        for f in os.listdir(m3u_dir):
            if f.lower().endswith(".m3u") or os.path.splitext(f)[0].lower() in dump_folders:
                os.remove(os.path.join(m3u_dir, f))
                stripped_m3u_count += 1

        updated_count = 0
        total_pl = max(1, len(parsed_m3u_lines))
        for idx, (pl_name, entries) in enumerate(sorted(parsed_m3u_lines.items()), 1):
            m3u8_filename = f"{pl_name}.m3u8"
            m3u8_path = os.path.join(m3u_dir, m3u8_filename)
            final_lines = []
            seen = set()

            pl_folder_path = os.path.join(self.base_dir, pl_name)
            folder_files_map = {}
            if os.path.isdir(pl_folder_path):
                for f in os.listdir(pl_folder_path):
                    if f.lower().endswith(audio_exts):
                        folder_files_map[f.lower()] = f

            # Preserve playlist order, pointing tracks to their local playlist folder
            for real_folder, real_file in entries:
                if real_file.lower() in folder_files_map:
                    actual_fname = folder_files_map[real_file.lower()]
                    effective_folder = pl_name
                elif real_folder.lower() in dump_folders:
                    actual_fname = real_file
                    effective_folder = pl_name
                else:
                    actual_fname = real_file
                    effective_folder = real_folder

                k = (effective_folder.lower(), actual_fname.lower())
                if k not in seen:
                    seen.add(k)
                    final_lines.append(f"../{effective_folder}/{actual_fname}")

            # Smart Artist & Album Cover Splicer for newly sorted tracks (and optional full re-clustering)
            new_in_folder = 0
            if os.path.isdir(pl_folder_path):
                new_files_to_splice = []
                for f in sorted(os.listdir(pl_folder_path)):
                    if f.lower().endswith(audio_exts):
                        k = (pl_name.lower(), f.lower())
                        if k not in seen:
                            seen.add(k)
                            new_files_to_splice.append(f)
                            new_in_folder += 1

                if new_files_to_splice or (hasattr(self, "chk_recluster_existing") and self.chk_recluster_existing.isChecked()):
                    final_lines = self.smart_splice_playlist_tracks(
                        pl_name, pl_folder_path, final_lines, new_files_to_splice,
                        recluster_all=(hasattr(self, "chk_recluster_existing") and self.chk_recluster_existing.isChecked())
                    )

            with open(m3u8_path, "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                for line in final_lines:
                    f.write(f"{line}\n")

            pct = int((idx / total_pl) * 100)
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(pct)
            self.progress_bar.setFormat(f"WRITING UTF-8 .M3U8 PLAYLISTS: {idx}/{total_pl} ({pct}%)")

            self.log(
                f"  [M3U8 Synced] {m3u8_filename} -> {len(final_lines)} tracks "
                f"({new_in_folder} newly added from folder)"
            )
            updated_count += 1

        self.refresh_playlist_stats_table()
        self.telemetry_label.setText(
            f"TELEMETRY // SYNC COMPLETE: {updated_count} .m3u8 Playlists | {stripped_m3u_count} Legacy .m3u Stripped"
        )
        self.log(
            f"\n==> Completed!\n"
            f"    • Relocated {consolidated_count} dump tracks into playlist folders\n"
            f"    • Purged {purged_stragglers} redundant dump stragglers already in playlists\n"
            f"    • Stripped {stripped_m3u_count} legacy .m3u files\n"
            f"    • Synced {updated_count} clean UTF-8 .m3u8 playlists.\n"
        )

    # =========================================================================
    # Core Utilities, Downloader, Acoustic Audit & Audio Player
    # =========================================================================
    # =========================================================================
    # Tab 5: Delta Recovery, Local Cross-Folder Healer, YT Matcher & File Picker
    # =========================================================================
    def clean_query_from_filename(self, fname):
        stem = os.path.splitext(fname)[0]
        # Strip common Telegram/YouTube rip noise like [Official Video], (320kbps), track numbers, etc.
        stem = re.sub(r'\[(?:official|audio|video|lyrics|hd|hq|4k|visualizer|mp3|flac)[^\]]*\]', ' ', stem, flags=re.I)
        stem = re.sub(r'\((?:official|audio|video|lyrics|hd|hq|320|128)[^\)]*\)', ' ', stem, flags=re.I)
        stem = re.sub(r'[_]+', ' ', stem)
        stem = re.sub(r'\s+', ' ', stem).strip()
        return stem

    def scan_and_heal_deltas(self):
        m3u_dir = self.get_m3u_directory()
        if not os.path.exists(m3u_dir):
            return

        audio_exts = (".mp3", ".m4a", ".flac", ".opus", ".ogg", ".wav")

        # 1. Build a global index of EVERY audio file anywhere inside base_dir (including other playlists, quarantine, staging)
        global_exact = {}  # filename_lower -> full_path
        global_stem = {}   # stem_lower -> full_path
        for root_dir, dirs, files in os.walk(self.base_dir):
            for f in files:
                if f.lower().endswith(audio_exts):
                    full_p = os.path.join(root_dir, f)
                    global_exact.setdefault(f.lower(), full_p)
                    stem_l = os.path.splitext(f)[0].lower().strip()
                    global_stem.setdefault(stem_l, full_p)

        self.delta_table.setRowCount(0)
        healed_locally = 0
        missing_entries = []

        m3u8_files = sorted([
            f for f in os.listdir(m3u_dir) if f.lower().endswith(".m3u8")
        ])

        for m3u8_f in m3u8_files:
            pl_name = os.path.splitext(m3u8_f)[0]
            m3u8_path = os.path.join(m3u_dir, m3u8_f)
            pl_folder = os.path.join(self.base_dir, pl_name)
            os.makedirs(pl_folder, exist_ok=True)

            local_folder_files = {
                f.lower(): f for f in os.listdir(pl_folder) if f.lower().endswith(audio_exts)
            }
            local_folder_stems = {
                os.path.splitext(f)[0].lower(): f for f in os.listdir(pl_folder) if f.lower().endswith(audio_exts)
            }

            with open(m3u8_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()

            modified_m3u8 = False
            new_lines = []

            for line in lines:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    new_lines.append(line)
                    continue

                decoded = urllib.parse.unquote(stripped).replace("\\", "/")
                parts = [p for p in decoded.split("/") if p and p != ".."]
                if not parts:
                    continue

                expected_fname = parts[-1]
                # Skip corrupt lines that aren't actual audio filenames
                if not expected_fname.lower().endswith(audio_exts):
                    modified_m3u8 = True
                    continue

                exp_low = expected_fname.lower()
                exp_stem = os.path.splitext(expected_fname)[0].lower().strip()

                # Case A: File already exists in this playlist's folder!
                if exp_low in local_folder_files:
                    actual_f = local_folder_files[exp_low]
                    new_lines.append(f"../{pl_name}/{actual_f}\n")
                    continue
                elif exp_stem in local_folder_stems:
                    actual_f = local_folder_stems[exp_stem]
                    new_lines.append(f"../{pl_name}/{actual_f}\n")
                    modified_m3u8 = True
                    continue

                # Case B: File exists in ANOTHER folder on this laptop! Copy it into this playlist folder automatically!
                found_elsewhere = global_exact.get(exp_low) or global_stem.get(exp_stem)
                if found_elsewhere and os.path.exists(found_elsewhere):
                    actual_f = os.path.basename(found_elsewhere)
                    dest_p = os.path.join(pl_folder, actual_f)
                    if not os.path.exists(dest_p):
                        shutil.copy2(found_elsewhere, dest_p)
                    local_folder_files[actual_f.lower()] = actual_f
                    local_folder_stems[os.path.splitext(actual_f)[0].lower()] = actual_f
                    new_lines.append(f"../{pl_name}/{actual_f}\n")
                    modified_m3u8 = True
                    healed_locally += 1
                    self.log(f"  [Auto-Healed Local Delta] Copied '{actual_f}' from '{os.path.basename(os.path.dirname(found_elsewhere))}/' -> '{pl_name}/'")
                    continue

                # Case C: Truly missing from local storage! Add to Delta Recovery Table
                new_lines.append(line)
                missing_entries.append((pl_name, m3u8_path, expected_fname))

            if modified_m3u8:
                with open(m3u8_path, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)

        # Populate Delta Recovery Table
        for pl_name, m3u8_path, expected_fname in missing_entries:
            row = self.delta_table.rowCount()
            self.delta_table.insertRow(row)

            item_pl = QTableWidgetItem(pl_name)
            item_fname = QTableWidgetItem(expected_fname)
            item_fname.setData(Qt.UserRole, {
                "pl_name": pl_name,
                "m3u8_path": m3u8_path,
                "expected_fname": expected_fname,
                "yt_url": None,
                "yt_title": None
            })

            item_status = QTableWidgetItem("⏳ Click '🔍 Search YT' or '📂 Pick File'")
            item_status.setForeground(QBrush(QColor("#8892b0")))

            self.delta_table.setItem(row, 0, item_pl)
            self.delta_table.setItem(row, 1, item_fname)
            self.delta_table.setItem(row, 2, item_status)

            btn_search = QPushButton("🔍 Search YT")
            set_btn_variant(btn_search, "restore")
            btn_search.clicked.connect(lambda _, b=btn_search: self.search_single_delta_yt(b))
            self.delta_table.setCellWidget(row, 3, btn_search)

            btn_prev = QPushButton("▶ Preview Match")
            set_btn_variant(btn_prev, "accent")
            btn_prev.clicked.connect(lambda _, b=btn_prev: self.preview_single_delta_yt(b))
            self.delta_table.setCellWidget(row, 4, btn_prev)

            btn_dl = QPushButton("⬇ Download & Fix")
            set_btn_variant(btn_dl, "restore")
            btn_dl.clicked.connect(lambda _, b=btn_dl: self.download_single_delta_yt(b))
            self.delta_table.setCellWidget(row, 5, btn_dl)

            btn_pick = QPushButton("📂 Pick Local File...")
            set_btn_variant(btn_pick, "accent")
            btn_pick.clicked.connect(lambda _, b=btn_pick: self.pick_local_file_for_delta(b))
            self.delta_table.setCellWidget(row, 6, btn_pick)

            btn_rm = QPushButton("✖ Remove Entry")
            set_btn_variant(btn_rm, "danger")
            btn_rm.clicked.connect(lambda _, b=btn_rm: self.remove_dead_m3u8_entry(b))
            self.delta_table.setCellWidget(row, 7, btn_rm)

        self.refresh_playlist_stats_table()
        self.delta_status_lbl.setText(
            f"DELTA SCAN COMPLETE // Auto-Healed {healed_locally} tracks from local folders | "
            f"{len(missing_entries)} tracks genuinely missing from disk."
        )
        self.tabs.setCurrentWidget(self.delta_tab)

    def search_single_delta_yt(self, btn_widget):
        row = self.find_row_by_widget(self.delta_table, btn_widget)
        if row == -1:
            return
        meta = self.delta_table.item(row, 1).data(Qt.UserRole)
        query = self.clean_query_from_filename(meta["expected_fname"])

        self.delta_table.item(row, 2).setText(f"🔎 Searching YT for: '{query}'...")
        QApplication.processEvents()

        try:
            res = subprocess.run(
                [
                    "yt-dlp", "--dump-json", "--no-playlist", "--flat-playlist",
                    f"ytsearch1:{query}"
                ],
                capture_output=True, text=True, timeout=15
            )
            if res.returncode == 0 and res.stdout.strip():
                first_line = res.stdout.strip().splitlines()[0]
                data = json.loads(first_line)
                yt_title = data.get("title", "Unknown Title")
                yt_uploader = data.get("uploader") or data.get("channel") or "YouTube"
                yt_id = data.get("id", "")
                yt_dur = data.get("duration")
                dur_str = f"{int(yt_dur)//60}:{int(yt_dur)%60:02d}" if yt_dur else "??:??"
                yt_url = data.get("url") or f"https://www.youtube.com/watch?v={yt_id}"
                if not yt_url.startswith("http"):
                    yt_url = f"https://www.youtube.com/watch?v={yt_id}"

                meta["yt_url"] = yt_url
                meta["yt_title"] = yt_title
                self.delta_table.item(row, 1).setData(Qt.UserRole, meta)

                status_item = self.delta_table.item(row, 2)
                status_item.setText(f"✔ MATCH: {yt_title} [{yt_uploader} • {dur_str}]")
                status_item.setForeground(QBrush(QColor("#66fcf1")))
            else:
                status_item = self.delta_table.item(row, 2)
                status_item.setText("❌ MATCH NOT FOUND (Use '📂 Pick Local File...' from Phone)")
                status_item.setForeground(QBrush(QColor("#ff2a54")))
        except Exception as e:
            status_item = self.delta_table.item(row, 2)
            status_item.setText(f"❌ Search Error: {e} (Use '📂 Pick Local File...')")
            status_item.setForeground(QBrush(QColor("#ff2a54")))

    def batch_search_all_deltas(self):
        total = self.delta_table.rowCount()
        if total == 0:
            QMessageBox.information(self, "No Missing Deltas", "Click '1. SCAN & AUTO-HEAL LOCAL DELTAS' first.")
            return
        for r in range(total):
            meta = self.delta_table.item(r, 1).data(Qt.UserRole)
            if not meta.get("yt_url"):
                btn = self.delta_table.cellWidget(r, 3)
                self.search_single_delta_yt(btn)
                pct = int(((r + 1) / total) * 100)
                self.progress_bar.setRange(0, 100)
                self.progress_bar.setValue(pct)
                self.progress_bar.setFormat(f"SEARCHING YT MUSIC DELTAS: {r+1}/{total} ({pct}%)")
                QApplication.processEvents()

    def preview_single_delta_yt(self, btn_widget):
        row = self.find_row_by_widget(self.delta_table, btn_widget)
        if row == -1:
            return
        meta = self.delta_table.item(row, 1).data(Qt.UserRole)
        if not meta.get("yt_url"):
            self.search_single_delta_yt(btn_widget)
            meta = self.delta_table.item(row, 1).data(Qt.UserRole)
            if not meta.get("yt_url"):
                return

        self.highlight_playing_row(self.delta_table, row)
        self.now_playing_label.setText(f"⏳ Buffering YT Stream: {meta.get('yt_title')}...")
        QApplication.processEvents()

        try:
            res = subprocess.run(
                [get_bin("yt-dlp"), "-f", "bestaudio", "-g", meta["yt_url"]],
                capture_output=True, text=True, timeout=15
            )
            if res.returncode == 0 and res.stdout.strip():
                stream_url = res.stdout.strip().splitlines()[0]
                self.player.setSource(QUrl(stream_url))
                self.player.play()
                self.now_playing_label.setText(f"▶ [YT STREAM PREVIEW] {meta.get('yt_title')}")
            else:
                QMessageBox.warning(self, "Stream Error", "Could not extract stream URL for preview.")
        except Exception as e:
            QMessageBox.warning(self, "Stream Error", str(e))

    def replace_m3u8_entry_in_place(self, m3u8_path, pl_name, old_expected_fname, new_actual_fname):
        """Updates the exact line in the .m3u8 file so track position/order is 100% preserved."""
        if not os.path.exists(m3u8_path):
            return
        with open(m3u8_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        updated_lines = []
        old_low = old_expected_fname.lower()
        for line in lines:
            stripped = line.strip()
            decoded = urllib.parse.unquote(stripped).replace("\\", "/")
            if stripped and not stripped.startswith("#") and decoded.lower().endswith("/" + old_low) or decoded.lower() == old_low:
                updated_lines.append(f"../{pl_name}/{new_actual_fname}\n")
            else:
                updated_lines.append(line)

        with open(m3u8_path, "w", encoding="utf-8") as f:
            f.writelines(updated_lines)

    def download_single_delta_yt(self, btn_widget):
        row = self.find_row_by_widget(self.delta_table, btn_widget)
        if row == -1:
            return
        meta = self.delta_table.item(row, 1).data(Qt.UserRole)
        if not meta.get("yt_url"):
            self.search_single_delta_yt(btn_widget)
            meta = self.delta_table.item(row, 1).data(Qt.UserRole)
            if not meta.get("yt_url"):
                return

        pl_name = meta["pl_name"]
        m3u8_path = meta["m3u8_path"]
        expected_fname = meta["expected_fname"]
        stem_only = os.path.splitext(expected_fname)[0]
        target_dir = os.path.join(self.base_dir, pl_name)
        os.makedirs(target_dir, exist_ok=True)

        # Save directly using the original stem + .mp3 so it fits cleanly and updates the .m3u8 in place
        final_mp3_name = f"{stem_only}.mp3"
        out_template = os.path.join(target_dir, f"{stem_only}.%(ext)s")

        self.delta_table.item(row, 2).setText(f"⬇ Downloading '{meta.get('yt_title')}' into '{pl_name}/'...")
        QApplication.processEvents()

        res = subprocess.run([
            "yt-dlp",
            "--extract-audio", "--audio-format", "mp3", "--audio-quality", "0",
            "--embed-thumbnail", "--embed-metadata",
            "-o", out_template,
            meta["yt_url"]
        ], capture_output=True, text=True)

        dest_file = os.path.join(target_dir, final_mp3_name)
        if res.returncode == 0 and os.path.exists(dest_file):
            self.replace_m3u8_entry_in_place(m3u8_path, pl_name, expected_fname, final_mp3_name)
            self.log(f"[DELTA DOWNLOADED & POSITIONED] '{final_mp3_name}' -> '{pl_name}/'")
            self.delta_table.removeRow(row)
            self.refresh_playlist_stats_table()
        else:
            QMessageBox.warning(self, "Download Failed", f"yt-dlp could not download track:\n{res.stderr[:300]}")

    def pick_local_file_for_delta(self, btn_widget):
        row = self.find_row_by_widget(self.delta_table, btn_widget)
        if row == -1:
            return
        meta = self.delta_table.item(row, 1).data(Qt.UserRole)
        pl_name = meta["pl_name"]
        m3u8_path = meta["m3u8_path"]
        expected_fname = meta["expected_fname"]

        picked_path, _ = QFileDialog.getOpenFileName(
            self,
            f"Select Local/Phone File to Replace '{expected_fname}' in [{pl_name}]",
            os.path.expanduser("~"),
            "Audio Files (*.mp3 *.m4a *.flac *.opus *.ogg *.wav)"
        )
        if not picked_path or not os.path.exists(picked_path):
            return

        target_dir = os.path.join(self.base_dir, pl_name)
        os.makedirs(target_dir, exist_ok=True)
        picked_fname = os.path.basename(picked_path)
        dest_path = os.path.join(target_dir, picked_fname)

        if os.path.abspath(picked_path) != os.path.abspath(dest_path):
            shutil.copy2(picked_path, dest_path)

        # Update the exact line in the .m3u8 to match the picked file's name at its original position
        self.replace_m3u8_entry_in_place(m3u8_path, pl_name, expected_fname, picked_fname)
        self.log(f"[DELTA LINKED FROM LOCAL FILE] '{picked_fname}' placed in '{pl_name}/' and positioned in '{os.path.basename(m3u8_path)}'")

        self.delta_table.removeRow(row)
        self.refresh_playlist_stats_table()

    def remove_dead_m3u8_entry(self, btn_widget):
        row = self.find_row_by_widget(self.delta_table, btn_widget)
        if row == -1:
            return
        meta = self.delta_table.item(row, 1).data(Qt.UserRole)
        m3u8_path = meta["m3u8_path"]
        expected_fname = meta["expected_fname"]

        if os.path.exists(m3u8_path):
            with open(m3u8_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            old_low = expected_fname.lower()
            cleaned = [
                l for l in lines
                if not (urllib.parse.unquote(l.strip()).replace("\\", "/").lower().endswith("/" + old_low))
            ]
            with open(m3u8_path, "w", encoding="utf-8") as f:
                f.writelines(cleaned)

        self.log(f"[REMOVED DEAD ENTRY] Stripped '{expected_fname}' from '{os.path.basename(m3u8_path)}'")
        self.delta_table.removeRow(row)
        self.refresh_playlist_stats_table()

    def select_directory(self):
        selected = QFileDialog.getExistingDirectory(self, "Select Library Root", self.base_dir)
        if selected:
            self.base_dir = selected
            self.dir_label.setText(f"ROOT: {self.base_dir}")
            self.refresh_staging_table()
            self.refresh_discarded_table()

    def play_from_table(self, table: QTableWidget, button_widget, filepath, tag_prefix=""):
        row = self.find_row_by_widget(table, button_widget)
        if row != -1:
            self.highlight_playing_row(table, row)
        self.play_file(filepath, tag_prefix)

    def play_file(self, filepath, tag_prefix=""):
        if not os.path.exists(filepath):
            self.now_playing_label.setText(f"[FILE MISSING] {os.path.basename(filepath)}")
            return
        self.player.stop()
        # Refresh default audio device in case PipeWire/Bluetooth sink changed
        dev = QMediaDevices.defaultAudioOutput()
        if dev and self.audio_output.device() != dev:
            self.audio_output.setDevice(dev)
        self.audio_output.setMuted(False)
        self.audio_output.setVolume(0.9)
        self.player.setSource(QUrl.fromLocalFile(os.path.abspath(filepath)))
        self.player.play()
        self.now_playing_label.setText(f"▶ {tag_prefix} {os.path.basename(filepath)}")

    def toggle_playback(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def update_slider_position(self, pos):
        if not self.seek_slider.isSliderDown():
            self.seek_slider.setValue(pos)
        self.update_time_label(pos, self.player.duration())

    def update_slider_duration(self, dur):
        self.seek_slider.setRange(0, dur)
        self.update_time_label(self.player.position(), dur)

    def update_time_label(self, pos, dur):
        def fmt(ms):
            s = max(0, ms // 1000)
            return f"{s // 60:02d}:{s % 60:02d}"
        self.time_label.setText(f"{fmt(pos)} / {fmt(dur)}")

    def run_cmd(self, prog, args, mode="generic", on_finish=None):
        if self.process and self.process.state() == QProcess.Running:
            self.log("[!] A background task is already running.")
            return

        self.active_task_mode = mode
        self.task_start_ts = datetime.now()
        self.tabs.setCurrentWidget(self.console)

        self.process = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONUNBUFFERED", "1")
        env.insert("RUST_LOG", "info")
        bundle_bin = os.path.join(get_base_bundle_dir(), "bin")
        if os.path.isdir(bundle_bin):
            env.insert("PATH", bundle_bin + os.pathsep + env.value("PATH", ""))
        self.process.setProcessEnvironment(env)

        self.process.readyReadStandardOutput.connect(
            lambda: self.append_stream(
                self.process.readAllStandardOutput().data().decode("utf-8", errors="ignore")
            )
        )
        self.process.readyReadStandardError.connect(
            lambda: self.append_stream(
                self.process.readAllStandardError().data().decode("utf-8", errors="ignore")
            )
        )

        def handle_finish():
            self.task_timer.stop()
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(100)
            self.progress_bar.setFormat(f"COMPLETED: {prog.upper()} — 100%")
            self.telemetry_label.setText(f"TELEMETRY // {prog.upper()} FINISHED SUCCESSFULLY (100%)")
            self.active_task_mode = None
            if on_finish:
                on_finish()

        self.process.finished.connect(handle_finish)

        self.log(f"\n==> EXEC: {prog} {' '.join(args)}\n")
        self.process.start(prog, args)

    def run_ytdlp(self):
        staging = os.path.join(self.base_dir, "_New_Arrivals")
        os.makedirs(staging, exist_ok=True)
        archive = os.path.join(self.base_dir, "ytdlp_liked_archive.txt")
        browser = self.browser_combo.currentText()
        max_dl = str(self.max_spin.value())

        self.ytdlp_current_idx = 0
        self.ytdlp_total_idx = self.max_spin.value()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("INITIALIZING YT-DLP — 0%")
        self.telemetry_label.setText("TELEMETRY // EXTRACTING BROWSER COOKIES & PLAYLIST METADATA...")

        args = [
            "--newline",
            "--cookies-from-browser", browser,
            "--extract-audio", "--audio-format", "mp3", "--audio-quality", "0",
            "--embed-thumbnail", "--embed-metadata",
            "--download-archive", archive,
            "--max-downloads", max_dl,
            "-o", f"{staging}/%(title)s.%(ext)s",
            "https://music.youtube.com/playlist?list=LM"
        ]
        self.run_cmd(get_bin("yt-dlp"), args, mode="ytdlp", on_finish=self.refresh_staging_table)

    def run_czkawka_audit(self):
        staging = os.path.join(self.base_dir, "_New_Arrivals")
        quarantine = os.path.join(self.base_dir, "_Quarantined_Dupes")
        os.makedirs(staging, exist_ok=True)

        if os.path.exists(quarantine):
            restored = 0
            for qf in os.listdir(quarantine):
                q_src = os.path.join(quarantine, qf)
                q_dst = os.path.join(staging, qf)
                if os.path.isfile(q_src):
                    shutil.move(q_src, q_dst)
                    restored += 1
            if restored > 0:
                self.log(f"==> Returned {restored} previously quarantined tracks to _New_Arrivals for fresh strict re-scan.")

        self.report_path = os.path.join(self.base_dir, "czkawka_audit_raw.txt")
        if os.path.exists(self.report_path):
            os.remove(self.report_path)

        audio_exts = (".mp3", ".m4a", ".flac", ".opus", ".ogg", ".wav")
        self.total_staging_files = len([
            f for f in os.listdir(staging) if f.lower().endswith(audio_exts)
        ])

        ref_dirs = []
        lib_count = 0
        for item in os.listdir(self.base_dir):
            full_path = os.path.join(self.base_dir, item)
            if os.path.isdir(full_path) and item not in SYSTEM_FOLDERS:
                ref_dirs.extend(["-d", full_path])
                try:
                    lib_count += len([
                        f for f in os.listdir(full_path) if f.lower().endswith(audio_exts)
                    ])
                except Exception:
                    pass
        self.total_library_files = lib_count
        self.czkawka_reported_pct = 0

        # Estimate scan duration based on total files & CPU core count (cache-aware)
        total_files = max(1, self.total_library_files + self.total_staging_files)
        cores = max(4, os.cpu_count() or 8)
        # Czkawka caches library fingerprints in ~/.cache/czkawka, so repeat runs are faster
        cache_exists = os.path.exists(os.path.expanduser("~/.cache/czkawka"))
        per_file_sec = 0.04 if cache_exists else 0.35
        self.estimated_scan_secs = max(15.0, (total_files * per_file_sec) / (cores * 0.65))

        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(1)
        self.progress_bar.setFormat("ACOUSTIC FINGERPRINT AUDIT — 1% (00m 00s)")
        self.telemetry_label.setText(
            f"TELEMETRY // STARTING CHROMAPRINT SCAN [1%] | {self.total_staging_files} New vs {self.total_library_files} Library Files"
        )
        self.task_timer.start(1000)

        args = ["music"] + ref_dirs + [
            "-d", staging,
            "--search-method", "CONTENT",
            "--minimum-segment-duration", "25.0",
            "--maximum-difference", "1.5",
            "-f", self.report_path
        ]
        self.run_cmd(get_bin("czkawka_cli"), args, mode="czkawka", on_finish=self.parse_and_quarantine_dupes)

    def parse_and_quarantine_dupes(self):
        self.log("\n==> Parsing 25-second acoustic fingerprint report & scanning against Discarded Blacklist...")
        staging = os.path.abspath(os.path.join(self.base_dir, "_New_Arrivals"))
        quarantine = os.path.abspath(os.path.join(self.base_dir, "_Quarantined_Dupes"))
        os.makedirs(quarantine, exist_ok=True)

        self.audit_table.setRowCount(0)
        quarantined_count = 0
        blacklist_caught_count = 0

        # --- PART A: Parse czkawka_cli Library Duplicates (if report file exists) ---
        if os.path.exists(self.report_path):
            with open(self.report_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            blocks = re.split(r'\n\s*\n', content)
            for block in blocks:
                paths = re.findall(r'(/[^\n"\']+\.(?:mp3|m4a|flac|opus|ogg|wav))', block, re.IGNORECASE)
                if len(paths) < 2:
                    continue

                staging_files = [p for p in paths if os.path.abspath(p).startswith(staging)]
                library_files = [p for p in paths if not os.path.abspath(p).startswith(staging)]

                if staging_files and library_files:
                    orig_lib_path = library_files[0]
                    lib_folder = os.path.basename(os.path.dirname(orig_lib_path))

                    for st_file in staging_files:
                        fname = os.path.basename(st_file)
                        dest_quarantine = os.path.join(quarantine, fname)
                        if os.path.exists(st_file):
                            shutil.move(st_file, dest_quarantine)
                            quarantined_count += 1

                        row = self.audit_table.rowCount()
                        self.audit_table.insertRow(row)

                        self.audit_table.setItem(row, 0, QTableWidgetItem(fname))
                        self.audit_table.setItem(row, 1, QTableWidgetItem(os.path.basename(orig_lib_path)))
                        self.audit_table.setItem(row, 2, QTableWidgetItem(lib_folder))
                        self.audit_table.setItem(row, 3, QTableWidgetItem("25s Waveform (<=1.5)"))

                        btn_play_dupe = QPushButton("▶ Dupe")
                        set_btn_variant(btn_play_dupe, "accent")
                        btn_play_dupe.clicked.connect(
                            lambda _, p=dest_quarantine, b=btn_play_dupe: self.play_from_table(
                                self.audit_table, b, p, "[QUARANTINED DUPE]"
                            )
                        )
                        self.audit_table.setCellWidget(row, 4, btn_play_dupe)

                        btn_play_orig = QPushButton("▶ Orig")
                        set_btn_variant(btn_play_orig, "accent")
                        btn_play_orig.clicked.connect(
                            lambda _, p=orig_lib_path, b=btn_play_orig: self.play_from_table(
                                self.audit_table, b, p, f"[LIBRARY: {lib_folder}]"
                            )
                        )
                        self.audit_table.setCellWidget(row, 5, btn_play_orig)

                        btn_restore = QPushButton("↩ Restore")
                        set_btn_variant(btn_restore, "restore")
                        btn_restore.clicked.connect(
                            lambda _, q_path=dest_quarantine, btn=btn_restore: self.restore_single_quarantined(q_path, btn)
                        )
                        self.audit_table.setCellWidget(row, 6, btn_restore)

                        btn_del_one = QPushButton("✖ Delete")
                        set_btn_variant(btn_del_one, "danger")
                        btn_del_one.clicked.connect(
                            lambda _, q_path=dest_quarantine, btn=btn_del_one: self.delete_single_quarantined(q_path, btn)
                        )
                        self.audit_table.setCellWidget(row, 7, btn_del_one)

        # --- PART B: Deep Acoustic Fingerprint Audit Against _Discarded_Songs Blacklist ---
        # Stop background worker first so it doesn't fight with the audit over fpcalc subprocesses
        if self.fp_worker and self.fp_worker.isRunning():
            self.fp_worker.stop()
            self.fp_worker.wait(500)

        audio_exts = (".mp3", ".m4a", ".flac", ".opus", ".ogg", ".wav")
        if os.path.exists(staging) and self.load_discard_db():
            remaining_files = sorted([
                f for f in os.listdir(staging) if f.lower().endswith(audio_exts)
            ])
            total_rem = max(1, len(remaining_files))
            for idx_f, fname in enumerate(remaining_files, 1):
                if idx_f % 3 == 0:
                    pct_b = int((idx_f / total_rem) * 100)
                    self.progress_bar.setFormat(f"CHECKING BLACKLIST FINGERPRINTS: {idx_f}/{total_rem} ({pct_b}%)")
                    QApplication.processEvents()
                st_file = os.path.join(staging, fname)
                discard_match = self.check_if_discarded(st_file, compute_if_missing=True)
                if discard_match:
                    dest_quarantine = os.path.join(quarantine, fname)
                    if os.path.exists(st_file):
                        shutil.move(st_file, dest_quarantine)
                        blacklist_caught_count += 1

                    orig_discard_name = discard_match.get("filename", "Unknown")
                    discard_reason = discard_match.get("reason", "Previously discarded")
                    discard_date = discard_match.get("timestamp", "")

                    self.log(
                        f"  [BLACKLIST FINGERPRINT MATCH] '{fname}' matched discarded track '{orig_discard_name}' "
                        f"(Reason: {discard_reason}) -> Isolated to _Quarantined_Dupes"
                    )

                    row = self.audit_table.rowCount()
                    self.audit_table.insertRow(row)

                    item_q = QTableWidgetItem(fname)
                    item_orig = QTableWidgetItem(f"🚫 {orig_discard_name} ({discard_date})")
                    item_folder = QTableWidgetItem("_Discarded_Songs (Blacklist)")
                    item_reason = QTableWidgetItem(f"BLACKLISTED: {discard_reason}")

                    warn_brush = QBrush(QColor("#ff2a54"))
                    for it in (item_q, item_orig, item_folder, item_reason):
                        it.setForeground(warn_brush)

                    self.audit_table.setItem(row, 0, item_q)
                    self.audit_table.setItem(row, 1, item_orig)
                    self.audit_table.setItem(row, 2, item_folder)
                    self.audit_table.setItem(row, 3, item_reason)

                    btn_play_dupe = QPushButton("▶ Dupe")
                    set_btn_variant(btn_play_dupe, "accent")
                    btn_play_dupe.clicked.connect(
                        lambda _, p=dest_quarantine, b=btn_play_dupe: self.play_from_table(
                            self.audit_table, b, p, "[BLACKLISTED DUPE]"
                        )
                    )
                    self.audit_table.setCellWidget(row, 4, btn_play_dupe)

                    lbl_deleted = QLabel("Deleted Previously")
                    lbl_deleted.setAlignment(Qt.AlignCenter)
                    lbl_deleted.setStyleSheet("color: #8892b0; font-style: italic;")
                    self.audit_table.setCellWidget(row, 5, lbl_deleted)

                    btn_restore = QPushButton("↩ Restore")
                    set_btn_variant(btn_restore, "restore")
                    btn_restore.clicked.connect(
                        lambda _, q_path=dest_quarantine, btn=btn_restore: self.restore_single_quarantined(q_path, btn)
                    )
                    self.audit_table.setCellWidget(row, 6, btn_restore)

                    btn_del_one = QPushButton("✖ Delete")
                    set_btn_variant(btn_del_one, "danger")
                    btn_del_one.clicked.connect(
                        lambda _, q_path=dest_quarantine, btn=btn_del_one: self.delete_single_quarantined(q_path, btn)
                    )
                    self.audit_table.setCellWidget(row, 7, btn_del_one)

        total_isolated = quarantined_count + blacklist_caught_count
        if total_isolated == 0:
            self.audit_summary.setText(
                "AUDIT COMPLETE: 0 library duplicates and 0 blacklisted tracks found! All tracks in _New_Arrivals are clean."
            )
        else:
            self.audit_summary.setText(
                f"AUDIT COMPLETE: Isolated {quarantined_count} library dupes + {blacklist_caught_count} previously discarded tracks. "
                f"Use '↩ Restore' on false positives, or '✖ Delete' to purge."
            )

        self.refresh_staging_table()
        self.tabs.setCurrentWidget(self.audit_tab)

    def restore_single_quarantined(self, q_path, btn_widget):
        staging = os.path.join(self.base_dir, "_New_Arrivals")
        os.makedirs(staging, exist_ok=True)
        fname = os.path.basename(q_path)
        dest = os.path.join(staging, fname)

        if self.player.source() == QUrl.fromLocalFile(q_path):
            self.player.stop()

        if os.path.exists(q_path):
            shutil.move(q_path, dest)
            self.log(f"[RESTORED FALSE POSITIVE] '{fname}' moved back to '_New_Arrivals/'")

        row = self.find_row_by_widget(self.audit_table, btn_widget)
        if row != -1:
            self.audit_table.removeRow(row)

        self.refresh_staging_table()
        self.audit_summary.setText(
            f"Restored '{fname}' to _New_Arrivals. ({self.audit_table.rowCount()} items left in audit)"
        )

    def delete_single_quarantined(self, q_path, btn_widget):
        fname = os.path.basename(q_path)
        if self.player.source() == QUrl.fromLocalFile(q_path):
            self.player.stop()

        if os.path.exists(q_path):
            os.remove(q_path)
            self.log(f"[DELETED SINGLE DUPE] Permanently removed '{fname}' from quarantine.")

        row = self.find_row_by_widget(self.audit_table, btn_widget)
        if row != -1:
            self.audit_table.removeRow(row)

        self.audit_summary.setText(
            f"Deleted '{fname}'. ({self.audit_table.rowCount()} items left in audit)"
        )

    def wipe_quarantine(self):
        quarantine = os.path.join(self.base_dir, "_Quarantined_Dupes")
        if os.path.exists(quarantine):
            shutil.rmtree(quarantine)
            self.audit_table.setRowCount(0)
            self.audit_summary.setText("All remaining quarantined duplicates permanently wiped from disk.")
            self.log("==> Wiped _Quarantined_Dupes folder permanently.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MusicVaultApp()
    window.show()
    sys.exit(app.exec())
