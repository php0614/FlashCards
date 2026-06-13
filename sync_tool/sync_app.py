#!/usr/bin/env python3
"""
FlashCards CSV Sync
===================
A small GUI tool to sync the local vocabulary file

    <Dropbox>/Books/_IntensiveReadings/_Eng/words.csv      (English, Korean Definition, Example Sentence)

with the master CSV stored in Supabase Storage

    bucket: csv-data   file: flashcards_words.csv          (word, meaning, example, prob)

It shows both lists side by side, highlights the differences, and can
overwrite the local file with the online version, or the online file with
the local version.

Runs on Windows and macOS (Dropbox path is detected automatically).
"""

import csv
import io
import sys
import platform

import requests
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QAbstractItemView, QFrame,
)

# --------------------------------------------------------------------------
# Config  (same Supabase project the HTML flashcard app uses)
# --------------------------------------------------------------------------
SUPABASE_URL = "https://upqnxyllnenivehmallp.supabase.co"
SUPABASE_KEY = "sb_publishable_o7KDz58nXdjLN7TwOw2Xhg_VBWzOccH"
BUCKET       = "csv-data"
DATA_FILE    = "flashcards_words.csv"


def dropbox_root() -> str:
    """Return the Dropbox root for the current OS."""
    return "/Volumes/Work/Dropbox" if platform.system() == "Darwin" else "D:/Dropbox"


LOCAL_CSV = dropbox_root() + "/Books/_IntensiveReadings/_Eng/words.csv"

PUBLIC_URL = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{DATA_FILE}"
OBJECT_URL = f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{DATA_FILE}"

# Colors for diff highlighting
C_SAME    = QColor("#ffffff")
C_DIFF    = QColor("#fff4cc")   # amber  - present both sides, content differs
C_LOCAL   = QColor("#d8f5dd")   # green  - only in local
C_ONLINE  = QColor("#d6e8ff")   # blue   - only online
C_MISSING = QColor("#f3f3f3")   # grey   - the empty counterpart cell


# --------------------------------------------------------------------------
# Data helpers
# --------------------------------------------------------------------------
def norm(s: str) -> str:
    return (s or "").strip()


def key_of(word: str) -> str:
    return norm(word).lower()


def read_local():
    """Return list of dicts {word, meaning, example} from the local file."""
    rows = []
    try:
        with open(LOCAL_CSV, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f)
            data = list(reader)
    except FileNotFoundError:
        return rows
    if not data:
        return rows
    start = 0
    h0 = norm(data[0][0]).lower() if data[0] else ""
    if h0 in ("english", "word"):
        start = 1
    for r in data[start:]:
        if not r or not norm(r[0]):
            continue
        prob = None
        if len(r) > 3 and norm(r[3]):
            try:
                prob = float(r[3])
            except ValueError:
                prob = None
        rows.append({
            "word":    norm(r[0]),
            "meaning": norm(r[1]) if len(r) > 1 else "",
            "example": norm(r[2]) if len(r) > 2 else "",
            "prob":    prob,          # None until a Probability column exists
        })
    return rows


def parse_online_csv(text: str):
    """Return list of dicts {word, meaning, example, prob}."""
    rows = []
    reader = csv.reader(io.StringIO(text))
    data = list(reader)
    if not data:
        return rows
    start = 0
    h0 = norm(data[0][0]).lower() if data[0] else ""
    if h0 in ("word", "english"):
        start = 1
    for r in data[start:]:
        if not r or not norm(r[0]):
            continue
        prob = 50.0
        if len(r) > 3 and norm(r[3]):
            try:
                prob = float(r[3])
            except ValueError:
                prob = 50.0
        rows.append({
            "word":    norm(r[0]),
            "meaning": norm(r[1]) if len(r) > 1 else "",
            "example": norm(r[2]) if len(r) > 2 else "",
            "prob":    prob,
        })
    return rows


def read_online():
    """Download and parse the online CSV. Returns [] if the file does not exist."""
    resp = requests.get(PUBLIC_URL, params={"t": "nocache"},
                        headers={"Cache-Control": "no-cache"}, timeout=20)
    if resp.status_code in (400, 404):   # object not found yet
        return []
    resp.raise_for_status()
    # Supabase serves the CSV without a charset, so requests would default to
    # latin-1 and mangle the Korean. Decode the raw bytes as UTF-8 explicitly.
    text = resp.content.decode("utf-8-sig", errors="replace")
    return parse_online_csv(text)


def write_local(rows):
    """Write rows to the local file (4 columns incl. Probability).
    A blank probability cell is written when a row has no probability yet."""
    with open(LOCAL_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["English", "Korean Definition", "Example Sentence", "Probability"])
        for r in rows:
            p = r.get("prob")
            pcell = "" if p is None else round(float(p) * 100) / 100
            w.writerow([r["word"], r.get("meaning", ""), r.get("example", ""), pcell])


def build_online_csv(rows, prob_lookup):
    """rows: list of {word, meaning, example}.  prob_lookup: {key: prob}."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["word", "meaning", "example", "prob"])
    for r in rows:
        prob = prob_lookup.get(key_of(r["word"]), 50.0)
        w.writerow([r["word"], r.get("meaning", ""), r.get("example", ""),
                    round(prob * 100) / 100])
    return buf.getvalue()


def upload_online(csv_text: str):
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "text/csv; charset=utf-8",
        "x-upsert": "true",
        "cache-control": "no-cache",
    }
    resp = requests.post(OBJECT_URL, headers=headers,
                         data=csv_text.encode("utf-8"), timeout=30)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Upload failed ({resp.status_code}): {resp.text}")


def online_rows_to_csv(rows):
    """Serialize already-parsed online rows ({word, meaning, example, prob})."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["word", "meaning", "example", "prob"])
    for r in rows:
        prob = r.get("prob", 50.0)
        if prob is None:
            prob = 50.0
        w.writerow([r["word"], r.get("meaning", ""), r.get("example", ""),
                    round(prob * 100) / 100])
    return buf.getvalue()


def sync_prob_online_to_local(local_rows, online_rows):
    """Copy probabilities online -> local for words in both lists, leaving the
    local word/definition/example untouched, then rewrite the local file.
    Returns the number of words updated."""
    online_prob = {key_of(r["word"]): r["prob"] for r in online_rows}
    updated = 0
    for r in local_rows:
        k = key_of(r["word"])
        if k in online_prob:
            r["prob"] = online_prob[k]
            updated += 1
    write_local(local_rows)
    return updated


def sync_prob_local_to_online(local_rows, online_rows):
    """Copy probabilities local -> online for words in both lists, leaving the
    online word/meaning/example untouched, then upload.
    Returns the number of words updated."""
    local_prob = {key_of(r["word"]): r["prob"]
                  for r in local_rows if r.get("prob") is not None}
    updated = 0
    for r in online_rows:
        k = key_of(r["word"])
        if k in local_prob:
            r["prob"] = local_prob[k]
            updated += 1
    upload_online(online_rows_to_csv(online_rows))
    return updated


def merge_local_to_online(local_rows, online_rows):
    """Append words that exist ONLY locally to the online list (word + meaning +
    example, plus the local probability or 50% default). Existing online
    entries are never overwritten or removed. Returns number of words added."""
    online_keys = {key_of(r["word"]) for r in online_rows}
    merged = list(online_rows)
    added = 0
    for r in local_rows:
        k = key_of(r["word"])
        if k not in online_keys:
            prob = r.get("prob")
            merged.append({
                "word":    r["word"],
                "meaning": r.get("meaning", ""),
                "example": r.get("example", ""),
                "prob":    50.0 if prob is None else prob,
            })
            online_keys.add(k)
            added += 1
    if added:
        upload_online(online_rows_to_csv(merged))
    return added


def merge_online_to_local(local_rows, online_rows):
    """Append words that exist ONLY online to the local file (word + meaning +
    example + probability). Existing local entries are never overwritten or
    removed. Returns number of words added."""
    local_keys = {key_of(r["word"]) for r in local_rows}
    merged = list(local_rows)
    added = 0
    for r in online_rows:
        k = key_of(r["word"])
        if k not in local_keys:
            merged.append({
                "word":    r["word"],
                "meaning": r.get("meaning", ""),
                "example": r.get("example", ""),
                "prob":    r.get("prob"),
            })
            local_keys.add(k)
            added += 1
    if added:
        write_local(merged)
    return added


# --------------------------------------------------------------------------
# GUI
# --------------------------------------------------------------------------
class SyncWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FlashCards CSV Sync")
        self.resize(1180, 720)
        self.local = []
        self.online = []

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        # --- header / paths ---
        title = QLabel("FlashCards CSV Sync")
        title.setFont(QFont("Helvetica Neue", 18, QFont.Bold))
        root.addWidget(title)

        paths = QLabel(f"Local:  {LOCAL_CSV}\nOnline:  {BUCKET}/{DATA_FILE}")
        paths.setStyleSheet("color:#666; font-size:12px;")
        root.addWidget(paths)

        # --- summary line ---
        self.summary = QLabel("Click Refresh to load both lists.")
        self.summary.setStyleSheet("font-size:13px; padding:6px 0;")
        root.addWidget(self.summary)

        # --- legend ---
        legend = QHBoxLayout()
        for color, text in [(C_LOCAL, "only local"), (C_ONLINE, "only online"),
                            (C_DIFF, "differs"), (C_SAME, "identical")]:
            chip = QLabel("  " + text + "  ")
            chip.setStyleSheet(
                f"background:{color.name()}; border:1px solid #ccc; "
                f"border-radius:4px; font-size:11px; padding:2px 6px;")
            legend.addWidget(chip)
        legend.addStretch(1)
        root.addLayout(legend)

        # --- the two tables ---
        tables = QHBoxLayout()
        tables.setSpacing(10)

        self.local_tbl = self._make_table(
            ["Word", "Definition", "Example", "%"], "LOCAL  (words.csv)")
        self.online_tbl = self._make_table(
            ["Word", "Definition", "Example", "%"], "ONLINE  (Supabase)")

        for box in (self.local_box, self.online_box):
            tables.addWidget(box, 1)
        root.addLayout(tables, 1)

        # keep the two tables scrolling together
        self.local_tbl.verticalScrollBar().valueChanged.connect(
            self.online_tbl.verticalScrollBar().setValue)
        self.online_tbl.verticalScrollBar().valueChanged.connect(
            self.local_tbl.verticalScrollBar().setValue)

        # --- buttons ---
        btns = QHBoxLayout()
        self.btn_refresh = QPushButton("↻  Refresh")
        self.btn_to_online = QPushButton("Local  →  Online  ⬆   (overwrite cloud)")
        self.btn_to_local = QPushButton("Online  →  Local  ⬇   (overwrite file)")

        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_to_online.clicked.connect(self.push_local_to_online)
        self.btn_to_local.clicked.connect(self.pull_online_to_local)

        for b in (self.btn_refresh, self.btn_to_online, self.btn_to_local):
            b.setMinimumHeight(40)
            b.setStyleSheet("font-size:13px; font-weight:600; padding:6px 14px;")
        self.btn_to_online.setStyleSheet(
            "font-size:13px; font-weight:700; padding:6px 14px;"
            "background:#3b82f6; color:white; border-radius:6px;")
        self.btn_to_local.setStyleSheet(
            "font-size:13px; font-weight:700; padding:6px 14px;"
            "background:#0a8f6a; color:white; border-radius:6px;")

        btns.addWidget(self.btn_refresh)
        btns.addStretch(1)
        btns.addWidget(self.btn_to_online)
        btns.addWidget(self.btn_to_local)
        root.addLayout(btns)

        # --- probability-only buttons ---
        prob_btns = QHBoxLayout()
        plbl = QLabel("Probability only  (never touches word / definition / example):")
        plbl.setStyleSheet("font-size:12px; color:#666;")
        self.btn_prob_to_online = QPushButton("% Prob  ⬆  local → online")
        self.btn_prob_to_local = QPushButton("% Prob  ⬇  online → local")
        self.btn_prob_to_online.clicked.connect(self.push_prob_to_online)
        self.btn_prob_to_local.clicked.connect(self.pull_prob_to_local)
        for b in (self.btn_prob_to_online, self.btn_prob_to_local):
            b.setMinimumHeight(34)
            b.setStyleSheet("font-size:12px; font-weight:600; padding:5px 12px;")
        prob_btns.addWidget(plbl)
        prob_btns.addStretch(1)
        prob_btns.addWidget(self.btn_prob_to_online)
        prob_btns.addWidget(self.btn_prob_to_local)
        root.addLayout(prob_btns)

        # --- merge buttons (add only the missing words; nothing overwritten) ---
        merge_btns = QHBoxLayout()
        mlbl = QLabel("Merge  (add only words missing on one side; nothing is overwritten):")
        mlbl.setStyleSheet("font-size:12px; color:#666;")
        self.btn_merge_to_online = QPushButton("Merge  ⬆  local → online")
        self.btn_merge_to_local = QPushButton("Merge  ⬇  online → local")
        self.btn_merge_to_online.clicked.connect(self.merge_local_to_online_action)
        self.btn_merge_to_local.clicked.connect(self.merge_online_to_local_action)
        for b in (self.btn_merge_to_online, self.btn_merge_to_local):
            b.setMinimumHeight(34)
            b.setStyleSheet("font-size:12px; font-weight:600; padding:5px 12px;")
        merge_btns.addWidget(mlbl)
        merge_btns.addStretch(1)
        merge_btns.addWidget(self.btn_merge_to_online)
        merge_btns.addWidget(self.btn_merge_to_local)
        root.addLayout(merge_btns)

        self.refresh()

    # -- helpers --------------------------------------------------------
    def _make_table(self, headers, caption):
        box = QFrame()
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(4)
        cap = QLabel(caption)
        cap.setStyleSheet("font-weight:700; font-size:13px; color:#333;")
        v.addWidget(cap)
        tbl = QTableWidget(0, len(headers))
        tbl.setHorizontalHeaderLabels(headers)
        tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tbl.setSelectionMode(QAbstractItemView.NoSelection)
        tbl.verticalHeader().setVisible(False)
        hh = tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.Interactive)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        if len(headers) == 4:
            hh.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        tbl.setColumnWidth(1, 200)
        tbl.setWordWrap(False)
        v.addWidget(tbl)
        if caption.startswith("LOCAL"):
            self.local_box = box
        else:
            self.online_box = box
        return tbl

    def _set_cell(self, tbl, row, col, text, color):
        item = QTableWidgetItem(text)
        item.setBackground(color)
        item.setToolTip(text)
        tbl.setItem(row, col, item)

    # -- actions --------------------------------------------------------
    def refresh(self):
        self.summary.setText("Loading…")
        QApplication.processEvents()
        try:
            self.local = read_local()
        except Exception as e:
            QMessageBox.critical(self, "Local read error", str(e))
            self.local = []
        try:
            self.online = read_online()
        except Exception as e:
            QMessageBox.critical(self, "Online read error", str(e))
            self.online = []
        self.render_diff()

    def render_diff(self):
        local_map = {key_of(r["word"]): r for r in self.local}
        online_map = {key_of(r["word"]): r for r in self.online}

        # ordered union of keys: local order first, then online-only
        keys = []
        seen = set()
        for r in self.local:
            k = key_of(r["word"])
            if k not in seen:
                seen.add(k); keys.append(k)
        for r in self.online:
            k = key_of(r["word"])
            if k not in seen:
                seen.add(k); keys.append(k)

        n_same = n_diff = n_local = n_online = 0
        self.local_tbl.setRowCount(len(keys))
        self.online_tbl.setRowCount(len(keys))

        for i, k in enumerate(keys):
            lo = local_map.get(k)
            on = online_map.get(k)

            if lo and on:
                differs = (norm(lo["meaning"]) != norm(on["meaning"]) or
                           norm(lo["example"]) != norm(on["example"]) or
                           norm(lo["word"]) != norm(on["word"]))
                color = C_DIFF if differs else C_SAME
                if differs:
                    n_diff += 1
                else:
                    n_same += 1
                self._set_cell(self.local_tbl, i, 0, lo["word"], color)
                self._set_cell(self.local_tbl, i, 1, lo["meaning"], color)
                self._set_cell(self.local_tbl, i, 2, lo["example"], color)
                self._set_cell(self.local_tbl, i, 3,
                               "" if lo.get("prob") is None else f'{lo["prob"]:.0f}', color)
                self._set_cell(self.online_tbl, i, 0, on["word"], color)
                self._set_cell(self.online_tbl, i, 1, on["meaning"], color)
                self._set_cell(self.online_tbl, i, 2, on["example"], color)
                self._set_cell(self.online_tbl, i, 3, f'{on["prob"]:.0f}', color)
            elif lo and not on:
                n_local += 1
                self._set_cell(self.local_tbl, i, 0, lo["word"], C_LOCAL)
                self._set_cell(self.local_tbl, i, 1, lo["meaning"], C_LOCAL)
                self._set_cell(self.local_tbl, i, 2, lo["example"], C_LOCAL)
                self._set_cell(self.local_tbl, i, 3,
                               "" if lo.get("prob") is None else f'{lo["prob"]:.0f}', C_LOCAL)
                for c in range(4):
                    self._set_cell(self.online_tbl, i, c, "", C_MISSING)
            else:  # online only
                n_online += 1
                for c in range(4):
                    self._set_cell(self.local_tbl, i, c, "", C_MISSING)
                self._set_cell(self.online_tbl, i, 0, on["word"], C_ONLINE)
                self._set_cell(self.online_tbl, i, 1, on["meaning"], C_ONLINE)
                self._set_cell(self.online_tbl, i, 2, on["example"], C_ONLINE)
                self._set_cell(self.online_tbl, i, 3, f'{on["prob"]:.0f}', C_ONLINE)

        self.summary.setText(
            f"Local: {len(self.local)} words   •   Online: {len(self.online)} words   "
            f"•   <b>{n_same}</b> identical, <b style='color:#c08a00'>{n_diff}</b> differ, "
            f"<b style='color:#1a8a3a'>{n_local}</b> only local, "
            f"<b style='color:#1565c0'>{n_online}</b> only online")

    def push_local_to_online(self):
        if not self.local:
            QMessageBox.warning(self, "Nothing to push", "The local list is empty.")
            return
        if QMessageBox.question(
                self, "Overwrite cloud?",
                f"This replaces the ONLINE list with the {len(self.local)} local words.\n"
                "Existing probabilities are kept for matching words; new words start at 50%.\n\n"
                "Continue?") != QMessageBox.Yes:
            return
        prob_lookup = {key_of(r["word"]): r["prob"] for r in self.online}
        csv_text = build_online_csv(self.local, prob_lookup)
        try:
            upload_online(csv_text)
        except Exception as e:
            QMessageBox.critical(self, "Upload error", str(e))
            return
        QMessageBox.information(self, "Done", "Online list overwritten from local. ✅")
        self.refresh()

    def pull_online_to_local(self):
        if not self.online:
            QMessageBox.warning(self, "Nothing to pull", "The online list is empty.")
            return
        if QMessageBox.question(
                self, "Overwrite local file?",
                f"This replaces the LOCAL file\n{LOCAL_CSV}\n"
                f"with the {len(self.online)} online words.\n\n"
                "Continue?") != QMessageBox.Yes:
            return
        try:
            write_local(self.online)
        except Exception as e:
            QMessageBox.critical(self, "Write error", str(e))
            return
        QMessageBox.information(self, "Done", "Local file overwritten from online. ✅")
        self.refresh()

    def push_prob_to_online(self):
        if not self.online:
            QMessageBox.warning(self, "No online list",
                                "The online list is empty — nothing to update.")
            return
        if not any(r.get("prob") is not None for r in self.local):
            QMessageBox.information(
                self, "No local probabilities",
                "Your local words.csv has no Probability column yet.\n\n"
                "Run  % Prob ⬇ online → local  first to create it, then you can "
                "push probabilities back up.")
            return
        if QMessageBox.question(
                self, "Push probabilities?",
                "Update ONLY the probability values online, using the local "
                "Probability column, for words present in both lists.\n\n"
                "Online word / definition / example are left unchanged.\n\nContinue?"
            ) != QMessageBox.Yes:
            return
        try:
            n = sync_prob_local_to_online(self.local, self.online)
        except Exception as e:
            QMessageBox.critical(self, "Upload error", str(e))
            return
        QMessageBox.information(self, "Done",
                                f"Updated {n} probabilities online. ✅")
        self.refresh()

    def pull_prob_to_local(self):
        if not self.online:
            QMessageBox.warning(self, "No online list",
                                "The online list is empty — nothing to copy.")
            return
        if not self.local:
            QMessageBox.warning(self, "No local file",
                                "The local file is empty — nothing to update.")
            return
        if QMessageBox.question(
                self, "Pull probabilities?",
                "Write ONLY the probability column into the local words.csv from "
                "online, for words present in both lists.\n\n"
                "Local word / definition / example stay as they are "
                "(a 'Probability' column is added if missing).\n\nContinue?"
            ) != QMessageBox.Yes:
            return
        try:
            n = sync_prob_online_to_local(self.local, self.online)
        except Exception as e:
            QMessageBox.critical(self, "Write error", str(e))
            return
        QMessageBox.information(self, "Done",
                                f"Updated {n} probabilities in the local file. ✅")
        self.refresh()

    def merge_local_to_online_action(self):
        if not self.local:
            QMessageBox.warning(self, "No local file", "The local file is empty.")
            return
        online_keys = {key_of(r["word"]) for r in self.online}
        missing = [r for r in self.local if key_of(r["word"]) not in online_keys]
        if not missing:
            QMessageBox.information(self, "Nothing to merge",
                                    "Every local word already exists online.")
            return
        if QMessageBox.question(
                self, "Merge into online?",
                f"Add {len(missing)} word(s) that exist only in the local file to "
                "the online list (with their definition and example).\n\n"
                "Nothing online is overwritten or removed; new words start at 50% "
                "(or their local probability, if set).\n\nContinue?"
            ) != QMessageBox.Yes:
            return
        try:
            n = merge_local_to_online(self.local, self.online)
        except Exception as e:
            QMessageBox.critical(self, "Upload error", str(e))
            return
        QMessageBox.information(self, "Done", f"Added {n} word(s) to the online list. ✅")
        self.refresh()

    def merge_online_to_local_action(self):
        if not self.online:
            QMessageBox.warning(self, "No online list", "The online list is empty.")
            return
        local_keys = {key_of(r["word"]) for r in self.local}
        missing = [r for r in self.online if key_of(r["word"]) not in local_keys]
        if not missing:
            QMessageBox.information(self, "Nothing to merge",
                                    "Every online word already exists locally.")
            return
        if QMessageBox.question(
                self, "Merge into local file?",
                f"Add {len(missing)} word(s) that exist only online to the local "
                "words.csv (with their definition, example and probability).\n\n"
                "Nothing in the local file is overwritten or removed.\n\nContinue?"
            ) != QMessageBox.Yes:
            return
        try:
            n = merge_online_to_local(self.local, self.online)
        except Exception as e:
            QMessageBox.critical(self, "Write error", str(e))
            return
        QMessageBox.information(self, "Done", f"Added {n} word(s) to the local file. ✅")
        self.refresh()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    # Use a font with Korean glyph coverage so Hangul renders cleanly.
    app.setFont(QFont("Malgun Gothic" if platform.system() == "Windows"
                      else "Apple SD Gothic Neo", 10))
    win = SyncWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
