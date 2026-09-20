from pathlib import Path
from PySide6.QtCore import QSettings, Qt, QUrl, QTimer, QThread, QObject, Signal, Slot
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QPushButton,
    QTextEdit,
    QLineEdit,
    QFileDialog,
    QVBoxLayout,
    QHBoxLayout,
    QComboBox,
    QCheckBox,
    QDoubleSpinBox,
    QDialog,
    QInputDialog,
    QListWidget,
    QListWidgetItem,
    QGroupBox,
    QFormLayout,
    QAbstractItemView,
    QSizePolicy,
    QSplitter,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QSlider,
    QFrame,
    QMessageBox,
    QProgressBar,
    QProgressDialog,
)

DEFAULT_LEAD_IN = 0.345
AUDIO_EXTENSIONS = {
    ".wav",
    ".mp3",
    ".flac",
    ".m4a",
    ".aac",
    ".ogg",
    ".opus",
}
TEXT_EXTENSIONS = {".txt"}
LRC_EXTENSIONS = {".lrc"}
LANGUAGE_ITEMS = [
    ("Japanese (jpn)", "jpn"),
    ("English (eng)", "eng"),
    ("Korean (kor)", "kor"),
    ("Chinese Mandarin (cmn)", "cmn"),
    ("Spanish (spa)", "spa"),
]
# Flat English strings (UI localization removed; English only).
STRINGS = {
        "language": "Lyrics language",
        "lead": "Lead-in seconds",
        "line": "Line LRC",
        "chars": "Character timing LRC",
        "sections": "Keep blank lines as sections",
        "generate": "Generate LRC",
        "progress": "Progress",
        "log": "Log",
        "audio_list": "Audio files",
        "lyrics_list": "Lyrics files",
        "add_files": "Add files",
        "remove": "Remove selected",
        "clear_list": "Clear list",
        "pairing": "Pairing rule",
        "pair_by_name": "Match by file name",
        "pair_by_order": "Match by order",
        "output_dir": "Output directory",
        "preview": "Preview",
        "choose_output_dir": "Browse",
        "batch_hint": "Select multiple audio and lyrics files, then pair them by name or order.",
        "batch_lyrics": "Lyrics for selected audio",
        "save_pasted": "Save pasted lyrics",
        "clear_pasted": "Clear pasted lyrics",
        "batch_lyrics_placeholder": "Paste lyrics for the selected audio item.",
        "existing_lrc_found": "Existing synced LRC found:",
        "export_existing": "Export existing LRC as separate file",
        "skip_and_continue": "Skip and continue",
        "batch_existing_lrc_count": "{n} audio files already have LRC. Export them separately?",
        "check_lrclib": "Check LRCLIB before generating",
        "upload_lrclib": "Upload to LRCLIB after generating",
        "embed_synced": "Embed synced lyrics into audio file",
        "open_viewer": "Lyric Viewer / Editor",
        "viewer_title": "Lyric Viewer & Editor",
        "play": "Play",
        "pause": "Pause",
        "stop": "Stop",
        "time_col": "Time",
        "lyric_col": "Lyric",
        "add_row": "Add row",
        "remove_row": "Remove row",
        "save_lrc": "Save LRC",
        "load_lrc": "Load LRC",
        "lrclib_found": "LRCLIB match found for {name}",
        "lrclib_not_found": "No LRCLIB match for {name}",
        "lrclib_use_existing": "Use LRCLIB lyrics instead of generating?",
        "download": "Download",
        "generate_anyway": "Generate anyway",
        "skip": "Skip",
        "device": "Device",
        "embed_audio": "Embed to Audio",
        "fix_times": "Fix Timestamps",
        "shift_times": "Shift Times",
}


def code_from_label(label: str) -> str:
    if "(" in label and ")" in label:
        return label.rsplit("(", 1)[1].split(")", 1)[0].strip()
    return "jpn"


def parse_lrc_time(text: str) -> float | None:
    """Parse [mm:ss.xx] or mm:ss.xx to seconds. Returns None if invalid."""
    t = text.strip().strip("[]")
    try:
        if ":" in t:
            m, s = t.split(":", 1)
            return int(m) * 60 + float(s)
        return float(t)
    except Exception:
        return None


def format_lrc_time(seconds: float) -> str:
    if seconds is None or seconds < 0:
        seconds = 0.0
    m = int(seconds // 60)
    s = seconds % 60
    return f"[{m:02d}:{s:05.2f}]"


def parse_time_offset(text: str) -> float | None:
    """Parse a signed offset like +00:02.11 or -00:03:45 to seconds.

    Accepts [+/-]SS.cc, [+/-]MM:SS.cc and [+/-]HH:MM:SS.cc, with optional
    spaces around the sign. The sign is required. Returns None if invalid.
    """
    t = (text or "").strip()
    if not t or t[0] not in "+-":
        return None
    sign = -1.0 if t[0] == "-" else 1.0
    t = t[1:].strip().strip("[]")
    if not t:
        return None
    try:
        parts = t.split(":")
        if len(parts) == 1:
            total = float(parts[0])
        elif len(parts) == 2:
            total = int(parts[0]) * 60 + float(parts[1])
        elif len(parts) == 3:
            total = int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        else:
            return None
    except Exception:
        return None
    if total < 0:
        return None
    return sign * total


# --------------------------------------------------------
# Dark grey theme (dark mode): window/base greys + light text.
# Applied app-wide via Fusion style + QPalette + stylesheet so the
# UI looks the same regardless of the OS light/dark setting
# (stylesheets override the OS theme reliably, palettes alone don't).
# --------------------------------------------------------
DARK_GREY = {
    "window": "#2b2b2b",
    "base": "#323232",        # inputs / lists / tables
    "alternate": "#2b2b2b",
    "button": "#3d3d3d",
    "button_hover": "#4a4a4a",
    "border": "#555555",
    "header": "#3a3a3a",
    "text": "#e6e6e6",
    "dim_text": "#aaaaaa",
    "disabled_text": "#777777",
    "highlight": "#3399FF",
    "highlight_text": "#ffffff",
}

APP_DARK_STYLESHEET = """
QWidget {
    background-color: #2b2b2b;
    color: #e6e6e6;
}
QMainWindow, QDialog {
    background-color: #2b2b2b;
}
QLabel {
    color: #e6e6e6;
    background-color: transparent;
}
QTextEdit, QLineEdit, QListWidget, QTableWidget, QPlainTextEdit {
    background-color: #323232;
    color: #e6e6e6;
    border: 1px solid #555555;
    selection-background-color: #3399FF;
    selection-color: #ffffff;
}
QTableWidget::item:selected {
    background-color: #3399FF;
    color: #ffffff;
}
QHeaderView::section {
    background-color: #3a3a3a;
    color: #e6e6e6;
    padding: 4px;
    border: 1px solid #555555;
}
QTableCornerButton::section {
    background-color: #3a3a3a;
    border: 1px solid #555555;
}
QPushButton, QToolButton {
    background-color: #3d3d3d;
    color: #e6e6e6;
    border: 1px solid #555555;
    border-radius: 4px;
    padding: 5px 12px;
}
QPushButton:hover, QToolButton:hover {
    background-color: #4a4a4a;
}
QPushButton:pressed, QToolButton:pressed {
    background-color: #333333;
}
QPushButton:disabled, QToolButton:disabled {
    background-color: #2b2b2b;
    color: #777777;
}
QComboBox, QDoubleSpinBox, QSpinBox {
    background-color: #323232;
    color: #e6e6e6;
    border: 1px solid #555555;
    border-radius: 3px;
    padding: 3px 6px;
}
QComboBox QAbstractItemView {
    background-color: #323232;
    color: #e6e6e6;
    selection-background-color: #3399FF;
    selection-color: #ffffff;
}
QCheckBox, QRadioButton {
    color: #e6e6e6;
    background-color: transparent;
}
QGroupBox {
    color: #e6e6e6;
    border: 1px solid #555555;
    border-radius: 4px;
    margin-top: 12px;
    padding-top: 6px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
    color: #e6e6e6;
}
QProgressBar {
    background-color: #323232;
    color: #e6e6e6;
    border: 1px solid #555555;
    border-radius: 3px;
    text-align: center;
}
QProgressBar::chunk {
    background-color: #3399FF;
}
QSlider::groove:horizontal {
    background: #3d3d3d;
    height: 6px;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #888888;
    width: 14px;
    margin: -5px 0;
    border-radius: 7px;
}
QScrollArea {
    background-color: #2b2b2b;
    border: none;
}
QSplitter::handle {
    background-color: #3d3d3d;
}
QScrollBar:vertical, QScrollBar:horizontal {
    background: #2b2b2b;
    border: none;
}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background: #555555;
    border-radius: 4px;
    min-height: 20px;
    min-width: 20px;
}
QToolTip {
    background-color: #2b2b2b;
    color: #e6e6e6;
    border: 1px solid #555555;
}
"""


def apply_dark_grey_theme(app) -> None:
    """Apply the dark grey (dark mode) theme to the whole application."""
    from PySide6.QtWidgets import QStyleFactory
    from PySide6.QtGui import QPalette, QColor

    fusion = QStyleFactory.create("Fusion")
    if fusion:
        app.setStyle(fusion)
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(DARK_GREY["window"]))
    pal.setColor(QPalette.WindowText, QColor(DARK_GREY["text"]))
    pal.setColor(QPalette.Base, QColor(DARK_GREY["base"]))
    pal.setColor(QPalette.AlternateBase, QColor(DARK_GREY["alternate"]))
    pal.setColor(QPalette.Text, QColor(DARK_GREY["text"]))
    pal.setColor(QPalette.Button, QColor(DARK_GREY["button"]))
    pal.setColor(QPalette.ButtonText, QColor(DARK_GREY["text"]))
    pal.setColor(QPalette.Highlight, QColor(DARK_GREY["highlight"]))
    pal.setColor(QPalette.HighlightedText, QColor(DARK_GREY["highlight_text"]))
    pal.setColor(QPalette.BrightText, QColor("#ffffff"))
    pal.setColor(QPalette.ToolTipBase, QColor(DARK_GREY["window"]))
    pal.setColor(QPalette.ToolTipText, QColor(DARK_GREY["text"]))
    pal.setColor(QPalette.PlaceholderText, QColor(DARK_GREY["dim_text"]))
    pal.setColor(QPalette.Disabled, QPalette.WindowText, QColor(DARK_GREY["disabled_text"]))
    pal.setColor(QPalette.Disabled, QPalette.Text, QColor(DARK_GREY["disabled_text"]))
    pal.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(DARK_GREY["disabled_text"]))
    app.setPalette(pal)
    app.setStyleSheet(APP_DARK_STYLESHEET)


class DropLineEdit(QLineEdit):
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            self.setText(urls[0].toLocalFile())


# --------------------------------------------------------
# Lyric Viewer Dialog (timetable + playback synced timeline, editable)
# --------------------------------------------------------
class LyricViewerDialog(QDialog):
    def __init__(self, parent=None, audio_path: str | None = None, lrc_path: str | None = None, lines: list[dict] | None = None):
        super().__init__(parent)
        self.setWindowTitle(parent.text("viewer_title") if parent and hasattr(parent, "text") else "Lyric Viewer")
        self.resize(800, 520)
        self.setMinimumSize(560, 400)
        self.audio_path = audio_path
        self.lrc_path = lrc_path
        self._player = None
        self._audio_output = None
        self._timer = QTimer(self)
        self._timer.setInterval(90)
        self._timer.timeout.connect(self._on_tick)
        self._duration_ms = 0
        self._is_seeking = False

        # try to init QMediaPlayer
        try:
            from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
            self._player = QMediaPlayer(self)
            self._audio_output = QAudioOutput(self)
            self._audio_output.setVolume(0.3)  # default 30% so not too loud
            self._player.setAudioOutput(self._audio_output)
            self._player.durationChanged.connect(self._on_duration_changed)
            self._player.positionChanged.connect(self._on_position_changed)
            self._player.mediaStatusChanged.connect(lambda s: None)
        except Exception as e:
            print(f"QtMultimedia not available: {e}")
            self._player = None
            self._audio_output = None

        self.setAcceptDrops(True)
        # Dark grey theme is applied app-wide (see apply_dark_grey_theme);
        # no per-dialog light overrides here so dark mode stays consistent.

        outer = QVBoxLayout(self)

        # Drop hint
        self.drop_hint = QLabel("Drag & drop audio / .lrc / .txt here to load")
        self.drop_hint.setStyleSheet("font-size: 11px; color: #aaaaaa; font-style: italic;")
        self.drop_hint.setAlignment(Qt.AlignCenter)
        outer.addWidget(self.drop_hint)

        # Top row: audio / lrc path display + load buttons
        top = QHBoxLayout()
        self.audio_label = QLabel(audio_path or "")
        self.audio_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.audio_label.setStyleSheet("font-size: 11px; color: #aaaaaa;")
        top.addWidget(self.audio_label, 1)
        self.btn_load_audio = QPushButton("Audio…")
        self.btn_load_audio.clicked.connect(self._pick_audio)
        top.addWidget(self.btn_load_audio)
        self.btn_load_lrc = QPushButton(parent.text("load_lrc") if parent and hasattr(parent, "text") else "Load LRC")
        self.btn_load_lrc.clicked.connect(self._pick_lrc)
        top.addWidget(self.btn_load_lrc)
        outer.addLayout(top)

        # Playback controls
        ctrl = QHBoxLayout()
        self.btn_play = QPushButton(parent.text("play") if parent and hasattr(parent, "text") else "Play")
        self.btn_play.clicked.connect(self.toggle_play)
        ctrl.addWidget(self.btn_play)
        self.btn_stop = QPushButton(parent.text("stop") if parent and hasattr(parent, "text") else "Stop")
        self.btn_stop.clicked.connect(self.stop)
        ctrl.addWidget(self.btn_stop)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 1000)
        self.slider.sliderPressed.connect(lambda: setattr(self, "_is_seeking", True))
        self.slider.sliderReleased.connect(self._seek_from_slider)
        ctrl.addWidget(self.slider, 1)
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setMinimumWidth(110)
        ctrl.addWidget(self.time_label)
        # Volume (default 30%)
        self.vol_label = QLabel("Vol")
        self.vol_label.setStyleSheet("font-size: 11px; color: #e6e6e6;")
        ctrl.addWidget(self.vol_label)
        self.vol_slider = QSlider(Qt.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(30)
        self.vol_slider.setFixedWidth(90)
        self.vol_slider.setToolTip("Volume")
        self.vol_slider.valueChanged.connect(self._on_volume_changed)
        ctrl.addWidget(self.vol_slider)
        self.vol_value_label = QLabel("30%")
        self.vol_value_label.setMinimumWidth(36)
        self.vol_value_label.setStyleSheet("font-size: 11px; color: #e6e6e6;")
        ctrl.addWidget(self.vol_value_label)
        outer.addLayout(ctrl)

        # Timeline / Table: Time | Lyric (standard LRC format, dark mode theme)
        self.table = QTableWidget(0, 2)
        _t = lambda key, fallback: parent.text(key) if parent and hasattr(parent, "text") else fallback
        self.table.setHorizontalHeaderLabels([_t("time_col", "Time"), _t("lyric_col", "Lyric")])
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Fixed)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setColumnWidth(0, 110)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed | QAbstractItemView.AnyKeyPressed)
        self.table.setAlternatingRowColors(False)
        self.table.setToolTip("Red row = timestamp out of order (use Fix Timestamps)")
        # Dark grey (dark mode) table: matches app-wide DARK_GREY theme.
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #323232;
                color: #e6e6e6;
                gridline-color: #555555;
                selection-background-color: #3399FF;
                selection-color: white;
            }
            QTableWidget::item:selected {
                background-color: #3399FF;
                color: white;
            }
            QHeaderView::section {
                background-color: #3a3a3a;
                color: #e6e6e6;
                padding: 4px;
                border: 1px solid #555555;
            }
            QTableCornerButton::section {
                background-color: #3a3a3a;
                border: 1px solid #555555;
            }
        """)
        # Dark Fusion palette for the dialog/table/viewport (consistent with app theme)
        try:
            from PySide6.QtWidgets import QStyleFactory
            from PySide6.QtGui import QPalette, QColor
            fusion = QStyleFactory.create("Fusion")
            if fusion:
                self.setStyle(fusion)
                self.table.setStyle(fusion)
                self.table.viewport().setStyle(fusion)
                hdr.setStyle(fusion)
            pal = QPalette()
            pal.setColor(QPalette.Window, QColor("#2b2b2b"))
            pal.setColor(QPalette.Base, QColor("#323232"))
            pal.setColor(QPalette.AlternateBase, QColor("#2b2b2b"))
            pal.setColor(QPalette.Text, QColor("#e6e6e6"))
            pal.setColor(QPalette.WindowText, QColor("#e6e6e6"))
            pal.setColor(QPalette.Button, QColor("#3d3d3d"))
            pal.setColor(QPalette.ButtonText, QColor("#e6e6e6"))
            pal.setColor(QPalette.Highlight, QColor("#3399FF"))
            pal.setColor(QPalette.HighlightedText, QColor("white"))
            pal.setColor(QPalette.BrightText, QColor("#ffffff"))
            self.setPalette(pal)
            self.table.setPalette(pal)
            self.table.viewport().setAutoFillBackground(True)
            vp = QPalette(pal)
            vp.setColor(QPalette.Base, QColor("#323232"))
            vp.setColor(QPalette.Window, QColor("#323232"))
            vp.setColor(QPalette.Text, QColor("#e6e6e6"))
            vp.setColor(QPalette.WindowText, QColor("#e6e6e6"))
            self.table.viewport().setPalette(vp)
            self.table.viewport().setStyleSheet("* { background-color: #323232; color: #e6e6e6; }")
        except Exception as e:
            print(f"palette fix failed: {e}")
            pass
        self.table.itemSelectionChanged.connect(self._on_table_select)
        self.table.itemClicked.connect(self._on_item_clicked)
        self._invalid_rows: set[int] = set()
        self.table.itemChanged.connect(self._on_table_time_edited)
        # Double-click edits, single-click jumps - keep edit on double click only
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        outer.addWidget(self.table, 1)

        # Bottom row: add/remove/save
        bottom = QHBoxLayout()
        self.btn_add = QPushButton(parent.text("add_row") if parent and hasattr(parent, "text") else "Add row")
        self.btn_add.clicked.connect(self.add_row)
        bottom.addWidget(self.btn_add)
        self.btn_remove = QPushButton(parent.text("remove_row") if parent and hasattr(parent, "text") else "Remove row")
        self.btn_remove.clicked.connect(self.remove_selected_rows)
        bottom.addWidget(self.btn_remove)
        self.btn_fix = QPushButton(parent.text("fix_times") if parent and hasattr(parent, "text") else "Fix Timestamps")
        self.btn_fix.setToolTip("Set out-of-order (red) timestamps to just after the line above")
        self.btn_fix.clicked.connect(self.fix_timestamps)
        bottom.addWidget(self.btn_fix)
        self.btn_shift = QPushButton(parent.text("shift_times") if parent and hasattr(parent, "text") else "Shift Times")
        self.btn_shift.setToolTip("Add/subtract time on all selected rows (e.g. +00:02.11 or -00:03.45)")
        self.btn_shift.clicked.connect(self._on_shift_button)
        bottom.addWidget(self.btn_shift)
        bottom.addStretch()
        self.btn_publish = QPushButton("Publish to LRCLIB")
        self.btn_publish.setToolTip("Publish verified lyrics to LRCLIB (manual after checking timings)")
        self.btn_publish.clicked.connect(self.publish_to_lrclib)
        bottom.addWidget(self.btn_publish)
        self.btn_embed = QPushButton(parent.text("embed_audio") if parent and hasattr(parent, "text") else "Embed to Audio")
        self.btn_embed.setToolTip("Embed the current lyrics into the loaded audio file")
        self.btn_embed.clicked.connect(self.embed_to_audio)
        bottom.addWidget(self.btn_embed)
        self.btn_save = QPushButton(parent.text("save_lrc") if parent and hasattr(parent, "text") else "Save LRC")
        self.btn_save.clicked.connect(self.save_lrc)
        bottom.addWidget(self.btn_save)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        bottom.addWidget(close_btn)
        outer.addLayout(bottom)

        # load initial data
        if lines is not None:
            self.load_lines(lines)
        elif lrc_path and Path(lrc_path).exists():
            self.load_lrc_file(lrc_path)
        if audio_path and Path(audio_path).exists():
            self.load_audio(audio_path)
        # Auto-load fallback (txt / embedded) if still empty
        if self.table.rowCount() == 0 and audio_path and Path(audio_path).exists():
            self._try_auto_load_for_audio(audio_path)

    # --- LRC parsing ---
    def load_lrc_file(self, path: str):
        self.lrc_path = path
        try:
            text = Path(path).read_text(encoding="utf-8-sig")
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))
            return
        parsed = self._parse_lrc_text(text)
        self.load_lines(parsed)

    def _parse_lrc_text(self, text: str) -> list[dict]:
        import re
        lines = []
        for raw in text.splitlines():
            raw = raw.strip()
            if not raw:
                continue
            # match one or more timestamps
            m = re.match(r"^((?:\[\d+:\d+(?:\.\d+)?\])+)(.*)$", raw)
            if m:
                ts_block, lyric = m.groups()
                tss = re.findall(r"\[(\d+:\d+(?:\.\d+)?)\]", ts_block)
                for ts in tss:
                    sec = parse_lrc_time(ts)
                    if sec is not None:
                        lines.append({"start": sec, "lyric": lyric.strip()})
            else:
                # plain lyric without timestamp -> append with last time + 1s estimate
                if lines:
                    lines.append({"start": lines[-1]["start"] + 1.0, "lyric": raw})
                else:
                    lines.append({"start": 0.0, "lyric": raw})
        return lines

    def load_lines(self, lines: list[dict]):
        from PySide6.QtGui import QBrush, QColor
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for item in lines:
            row = self.table.rowCount()
            self.table.insertRow(row)
            t_item = QTableWidgetItem(format_lrc_time(float(item.get("start", 0))))
            t_item.setTextAlignment(Qt.AlignCenter)
            t_item.setForeground(QBrush(QColor("#e6e6e6")))
            # Transparent so the table's dark grey (#323232) shows, not white
            self.table.setItem(row, 0, t_item)
            l_item = QTableWidgetItem(str(item.get("lyric", "")))
            l_item.setForeground(QBrush(QColor("#e6e6e6")))
            self.table.setItem(row, 1, l_item)
        self.table.blockSignals(False)
        self._refresh_row_marking()

    def collect_lines(self) -> list[dict]:
        out = []
        for r in range(self.table.rowCount()):
            t_item = self.table.item(r, 0)
            l_item = self.table.item(r, 1)
            t = parse_lrc_time(t_item.text() if t_item else "0:00") if t_item else 0.0
            if t is None:
                t = 0.0
            lyric = l_item.text() if l_item else ""
            out.append({"start": t, "lyric": lyric})
        return out

    # --- audio ---
    def load_audio(self, path: str):
        self.audio_path = path
        self.audio_label.setText(path)
        if self._player is not None:
            try:
                self._player.setSource(QUrl.fromLocalFile(path))
            except Exception as e:
                print(f"load_audio error: {e}")

    def _pick_audio(self):
        f, _ = QFileDialog.getOpenFileName(self, "Audio", "", "Audio (*.wav *.mp3 *.flac *.m4a *.aac *.ogg *.opus)")
        if f:
            self.load_audio(f)

    def _pick_lrc(self):
        f, _ = QFileDialog.getOpenFileName(self, "LRC", "", "LRC (*.lrc)")
        if f:
            self.load_lrc_file(f)

    # --- playback ---
    def toggle_play(self):
        if self._player is None:
            QMessageBox.information(self, "Info", "Audio playback not available (QtMultimedia missing). Timeline editing still works.")
            return
        if self._player.playbackState() == self._player.PlaybackState.PlayingState:
            self._player.pause()
            self.btn_play.setText(self.parent().text("play") if self.parent() and hasattr(self.parent(), "text") else "Play")
            self._timer.stop()
        else:
            # if at end, seek to 0
            if self._player.position() >= max(0, self._player.duration() - 200):
                self._player.setPosition(0)
            self._player.play()
            self.btn_play.setText(self.parent().text("pause") if self.parent() and hasattr(self.parent(), "text") else "Pause")
            self._timer.start()

    def stop(self):
        if self._player is not None:
            self._player.stop()
            self._player.setPosition(0)
            self.btn_play.setText(self.parent().text("play") if self.parent() and hasattr(self.parent(), "text") else "Play")
            self._timer.stop()

    def _stop_playback(self):
        """Silently stop audio + timer and release the file (used on close)."""
        try:
            if getattr(self, "_timer", None) is not None:
                self._timer.stop()
        except Exception:
            pass
        try:
            if getattr(self, "_player", None) is not None:
                try:
                    self._player.stop()
                except Exception:
                    pass
                try:
                    self._player.setPosition(0)
                except Exception:
                    pass
                try:
                    from PySide6.QtCore import QUrl
                    self._player.setSource(QUrl())
                except Exception:
                    pass
        except Exception:
            pass

    def done(self, result):
        # Covers Close button, X button and reject(): never leave audio playing
        self._stop_playback()
        super().done(result)

    def closeEvent(self, event):
        self._stop_playback()
        super().closeEvent(event)

    def _on_duration_changed(self, d):
        self._duration_ms = d
        self._update_time_label(self._player.position() if self._player else 0, d)

    def _on_position_changed(self, pos):
        if not self._is_seeking:
            if self._duration_ms > 0:
                self.slider.blockSignals(True)
                self.slider.setValue(int(pos / self._duration_ms * 1000))
                self.slider.blockSignals(False)
            self._update_time_label(pos, self._duration_ms)

    def _on_tick(self):
        if self._player is None:
            return
        pos = self._player.position()
        self._on_position_changed(pos)

    def _seek_from_slider(self):
        self._is_seeking = False
        if self._player is None or self._duration_ms <= 0:
            return
        val = self.slider.value()
        pos = int(val / 1000 * self._duration_ms)
        self._player.setPosition(pos)

    def _on_volume_changed(self, v: int):
        if self._audio_output is not None:
            try:
                self._audio_output.setVolume(v / 100.0)
            except Exception:
                pass
        if hasattr(self, "vol_value_label"):
            self.vol_value_label.setText(f"{v}%")

    def _on_item_clicked(self, item):
        # Single click = jump to timestamp (double click still edits)
        row = item.row() if item else self.table.currentRow()
        if row < 0:
            return
        t_item = self.table.item(row, 0)
        if t_item is None:
            return
        sec = parse_lrc_time(t_item.text())
        if sec is None:
            return
        # Seek playback to this timestamp
        if self._player is not None:
            # If no duration yet, estimate from max timestamp
            if self._duration_ms > 0:
                ms = int(sec * 1000)
                # Clamp to duration
                ms = max(0, min(ms, self._duration_ms))
                self._player.setPosition(ms)
                # If paused, update slider/label immediately
                self._update_time_label(ms, self._duration_ms)
            else:
                # No duration (audio not loaded or not yet), just store seek for when it loads
                # Set position anyway if player has source
                try:
                    self._player.setPosition(int(sec * 1000))
                except Exception:
                    pass

    def _on_table_select(self):
        # Keep for programmatic selection; do not auto-seek here
        pass

    def _update_time_label(self, pos_ms, dur_ms):
        def fmt(ms):
            s = int(ms // 1000)
            tenth = (int(ms) % 1000) // 100
            return f"{s//60:02d}:{s%60:02d}.{tenth}"
        self.time_label.setText(f"{fmt(pos_ms)} / {fmt(dur_ms)}")

    def _repaint_rows(self):
        # Paint every row: red background for out-of-sequence rows, plain
        # dark grey otherwise. No playback highlight by design.
        from PySide6.QtGui import QBrush, QColor
        invalid = getattr(self, "_invalid_rows", set())
        for r in range(self.table.rowCount()):
            for c in range(self.table.columnCount()):
                it = self.table.item(r, c)
                if it:
                    if r in invalid:
                        # Out-of-sequence row: flag with a red background
                        it.setBackground(QBrush(QColor("#6e1f1f")))
                        it.setForeground(QBrush(QColor("#ffd7d7")))
                    else:
                        # Transparent so the table's dark grey shows
                        it.setBackground(QBrush(QColor("transparent")))
                        it.setForeground(QBrush(QColor("#e6e6e6")))

    def _on_table_time_edited(self, item):
        """A timestamp edit committed: refresh red marking only.

        Never touches times here — correction is manual via fix_timestamps()."""
        try:
            if item.column() != 0:
                return
        except Exception:
            return
        self._refresh_row_marking()

    def _refresh_row_marking(self) -> None:
        """Flag rows whose timestamp runs earlier than any row above them.

        Marking only: never moves rows or edits times."""
        invalid: set[int] = set()
        try:
            running_max = None
            for r in range(self.table.rowCount()):
                t_item = self.table.item(r, 0)
                s = parse_lrc_time(t_item.text()) if t_item and t_item.text().strip() else None
                if s is None or (running_max is not None and s < running_max):
                    invalid.add(r)
                elif running_max is None or s > running_max:
                    running_max = s
        except Exception:
            pass
        self._invalid_rows = invalid
        self._repaint_rows()

    def fix_timestamps(self):
        """Manual fix: set each out-of-order (red) timestamp to just after
        the line above (previous timestamp + 0.01s). Order never changes."""
        from PySide6.QtGui import QBrush, QColor
        n = self.table.rowCount()
        if not n:
            return
        self.table.blockSignals(True)
        try:
            running_max = None
            for r in range(n):
                t_item = self.table.item(r, 0)
                if t_item is None:
                    continue
                s = parse_lrc_time(t_item.text()) if t_item.text().strip() else None
                if s is None:
                    continue  # unreadable cells stay red until fixed by hand
                if running_max is not None and s < running_max:
                    s = round(running_max + 0.01, 2)
                    t_item.setText(format_lrc_time(s))
                    t_item.setTextAlignment(Qt.AlignCenter)
                    t_item.setForeground(QBrush(QColor("#e6e6e6")))
                if running_max is None or s > running_max:
                    running_max = s
        finally:
            self.table.blockSignals(False)
        self._refresh_row_marking()

    # --- edit actions ---
    def add_row(self):
        from PySide6.QtGui import QBrush, QColor
        row = self.table.currentRow()
        insert_at = row + 1 if row >= 0 else self.table.rowCount()
        self.table.insertRow(insert_at)
        # default time = previous line + 2s (or 0)
        last_sec = 0.0
        if self.table.rowCount() > 1 and insert_at > 0:
            prev = self.table.item(insert_at - 1, 0)
            if prev:
                last_sec = parse_lrc_time(prev.text()) or 0.0
                last_sec += 2.0
        t_it = QTableWidgetItem(format_lrc_time(last_sec))
        t_it.setTextAlignment(Qt.AlignCenter)
        t_it.setForeground(QBrush(QColor("#e6e6e6")))
        l_it = QTableWidgetItem("")
        l_it.setForeground(QBrush(QColor("#e6e6e6")))
        self.table.setItem(insert_at, 0, t_it)
        self.table.setItem(insert_at, 1, l_it)
        self._refresh_row_marking()
        self.table.setCurrentCell(insert_at, 1)
        self.table.edit(self.table.model().index(insert_at, 1))

    def remove_selected_rows(self):
        rows = sorted({idx.row() for idx in self.table.selectedIndexes()}, reverse=True)
        for r in rows:
            self.table.removeRow(r)
        self._refresh_row_marking()

    def _on_shift_button(self):
        ok, msg = self.shift_selected_times()
        if not ok and msg != "Cancelled.":
            QMessageBox.warning(self, "Shift Times", msg)

    def shift_selected_times(self, offset_text: str | None = None) -> tuple[bool, str]:
        """Shift all selected rows' timestamps by an offset like +00:02.11.

        Prompts for the offset unless offset_text is given (tests / callers).
        Returns (applied, message). Never reorders rows; red marking refreshes
        afterwards so newly out-of-order rows get flagged, not rewritten.
        """
        from PySide6.QtGui import QBrush, QColor
        rows = sorted({idx.row() for idx in self.table.selectedIndexes()})
        if not rows:
            return False, "No rows selected. Select rows with click, Shift+click or Ctrl+click first."
        if offset_text is None:
            text, ok = QInputDialog.getText(
                self, "Shift Times",
                "Offset for the selected rows ([+/-]MM:SS.cc):",
                text="+00:02.00",
            )
            if not ok:
                return False, "Cancelled."
            offset_text = text
        offset = parse_time_offset(offset_text)
        if offset is None:
            return False, f"Invalid offset {offset_text!r}. Use e.g. +00:02.11 or -00:03.45."
        if offset == 0:
            return False, "Offset is zero, nothing to shift."
        shifted = 0
        self.table.blockSignals(True)
        try:
            for r in rows:
                t_item = self.table.item(r, 0)
                if t_item is None:
                    continue
                cur = parse_lrc_time(t_item.text()) if t_item.text().strip() else None
                if cur is None:
                    continue
                t_item.setText(format_lrc_time(max(0.0, round(cur + offset, 2))))
                t_item.setTextAlignment(Qt.AlignCenter)
                t_item.setForeground(QBrush(QColor("#e6e6e6")))
                shifted += 1
        finally:
            self.table.blockSignals(False)
        self._refresh_row_marking()
        sign = "+" if offset > 0 else "-"
        return True, f"Shifted {shifted} row(s) by {sign}{format_lrc_time(abs(offset))[1:-1]}."

    def save_lrc(self):
        lines = self.collect_lines()
        if not lines:
            QMessageBox.warning(self, "Error", "No lyrics to save.")
            return
        default = self.lrc_path or (str(Path(self.audio_path).with_suffix(".lrc")) if self.audio_path else "")
        path, _ = QFileDialog.getSaveFileName(self, "Save LRC", default, "LRC (*.lrc)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                for item in lines:
                    f.write(f"{format_lrc_time(item['start'])}{item['lyric']}\n")
            self.lrc_path = path
            QMessageBox.information(self, "Saved", f"Saved to {path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _log_to_main(self, message: str) -> None:
        """Append a line to the main window log (and any re-emit it)."""
        try:
            parent = self.parent()
            if parent and hasattr(parent, "append_log"):
                parent.append_log(message)
            from PySide6.QtWidgets import QApplication
            for w in QApplication.topLevelWidgets():
                if hasattr(w, "append_log") and w is not self:
                    try:
                        w.append_log(message)
                    except Exception:
                        pass
        except Exception:
            pass

    def embed_to_audio(self):
        if not self.audio_path or not Path(self.audio_path).exists():
            QMessageBox.warning(self, "Embed", "No audio file loaded. Load an audio file first to embed.")
            return
        lines = self.collect_lines()
        if not lines:
            QMessageBox.warning(self, "Embed", "No lyrics to embed.")
            return
        synced = "\n".join(f"{format_lrc_time(l['start'])}{l['lyric']}" for l in lines)
        plain = "\n".join(l["lyric"] for l in lines)
        name = Path(self.audio_path).name
        msg = (f"Embed {len(lines)} synced line(s) into the audio file?\n\n"
               f"File: {name}\nThis overwrites any lyrics already embedded in it.")
        if QMessageBox.question(self, "Embed", msg, QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        try:
            from embed_lyrics import embed_synced_lyrics
            ok, result = embed_synced_lyrics(self.audio_path, synced, plain)
        except Exception as e:
            ok, result = False, str(e)
        self._log_to_main(f"[Embed] {'OK' if ok else 'Failed'} {name}: {result}")
        if ok:
            QMessageBox.information(self, "Embed", f"✓ {result}")
        else:
            QMessageBox.critical(self, "Embed", f"✗ Embed failed:\n{result}")

    def publish_to_lrclib(self):
        if not self.audio_path or not Path(self.audio_path).exists():
            QMessageBox.warning(self, "LRCLIB", "No audio file loaded. Load an audio file first to publish.")
            return
        lines = self.collect_lines()
        if not lines:
            QMessageBox.warning(self, "LRCLIB", "No lyrics to publish.")
            return
        # Build synced and plain
        synced = "\n".join(f"{format_lrc_time(l['start'])}{l['lyric']}" for l in lines)
        plain = "\n".join(l["lyric"] for l in lines)
        # Get metadata
        try:
            from lrclib_client import get_track_metadata
            meta = get_track_metadata(self.audio_path)
        except Exception as e:
            QMessageBox.critical(self, "LRCLIB", f"Failed to read metadata: {e}")
            return
        if not meta.get("duration") or meta["duration"] < 5:
            QMessageBox.warning(self, "LRCLIB", f"Duration missing ({meta.get('duration')}), cannot publish. Try with a different file.")
            return
        # Confirm
        msg = f"Publish to LRCLIB?\n\nTrack: {meta['trackName']}\nArtist: {meta['artistName']}\nAlbum: {meta['albumName']}\nDuration: {meta['duration']:.1f}s\nLines: {len(lines)}\n\nThis will solve a proof-of-work (may take 10-30s) and upload."
        if QMessageBox.question(self, "LRCLIB Publish", msg, QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        # Show progress dialog with clear steps
        prog = QProgressDialog("Requesting challenge from LRCLIB...", "Cancel", 0, 0, self)
        prog.setWindowTitle("Publishing to LRCLIB")
        prog.setWindowModality(Qt.WindowModal)
        prog.setMinimumDuration(0)
        prog.setAutoClose(False)
        prog.setAutoReset(False)
        # Dark grey palette for progress dialog too (matches app theme)
        try:
            from PySide6.QtGui import QPalette, QColor
            pal = prog.palette()
            pal.setColor(QPalette.Window, QColor("#2b2b2b"))
            pal.setColor(QPalette.WindowText, QColor("#e6e6e6"))
            pal.setColor(QPalette.Base, QColor("#323232"))
            pal.setColor(QPalette.Text, QColor("#e6e6e6"))
            pal.setColor(QPalette.Button, QColor("#3d3d3d"))
            pal.setColor(QPalette.ButtonText, QColor("#e6e6e6"))
            prog.setPalette(pal)
        except Exception:
            pass
        prog.show()
        # Worker in thread with progress and cancellation
        class _PublishWorker(QObject):
            finished = Signal(bool, str)
            progress = Signal(str)
            def __init__(self, track, artist, album, duration, plain_, synced_):
                super().__init__()
                self.track = track
                self.artist = artist
                self.album = album
                self.duration = duration
                self.plain = plain_
                self.synced = synced_
                self._cancelled = False
            def cancel(self):
                self._cancelled = True
            def is_cancelled(self):
                return self._cancelled or (hasattr(self, "_thread") and self._thread and self._thread.isInterruptionRequested())
            @Slot()
            def run(self):
                try:
                    from lrclib_client import publish_lyrics
                    import time
                    self.progress.emit("Requesting challenge from LRCLIB...")
                    # Use cancellable publish with progress callback.
                    # Solver emits (nonce, rate) numbers; stage updates are strings.
                    def prog_cb(nonce, rate):
                        if self.is_cancelled():
                            return
                        if isinstance(nonce, str):
                            self.progress.emit(nonce)
                        else:
                            self.progress.emit(f"Solving… {nonce:,} hashes ({rate:,.0f} h/s)")
                    ok, m = publish_lyrics(
                        self.track, self.artist, self.album, self.duration, self.plain, self.synced,
                        cancel_check=self.is_cancelled, progress_cb=prog_cb
                    )
                    if self.is_cancelled():
                        self.finished.emit(False, "Cancelled by user.")
                        return
                    if ok:
                        self.progress.emit("Published successfully!")
                        time.sleep(0.4)
                    self.finished.emit(ok, m)
                except Exception as e:
                    import traceback
                    self.finished.emit(False, traceback.format_exc())

        self._pub_thread = QThread(self)
        self._pub_worker = _PublishWorker(meta["trackName"], meta["artistName"], meta["albumName"], meta["duration"], plain, synced)
        # keep ref for cancel check
        self._pub_worker._thread = self._pub_thread
        self._pub_worker.moveToThread(self._pub_thread)
        self._pub_thread.started.connect(self._pub_worker.run)
        # Keep dialog/widgets reachable from the GUI-thread slots below.
        # NOTE: progress/finished must be handled by bound methods (queued to
        # the GUI thread). Plain closures would run IN the worker thread and
        # touch widgets off-thread, freezing the app.
        self._prog = prog
        self._pub_meta = meta
        self._pub_done = False
        self._pub_worker.progress.connect(self._on_pub_progress)
        self._pub_worker.finished.connect(self._on_pub_done)
        prog.canceled.connect(self._on_pub_cancel)
        # Ensure dialog close also cancels
        prog.finished.connect(self._on_pub_dlg_finished)
        self._pub_thread.start()

    @Slot(str)
    def _on_pub_progress(self, text):
        # Runs in the GUI thread (queued connection from worker/ticker threads)
        prog = getattr(self, "_prog", None)
        if prog is not None and prog.isVisible():
            prog.setLabelText(text)
            prog.setValue(0)
        # Also log to main window if available
        try:
            if hasattr(self.parent(), "append_log"):
                self.parent().append_log(f"[LRCLIB] {text}")
        except Exception:
            pass

    @Slot(bool, str)
    def _on_pub_done(self, ok, m):
        # Runs in the GUI thread (queued connection from the worker thread)
        # Guard against double delivery (e.g. cancel racing completion)
        if getattr(self, "_pub_done", False):
            return
        self._pub_done = True
        prog = getattr(self, "_prog", None)
        meta = getattr(self, "_pub_meta", {}) or {}
        try:
            if prog is not None:
                prog.close()
        except Exception:
            pass
        # Log result
        try:
            log_msg = f"[LRCLIB] Publish {'succeeded' if ok else 'failed'}: {meta.get('trackName')} - {m[:120]}"
            parent = self.parent()
            if parent and hasattr(parent, "append_log"):
                parent.append_log(log_msg)
            # Also try app's main window via QApplication
            from PySide6.QtWidgets import QApplication
            for w in QApplication.topLevelWidgets():
                if hasattr(w, "append_log") and w is not self:
                    try:
                        w.append_log(log_msg)
                    except Exception:
                        pass
        except Exception:
            pass
        try:
            if self._pub_thread is not None:
                self._pub_thread.quit()
                self._pub_thread.wait(2000)
        except Exception:
            pass
        if ok:
            QMessageBox.information(self, "LRCLIB", f"✓ Published successfully!\n\nTrack: {meta.get('trackName')}\nArtist: {meta.get('artistName')}\n\n{m}")
        else:
            # Don't show error if cancelled
            if "Cancelled" not in str(m):
                try:
                    from lrclib_client import get_publish_debug_path
                    dbg = get_publish_debug_path()
                except Exception:
                    dbg = ""
                detail = f"\n\nStage log saved to:\n{dbg}" if dbg else ""
                QMessageBox.critical(self, "LRCLIB", f"✗ Publish failed:\n{m}{detail}")
        # cleanup
        try:
            self._pub_worker.deleteLater()
            self._pub_thread.deleteLater()
        except Exception:
            pass
        self._pub_thread = None
        self._pub_worker = None
        self._prog = None

    @Slot()
    def _on_pub_cancel(self):
        # Runs in the GUI thread (emitted by the progress dialog)
        try:
            if getattr(self, "_prog", None) is not None:
                self._prog.setLabelText("Cancelling…")
            if getattr(self, "_pub_worker", None) is not None:
                self._pub_worker.cancel()
            if getattr(self, "_pub_thread", None) is not None:
                self._pub_thread.requestInterruption()
                # Give it a moment then force quit
                QTimer.singleShot(1000, self._force_pub_quit)
        except Exception:
            pass

    @Slot()
    def _force_pub_quit(self):
        try:
            if getattr(self, "_pub_thread", None) is not None and self._pub_thread.isRunning():
                self._pub_thread.quit()
        except Exception:
            pass

    @Slot(int)
    def _on_pub_dlg_finished(self, _result):
        # Dialog closed: cancel only if the worker is still running
        try:
            if getattr(self, "_pub_thread", None) is not None and self._pub_thread.isRunning():
                self._on_pub_cancel()
        except Exception:
            pass

    # --- Plain text / TXT loading (drag & drop, auto-load) ---
    def load_txt_file(self, path: str):
        try:
            text = Path(path).read_text(encoding="utf-8-sig")
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))
            return
        # Plain txt: each non-empty line becomes a timed entry with incremental times
        lines = []
        t = 0.0
        for raw in text.splitlines():
            raw = raw.strip()
            if not raw:
                continue
            # If line already has timestamps, parse as LRC
            if raw.startswith("[") and "]" in raw:
                lines.extend(self._parse_lrc_text(raw))
            else:
                lines.append({"start": t, "lyric": raw})
                t += 2.5
        if lines:
            self.load_lines(lines)
            self.lrc_path = str(Path(path).with_suffix(".lrc"))

    def load_plain_text(self, text: str):
        lines = []
        t = 0.0
        for raw in text.splitlines():
            raw = raw.strip()
            if not raw:
                continue
            if raw.startswith("[") and "]" in raw:
                lines.extend(self._parse_lrc_text(raw))
            else:
                lines.append({"start": t, "lyric": raw})
                t += 2.5
        if lines:
            self.load_lines(lines)

    def _try_auto_load_for_audio(self, audio_path: str):
        if not audio_path or not Path(audio_path).exists():
            return False
        # 1) .lrc next to audio
        cand = Path(audio_path).with_suffix(".lrc")
        if cand.exists():
            self.load_lrc_file(str(cand))
            return True
        # 2) _word.lrc
        cand2 = Path(audio_path).with_name(Path(audio_path).stem + "_word.lrc")
        if cand2.exists():
            self.load_lrc_file(str(cand2))
            return True
        # 3) .txt next to audio
        cand3 = Path(audio_path).with_suffix(".txt")
        if cand3.exists():
            self.load_txt_file(str(cand3))
            return True
        # 4) embedded lyrics
        try:
            from align import extract_embedded_lyrics
            emb = extract_embedded_lyrics(audio_path)
            if emb and emb.strip():
                self.load_plain_text(emb)
                return True
        except Exception:
            pass
        return False

    # --- Drag & Drop ---
    def dragEnterEvent(self, event):
        mime = event.mimeData()
        if mime.hasUrls() or mime.hasText():
            # check if any url is supported
            if mime.hasUrls():
                for url in mime.urls():
                    p = url.toLocalFile().lower()
                    if p.endswith((".lrc", ".txt", ".wav", ".mp3", ".flac", ".m4a", ".aac", ".ogg", ".opus")):
                        event.acceptProposedAction()
                        return
            if mime.hasText() and mime.text().strip():
                event.acceptProposedAction()
                return
        event.ignore()

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def dropEvent(self, event):
        mime = event.mimeData()
        if mime.hasUrls():
            for url in mime.urls():
                path = url.toLocalFile()
                if not path:
                    continue
                low = path.lower()
                if low.endswith(".lrc"):
                    self.load_lrc_file(path)
                    self.lrc_path = path
                    event.acceptProposedAction()
                    return
                elif low.endswith(".txt"):
                    self.load_txt_file(path)
                    event.acceptProposedAction()
                    return
                elif low.endswith(tuple(AUDIO_EXTENSIONS)):
                    self.load_audio(path)
                    # auto-load associated lyrics if table empty
                    if self.table.rowCount() == 0:
                        self._try_auto_load_for_audio(path)
                    event.acceptProposedAction()
                    return
        if mime.hasText():
            text = mime.text().strip()
            if text:
                # Heuristic: if text contains timestamps, treat as LRC, else plain
                if "[" in text and "]" in text:
                    lines = self._parse_lrc_text(text)
                    if lines:
                        self.load_lines(lines)
                else:
                    self.load_plain_text(text)
                event.acceptProposedAction()
                return
        event.ignore()


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("CTCLRC", "CTCLRC")
        self.setAcceptDrops(True)
        self.setWindowTitle("CTCLRC")
        # --- FIX: window resizing is now flexible ---
        self.setMinimumSize(680, 560)
        self.resize(960, 760)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._device_info: dict | None = None
        self.init_ui()
        self.load_settings()
        self.apply_static_texts()

    def init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 8)
        outer.setSpacing(8)

        # Splitter to make resizing fluid
        self.main_splitter = QSplitter(Qt.Vertical)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setHandleWidth(6)
        outer.addWidget(self.main_splitter, 1)

        # Top container: common options + stack
        top_container = QWidget()
        top_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        top_layout2 = QVBoxLayout(top_container)
        top_layout2.setContentsMargins(0, 0, 0, 0)
        top_layout2.setSpacing(8)

        common_box = QGroupBox()
        common_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        common_layout = QFormLayout(common_box)
        common_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        self.language_label = QLabel()
        self.language_combo = QComboBox()
        self.language_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        for label, code in LANGUAGE_ITEMS:
            self.language_combo.addItem(label, code)
        common_layout.addRow(self.language_label, self.language_combo)
        self.lead_label = QLabel()
        self.lead_in_spin = QDoubleSpinBox()
        self.lead_in_spin.setRange(0.0, 2.0)
        self.lead_in_spin.setSingleStep(0.005)
        self.lead_in_spin.setDecimals(3)
        self.lead_in_spin.setValue(DEFAULT_LEAD_IN)
        self.lead_in_spin.setSuffix(" s")
        common_layout.addRow(self.lead_label, self.lead_in_spin)
        self.line_checkbox = QCheckBox()
        self.line_checkbox.setChecked(True)
        self.word_checkbox = QCheckBox()
        self.section_checkbox = QCheckBox()
        self.section_checkbox.setChecked(True)
        mode_row = QHBoxLayout()
        mode_row.addWidget(self.line_checkbox)
        mode_row.addWidget(self.word_checkbox)
        mode_row.addWidget(self.section_checkbox)
        mode_row.addStretch()
        common_layout.addRow(mode_row)

        # New options row: LRCLIB + embed
        opts_row = QHBoxLayout()
        self.check_lrclib_checkbox = QCheckBox()
        self.check_lrclib_checkbox.setChecked(True)
        opts_row.addWidget(self.check_lrclib_checkbox)
        self.upload_lrclib_checkbox = QCheckBox()
        self.upload_lrclib_checkbox.setChecked(False)
        self.upload_lrclib_checkbox.setToolTip("Automatically publish generated lyrics to LRCLIB after generation")
        opts_row.addWidget(self.upload_lrclib_checkbox)
        self.embed_checkbox = QCheckBox()
        self.embed_checkbox.setChecked(False)
        opts_row.addWidget(self.embed_checkbox)
        opts_row.addStretch()
        common_layout.addRow(opts_row)

        # viewer button row
        viewer_row = QHBoxLayout()
        self.open_viewer_button = QPushButton()
        self.open_viewer_button.clicked.connect(self.open_lyric_viewer)
        viewer_row.addWidget(self.open_viewer_button)
        viewer_row.addStretch()
        common_layout.addRow(viewer_row)

        top_layout2.addWidget(common_box)

        # Single batch page in a scroll area so small windows can still scroll
        self.batch_page = self._build_advanced_page()
        self.batch_scroll = QScrollArea()
        self.batch_scroll.setWidgetResizable(True)
        self.batch_scroll.setFrameShape(QFrame.NoFrame)
        self.batch_scroll.setWidget(self.batch_page)
        self.batch_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        top_layout2.addWidget(self.batch_scroll, 1)

        # Bottom container: generate + progress + log
        bottom_container = QWidget()
        bottom_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        bottom_layout = QVBoxLayout(bottom_container)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(4)
        self.batch_generate_button = QPushButton()
        self.batch_generate_button.setMinimumHeight(42)
        self.batch_generate_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        bottom_layout.addWidget(self.batch_generate_button)
        progress_row = QHBoxLayout()
        self.progress_label = QLabel()
        progress_row.addWidget(self.progress_label)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setMinimumHeight(16)
        self.progress_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        progress_row.addWidget(self.progress_bar, 1)
        self.device_label = QLabel()
        self.device_label.setObjectName("device_label")
        self.device_label.setStyleSheet("font-weight: bold;")
        self.device_label.setToolTip("")
        progress_row.addWidget(self.device_label)
        bottom_layout.addLayout(progress_row)
        self.log_label = QLabel()
        bottom_layout.addWidget(self.log_label)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(120)
        self.log.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        bottom_layout.addWidget(self.log, 1)

        self.main_splitter.addWidget(top_container)
        self.main_splitter.addWidget(bottom_container)
        # initial sizes: top larger
        self.main_splitter.setSizes([520, 200])
        self.main_splitter.setStretchFactor(0, 3)
        self.main_splitter.setStretchFactor(1, 1)

    def _build_list_section(self, title_key: str, add_slot, remove_slot, clear_slot):
        box = QGroupBox()
        box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        box_layout = QVBoxLayout(box)
        title = QLabel()
        title.setObjectName(title_key)
        add_button = QPushButton()
        add_button.clicked.connect(add_slot)
        remove_button = QPushButton()
        remove_button.clicked.connect(remove_slot)
        clear_button = QPushButton()
        clear_button.clicked.connect(clear_slot)
        header = QHBoxLayout()
        header.addWidget(title)
        header.addStretch()
        header.addWidget(add_button)
        header.addWidget(remove_button)
        header.addWidget(clear_button)
        box_layout.addLayout(header)
        list_widget = QListWidget()
        list_widget.setSelectionMode(QAbstractItemView.ExtendedSelection)
        list_widget.setMinimumHeight(90)
        list_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        box_layout.addWidget(list_widget, 1)
        return box, title, list_widget, add_button, remove_button, clear_button

    def _build_advanced_page(self) -> QWidget:
        page = QWidget()
        page.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)
        # Directory batch row (recursive)
        dir_row = QHBoxLayout()
        self.add_directory_button = QPushButton("Add Directory")
        self.add_directory_button.setToolTip("Add a folder (and subfolders if checked) and auto-pair audio + .lrc/.txt by name")
        self.add_directory_button.clicked.connect(self.add_directory_files)
        dir_row.addWidget(self.add_directory_button)
        self.include_subfolders_checkbox = QCheckBox("Include subfolders")
        self.include_subfolders_checkbox.setChecked(True)
        dir_row.addWidget(self.include_subfolders_checkbox)
        dir_row.addStretch()
        layout.addLayout(dir_row)
        # Track counter
        self.track_counter_label = QLabel("Tracks: 0  •  With lyrics: 0  •  Existing .lrc: 0  •  Missing: 0")
        self.track_counter_label.setStyleSheet("font-weight: bold; color: #e6e6e6;")
        layout.addWidget(self.track_counter_label)
        self.audio_box, self.audio_list_title, self.audio_list, self.audio_add_button, self.audio_remove_button, self.audio_clear_button = self._build_list_section(
            "audio_list",
            self.add_audio_files,
            self.remove_selected_audio,
            self.clear_audio_files,
        )
        layout.addWidget(self.audio_box, 1)
        self.lyrics_box, self.lyrics_list_title, self.lyrics_list, self.lyrics_add_button, self.lyrics_remove_button, self.lyrics_clear_button = self._build_list_section(
            "lyrics_list",
            self.add_lyrics_files,
            self.remove_selected_lyrics,
            self.clear_lyrics_files,
        )
        layout.addWidget(self.lyrics_box, 1)
        # Lyrics manual input / paste (right below the file sections)
        self.batch_lyrics_box = QGroupBox()
        self.batch_lyrics_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        batch_lyrics_layout = QVBoxLayout(self.batch_lyrics_box)
        batch_lyrics_header = QHBoxLayout()
        self.batch_lyrics_label = QLabel()
        batch_lyrics_header.addWidget(self.batch_lyrics_label)
        batch_lyrics_header.addStretch()
        self.batch_lyrics_save_button = QPushButton()
        self.batch_lyrics_save_button.clicked.connect(self._sync_batch_lyrics_to_current_item)
        batch_lyrics_header.addWidget(self.batch_lyrics_save_button)
        self.batch_lyrics_clear_button = QPushButton()
        self.batch_lyrics_clear_button.clicked.connect(self.clear_selected_batch_lyrics)
        batch_lyrics_header.addWidget(self.batch_lyrics_clear_button)
        batch_lyrics_layout.addLayout(batch_lyrics_header)
        self.batch_lyrics_edit = QTextEdit()
        self.batch_lyrics_edit.setAcceptRichText(False)
        self.batch_lyrics_edit.setPlaceholderText("Paste lyrics for the selected audio item.")
        self.batch_lyrics_edit.setMinimumHeight(80)
        self.batch_lyrics_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.batch_lyrics_edit.textChanged.connect(self._sync_batch_lyrics_to_current_item)
        batch_lyrics_layout.addWidget(self.batch_lyrics_edit)
        layout.addWidget(self.batch_lyrics_box)
        pair_row = QHBoxLayout()
        self.pairing_label = QLabel()
        pair_row.addWidget(self.pairing_label)
        self.pairing_combo = QComboBox()
        self.pairing_combo.addItem("Match by file name", "name")
        self.pairing_combo.addItem("Match by order", "order")
        self.pairing_combo.currentIndexChanged.connect(self.update_batch_preview)
        pair_row.addWidget(self.pairing_combo, 1)
        layout.addLayout(pair_row)
        output_row = QHBoxLayout()
        self.output_dir_label = QLabel()
        output_row.addWidget(self.output_dir_label)
        self.output_dir_edit = DropLineEdit()
        self.output_dir_edit.textChanged.connect(self.update_batch_preview)
        output_row.addWidget(self.output_dir_edit, 1)
        self.output_dir_button = QPushButton()
        self.output_dir_button.clicked.connect(self.select_output_dir)
        output_row.addWidget(self.output_dir_button)
        layout.addLayout(output_row)
        self.batch_hint_label = QLabel()
        self.batch_hint_label.setWordWrap(True)
        layout.addWidget(self.batch_hint_label)
        self.preview_label = QLabel()
        layout.addWidget(self.preview_label)
        self.batch_preview = QTextEdit()
        self.batch_preview.setReadOnly(True)
        self.batch_preview.setMinimumHeight(80)
        self.batch_preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.batch_preview, 1)
        self.audio_list.itemSelectionChanged.connect(self.update_batch_preview)
        self.audio_list.currentItemChanged.connect(self._load_batch_lyrics_for_current_audio)
        self.audio_list.model().rowsInserted.connect(self.update_batch_preview)
        self.audio_list.model().rowsRemoved.connect(self.update_batch_preview)
        self.lyrics_list.itemSelectionChanged.connect(self.update_batch_preview)
        self.lyrics_list.model().rowsInserted.connect(self.update_batch_preview)
        self.lyrics_list.model().rowsRemoved.connect(self.update_batch_preview)
        self.audio_list.itemDoubleClicked.connect(lambda _: self.view_selected_lyrics())
        return page

    def text(self, key: str) -> str:
        return STRINGS.get(key, key)

    def apply_static_texts(self):
        texts = STRINGS
        self.language_label.setText(texts["language"])
        self.lead_label.setText(texts["lead"])
        self.language_combo.setToolTip(texts["language"])
        self.section_checkbox.setText(texts["sections"])
        self.line_checkbox.setText(texts["line"])
        self.word_checkbox.setText(texts["chars"])
        self.batch_generate_button.setText(texts["generate"])
        self.log_label.setText(texts["log"])
        self.progress_label.setText(f"{texts['progress']} : {getattr(self, 'current_progress', 0)}%")
        self.audio_list_title.setText(texts["audio_list"])
        self.lyrics_list_title.setText(texts["lyrics_list"])
        self.audio_add_button.setText(texts["add_files"])
        self.audio_remove_button.setText(texts["remove"])
        self.audio_clear_button.setText(texts["clear_list"])
        self.lyrics_add_button.setText(texts["add_files"])
        self.lyrics_remove_button.setText(texts["remove"])
        self.lyrics_clear_button.setText(texts["clear_list"])
        self.pairing_label.setText(texts["pairing"])
        self.output_dir_label.setText(texts["output_dir"])
        self.output_dir_button.setText(texts["choose_output_dir"])
        self.batch_lyrics_label.setText(texts["batch_lyrics"])
        self.batch_lyrics_save_button.setText(texts["save_pasted"])
        self.batch_lyrics_clear_button.setText(texts["clear_pasted"])
        self.batch_lyrics_edit.setPlaceholderText(texts["batch_lyrics_placeholder"])
        self.preview_label.setText(texts["preview"])
        self.batch_hint_label.setText(texts["batch_hint"])
        # new
        self.check_lrclib_checkbox.setText(texts["check_lrclib"])
        self.upload_lrclib_checkbox.setText(texts["upload_lrclib"])
        self.embed_checkbox.setText(texts["embed_synced"])
        self.open_viewer_button.setText(texts["open_viewer"])
        current_pair = self.pairing_combo.currentData() or "name"
        self.pairing_combo.blockSignals(True)
        self.pairing_combo.clear()
        self.pairing_combo.addItem(texts["pair_by_name"], "name")
        self.pairing_combo.addItem(texts["pair_by_order"], "order")
        idx = self.pairing_combo.findData(current_pair)
        if idx >= 0:
            self.pairing_combo.setCurrentIndex(idx)
        self.pairing_combo.blockSignals(False)
        self.set_progress(getattr(self, "current_progress", 0))
        self._refresh_device_label()
        self.update_batch_preview()

    def load_settings(self):
        self.current_progress = 0
        self.lead_in_spin.setValue(self.settings.value("lead_in", DEFAULT_LEAD_IN, type=float))
        language_code = self.settings.value("lyrics_language", "jpn")
        index = self.language_combo.findData(language_code)
        self.language_combo.setCurrentIndex(max(index, 0))
        self.line_checkbox.setChecked(self.settings.value("line_mode", True, type=bool))
        self.word_checkbox.setChecked(self.settings.value("word_mode", False, type=bool))
        self.section_checkbox.setChecked(self.settings.value("keep_sections", True, type=bool))
        self.output_dir_edit.setText(self.settings.value("output_dir", ""))
        self.check_lrclib_checkbox.setChecked(self.settings.value("check_lrclib", True, type=bool))
        self.upload_lrclib_checkbox.setChecked(self.settings.value("upload_lrclib", False, type=bool))
        self.embed_checkbox.setChecked(self.settings.value("embed_synced", False, type=bool))
        if hasattr(self, "include_subfolders_checkbox"):
            self.include_subfolders_checkbox.setChecked(self.settings.value("include_subfolders", True, type=bool))

    def save_settings(self):
        self.settings.setValue("lead_in", self.lead_in_spin.value())
        self.settings.setValue("lyrics_language", self.language_combo.currentData())
        self.settings.setValue("line_mode", self.line_checkbox.isChecked())
        self.settings.setValue("word_mode", self.word_checkbox.isChecked())
        self.settings.setValue("keep_sections", self.section_checkbox.isChecked())
        self.settings.setValue("output_dir", self.output_dir_edit.text())
        self.settings.setValue("check_lrclib", self.check_lrclib_checkbox.isChecked())
        self.settings.setValue("upload_lrclib", self.upload_lrclib_checkbox.isChecked())
        self.settings.setValue("embed_synced", self.embed_checkbox.isChecked())
        if hasattr(self, "include_subfolders_checkbox"):
            self.settings.setValue("include_subfolders", self.include_subfolders_checkbox.isChecked())

    def open_lyric_viewer(self):
        # Gather audio + try to auto-find lyrics (lrc / txt / pasted / embedded)
        audio = None
        lrc = None
        auto_lines = None
        pasted_text = None
        cur = self.audio_list.currentItem()
        if cur:
            audio = cur.text()
        elif self.audio_list.count() > 0:
            audio = self.audio_list.item(0).text()
        if audio and Path(audio).exists():
            cand = Path(audio).with_suffix(".lrc")
            if cand.exists():
                lrc = str(cand)
            else:
                cand2 = Path(audio).with_name(Path(audio).stem + "_word.lrc")
                if cand2.exists():
                    lrc = str(cand2)
            if not lrc:
                cand3 = Path(audio).with_suffix(".txt")
                if cand3.exists():
                    try:
                        txt = cand3.read_text(encoding="utf-8-sig")
                        auto_lines = []
                        t = 0.0
                        for raw in txt.splitlines():
                            raw = raw.strip()
                            if not raw:
                                continue
                            auto_lines.append({"start": t, "lyric": raw})
                            t += 2.5
                    except Exception:
                        pass
            if not lrc and not auto_lines:
                # check batch pasted for current item
                cur_item = self.audio_list.currentItem()
                if cur_item is not None:
                    data = cur_item.data(Qt.UserRole)
                    if data and str(data).strip():
                        pasted_text = str(data).strip()
                        auto_lines = []
                        t = 0.0
                        for raw in pasted_text.splitlines():
                            raw = raw.strip()
                            if not raw:
                                continue
                            auto_lines.append({"start": t, "lyric": raw})
                            t += 2.5
                # embedded fallback
                if not auto_lines:
                    try:
                        from align import extract_embedded_lyrics
                        emb = extract_embedded_lyrics(audio)
                        if emb and emb.strip():
                            auto_lines = []
                            t = 0.0
                            for raw in emb.splitlines():
                                raw = raw.strip()
                                if not raw:
                                    continue
                                auto_lines.append({"start": t, "lyric": raw})
                                t += 2.5
                    except Exception:
                        pass
        dlg = LyricViewerDialog(self, audio_path=audio, lrc_path=lrc, lines=auto_lines)
        dlg.exec()

    def add_audio_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            self.text("audio_list"),
            "",
            "Audio (*.wav *.mp3 *.flac *.m4a *.aac *.ogg *.opus);;All files (*.*)",
        )
        # Fallback: if native dialog only returned one due to filter, try again with All files
        for file in files:
            self._add_list_item(self.audio_list, file)
        if files:
            self.append_log(f"Added {len(files)} audio file(s)")
        self.update_batch_preview()

    def add_lyrics_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            self.text("lyrics_list"),
            "",
            "Text (*.txt);;LRC (*.lrc);;All files (*.*)",
        )
        for file in files:
            self._add_list_item(self.lyrics_list, file)
        if files:
            self.append_log(f"Added {len(files)} lyric file(s)")
        self.update_batch_preview()

    def remove_selected_audio(self):
        self._remove_selected_items(self.audio_list)
        self.update_batch_preview()

    def remove_selected_lyrics(self):
        self._remove_selected_items(self.lyrics_list)
        self.update_batch_preview()

    def clear_audio_files(self):
        self.audio_list.clear()
        self.update_batch_preview()

    def clear_lyrics_files(self):
        self.lyrics_list.clear()
        self.update_batch_preview()

    def select_output_dir(self):
        directory = QFileDialog.getExistingDirectory(
            self,
            self.text("output_dir"),
            "",
        )
        if directory:
            self.output_dir_edit.setText(directory)

    def add_directory_files(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Directory", "")
        if not directory:
            return
        try:
            from batch_utils import scan_directory
            recursive = self.include_subfolders_checkbox.isChecked() if hasattr(self, "include_subfolders_checkbox") else True
            results = scan_directory(directory, recursive=recursive)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to scan directory: {e}")
            return
        added_audio = 0
        added_lyric = 0
        for res in results:
            before = self.audio_list.count()
            self._add_list_item(self.audio_list, res.audio_path)
            if self.audio_list.count() > before:
                added_audio += 1
            # Add lyric if any match found (including existing .lrc next to track)
            if res.lyric_path:
                before_l = self.lyrics_list.count()
                self._add_list_item(self.lyrics_list, res.lyric_path)
                if self.lyrics_list.count() > before_l:
                    added_lyric += 1
        self.update_batch_preview()
        if hasattr(self, "log"):
            self.append_log(f"Scanned {directory}: {len(results)} audio, {added_audio} new, {added_lyric} lyrics matched (recursive={recursive})")

    def view_selected_lyrics(self):
        item = self.audio_list.currentItem()
        if item is None and self.audio_list.count() > 0:
            item = self.audio_list.item(0)
        if item is None:
            QMessageBox.warning(self, "Viewer", "No track selected.")
            return
        audio_path = item.text()
        pasted = self._audio_item_lyrics_text(item)
        lyric_path = None
        lines = None
        if pasted:
            auto_lines = []
            t = 0.0
            for raw in pasted.splitlines():
                raw = raw.strip()
                if raw:
                    auto_lines.append({"start": t, "lyric": raw})
                    t += 2.5
            lines = auto_lines
        else:
            jobs = self.collect_batch_jobs()
            for job in jobs:
                if job["audio"] == audio_path and job["lyrics_file"]:
                    lyric_path = job["lyrics_file"]
                    break
            if not lyric_path:
                cand = Path(audio_path).with_suffix(".lrc")
                if cand.exists():
                    lyric_path = str(cand)
                else:
                    cand2 = Path(audio_path).with_suffix(".txt")
                    if cand2.exists():
                        lyric_path = str(cand2)
        dlg = LyricViewerDialog(self, audio_path=audio_path, lrc_path=lyric_path, lines=lines)
        dlg.exec()
        self.update_batch_preview()

    def _add_list_item(self, list_widget: QListWidget, path: str):
        path = str(Path(path))
        for i in range(list_widget.count()):
            if list_widget.item(i).text() == path:
                return
        item = QListWidgetItem(path)
        list_widget.addItem(item)

    def _remove_selected_items(self, list_widget: QListWidget):
        for item in list_widget.selectedItems():
            row = list_widget.row(item)
            list_widget.takeItem(row)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            suffix = path.lower().rsplit(".", 1)[-1]
            suffix = f".{suffix}" if suffix else ""
            if suffix in AUDIO_EXTENSIONS:
                self._add_list_item(self.audio_list, path)
            elif suffix in TEXT_EXTENSIONS or suffix in LRC_EXTENSIONS:
                self._add_list_item(self.lyrics_list, path)
        self.update_batch_preview()

    def _collect_list_paths(self, list_widget: QListWidget) -> list[str]:
        return [list_widget.item(i).text() for i in range(list_widget.count())]

    def _audio_item_lyrics_text(self, item) -> str | None:
        if item is None:
            return None
        data = item.data(Qt.UserRole)
        if data is None:
            return None
        text = str(data).strip()
        return text or None

    def collect_batch_jobs(self):
        audio_items = [self.audio_list.item(i) for i in range(self.audio_list.count())]
        lyric_paths = self._collect_list_paths(self.lyrics_list)
        pairing = self.pairing_combo.currentData() or "name"
        output_dir = self.output_dir_edit.text().strip() or None
        jobs = []
        if not audio_items:
            return jobs
        single_pair = len(audio_items) == 1 and len(lyric_paths) == 1
        lyric_by_stem = {}
        for lyric_path in lyric_paths:
            lyric_by_stem[Path(lyric_path).stem.lower()] = lyric_path
        for index, item in enumerate(audio_items):
            audio_path = item.text()
            lyrics_text = self._audio_item_lyrics_text(item)
            lyric_path = None
            if not lyrics_text:
                if pairing == "order":
                    lyric_path = lyric_paths[index] if index < len(lyric_paths) else None
                else:
                    lyric_path = lyric_by_stem.get(Path(audio_path).stem.lower())
                    if lyric_path is None and single_pair:
                        lyric_path = lyric_paths[0]
            jobs.append(self._make_job(audio_path, lyric_path, lyrics_text, output_dir))
        return jobs

    def _make_job(self, audio_path: str, lyric_path: str | None, lyrics_text: str | None, output_dir: str | None):
        output_path = None
        if output_dir:
            output_path = str(Path(output_dir) / Path(audio_path).stem)
        return {
            "audio": audio_path,
            "lyrics_file": lyric_path,
            "lyrics_text": lyrics_text,
            "output_path": output_path,
        }

    def _load_batch_lyrics_for_current_audio(self, current, previous=None):
        if getattr(self, "_batch_lyrics_syncing", False):
            return
        self._batch_lyrics_syncing = True
        try:
            text = ""
            if current is not None:
                text = self._audio_item_lyrics_text(current) or ""
            self.batch_lyrics_edit.blockSignals(True)
            self.batch_lyrics_edit.setPlainText(text)
            self.batch_lyrics_edit.blockSignals(False)
        finally:
            self._batch_lyrics_syncing = False
        self.update_batch_preview()

    def _sync_batch_lyrics_to_current_item(self, *args):
        if getattr(self, "_batch_lyrics_syncing", False):
            return
        item = self.audio_list.currentItem()
        if item is None:
            return
        text = self.batch_lyrics_edit.toPlainText().strip()
        item.setData(Qt.UserRole, text or None)
        item.setToolTip(text[:120].replace("\n", " "))
        self.update_batch_preview()

    def clear_selected_batch_lyrics(self, *args):
        item = self.audio_list.currentItem()
        self._batch_lyrics_syncing = True
        try:
            self.batch_lyrics_edit.blockSignals(True)
            self.batch_lyrics_edit.clear()
            self.batch_lyrics_edit.blockSignals(False)
            if item is not None:
                item.setData(Qt.UserRole, None)
                item.setToolTip("")
        finally:
            self._batch_lyrics_syncing = False
        self.update_batch_preview()

    def update_batch_preview(self):
        if not hasattr(self, "batch_preview"):
            return
        audio_paths = self._collect_list_paths(self.audio_list)
        lyric_paths = self._collect_list_paths(self.lyrics_list)
        # Always update counter
        if hasattr(self, "track_counter_label"):
            try:
                total = len(audio_paths)
                # Count with lyrics via jobs (handles pasted too)
                jobs_tmp = self.collect_batch_jobs() if hasattr(self, "collect_batch_jobs") else []
                with_lyric = sum(1 for j in jobs_tmp if j["lyrics_file"] or j["lyrics_text"])
                existing = 0
                for ap in audio_paths:
                    cand = Path(ap).with_suffix(".lrc")
                    cand2 = Path(ap).with_name(Path(ap).stem + "_word.lrc")
                    if cand.exists() or cand2.exists():
                        existing += 1
                missing = max(0, total - with_lyric)
                self.track_counter_label.setText(f"Tracks: {total}  •  With lyrics: {with_lyric}  •  Existing .lrc: {existing}  •  Missing: {missing}")
            except Exception:
                pass
        pairing = self.pairing_combo.currentData() or "name"
        output_dir = self.output_dir_edit.text().strip()
        lines = []
        lines.append(f"Audio: {len(audio_paths)}")
        lines.append(f"Lyrics: {len(lyric_paths)}")
        lines.append(f"Pairing: {pairing}")
        if output_dir:
            lines.append(f"Output: {output_dir}")
        lines.append("")
        jobs = self.collect_batch_jobs()
        if not jobs:
            lines.append("No batch jobs.")
        else:
            for index, job in enumerate(jobs, start=1):
                if job["lyrics_text"]:
                    lyric_label = "<pasted text>"
                elif job["lyrics_file"]:
                    lyric_label = Path(job["lyrics_file"]).name
                else:
                    lyric_label = "<missing>"
                output_label = job["output_path"] or Path(job["audio"]).with_suffix("")
                lines.append(f"{index}. {Path(job['audio']).name} -> {lyric_label}")
                lines.append(f"   out: {output_label}")
                if job["lyrics_text"]:
                    lines.append("   source: pasted text")
                elif job["lyrics_file"] is None:
                    lines.append("   warning: lyrics not matched")
        self.batch_preview.setPlainText("\n".join(lines))
        # Update track counter (grey, bold)
        if hasattr(self, "track_counter_label"):
            try:
                total = len(audio_paths)
                with_lyric = sum(1 for j in jobs if j["lyrics_file"] or j["lyrics_text"])
                existing = 0
                for ap in audio_paths:
                    cand = Path(ap).with_suffix(".lrc")
                    cand2 = Path(ap).with_name(Path(ap).stem + "_word.lrc")
                    if cand.exists() or cand2.exists():
                        existing += 1
                missing = total - with_lyric
                # Clamp missing to not negative if existing overlaps
                if missing < 0:
                    missing = 0
                self.track_counter_label.setText(f"Tracks: {total}  •  With lyrics: {with_lyric}  •  Existing .lrc: {existing}  •  Missing: {missing}")
            except Exception:
                pass

    def closeEvent(self, event):
        self.save_settings()
        super().closeEvent(event)

    def set_device_info(self, info: dict | None) -> None:
        """Show the CPU/GPU compute indicator (green dot = GPU, orange = CPU)."""
        self._device_info = info or {}
        self._refresh_device_label()

    def _refresh_device_label(self) -> None:
        if not hasattr(self, "device_label"):
            return
        info = self._device_info or {}
        is_gpu = info.get("device") == "cuda"
        dot = "●"
        name = info.get("label", "CPU" if not info else "?")
        self.device_label.setText(f"{self.text('device')}: {dot} {name}")
        color = "#7fd67f" if is_gpu else "#e0a75e"
        self.device_label.setStyleSheet(f"font-weight: bold; color: {color};")
        detail = info.get("detail", "")
        torch_v = info.get("torch_version", "")
        tip = f"{detail} (torch {torch_v})" if detail or torch_v else ""
        self.device_label.setToolTip(tip.strip())

    def append_log(self, text):
        self.log.append(text)

    def clear_log(self):
        self.log.clear()

    def set_progress(self, value):
        self.current_progress = int(value)
        self.progress_label.setText(f"{self.text('progress')} : {self.current_progress}%")
        if hasattr(self, "progress_bar"):
            self.progress_bar.setValue(self.current_progress)
