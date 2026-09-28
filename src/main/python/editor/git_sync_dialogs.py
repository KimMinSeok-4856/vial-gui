# SPDX-License-Identifier: GPL-2.0-or-later
import os
import glob
import json
import datetime
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QGroupBox, QMessageBox, QApplication, QFrame
)
from PyQt5.QtCore import Qt


class GitProgressDialog(QDialog):
    """ Modern, dark-themed modal progress dialog for Git backup and restore operations """

    def __init__(self, parent=None, title="GitHub 동기화 진행 중"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(500, 180)
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.CustomizeWindowHint)
        self.setModal(True)

        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e2e;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 8px;
            }
            QLabel {
                color: #cdd6f4;
                font-size: 13px;
            }
            QProgressBar {
                border: 1px solid #45475a;
                border-radius: 8px;
                background-color: #181825;
                text-align: center;
                color: #ffffff;
                font-weight: bold;
                font-size: 12px;
                height: 24px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1f6feb, stop:1 #238636);
                border-radius: 7px;
            }
        """)

        layout = QVBoxLayout()
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        self.lbl_title = QLabel(f"<b>{title}</b>")
        self.lbl_title.setStyleSheet("font-size: 15px; color: #89b4fa;")
        layout.addWidget(self.lbl_title)

        self.lbl_status = QLabel("동기화 작업을 시작하는 중...")
        self.lbl_status.setStyleSheet("color: #a6adc8; font-size: 12px;")
        layout.addWidget(self.lbl_status)

        self.pbar = QProgressBar()
        self.pbar.setRange(0, 100)
        self.pbar.setValue(0)
        layout.addWidget(self.pbar)

        self.lbl_detail = QLabel("")
        self.lbl_detail.setStyleSheet("color: #6c7086; font-size: 11px;")
        layout.addWidget(self.lbl_detail)

        self.setLayout(layout)

    def set_progress(self, percent: int, status_msg: str, detail_msg: str = ""):
        self.pbar.setValue(max(0, min(100, percent)))
        self.lbl_status.setText(status_msg)
        if detail_msg:
            self.lbl_detail.setText(detail_msg)
        QApplication.processEvents()


class RestoreSelectDialog(QDialog):
    """ Elegant selection dialog allowing user to choose any historical backup to restore """

    def __init__(self, parent=None, saved_dir=r"C:\vial-gui\saved_layouts"):
        super().__init__(parent)
        self.saved_dir = saved_dir
        self.selected_path = None
        self.backup_items = []

        self.setWindowTitle("📥 복원할 GitHub 레이아웃 선택")
        self.resize(780, 560)
        self.setModal(True)

        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e2e;
                color: #cdd6f4;
            }
            QLabel {
                color: #cdd6f4;
            }
            QTableWidget {
                background-color: #181825;
                color: #cdd6f4;
                border: 1px solid #313244;
                border-radius: 6px;
                gridline-color: #313244;
                selection-background-color: #313244;
                selection-color: #89b4fa;
                font-size: 12px;
            }
            QTableWidget::item {
                padding: 6px;
            }
            QTableWidget::item:selected {
                background-color: #313244;
                color: #89b4fa;
            }
            QHeaderView::section {
                background-color: #11111b;
                color: #a6adc8;
                font-weight: bold;
                padding: 6px;
                border: 1px solid #313244;
            }
            QGroupBox {
                border: 1px solid #45475a;
                border-radius: 8px;
                margin-top: 14px;
                padding-top: 12px;
                font-weight: bold;
                color: #89b4fa;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
            }
            QPushButton {
                border: 1px solid #45475a;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                background-color: #313244;
                color: #cdd6f4;
            }
            QPushButton:hover {
                background-color: #45475a;
            }
            QPushButton#btnRestore {
                background-color: #238636;
                color: #ffffff;
                border: 1px solid #2ea043;
                font-size: 13px;
                padding: 9px 20px;
            }
            QPushButton#btnRestore:hover {
                background-color: #2ea043;
            }
            QPushButton#btnRestore:disabled {
                background-color: #21262d;
                color: #484f58;
                border: 1px solid #30363d;
            }
        """)

        layout = QVBoxLayout()
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # Header
        top_hbox = QHBoxLayout()
        icon_lbl = QLabel("📦")
        icon_lbl.setStyleSheet("font-size: 26px;")
        top_hbox.addWidget(icon_lbl)

        header_vbox = QVBoxLayout()
        lbl_title = QLabel("<b>GitHub 백업 히스토리에서 복원</b>")
        lbl_title.setStyleSheet("font-size: 16px; color: #89b4fa;")
        lbl_sub = QLabel("저장된 레이아웃 목록 중 복원하고자 하는 시점의 설정을 선택하세요.")
        lbl_sub.setStyleSheet("font-size: 12px; color: #a6adc8;")
        header_vbox.addWidget(lbl_title)
        header_vbox.addWidget(lbl_sub)
        top_hbox.addLayout(header_vbox)
        top_hbox.addStretch()
        layout.addLayout(top_hbox)

        # Table of backups
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["상태", "백업 일시", "메모 / 설명", "트랙볼 DPI", "세부 구성"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        self.table.doubleClicked.connect(self.on_restore_clicked)
        layout.addWidget(self.table, stretch=3)

        # Detail preview card
        self.grp_detail = QGroupBox("선택한 레이아웃 상세 정보 미리보기")
        detail_layout = QVBoxLayout()
        detail_layout.setContentsMargins(14, 14, 14, 14)

        self.lbl_detail_info = QLabel("목록에서 백업 항목을 선택하면 상세 정보가 표시됩니다.")
        self.lbl_detail_info.setStyleSheet("font-size: 12px; line-height: 1.5; color: #cdd6f4;")
        self.lbl_detail_info.setTextFormat(Qt.RichText)
        detail_layout.addWidget(self.lbl_detail_info)

        self.grp_detail.setLayout(detail_layout)
        layout.addWidget(self.grp_detail, stretch=2)

        # Bottom buttons
        btn_layout = QHBoxLayout()
        self.btn_refresh = QPushButton("🔄 목록 새로고침")
        self.btn_refresh.clicked.connect(self.load_backups)
        btn_layout.addWidget(self.btn_refresh)

        btn_layout.addStretch()

        self.btn_cancel = QPushButton("취소")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_restore = QPushButton("📥 선택한 레이아웃 키보드에 복원")
        self.btn_restore.setObjectName("btnRestore")
        self.btn_restore.setEnabled(False)
        self.btn_restore.clicked.connect(self.on_restore_clicked)
        btn_layout.addWidget(self.btn_restore)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

        # Load data
        self.load_backups()

    def load_backups(self):
        self.backup_items = []
        self.table.setRowCount(0)
        self.btn_restore.setEnabled(False)
        self.lbl_detail_info.setText("목록에서 백업 항목을 선택하면 상세 정보가 표시됩니다.")

        if not os.path.exists(self.saved_dir):
            return

        json_files = glob.glob(os.path.join(self.saved_dir, "*.json"))
        # Exclude latest file from duplicating timestamped entries, but know which one is latest
        latest_file = os.path.join(self.saved_dir, "charybdis_layout_latest.json")
        has_latest = os.path.exists(latest_file)

        raw_list = []
        seen_timestamps = set()

        # Gather timestamped files first
        for fpath in json_files:
            fname = os.path.basename(fpath)
            if fname == "charybdis_layout_latest.json":
                continue
            try:
                with open(fpath, "r", encoding="utf-8") as inf:
                    data = json.load(inf)
                ts = data.get("backup_timestamp", "")
                mtime = os.path.getmtime(fpath)
                raw_list.append({
                    "path": fpath,
                    "filename": fname,
                    "timestamp": ts,
                    "mtime": mtime,
                    "data": data,
                    "is_latest": False
                })
                if ts:
                    seen_timestamps.add(ts)
            except Exception:
                pass

        # Sort descending by mtime
        raw_list.sort(key=lambda x: x["mtime"], reverse=True)

        # Check latest file
        if has_latest:
            try:
                with open(latest_file, "r", encoding="utf-8") as inf:
                    latest_data = json.load(inf)
                latest_ts = latest_data.get("backup_timestamp", "")
                if raw_list:
                    # Mark the first one as latest if timestamps match or top entry
                    raw_list[0]["is_latest"] = True
                else:
                    raw_list.append({
                        "path": latest_file,
                        "filename": "charybdis_layout_latest.json",
                        "timestamp": latest_ts,
                        "mtime": os.path.getmtime(latest_file),
                        "data": latest_data,
                        "is_latest": True
                    })
            except Exception:
                pass

        self.backup_items = raw_list
        self.table.setRowCount(len(self.backup_items))

        for row, item in enumerate(self.backup_items):
            d = item["data"]
            cfg = d.get("charybdis_config", {})
            memo = d.get("backup_memo", "")
            if not memo:
                memo = "자동 백업" if item["is_latest"] else "수동 백업"

            tag_item = QTableWidgetItem("⭐ 최신" if item["is_latest"] else "📄 백업")
            if item["is_latest"]:
                tag_item.setForeground(QtGui.QColor("#3fb950"))
                tag_item.setFont(QtGui.QFont("", -1, QtGui.QFont.Bold))
            else:
                tag_item.setForeground(QtGui.QColor("#8b949e"))

            ts_item = QTableWidgetItem(item["timestamp"] or "알 수 없음")
            memo_item = QTableWidgetItem(memo)

            def_dpi = cfg.get("default_dpi", 800)
            snp_dpi = cfg.get("sniping_dpi", 200)
            dpi_item = QTableWidgetItem(f"{def_dpi} / {snp_dpi} DPI")

            # Quick summary of key functions
            td_cnt = len([x for x in d.get("tap_dance", []) if any(k != "KC_NO" for k in x[:4])])
            cb_cnt = len([x for x in d.get("combo", []) if any(k != "KC_NO" for k in x[:4])])
            ov_cnt = len([x for x in d.get("key_override", []) if x.get("trigger") != "KC_NO"])
            sum_str = f"탭댄스 {td_cnt}개, 콤보 {cb_cnt}개, 오버라이드 {ov_cnt}개"
            sum_item = QTableWidgetItem(sum_str)

            self.table.setItem(row, 0, tag_item)
            self.table.setItem(row, 1, ts_item)
            self.table.setItem(row, 2, memo_item)
            self.table.setItem(row, 3, dpi_item)
            self.table.setItem(row, 4, sum_item)

        if self.backup_items:
            self.table.selectRow(0)

    def on_selection_changed(self):
        row = self.table.currentRow()
        if 0 <= row < len(self.backup_items):
            self.btn_restore.setEnabled(True)
            item = self.backup_items[row]
            self.selected_path = item["path"]
            d = item["data"]
            cfg = d.get("charybdis_config", {})
            memo = d.get("backup_memo", "메모 없음")
            ts = item["timestamp"] or "알 수 없음"

            def_dpi = cfg.get("default_dpi", 800)
            snp_dpi = cfg.get("sniping_dpi", 200)
            auto_en = "켜짐 (650ms)" if cfg.get("auto_mouse_enable", True) else "꺼짐"
            colors = cfg.get("layer_colors", {})

            c1 = colors.get("1", [255, 0, 0])
            c2 = colors.get("2", [0, 0, 255])
            c3 = colors.get("3", [180, 0, 255])

            c1_hex = f"#{c1[0]:02x}{c1[1]:02x}{c1[2]:02x}"
            c2_hex = f"#{c2[0]:02x}{c2[1]:02x}{c2[2]:02x}"
            c3_hex = f"#{c3[0]:02x}{c3[1]:02x}{c3[2]:02x}"

            td_cnt = len([x for x in d.get("tap_dance", []) if any(k != "KC_NO" for k in x[:4])])
            cb_cnt = len([x for x in d.get("combo", []) if any(k != "KC_NO" for k in x[:4])])
            ov_cnt = len([x for x in d.get("key_override", []) if x.get("trigger") != "KC_NO"])
            layers_cnt = len(d.get("layout", []))

            fsize_kb = os.path.getsize(item["path"]) / 1024.0

            html = f"""
            <table cellpadding="4" style="color: #cdd6f4; font-size: 12px;">
                <tr>
                    <td style="color: #89b4fa; font-weight: bold;">🕒 백업 일시:</td>
                    <td>{ts} &nbsp;&nbsp; <b>📝 메모:</b> <span style="color: #f9e2af;">{memo}</span></td>
                </tr>
                <tr>
                    <td style="color: #89b4fa; font-weight: bold;">🎯 트랙볼 감도:</td>
                    <td>기본 <b>{def_dpi} DPI</b> / 스나이핑 <b>{snp_dpi} DPI</b> &nbsp;|&nbsp; 오토 마우스: <b>{auto_en}</b></td>
                </tr>
                <tr>
                    <td style="color: #89b4fa; font-weight: bold;">💡 레이어 조명:</td>
                    <td>
                        Layer 1: <span style="background-color: {c1_hex}; padding: 2px 8px; border-radius: 4px; color: #fff;">{c1_hex}</span> &nbsp;
                        Layer 2: <span style="background-color: {c2_hex}; padding: 2px 8px; border-radius: 4px; color: #fff;">{c2_hex}</span> &nbsp;
                        Layer 3: <span style="background-color: {c3_hex}; padding: 2px 8px; border-radius: 4px; color: #fff;">{c3_hex}</span>
                    </td>
                </tr>
                <tr>
                    <td style="color: #89b4fa; font-weight: bold;">⌨️ 키맵 구성:</td>
                    <td>총 <b>{layers_cnt}개</b> 레이어 | 탭 댄스 <b>{td_cnt}개</b> | 콤보 <b>{cb_cnt}개</b> | 키 오버라이드 <b>{ov_cnt}개</b></td>
                </tr>
                <tr>
                    <td style="color: #6c7086;">📁 파일 위치:</td>
                    <td style="color: #6c7086;">{os.path.basename(item["path"])} ({fsize_kb:.1f} KB)</td>
                </tr>
            </table>
            """
            self.lbl_detail_info.setText(html)
        else:
            self.btn_restore.setEnabled(False)
            self.selected_path = None
            self.lbl_detail_info.setText("목록에서 백업 항목을 선택하면 상세 정보가 표시됩니다.")

    def on_restore_clicked(self):
        if self.selected_path and os.path.exists(self.selected_path):
            self.accept()
