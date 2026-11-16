import sys
import os
import re
import json
import shutil
import subprocess
import urllib.parse
import unicodedata
import hashlib
import difflib
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

        self.btn_dedupe = QPushButton("2. HYBRID 25s ACOUSTIC + METADATA AUDIT")
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

        self.staging_search_input = QLineEdit()
        self.staging_search_input.setPlaceholderText("🔍 Search / filter _New_Arrivals tracks...")
        self.staging_search_input.setClearButtonEnabled(True)
        self.staging_search_input.setMinimumWidth(280)
        self.staging_search_input.textChanged.connect(self.filter_staging_table)

        self.chk_autoplay = QCheckBox("Auto-Play Next")
        self.chk_autoplay.setChecked(True)

        btn_bulk_sort = QPushButton("SORT / DISCARD SELECTED...")
        set_btn_variant(btn_bulk_sort, "accent")
        btn_bulk_sort.clicked.connect(self.sort_selected_staging_rows)

        btn_refresh_staging = QPushButton("REFRESH STAGING")
        btn_refresh_staging.clicked.connect(self.refresh_staging_table)

        staging_top.addWidget(self.staging_status_lbl)
        staging_top.addWidget(self.staging_search_input, stretch=1)
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
                ints = [int(raw_ptr[i]) for i in range(min(240, size.value))]
                lib.chromaprint_dealloc(raw_ptr)
                return ints
        except Exception:
            pass
        return []

    def raw_fingerprints_match(self, raw_a, raw_b):
        """
        Generalized 25-second (~200-frame) Chromaprint matcher:
          - Masks noisy LSB compression bits (0xAAAAAAAA) to isolate dominant spectral peaks.
          - Checks 25-second continuous alignment across sliding intro-offset windows.
        """
        if not raw_a or not raw_b or len(raw_a) < 20 or len(raw_b) < 20:
            return False
        a = raw_a[:240]
        b = raw_b[:240]

        MASK = 0xAAAAAAAA
        coarse_a = [x & MASK for x in a if x != 0]
        coarse_b = [x & MASK for x in b if x != 0]

        # Require strong landmark overlap across the 25s window
        if len(set(a) & set(b)) >= 12:
            return True
        if len(set(coarse_a) & set(coarse_b)) >= 24:
            return True

        min_len = min(len(a), len(b))
        for offset in range(-24, 25):
            full_matched = 0.0
            coarse_matched = 0.0
            compared_frames = 0

            for i in range(min_len):
                j = i + offset
                if 0 <= j < len(b):
                    compared_frames += 1
                    xor_full = (a[i] ^ b[j]) & 0xFFFFFFFF
                    xor_coarse = (a[i] ^ b[j]) & MASK
                    full_matched += 1.0 - (xor_full.bit_count() / 32.0)
                    coarse_matched += 1.0 - (xor_coarse.bit_count() / 16.0)

            # Enforce a full 25s (~195+ frame) comparison window (or full available length if legacy entry)
            required_frames = 195 if min_len >= 200 else max(20, int(min_len * 0.85))
            if compared_frames >= required_frames:
                if (full_matched / compared_frames) >= 0.74:
                    return True
                if (coarse_matched / compared_frames) >= 0.79:
                    return True
        return False

    def build_library_metadata_index(self):
        """Scans all playlist folders once (using persistent cache) to cross-reference Title, Artist, Genre, Album & Duration."""
        audio_exts = (".mp3", ".m4a", ".flac", ".opus", ".ogg", ".wav")
        index = []
        if not os.path.exists(self.base_dir):
            return index
        for folder in self.get_playlist_folders():
            f_dir = os.path.join(self.base_dir, folder)
            if not os.path.isdir(f_dir):
                continue
            for fname in os.listdir(f_dir):
                if fname.lower().endswith(audio_exts):
                    full_p = os.path.join(f_dir, fname)
                    meta = self.extract_full_track_metadata(full_p)
                    index.append((folder, fname, full_p, meta))
        self.save_metadata_cache()
        return index

    def compare_metadata_for_duplicate(self, st_meta, lib_meta, st_fname="", lib_fname=""):
        """
        Cross-references Core Title, Clean Title, Normalized Artist ('&'/'and' unified),
        Duration, Genre, and Album to catch duplicates even when tags or remaster suffixes differ.
        """
        s_core = st_meta.get("core_title") or st_meta.get("clean_title", "")
        l_core = lib_meta.get("core_title") or lib_meta.get("clean_title", "")
        s_title = st_meta.get("clean_title", "")
        l_title = lib_meta.get("clean_title", "")
        s_art = st_meta.get("norm_artist", "")
        l_art = lib_meta.get("norm_artist", "")
        s_dur = float(st_meta.get("duration", 0.0))
        l_dur = float(lib_meta.get("duration", 0.0))
        s_gen = st_meta.get("norm_genre", "")
        l_gen = lib_meta.get("norm_genre", "")
        s_alb = st_meta.get("norm_album", "")
        l_alb = lib_meta.get("norm_album", "")

        both_have_dur = (s_dur > 0 and l_dur > 0)
        dur_diff = abs(s_dur - l_dur) if both_have_dur else 0.0
        dur_close = (not both_have_dur) or (dur_diff <= 4.0)
        dur_moderate = (not both_have_dur) or (dur_diff <= 15.0)

        same_artist = False
        if s_art and l_art and s_art not in {"unknown", "unknownartist"} and l_art not in {"unknown", "unknownartist"}:
            if s_art == l_art or (len(s_art) >= 4 and len(l_art) >= 4 and (s_art in l_art or l_art in s_art)):
                same_artist = True
        # Also check if one track's artist appears inside the other track's filename/title
        if not same_artist:
            s_fn_norm = re.sub(r'[^\w]', '', re.sub(r'\b(?:the|and)\b', ' ', st_fname.lower().replace('&', ' and ')))
            l_fn_norm = re.sub(r'[^\w]', '', re.sub(r'\b(?:the|and)\b', ' ', lib_fname.lower().replace('&', ' and ')))
            if (s_art and len(s_art) >= 5 and s_art in l_fn_norm) or (l_art and len(l_art) >= 5 and l_art in s_fn_norm):
                same_artist = True

        # 1. Exact Core Title or Clean Title Match
        if (s_core and l_core and s_core == l_core) or (s_title and l_title and s_title == l_title):
            matched_t = s_core or s_title
            if same_artist and dur_moderate:
                return f"METADATA MATCH: Artist + Title ({st_meta.get('duration_str')})"
            if dur_close and len(matched_t) >= 5:
                extra = []
                if s_gen and s_gen == l_gen:
                    extra.append("Genre")
                if s_alb and s_alb == l_alb:
                    extra.append("Album")
                suffix = f" + {'/'.join(extra)}" if extra else ""
                return f"TITLE + DURATION ({st_meta.get('duration_str')} Δ{dur_diff:.1f}s{suffix})"
            if same_artist and len(matched_t) >= 8:
                return f"ARTIST + EXACT TITLE ({st_meta.get('duration_str')})"

        # 2. Substring Core Title containment + Same Artist or Close Duration
        if s_core and l_core and len(s_core) >= 5 and len(l_core) >= 5:
            if s_core in l_core or l_core in s_core:
                if (same_artist and dur_moderate) or (dur_diff <= 2.5 and both_have_dur):
                    return f"TITLE MATCH + {'ARTIST' if same_artist else 'DURATION'} ({st_meta.get('duration_str')})"

        # 3. Fuzzy Similarity + Artist / Duration
        if s_core and l_core:
            ratio = difflib.SequenceMatcher(None, s_core, l_core).ratio()
            if same_artist and ratio >= 0.72 and dur_moderate:
                return f"ARTIST + FUZZY TITLE ({int(ratio*100)}%) ({st_meta.get('duration_str')})"
            if ratio >= 0.86 and dur_close:
                return f"HIGH TITLE SIMILARITY ({int(ratio*100)}%) + DURATION ({st_meta.get('duration_str')})"

        return None

    def check_if_discarded(self, filepath, compute_if_missing=False):
        db = self.load_discard_db()
        if not db:
            return None

        fname = os.path.basename(filepath)
        norm_name = re.sub(r'[^\w]', '', os.path.splitext(fname)[0].lower())
        st_meta = self.extract_full_track_metadata(filepath)
        s_clean_title = st_meta.get("clean_title", "")
        s_dur = float(st_meta.get("duration", 0.0))

        # 1. Fast filename & metadata/duration check against discarded_db.json
        for entry in db:
            saved_fname = entry.get("filename", "")
            saved_norm = re.sub(r'[^\w]', '', os.path.splitext(saved_fname)[0].lower())
            if norm_name and saved_norm and norm_name == saved_norm:
                return entry
            saved_dur = float(entry.get("duration", 0.0))
            if s_clean_title and len(s_clean_title) >= 5 and saved_norm:
                if s_clean_title in saved_norm and s_dur > 0 and saved_dur > 0 and abs(s_dur - saved_dur) <= 2.5:
                    return entry

        # 2. 25s Coarse Spectral Chromaprint check
        if compute_if_missing or filepath in self.staging_fingerprint_cache:
            fp, dur, raw_ints = self.compute_fingerprint(filepath)
            if not raw_ints and fp:
                raw_ints = self.decode_base64_fingerprint_to_raw(fp)

            db_updated = False
            matched_entry = None
            for entry in db:
                saved_fp = entry.get("fingerprint", "")
                saved_raw = entry.get("raw_fingerprint", [])

                if not saved_raw and saved_fp:
                    saved_raw = self.decode_base64_fingerprint_to_raw(saved_fp)
                    if saved_raw:
                        entry["raw_fingerprint"] = saved_raw
                        db_updated = True

                if fp and saved_fp and (fp == saved_fp or (len(fp) > 36 and fp[:36] == saved_fp[:36])):
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
    def get_existing_m3u8_stems_map(self):
        """Returns {nfc_stem: full_m3u8_path} for all existing playlists with Unicode NFC normalization."""
        m3u_dir = self.get_m3u_directory()
        stems_map = {}
        if os.path.exists(m3u_dir):
            for f in sorted(os.listdir(m3u_dir)):
                if f.lower().endswith((".m3u8", ".m3u", ".pls", ".xspf")):
                    stem = unicodedata.normalize("NFC", os.path.splitext(f)[0].strip())
                    if "dump" in stem.lower():
                        continue
                    stems_map[stem] = os.path.join(m3u_dir, f)
        return stems_map

    def is_loose_dump_folder(self, folder_name, stems_map=None):
        if "dump" in folder_name.lower():
            return True
        if stems_map is None:
            stems_map = self.get_existing_m3u8_stems_map()
        norm_f = unicodedata.normalize("NFC", folder_name.strip())
        return norm_f not in stems_map and folder_name.strip() not in stems_map

    def get_playlist_folders(self):
        if not os.path.exists(self.base_dir):
            return []
        stems_map = self.get_existing_m3u8_stems_map()
        return sorted([
            d for d in os.listdir(self.base_dir)
            if os.path.isdir(os.path.join(self.base_dir, d))
            and d not in SYSTEM_FOLDERS
            and not self.is_loose_dump_folder(d, stems_map)
        ])

    def on_background_fp_scanned(self, filepath, fp_data):
        """Called asynchronously as the background thread fingerprints each file in _New_Arrivals."""
        self.staging_fingerprint_cache[filepath] = fp_data
        discard_match = self.check_if_discarded(filepath, compute_if_missing=False)
        if not discard_match:
            return

        for r in range(self.staging_table.rowCount()):
            item_name = self.staging_table.item(r, 0)
            if item_name and item_name.data(Qt.UserRole) == filepath:
                reason_txt = discard_match.get("reason", "Unspecified")
                orig_name = discard_match.get("filename", "")
                date_txt = discard_match.get("timestamp", "")
                status_str = f"⚠️ BLACKLIST FINGERPRINT ({orig_name} | {date_txt}): {reason_txt}"
                item_status = self.staging_table.item(r, 4)
                if item_status:
                    item_status.setText(status_str)
                    warn_color = QBrush(QColor("#ff2a54"))
                    item_name.setForeground(warn_color)
                    item_status.setForeground(warn_color)
                break

    def refresh_staging_table(self):
        staging = os.path.join(self.base_dir, "_New_Arrivals")
        if self.staging_table.columnCount() != 8:
            self.staging_table.setColumnCount(8)
            self.staging_table.setHorizontalHeaderLabels([
                "Track Filename",
                "Artist",
                "Album / Genre",
                "Duration",
                "Vault & Blacklist Status",
                "Size",
                "Preview",
                "Action"
            ])
            hdr = self.staging_table.horizontalHeader()
            hdr.setSectionResizeMode(0, QHeaderView.Stretch)
            hdr.setSectionResizeMode(1, QHeaderView.Interactive)
            hdr.setSectionResizeMode(2, QHeaderView.Interactive)
            hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
            hdr.setSectionResizeMode(4, QHeaderView.Stretch)
            hdr.setSectionResizeMode(5, QHeaderView.ResizeToContents)
            hdr.setSectionResizeMode(6, QHeaderView.ResizeToContents)
            hdr.setSectionResizeMode(7, QHeaderView.ResizeToContents)
            self.staging_table.setColumnWidth(1, 165)
            self.staging_table.setColumnWidth(2, 175)

        self.staging_table.setRowCount(0)
        if not os.path.exists(staging):
            self.staging_status_lbl.setText("Staging Queue: _New_Arrivals folder not created yet.")
            return

        files = sorted([
            f for f in os.listdir(staging)
            if f.lower().endswith((".mp3", ".m4a", ".flac", ".opus", ".ogg", ".wav"))
        ])

        lib_index = self.build_library_metadata_index()
        uncached_paths = []
        flagged_count = 0
        lib_dupe_count = 0

        for fname in files:
            fpath = os.path.join(staging, fname)
            size_mb = os.path.getsize(fpath) / (1024 * 1024)
            meta = self.extract_full_track_metadata(fpath)
            discard_match = self.check_if_discarded(fpath, compute_if_missing=False)
            if fpath not in self.staging_fingerprint_cache:
                uncached_paths.append(fpath)

            lib_match_info = None
            if not discard_match:
                for lib_folder, lib_fname, lib_full_p, lib_meta in lib_index:
                    m_reason = self.compare_metadata_for_duplicate(meta, lib_meta, fname, lib_fname)
                    if m_reason:
                        lib_match_info = (lib_folder, lib_fname, m_reason)
                        break

            row = self.staging_table.rowCount()
            self.staging_table.insertRow(row)

            item_name = QTableWidgetItem(fname)
            item_name.setData(Qt.UserRole, fpath)

            artist_str = meta.get("artist") or "Unknown Artist"
            alb = meta.get("album", "").strip()
            gen = meta.get("genre", "").strip()
            if alb and gen:
                alb_gen_str = f"{gen} • {alb}"
            elif gen:
                alb_gen_str = gen
            elif alb:
                alb_gen_str = alb
            else:
                alb_gen_str = "—"

            item_artist = QTableWidgetItem(artist_str)
            item_artist.setForeground(QBrush(QColor("#c5c6c7")))

            item_alb_gen = QTableWidgetItem(alb_gen_str)
            item_alb_gen.setForeground(QBrush(QColor("#8892b0")))

            item_dur = QTableWidgetItem(meta.get("duration_str", "--:--"))
            item_dur.setTextAlignment(Qt.AlignCenter)

            if discard_match:
                flagged_count += 1
                reason_txt = discard_match.get("reason", "Unspecified")
                date_txt = discard_match.get("timestamp", "")
                status_str = f"🚫 DISCARDED ({date_txt}): {reason_txt}"
                item_status = QTableWidgetItem(status_str)
                warn_color = QBrush(QColor("#ff2a54"))
                item_name.setForeground(warn_color)
                item_status.setForeground(warn_color)
            elif lib_match_info:
                lib_dupe_count += 1
                l_folder, l_fname, l_reason = lib_match_info
                status_str = f"⚠️ IN LIBRARY [{l_folder}]: {l_reason}"
                item_status = QTableWidgetItem(status_str)
                dupe_color = QBrush(QColor("#ffb86c"))
                item_name.setForeground(dupe_color)
                item_status.setForeground(dupe_color)
            else:
                item_status = QTableWidgetItem("✔ Clean / Ready to Sort")
                item_status.setForeground(QBrush(QColor("#45a29e")))

            self.staging_table.setItem(row, 0, item_name)
            self.staging_table.setItem(row, 1, item_artist)
            self.staging_table.setItem(row, 2, item_alb_gen)
            self.staging_table.setItem(row, 3, item_dur)
            self.staging_table.setItem(row, 4, item_status)
            self.staging_table.setItem(row, 5, QTableWidgetItem(f"{size_mb:.2f} MB"))

            btn_play = QPushButton("▶ Preview")
            set_btn_variant(btn_play, "accent")
            btn_play.clicked.connect(
                lambda _, p=fpath, b=btn_play: self.play_from_table(self.staging_table, b, p, "[STAGING]")
            )
            self.staging_table.setCellWidget(row, 6, btn_play)

            btn_sort = QPushButton("SORT / DISCARD ▾")
            set_btn_variant(btn_sort, "restore")
            btn_sort.clicked.connect(lambda _, p=fpath: self.open_sort_modal([p]))
            self.staging_table.setCellWidget(row, 7, btn_sort)

        self.save_metadata_cache()
        self.staging_status_lbl.setText(
            f"Staging (_New_Arrivals): {len(files)} tracks "
            f"({lib_dupe_count} in library, {flagged_count} blacklisted)."
        )

        if hasattr(self, "staging_search_input") and self.staging_search_input.text().strip():
            self.filter_staging_table(self.staging_search_input.text())

        if uncached_paths and self.load_discard_db():
            if self.fp_worker and self.fp_worker.isRunning():
                self.fp_worker.stop()
                self.fp_worker.wait(500)
            self.fp_worker = StagingFingerprintWorker(uncached_paths)
            self.fp_worker.file_scanned.connect(self.on_background_fp_scanned)
            self.fp_worker.start()

    def filter_staging_table(self, text=""):
        """Hides/shows rows in _New_Arrivals based on Filename, Artist, Album/Genre, Duration, or Status."""
        if hasattr(self, "staging_search_input") and not isinstance(text, str):
            text = self.staging_search_input.text()
        query = (text or "").strip().lower()
        visible_count = 0
        total_count = self.staging_table.rowCount()

        for r in range(total_count):
            row_text_parts = []
            for col_idx in (0, 1, 2, 3, 4):
                it = self.staging_table.item(r, col_idx)
                if it:
                    row_text_parts.append(it.text().lower())
            combined = " ".join(row_text_parts)
            match = (not query) or all(tok in combined for tok in query.split())
            self.staging_table.setRowHidden(r, not match)
            if match:
                visible_count += 1

        if query:
            self.staging_status_lbl.setText(
                f"Staging (_New_Arrivals): Showing {visible_count} of {total_count} tracks"
            )
        else:
            self.staging_status_lbl.setText(
                f"Staging Queue (_New_Arrivals): {total_count} tracks remaining"
            )

    def remove_staging_rows_by_paths(self, removed_paths):
        """Removes sorted/discarded rows in-place in <1ms without rebuilding the entire table or restarting threads."""
        target_set = set(removed_paths)
        for r in range(self.staging_table.rowCount() - 1, -1, -1):
            item = self.staging_table.item(r, 0)
            if item and item.data(Qt.UserRole) in target_set:
                self.staging_table.removeRow(r)
        current_search = self.staging_search_input.text() if hasattr(self, "staging_search_input") else ""
        self.filter_staging_table(current_search)

    def sort_selected_staging_rows(self):
        selected_rows = sorted(set(
            idx.row() for idx in self.staging_table.selectedIndexes()
            if not self.staging_table.isRowHidden(idx.row())
        ))
        if not selected_rows:
            QMessageBox.information(
                self, "No Rows Selected",
                "Select one or more visible tracks in the table first (use Shift/Ctrl + Click), or click 'SORT / DISCARD ▾' on any row."
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

        processed_paths = []

        if dlg.action_type == "discard":
            already_blacklisted = []
            brand_new_discards = []
            for fp in filepaths:
                # Use cached fingerprint first so UI doesn't block on large selections
                if self.check_if_discarded(fp, compute_if_missing=(len(filepaths) <= 3)):
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

            for fp in already_blacklisted:
                self.record_and_delete_discarded(fp, reason=None)
                processed_paths.append(fp)

            for fp in brand_new_discards:
                self.record_and_delete_discarded(fp, reason=clean_reason)
                processed_paths.append(fp)

            self.remove_staging_rows_by_paths(processed_paths)
            self.refresh_discarded_table()
            self.trigger_autoplay_next()

        elif dlg.action_type == "sort":
            target_folders = dlg.selected_folders
            for fp in filepaths:
                if not os.path.exists(fp):
                    processed_paths.append(fp)
                    continue
                fname = os.path.basename(fp)

                # Fast non-blocking check against cache/filename
                discard_match = self.check_if_discarded(fp, compute_if_missing=False)
                if discard_match:
                    ans = QMessageBox.warning(
                        self,
                        "⚠️ Previously Discarded Track Detected!",
                        f"Track: {fname}\n\n"
                        f"This audio matches a previously discarded file!\n"
                        f"• Discarded On: {discard_match.get('timestamp')}\n"
                        f"• Original Name: {discard_match.get('filename')}\n"
                        f"• Reason: {discard_match.get('reason')}\n\n"
                        f"Are you sure you want to proceed and add it to {target_folders}?",
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

                    self.append_sorted_track_to_m3u8_immediately(folder_name, fname)

                processed_paths.append(fp)

            self.remove_staging_rows_by_paths(processed_paths)
            self.refresh_playlist_stats_table()
            self.trigger_autoplay_next()

    def trigger_autoplay_next(self):
        if self.chk_autoplay.isChecked() and self.staging_table.rowCount() > 0:
            for r in range(self.staging_table.rowCount()):
                if not self.staging_table.isRowHidden(r):
                    next_path = self.staging_table.item(r, 0).data(Qt.UserRole)
                    self.highlight_playing_row(self.staging_table, r)
                    self.play_file(next_path, "[AUTO-NEXT STAGING]")
                    break

    # =========================================================================
    # Option B: Auto-Consolidate Telegram Dump & Rebuild Relative M3Us
    # =========================================================================
    def find_existing_m3u8_for_playlist(self, pl_name):
        """Finds the exact .m3u8 path for pl_name using Unicode NFC normalization."""
        m3u_dir = self.get_m3u_directory()
        os.makedirs(m3u_dir, exist_ok=True)
        target_nfc = unicodedata.normalize("NFC", pl_name.strip())
        for f in sorted(os.listdir(m3u_dir)):
            if f.lower().endswith(".m3u8"):
                f_nfc = unicodedata.normalize("NFC", os.path.splitext(f)[0].strip())
                if f_nfc == target_nfc:
                    return os.path.join(m3u_dir, f)
        return os.path.join(m3u_dir, f"{pl_name.strip()}.m3u8")

    def write_clean_m3u8_file(self, m3u8_path, rel_lines):
        """Writes an .m3u8 with #EXTINF:-1,Title headers and clean ../Folder/Track.ext relative paths."""
        with open(m3u8_path, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for line in rel_lines:
                clean_rel = line.strip().replace("\\", "/")
                if not clean_rel or clean_rel.startswith("#"):
                    continue
                parts = [p for p in re.split(r'[\\/]+', clean_rel) if p and p != ".."]
                if len(parts) >= 2:
                    folder_part, file_part = parts[-2], parts[-1]
                    clean_rel = f"../{folder_part}/{file_part}"
                else:
                    file_part = parts[-1] if parts else clean_rel
                display_title = os.path.splitext(file_part)[0]
                f.write(f"#EXTINF:-1,{display_title}\n{clean_rel}\n")

    def append_sorted_track_to_m3u8_immediately(self, folder_name, fname):
        """Immediately splices a newly sorted track into that playlist's .m3u8 file."""
        try:
            m3u8_path = self.find_existing_m3u8_for_playlist(folder_name)
            pl_folder_path = os.path.join(self.base_dir, folder_name)
            existing_rel_lines = []
            seen = set()

            if os.path.exists(m3u8_path):
                with open(m3u8_path, "r", encoding="utf-8", errors="ignore") as f:
                    for raw_line in f:
                        s = raw_line.strip()
                        if not s or s.startswith("#"):
                            continue
                        decoded = urllib.parse.unquote(s)
                        parts = [p for p in re.split(r'[\\/]+', decoded) if p and p != ".."]
                        if not parts:
                            continue
                        f_only = parts[-1]
                        if f_only.lower() not in seen:
                            seen.add(f_only.lower())
                            existing_rel_lines.append(f"../{folder_name}/{f_only}")

            if fname.lower() in seen:
                return

            updated_lines = self.smart_splice_playlist_tracks(
                folder_name, pl_folder_path, existing_rel_lines, [fname], recluster_all=False
            )
            self.write_clean_m3u8_file(m3u8_path, updated_lines)
            self.log(f"  [M3U8 Auto-Updated] Spliced '{fname}' into '{os.path.basename(m3u8_path)}'")
        except Exception as e:
            self.log(f"  [M3U8 Immediate Update Warning] {e}")

    def get_m3u_directory(self):
        master = os.path.join(self.base_dir, "Playlist masterfiles")
        if os.path.exists(master):
            return master
        return os.path.join(self.base_dir, "playlist M3U files")

    def refresh_playlist_stats_table(self):
        if not hasattr(self, "stats_table") or not os.path.exists(self.base_dir):
            return
        audio_exts = (".mp3", ".m4a", ".flac", ".opus", ".ogg", ".wav")
        stems_map = self.get_existing_m3u8_stems_map()

        folders = [
            d for d in os.listdir(self.base_dir)
            if os.path.isdir(os.path.join(self.base_dir, d)) and d not in SYSTEM_FOLDERS
        ]

        all_keys = sorted(
            set(folders) | set(stems_map.keys()),
            key=lambda s: (s.lower(), s)
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

            m3u8_path = stems_map.get(name.strip())
            is_dump = self.is_loose_dump_folder(name, stems_map)

            m3u8_count = 0
            if not is_dump and m3u8_path and os.path.exists(m3u8_path):
                try:
                    with open(m3u8_path, "r", encoding="utf-8", errors="ignore") as pf:
                        m3u8_count = sum(1 for line in pf if line.strip() and not line.strip().startswith("#"))
                except Exception:
                    pass

            if not is_dump:
                total_disk_tracks += len(disk_files)
                total_m3u8_tracks += m3u8_count
                total_size_mb += folder_mb

            row = self.stats_table.rowCount()
            self.stats_table.insertRow(row)

            item_name = QTableWidgetItem(name)
            item_disk = QTableWidgetItem(str(len(disk_files)))
            item_m3u = QTableWidgetItem("Dump / Loose Folder" if is_dump else (str(m3u8_count) if m3u8_path else "No .m3u8"))
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
        cache_p = os.path.join(self.get_discard_dir(), "_metadata_cache.json")
        if not getattr(self, "metadata_cache", None) and os.path.exists(cache_p):
            try:
                with open(cache_p, "r", encoding="utf-8") as f:
                    self.metadata_cache = json.load(f)
            except Exception:
                self.metadata_cache = {}
        elif not hasattr(self, "metadata_cache"):
            self.metadata_cache = {}

    def save_metadata_cache(self):
        if not hasattr(self, "metadata_cache"):
            return
        cache_p = os.path.join(self.get_discard_dir(), "_metadata_cache.json")
        try:
            with open(cache_p, "w", encoding="utf-8") as f:
                json.dump(self.metadata_cache, f, ensure_ascii=False)
        except Exception:
            pass

    def extract_full_track_metadata(self, filepath):
        """
        Extracts and caches full metadata for any audio file:
        Unifies '&' and 'and', strips leading 'the', strips artist words from core_title,
        and falls back to ffprobe if mutagen is unavailable so duration is never 0.0.
        """
        if not os.path.exists(filepath):
            return {
                "title": "", "artist": "", "album": "", "genre": "",
                "duration": 0.0, "duration_str": "--:--", "bitrate_kbps": 0, "cover": "",
                "clean_title": "", "core_title": "", "norm_artist": "", "norm_album": "", "norm_genre": ""
            }
        self.load_metadata_cache()
        try:
            mtime = int(os.path.getmtime(filepath))
            fsize = os.path.getsize(filepath)
        except Exception:
            mtime = 0
            fsize = 0
        cache_key = f"v32::{filepath}::{mtime}"
        if cache_key in self.metadata_cache:
            return self.metadata_cache[cache_key]

        fname = os.path.basename(filepath)
        fname_stem = os.path.splitext(fname)[0]
        title = ""
        artist = ""
        album = ""
        genre = ""
        duration = 0.0
        bitrate_kbps = 0
        cover_hash = ""

        try:
            import mutagen
            audio = mutagen.File(filepath)
            if audio:
                if getattr(audio, "info", None):
                    if getattr(audio.info, "length", 0):
                        duration = float(audio.info.length)
                    if getattr(audio.info, "bitrate", 0):
                        bitrate_kbps = int(round(float(audio.info.bitrate) / 1000.0))
                tags = audio.tags
                if tags:
                    for k in ("TIT2", "©nam", "title", "TITLE"):
                        if k in tags and str(tags[k]).strip():
                            title = str(tags[k][0] if isinstance(tags[k], list) else tags[k]).strip()
                            break
                    for k in ("TPE1", "TPE2", "©ART", "artist", "ARTIST", "Author"):
                        if k in tags and str(tags[k]).strip():
                            artist = str(tags[k][0] if isinstance(tags[k], list) else tags[k]).strip()
                            break
                    for k in ("TALB", "©alb", "album", "ALBUM"):
                        if k in tags and str(tags[k]).strip():
                            album = str(tags[k][0] if isinstance(tags[k], list) else tags[k]).strip()
                            break
                    for k in ("TCON", "©gen", "genre", "GENRE"):
                        if k in tags and str(tags[k]).strip():
                            genre = str(tags[k][0] if isinstance(tags[k], list) else tags[k]).strip()
                            break
                    for k in tags.keys():
                        if k.startswith("APIC") or k == "covr":
                            pic = tags[k]
                            raw_bytes = getattr(pic, "data", None) or (bytes(pic[0]) if isinstance(pic, list) and pic else None)
                            if raw_bytes:
                                cover_hash = hashlib.md5(raw_bytes[:4096]).hexdigest()[:12]
                                break
        except Exception:
            pass

        # Fallback to ffprobe if duration is still 0.0 (cached permanently so it only runs once per file)
        if duration <= 0.0:
            try:
                res = subprocess.run(
                    [get_bin("ffprobe"), "-v", "quiet", "-print_format", "json", "-show_format", filepath],
                    capture_output=True, text=True, timeout=4
                )
                if res.returncode == 0 and res.stdout:
                    fmt = json.loads(res.stdout).get("format", {})
                    if fmt.get("duration"):
                        duration = float(fmt["duration"])
                    if fmt.get("bit_rate") and not bitrate_kbps:
                        bitrate_kbps = int(round(float(fmt["bit_rate"]) / 1000.0))
                    t_dict = fmt.get("tags", {})
                    for k, v in t_dict.items():
                        kl = k.lower()
                        if kl in ("title",) and not title:
                            title = str(v).strip()
                        elif kl in ("artist", "album_artist", "author") and not artist:
                            artist = str(v).strip()
                        elif kl == "album" and not album:
                            album = str(v).strip()
                        elif kl == "genre" and not genre:
                            genre = str(v).strip()
            except Exception:
                pass

        if not bitrate_kbps and duration > 0 and fsize > 0:
            bitrate_kbps = int(round((fsize * 8) / (duration * 1000.0)))

        # Parse "Artist - Title" from filename if tags are missing or generic
        if " - " in fname_stem:
            parts = fname_stem.split(" - ", 1)
            if not artist or artist.lower() in {"unknown", "unknown artist", "various artists", "youtube"}:
                artist = parts[0].strip()
            if not title:
                title = parts[1].strip()
        if not title:
            title = fname_stem

        # Normalize Artist: Do NOT split on '&'! Unify '&'/'+'/'and' and strip 'the'/'and' so
        # "Siouxsie & The Banshees" and "Siouxsie and the Banshees" both -> "siouxsiebanshees"
        artist_clean = re.sub(r'\s*-\s*topic$', '', artist, flags=re.IGNORECASE).strip()
        primary_artist = re.split(r'\s+(?:feat\.?|ft\.?|featuring|with)\s+|[,;/]', artist_clean.lower())[0]
        norm_artist_words = re.sub(r'[&\+]', ' and ', primary_artist)
        norm_artist_words = re.sub(r'\b(?:the|and)\b', ' ', norm_artist_words)
        norm_artist = re.sub(r'[^\w]', '', norm_artist_words)

        # Clean Title & extract pure Core Title (with artist tokens and remaster/video noise removed)
        noise_pat = (
            r'\b(?:official\s*(?:music\s*)?(?:video|audio|lyric\s*video|visualizer)|'
            r'lyrics?|hd|hq|4k|remastered(?:\s*\d{4})?|\d{4}\s*remaster(?:ed)?|remaster|'
            r'single\s*version|album\s*version|radio\s*edit|extended(?:\s*mix|\s*version)?|'
            r'original\s*mix|audio|video|explicit|clean|full\s*album|ost|soundtrack)\b'
        )
        raw_t = title.lower()
        raw_t = re.sub(r'[\(\[\{][^\)\]\}]*' + noise_pat + r'[^\)\]\}]*[\)\]\}]', ' ', raw_t, flags=re.IGNORECASE)
        raw_t = re.sub(noise_pat, ' ', raw_t, flags=re.IGNORECASE)
        raw_t = re.sub(r'^\s*\d{1,3}[\.\-\s]+', '', raw_t)

        # If title contains " - ", strip whichever side is the artist
        if " - " in raw_t and norm_artist:
            t_parts = raw_t.split(" - ")
            kept_parts = []
            for tp in t_parts:
                tp_norm = re.sub(r'[^\w]', '', re.sub(r'\b(?:the|and)\b', ' ', tp.replace('&', ' and ')))
                if tp_norm and (tp_norm == norm_artist or tp_norm in norm_artist or norm_artist in tp_norm):
                    continue
                kept_parts.append(tp)
            if kept_parts:
                raw_t = " ".join(kept_parts)

        clean_title = re.sub(r'[^\w]', '', raw_t)
        if not clean_title:
            clean_title = re.sub(r'[^\w]', '', fname_stem.lower())

        # Also create core_title by stripping norm_artist prefix/suffix if attached without " - "
        core_title = clean_title
        if norm_artist and len(norm_artist) >= 4:
            if core_title.startswith(norm_artist) and len(core_title) > len(norm_artist) + 2:
                core_title = core_title[len(norm_artist):]
            elif core_title.endswith(norm_artist) and len(core_title) > len(norm_artist) + 2:
                core_title = core_title[:-len(norm_artist)]

        norm_album = re.sub(r'[^\w]', '', album.lower())
        norm_genre = re.sub(r'[^\w]', '', genre.lower())

        if duration > 0:
            mins = int(round(duration)) // 60
            secs = int(round(duration)) % 60
            dur_str = f"{mins:02d}:{secs:02d}"
        else:
            dur_str = "--:--"

        info = {
            "title": title,
            "artist": artist_clean if artist_clean else "Unknown Artist",
            "album": album,
            "genre": genre,
            "duration": round(duration, 2),
            "duration_str": dur_str,
            "bitrate_kbps": bitrate_kbps,
            "cover": cover_hash,
            "clean_title": clean_title,
            "core_title": core_title,
            "norm_artist": norm_artist,
            "norm_album": norm_album,
            "norm_genre": norm_genre
        }
        self.metadata_cache[cache_key] = info
        return info

    def get_track_grouping_signature(self, filepath):
        info = self.extract_full_track_metadata(filepath)
        return (info.get("norm_artist", ""), info.get("norm_album", ""), info.get("cover", ""))

    def smart_splice_playlist_tracks(self, pl_name, pl_folder_path, existing_rel_lines, new_filenames, recluster_all=False):
        """Splices newly added tracks right after matching Artist+Album/Cover blocks, or Artist blocks."""
        self.load_metadata_cache()

        def resolve_disk_path(rel_line):
            clean = rel_line.replace("\\", "/").lstrip("./")
            parts = [p for p in re.split(r'[\\/]+', clean) if p and p != ".."]
            if len(parts) >= 2:
                return os.path.join(self.base_dir, parts[-2], parts[-1])
            return os.path.normpath(os.path.join(self.base_dir, clean))

        working_lines = list(existing_rel_lines)

        if recluster_all and working_lines:
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

        line_sigs = [self.get_track_grouping_signature(resolve_disk_path(l)) for l in working_lines]

        for new_f in new_filenames:
            new_rel = f"../{pl_name}/{new_f}"
            new_full = os.path.join(pl_folder_path, new_f)
            n_art, n_alb, n_cov = self.get_track_grouping_signature(new_full)

            insert_idx = None
            if n_art:
                if n_alb or n_cov:
                    for i in range(len(line_sigs) - 1, -1, -1):
                        e_art, e_alb, e_cov = line_sigs[i]
                        if e_art == n_art and ((n_alb and e_alb == n_alb) or (n_cov and e_cov == n_cov)):
                            insert_idx = i + 1
                            self.log(f"  [Smart Splice: Album Match] Inserted '{new_f}' after '{os.path.basename(working_lines[i])}' in '{pl_name}.m3u8'")
                            break
                if insert_idx is None:
                    for i in range(len(line_sigs) - 1, -1, -1):
                        e_art, e_alb, e_cov = line_sigs[i]
                        if e_art == n_art:
                            insert_idx = i + 1
                            self.log(f"  [Smart Splice: Artist Block] Inserted '{new_f}' at end of '{n_art}' block in '{pl_name}.m3u8'")
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
        try:
            m3u_dir = self.get_m3u_directory()
            backup_dir = os.path.join(self.base_dir, "_M3U_Safety_Backup")
            os.makedirs(m3u_dir, exist_ok=True)
            os.makedirs(backup_dir, exist_ok=True)

            self.tabs.setCurrentWidget(self.console)
            self.log(f"\n==> Starting Deep Consolidation & Pure .M3U8 Sync in '{os.path.basename(m3u_dir)}'...")
            QApplication.processEvents()

            audio_exts = (".mp3", ".m4a", ".flac", ".opus", ".ogg", ".wav")

            stems_map = self.get_existing_m3u8_stems_map()
            dump_folders = set()
            regular_folders = set()
            for d in os.listdir(self.base_dir):
                full_d = os.path.join(self.base_dir, d)
                if os.path.isdir(full_d) and d not in SYSTEM_FOLDERS:
                    if self.is_loose_dump_folder(d, stems_map):
                        dump_folders.add(d)
                    else:
                        regular_folders.add(d)

            exact_index = {}
            dump_file_index = {}
            dump_norm_index = {}
            regular_file_index = {}
            regular_norm_index = {}

            def norm_stem(filename):
                stem = os.path.splitext(filename)[0].lower().strip()
                cleaned = re.sub(r'[^\w]', '', stem)
                return cleaned if len(cleaned) >= 3 else stem

            for d_real in dump_folders:
                f_path = os.path.join(self.base_dir, d_real)
                for f in os.listdir(f_path):
                    if f.lower().endswith(audio_exts):
                        exact_index[(d_real, f.lower())] = (d_real, f)
                        dump_file_index[f.lower()] = (d_real, f)
                        dump_norm_index[norm_stem(f)] = (d_real, f)

            for r_real in regular_folders:
                f_path = os.path.join(self.base_dir, r_real)
                for f in os.listdir(f_path):
                    if f.lower().endswith(audio_exts):
                        exact_index[(r_real, f.lower())] = (r_real, f)
                        regular_file_index[f.lower()] = (r_real, f)
                        regular_norm_index[norm_stem(f)] = (r_real, f)

            existing_files = [
                f for f in os.listdir(m3u_dir)
                if f.lower().endswith((".m3u", ".m3u8", ".pls", ".xspf"))
            ]
            for pl_f in existing_files:
                shutil.copy2(os.path.join(m3u_dir, pl_f), os.path.join(backup_dir, pl_f))
            self.log(f"  [Safety Backup] Backed up {len(existing_files)} original playlist files to '_M3U_Safety_Backup/'")

            grouped_pl_files = {}
            for f in sorted(existing_files):
                base_name = unicodedata.normalize('NFC', os.path.splitext(f)[0].strip())
                ext = os.path.splitext(f)[1]
                if base_name in dump_folders or "dump" in base_name.lower():
                    continue
                grouped_pl_files.setdefault(base_name, {"display_name": base_name, "files": []})
                grouped_pl_files[base_name]["files"].append(f)

            for r_real in regular_folders:
                if r_real not in grouped_pl_files:
                    grouped_pl_files[r_real] = {"display_name": r_real, "files": []}

            dump_usage_map = {}
            parsed_m3u_lines = {}

            for pl_name, info in sorted(grouped_pl_files.items()):
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
                            decoded = urllib.parse.unquote(stripped).replace("\\", "/")
                            parts = [p for p in re.split(r'[\\/]+', decoded) if p and p != ".."]
                            if not parts:
                                continue

                            fname = parts[-1]
                            parent_folder = parts[-2] if len(parts) >= 2 else pl_name
                            f_low = fname.lower()
                            n_stem = norm_stem(fname)

                            if (parent_folder, f_low) in exact_index:
                                real_folder, real_file = exact_index[(parent_folder, f_low)]
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

                            if real_folder in dump_folders:
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

            current_regular_files = {}
            current_regular_norms = {}
            for r_real in regular_folders:
                f_path = os.path.join(self.base_dir, r_real)
                if os.path.isdir(f_path):
                    for f in os.listdir(f_path):
                        if f.lower().endswith(audio_exts):
                            current_regular_files[f.lower()] = (r_real, f)
                            current_regular_norms[norm_stem(f)] = (r_real, f)

            purged_stragglers = 0
            for d_real in dump_folders:
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

            stripped_m3u_count = 0
            for f in os.listdir(m3u_dir):
                if f.lower().endswith(".m3u") or os.path.splitext(f)[0] in dump_folders:
                    os.remove(os.path.join(m3u_dir, f))
                    stripped_m3u_count += 1

            updated_count = 0
            total_spiced_tracks = 0
            total_pl = max(1, len(parsed_m3u_lines))
            for idx, (pl_name, entries) in enumerate(sorted(parsed_m3u_lines.items()), 1):
                m3u8_path = self.find_existing_m3u8_for_playlist(pl_name)
                m3u8_filename = os.path.basename(m3u8_path)
                final_lines = []
                seen_filenames = set()

                pl_folder_path = os.path.join(self.base_dir, pl_name)
                folder_files_map = {}
                if os.path.isdir(pl_folder_path):
                    for f in os.listdir(pl_folder_path):
                        if f.lower().endswith(audio_exts):
                            folder_files_map[f.lower()] = f

                for real_folder, real_file in entries:
                    if real_file.lower() in folder_files_map:
                        actual_fname = folder_files_map[real_file.lower()]
                        effective_folder = pl_name
                    elif real_folder in dump_folders:
                        actual_fname = real_file
                        effective_folder = pl_name
                    else:
                        actual_fname = real_file
                        effective_folder = real_folder

                    f_key = actual_fname.lower()
                    if f_key not in seen_filenames:
                        seen_filenames.add(f_key)
                        final_lines.append(f"../{effective_folder}/{actual_fname}")

                new_in_folder = 0
                if os.path.isdir(pl_folder_path):
                    new_files_to_splice = []
                    for f in sorted(os.listdir(pl_folder_path)):
                        if f.lower().endswith(audio_exts):
                            if f.lower() not in seen_filenames:
                                seen_filenames.add(f.lower())
                                new_files_to_splice.append(f)
                                new_in_folder += 1
                                total_spiced_tracks += 1

                    if new_files_to_splice or (hasattr(self, "chk_recluster_existing") and self.chk_recluster_existing.isChecked()):
                        final_lines = self.smart_splice_playlist_tracks(
                            pl_name, pl_folder_path, final_lines, new_files_to_splice,
                            recluster_all=(hasattr(self, "chk_recluster_existing") and self.chk_recluster_existing.isChecked())
                        )

                self.write_clean_m3u8_file(m3u8_path, final_lines)

                pct = int((idx / total_pl) * 100)
                self.progress_bar.setRange(0, 100)
                self.progress_bar.setValue(pct)
                self.progress_bar.setFormat(f"WRITING UTF-8 .M3U8 PLAYLISTS: {idx}/{total_pl} ({pct}%)")
                QApplication.processEvents()

                self.log(
                    f"  [M3U8 Synced] {m3u8_filename} -> {len(final_lines)} tracks "
                    f"({new_in_folder} newly spliced from folder)"
                )
                updated_count += 1

            self.refresh_playlist_stats_table()
            self.telemetry_label.setText(
                f"TELEMETRY // SYNC COMPLETE: {updated_count} .m3u8 Playlists | +{total_spiced_tracks} New Tracks Spliced"
            )
            self.log(
                f"\n==> Completed!\n"
                f"    • Spliced {total_spiced_tracks} newly sorted folder tracks into .m3u8 playlists\n"
                f"    • Relocated {consolidated_count} dump tracks into playlist folders\n"
                f"    • Purged {purged_stragglers} redundant dump stragglers\n"
                f"    • Synced {updated_count} clean UTF-8 .m3u8 playlists.\n"
            )
        except Exception as e:
            import traceback
            self.log(f"\n[CONSOLIDATE ERROR] {e}\n{traceback.format_exc()}")

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
            "--maximum-difference", "4.5",
            "-f", self.report_path
        ]
        self.run_cmd(get_bin("czkawka_cli"), args, mode="czkawka", on_finish=self.parse_and_quarantine_dupes)

    def parse_and_quarantine_dupes(self):
        self.log("\n==> Running Multi-Layer Audit: (1) 25s Acoustic Waveform, (2) Metadata/Duration/Artist/Genre, (3) Blacklist...")
        staging = os.path.abspath(os.path.join(self.base_dir, "_New_Arrivals"))
        quarantine = os.path.abspath(os.path.join(self.base_dir, "_Quarantined_Dupes"))
        os.makedirs(quarantine, exist_ok=True)

        if self.fp_worker and self.fp_worker.isRunning():
            self.fp_worker.stop()
            self.fp_worker.wait(500)

        # Configure 9-column Audit Report with "⇄ Replace Orig" and Quality Badges
        if self.audit_table.columnCount() != 9:
            self.audit_table.setColumnCount(9)
            self.audit_table.setHorizontalHeaderLabels([
                "Quarantined Dupe (_New_Arrivals)",
                "Existing Library Match",
                "Playlist Folder",
                "Match Basis & Quality Comparison",
                "Audition Dupe",
                "Audition Orig",
                "Replace Original",
                "Restore",
                "Delete"
            ])
            hdr = self.audit_table.horizontalHeader()
            hdr.setSectionResizeMode(0, QHeaderView.Stretch)
            hdr.setSectionResizeMode(1, QHeaderView.Stretch)
            hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
            hdr.setSectionResizeMode(3, QHeaderView.Stretch)
            for c_i in (4, 5, 6, 7, 8):
                hdr.setSectionResizeMode(c_i, QHeaderView.ResizeToContents)

        self.audit_table.setRowCount(0)
        quarantined_count = 0
        metadata_caught_count = 0
        blacklist_caught_count = 0

        def format_quality_badge(filepath):
            if not filepath or not os.path.exists(filepath):
                return ""
            try:
                sz_mb = os.path.getsize(filepath) / (1024 * 1024)
                meta = self.extract_full_track_metadata(filepath)
                kbps = meta.get("bitrate_kbps", 0)
                dur_s = meta.get("duration_str", "--:--")
                if kbps > 0:
                    return f"[{kbps}kbps • {sz_mb:.1f}MB • {dur_s}]"
                return f"[{sz_mb:.1f}MB • {dur_s}]"
            except Exception:
                return ""

        def add_audit_row(fname, dest_quarantine, orig_display, folder_display, reason_display, orig_lib_path=None, is_blacklist=False):
            row = self.audit_table.rowCount()
            self.audit_table.insertRow(row)

            q_badge = format_quality_badge(dest_quarantine)
            o_badge = format_quality_badge(orig_lib_path) if orig_lib_path else ""

            it_q = QTableWidgetItem(f"{fname}  {q_badge}".strip())
            it_orig = QTableWidgetItem(f"{orig_display}  {o_badge}".strip())
            it_fold = QTableWidgetItem(folder_display)
            it_reas = QTableWidgetItem(reason_display)

            if is_blacklist:
                brush = QBrush(QColor("#ff2a54"))
                for it in (it_q, it_orig, it_fold, it_reas):
                    it.setForeground(brush)
            elif "METADATA" in reason_display or "TITLE" in reason_display or "ARTIST" in reason_display or "SPECTRAL" in reason_display:
                brush = QBrush(QColor("#ffb86c"))
                it_reas.setForeground(brush)

            self.audit_table.setItem(row, 0, it_q)
            self.audit_table.setItem(row, 1, it_orig)
            self.audit_table.setItem(row, 2, it_fold)
            self.audit_table.setItem(row, 3, it_reas)

            btn_play_dupe = QPushButton("▶ Dupe")
            set_btn_variant(btn_play_dupe, "accent")
            btn_play_dupe.clicked.connect(
                lambda _, p=dest_quarantine, b=btn_play_dupe: self.play_from_table(
                    self.audit_table, b, p, "[QUARANTINED DUPE]"
                )
            )
            self.audit_table.setCellWidget(row, 4, btn_play_dupe)

            if orig_lib_path and os.path.exists(orig_lib_path):
                btn_play_orig = QPushButton("▶ Orig")
                set_btn_variant(btn_play_orig, "accent")
                btn_play_orig.clicked.connect(
                    lambda _, p=orig_lib_path, b=btn_play_orig: self.play_from_table(
                        self.audit_table, b, p, f"[LIBRARY: {folder_display}]"
                    )
                )
                self.audit_table.setCellWidget(row, 5, btn_play_orig)

                btn_replace = QPushButton("⇄ Replace Orig")
                set_btn_variant(btn_replace, "restore")
                btn_replace.setToolTip(f"Overwrite '{orig_display}' in '{folder_display}' with this new version")
                btn_replace.clicked.connect(
                    lambda _, qp=dest_quarantine, op=orig_lib_path, b=btn_replace: self.replace_original_with_quarantined(qp, op, b)
                )
                self.audit_table.setCellWidget(row, 6, btn_replace)
            else:
                lbl_deleted = QLabel("Deleted Previously")
                lbl_deleted.setAlignment(Qt.AlignCenter)
                lbl_deleted.setStyleSheet("color: #8892b0; font-style: italic;")
                self.audit_table.setCellWidget(row, 5, lbl_deleted)

                lbl_na = QLabel("—")
                lbl_na.setAlignment(Qt.AlignCenter)
                self.audit_table.setCellWidget(row, 6, lbl_na)

            btn_restore = QPushButton("↩ Restore")
            set_btn_variant(btn_restore, "restore")
            btn_restore.clicked.connect(
                lambda _, q_path=dest_quarantine, btn=btn_restore: self.restore_single_quarantined(q_path, btn)
            )
            self.audit_table.setCellWidget(row, 7, btn_restore)

            btn_del_one = QPushButton("✖ Delete")
            set_btn_variant(btn_del_one, "danger")
            btn_del_one.clicked.connect(
                lambda _, q_path=dest_quarantine, btn=btn_del_one: self.delete_single_quarantined(q_path, btn)
            )
            self.audit_table.setCellWidget(row, 8, btn_del_one)

        # --- PART A: Parse czkawka_cli 25-Second Acoustic Waveform Matches (allowing apostrophes in paths!) ---
        if os.path.exists(self.report_path):
            with open(self.report_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            blocks = re.split(r'\n\s*\n|----+', content)
            for block in blocks:
                paths = re.findall(r'((?:[a-zA-Z]:[\\/]|/)[^\n"]+\.(?:mp3|m4a|flac|opus|ogg|wav))', block, re.IGNORECASE)
                if len(paths) < 2:
                    continue

                staging_files = [p for p in paths if os.path.abspath(p).startswith(staging)]
                library_files = [p for p in paths if not os.path.abspath(p).startswith(staging)]

                if staging_files and library_files:
                    orig_lib_path = library_files[0]
                    lib_folder = os.path.basename(os.path.dirname(orig_lib_path))

                    for st_file in staging_files:
                        if not os.path.exists(st_file):
                            continue
                        fname = os.path.basename(st_file)
                        dest_quarantine = os.path.join(quarantine, fname)
                        shutil.move(st_file, dest_quarantine)
                        quarantined_count += 1
                        add_audit_row(
                            fname, dest_quarantine,
                            os.path.basename(orig_lib_path), lib_folder,
                            "🔊 25s WAVEFORM MATCH",
                            orig_lib_path=orig_lib_path
                        )

        # --- PART B: Deep Metadata + Duration + 25s Coarse Spectral Cross-Reference Against Library ---
        audio_exts = (".mp3", ".m4a", ".flac", ".opus", ".ogg", ".wav")
        if os.path.exists(staging):
            lib_index = self.build_library_metadata_index()
            remaining = sorted([f for f in os.listdir(staging) if f.lower().endswith(audio_exts)])
            total_rem = max(1, len(remaining))

            for idx_f, fname in enumerate(remaining, 1):
                if idx_f % 2 == 0:
                    pct = int((idx_f / total_rem) * 100)
                    self.progress_bar.setFormat(f"CROSS-REFERENCING METADATA & 25s SPECTRAL FINGERPRINTS: {idx_f}/{total_rem} ({pct}%)")
                    QApplication.processEvents()

                st_file = os.path.join(staging, fname)
                if not os.path.exists(st_file):
                    continue

                # 1. Check Blacklist first
                discard_match = self.check_if_discarded(st_file, compute_if_missing=True)
                if discard_match:
                    dest_quarantine = os.path.join(quarantine, fname)
                    shutil.move(st_file, dest_quarantine)
                    blacklist_caught_count += 1
                    orig_discard_name = discard_match.get("filename", "Unknown")
                    discard_reason = discard_match.get("reason", "Previously discarded")
                    discard_date = discard_match.get("timestamp", "")
                    self.log(f"  [BLACKLIST MATCH] '{fname}' matched '{orig_discard_name}' -> Quarantined")
                    add_audit_row(
                        fname, dest_quarantine,
                        f"🚫 {orig_discard_name} ({discard_date})",
                        "_Discarded_Songs (Blacklist)",
                        f"BLACKLISTED: {discard_reason}",
                        orig_lib_path=None,
                        is_blacklist=True
                    )
                    continue

                # 2. Check Library Metadata + Duration + Fuzzy Title/Artist/Genre + 25s Spectral Fallback
                st_meta = self.extract_full_track_metadata(st_file)
                st_dur = float(st_meta.get("duration", 0.0))
                matched_lib = None

                for lib_folder, lib_fname, lib_full_p, lib_meta in lib_index:
                    m_reason = self.compare_metadata_for_duplicate(st_meta, lib_meta, fname, lib_fname)
                    if m_reason:
                        matched_lib = (lib_folder, lib_fname, lib_full_p, f"🎯 {m_reason}")
                        break

                # If metadata didn't match directly, check 25s Coarse Spectral Fingerprint on any track within ±6.0s duration!
                if not matched_lib and st_dur > 0:
                    raw_st = None
                    for lib_folder, lib_fname, lib_full_p, lib_meta in lib_index:
                        lib_dur = float(lib_meta.get("duration", 0.0))
                        if lib_dur > 0 and abs(st_dur - lib_dur) <= 6.0:
                            s_art = st_meta.get("norm_artist", "")
                            l_art = lib_meta.get("norm_artist", "")
                            s_core = st_meta.get("core_title", "")
                            l_core = lib_meta.get("core_title", "")
                            same_art = bool(s_art and l_art and (s_art == l_art or s_art in l_art or l_art in s_art))
                            title_sim = difflib.SequenceMatcher(None, s_core, l_core).ratio() if (s_core and l_core) else 0.0
                            if same_art or title_sim >= 0.35 or abs(st_dur - lib_dur) <= 1.5:
                                if raw_st is None:
                                    _, _, raw_st = self.compute_fingerprint(st_file)
                                if raw_st:
                                    _, _, raw_lib = self.compute_fingerprint(lib_full_p)
                                    if raw_lib and self.raw_fingerprints_match(raw_st, raw_lib):
                                        matched_lib = (
                                            lib_folder, lib_fname, lib_full_p,
                                            f"🔊 25s SPECTRAL + DURATION ({st_meta.get('duration_str')})"
                                        )
                                        break

                if matched_lib:
                    lib_folder, lib_fname, lib_full_p, reason_str = matched_lib
                    dest_quarantine = os.path.join(quarantine, fname)
                    shutil.move(st_file, dest_quarantine)
                    metadata_caught_count += 1
                    self.log(f"  [HYBRID DUPE MATCH] '{fname}' matched '{lib_folder}/{lib_fname}' ({reason_str}) -> Quarantined")
                    add_audit_row(
                        fname, dest_quarantine,
                        lib_fname, lib_folder,
                        reason_str,
                        orig_lib_path=lib_full_p
                    )

        total_isolated = quarantined_count + metadata_caught_count + blacklist_caught_count
        if total_isolated == 0:
            self.audit_summary.setText(
                "AUDIT COMPLETE: 0 25s waveform dupes, 0 metadata/duration dupes, and 0 blacklisted tracks found!"
            )
        else:
            self.audit_summary.setText(
                f"AUDIT COMPLETE: Isolated {quarantined_count} 25s waveform dupes + {metadata_caught_count} metadata/spectral dupes + "
                f"{blacklist_caught_count} blacklisted tracks. Use '⇄ Replace Orig' if the new version is higher quality."
            )

        self.refresh_staging_table()
        self.tabs.setCurrentWidget(self.audit_tab)

    def replace_original_with_quarantined(self, q_path, orig_lib_path, btn_widget):
        """
        Replaces the existing library track with the higher-quality duplicate from _Quarantined_Dupes.
        Preserves or updates .m3u8 references automatically so playlists stay 100% intact.
        """
        if not os.path.exists(q_path):
            QMessageBox.warning(self, "File Missing", f"Quarantined file no longer exists:\n{q_path}")
            return
        if not os.path.exists(orig_lib_path):
            QMessageBox.warning(self, "Original Missing", f"Library target no longer exists:\n{orig_lib_path}")
            return

        q_fname = os.path.basename(q_path)
        orig_fname = os.path.basename(orig_lib_path)
        lib_dir = os.path.dirname(orig_lib_path)
        lib_folder_name = os.path.basename(lib_dir)

        if self.player.source() in (QUrl.fromLocalFile(q_path), QUrl.fromLocalFile(orig_lib_path)):
            self.player.stop()

        q_ext = os.path.splitext(q_fname)[1].lower()
        orig_ext = os.path.splitext(orig_fname)[1].lower()

        try:
            if q_ext == orig_ext:
                # Overwrite original file path in-place so every existing .m3u8 reference works without modification
                shutil.move(q_path, orig_lib_path)
                final_dest = orig_lib_path
            else:
                # Different audio container extension: replace file and update any .m3u8 reference
                final_dest = os.path.join(lib_dir, os.path.splitext(orig_fname)[0] + q_ext)
                shutil.move(q_path, final_dest)
                if os.path.exists(orig_lib_path) and os.path.abspath(orig_lib_path) != os.path.abspath(final_dest):
                    os.remove(orig_lib_path)
                m3u8_p = self.find_existing_m3u8_for_playlist(lib_folder_name)
                if os.path.exists(m3u8_p):
                    with open(m3u8_p, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    content = content.replace(orig_fname, os.path.basename(final_dest))
                    with open(m3u8_p, "w", encoding="utf-8") as f:
                        f.write(content)

            self.log(
                f"[REPLACED ORIGINAL] Replaced '{lib_folder_name}/{orig_fname}' with new version '{q_fname}'!"
            )

            for r in range(self.audit_table.rowCount()):
                if self.audit_table.cellWidget(r, 6) == btn_widget:
                    status_item = QTableWidgetItem(f"✔ REPLACED ORIGINAL IN [{lib_folder_name}]")
                    status_item.setForeground(QBrush(QColor("#66fcf1")))
                    self.audit_table.setItem(r, 3, status_item)
                    for col_i in (4, 5, 6, 7, 8):
                        w = self.audit_table.cellWidget(r, col_i)
                        if w:
                            w.setEnabled(False)
                    break

            self.refresh_playlist_stats_table()
        except Exception as e:
            QMessageBox.critical(self, "Replace Error", f"Failed to replace original track:\n{e}")

    def restore_single_quarantined(self, q_path, btn_widget):
        staging = os.path.join(self.base_dir, "_New_Arrivals")
        os.makedirs(staging, exist_ok=True)
        fname = os.path.basename(q_path)
        dest = os.path.join(staging, fname)

        if self.player.source() == QUrl.fromLocalFile(q_path):
            self.player.stop()

        if os.path.exists(q_path):
            shutil.move(q_path, dest)
            self.log(f"[RESTORED FALSE POSITIVE] '{fname}' -> Moved back to '_New_Arrivals'")

        for r in range(self.audit_table.rowCount()):
            if self.audit_table.cellWidget(r, 7) == btn_widget or self.audit_table.cellWidget(r, 6) == btn_widget:
                status_item = QTableWidgetItem("↩ RESTORED TO _New_Arrivals")
                status_item.setForeground(QBrush(QColor("#66fcf1")))
                self.audit_table.setItem(r, 3, status_item)
                for col_i in range(4, self.audit_table.columnCount()):
                    w = self.audit_table.cellWidget(r, col_i)
                    if w:
                        w.setEnabled(False)
                break
        self.refresh_staging_table()

    def delete_single_quarantined(self, q_path, btn_widget):
        fname = os.path.basename(q_path)
        if self.player.source() == QUrl.fromLocalFile(q_path):
            self.player.stop()

        if os.path.exists(q_path):
            os.remove(q_path)
            self.log(f"[DELETED QUARANTINED DUPE] '{fname}' permanently removed.")

        for r in range(self.audit_table.rowCount()):
            if self.audit_table.cellWidget(r, 8) == btn_widget or self.audit_table.cellWidget(r, 7) == btn_widget:
                status_item = QTableWidgetItem("✖ DELETED PERMANENTLY")
                status_item.setForeground(QBrush(QColor("#ff2a54")))
                self.audit_table.setItem(r, 3, status_item)
                for col_i in range(4, self.audit_table.columnCount()):
                    w = self.audit_table.cellWidget(r, col_i)
                    if w:
                        w.setEnabled(False)
                break

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
