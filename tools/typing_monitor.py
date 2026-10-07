# SPDX-License-Identifier: GPL-2.0-or-later
import sys
import os
import time
import queue
import threading
import keyboard
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QTableWidget, QTableWidgetItem, QLabel, QPushButton,
    QHeaderView, QSplitter, QFrame, QMessageBox, QGroupBox
)

# Korean vowel scancodes / key names in Qwerty layout
KOREAN_VOWELS = {
    'o': 'ㅐ', 'p': 'ㅔ', 'u': 'ㅕ', 'y': 'ㅛ', 'i': 'ㅑ',
    'h': 'ㅗ', 'j': 'ㅓ', 'k': 'ㅏ', 'l': 'ㅣ', 'n': 'ㅜ', 'm': 'ㅡ'
}
KOREAN_CONSONANTS = {
    'r': 'ㄱ', 's': 'ㄴ', 'e': 'ㄷ', 'f': 'ㄹ', 'a': 'ㅁ',
    'q': 'ㅂ', 't': 'ㅅ', 'd': 'ㅇ', 'w': 'ㅈ', 'c': 'ㅊ',
    'z': 'ㅋ', 'x': 'ㅌ', 'v': 'ㅍ', 'g': 'ㅎ'
}

event_queue = queue.Queue()

def low_level_key_hook(e):
    t = time.perf_counter()
    event_queue.put((t, e.event_type, e.name.lower(), e.scan_code))

class TypingMonitorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🔍 Charybdis 실시간 타이핑 & 롤오버 정밀 진단기")
        self.resize(1100, 720)
        self.setMinimumSize(850, 550)

        self.start_time = None
        self.events_history = []
        self.active_keys = {} # key -> press_time

        # Shift tracking
        self.shift_down_time = None
        self.last_consonant_shift_time = None
        self.last_consonant_name = None

        # Space tracking
        self.last_space_up_time = None
        self.last_space_down_time = None

        self._init_ui()
        self._start_hook()

        # Timer to consume queue
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self._process_queue)
        self.timer.start(10) # 100Hz UI poll

    def _init_ui(self):
        # Modern Dark Theme Palette
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #0d1117;
                color: #c9d1d9;
                font-family: 'Malgun Gothic', 'Segoe UI', sans-serif;
            }
            QGroupBox {
                border: 1px solid #30363d;
                border-radius: 8px;
                margin-top: 10px;
                font-weight: bold;
                font-size: 13px;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
                color: #58a6ff;
            }
            QTextEdit {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 10px;
                font-size: 15px;
                color: #f0f6fc;
            }
            QTextEdit:focus {
                border: 1px solid #58a6ff;
            }
            QTableWidget {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 6px;
                gridline-color: #21262d;
                font-size: 12px;
            }
            QHeaderView::section {
                background-color: #21262d;
                color: #8b949e;
                padding: 5px;
                border: 1px solid #30363d;
                font-weight: bold;
            }
            QPushButton {
                background-color: #21262d;
                border: 1px solid #30363d;
                border-radius: 6px;
                color: #c9d1d9;
                font-size: 12px;
                font-weight: bold;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background-color: #30363d;
                border-color: #8b949e;
            }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Header Title Banner
        header = QLabel("⚡ Charybdis 실시간 타이핑 & 롤오버 정밀 진단기")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #58a6ff;")
        main_layout.addWidget(header)

        sub_desc = QLabel(
            "아래 입력창에 평소처럼 자연스럽게 <b>'깨'</b>나 <b>'다'</b>, 또는 <b>문장을 치다가 숫자를 입력하듯 Space</b>를 눌러보세요.<br>"
            "키보드 하드웨어 스위치의 눌림/뗌 시점을 <b>0.1ms 정밀도</b>로 실시간 분석하여 오타 및 락 원인을 즉시 짚어냅니다."
        )
        sub_desc.setStyleSheet("color: #8b949e; font-size: 12px; line-height: 1.4;")
        main_layout.addWidget(sub_desc)

        # Splitter: Left (Typing & Instructions) / Right (Timeline Log)
        splitter = QSplitter(QtCore.Qt.Horizontal)
        splitter.setHandleWidth(8)

        # Left Widget
        left_widget = QWidget()
        l_layout = QVBoxLayout(left_widget)
        l_layout.setContentsMargins(0, 0, 0, 0)
        l_layout.setSpacing(10)

        grp_input = QGroupBox("✍️ 타이핑 테스트 입력창")
        in_layout = QVBoxLayout(grp_input)
        self.txt_input = QTextEdit()
        self.txt_input.setPlaceholderText("여기를 클릭하고 평소처럼 '깨'나 '다', 또는 '문장입력 후 Space 길게 누르기'를 타이핑해 보세요...")
        in_layout.addWidget(self.txt_input)
        l_layout.addWidget(grp_input)

        # Guide Card
        grp_guide = QGroupBox("🎯 테스트 추천 패턴")
        g_layout = QVBoxLayout(grp_guide)
        lbl_patterns = QLabel(
            "<b>1. '깨' 타이핑:</b><br>"
            "&nbsp;&nbsp;• <code>Shift + ㄱ(r)</code> 누른 뒤 빠르게 <code>ㅐ(o)</code> 입력<br>"
            "&nbsp;&nbsp;• 엄지가 Shift를 미처 다 못 뗐는지 겹침 시간(Overlap ms) 측정<br><br>"
            "<b>2. 'Space ➔ 레이어2' 타이핑:</b><br>"
            "&nbsp;&nbsp;• <code>'단어입력 '</code> (Space 단타) 직후 곧바로 <code>Space 꾹 누르기</code><br>"
            "&nbsp;&nbsp;• 스페이스를 뗀 후 다시 누르기까지의 간격(Delta ms) 측정 (Quick Tap Term 판정)"
        )
        lbl_patterns.setStyleSheet("font-size: 12px; color: #a5d6ff; line-height: 1.5;")
        g_layout.addWidget(lbl_patterns)
        l_layout.addWidget(grp_guide)

        splitter.addWidget(left_widget)

        # Right Widget (Event Timeline Table)
        right_widget = QWidget()
        r_layout = QVBoxLayout(right_widget)
        r_layout.setContentsMargins(0, 0, 0, 0)
        r_layout.setSpacing(10)

        grp_timeline = QGroupBox("⏱️ 실시간 스위치 이벤트 타임라인 (0.1ms 정밀 계측)")
        t_layout = QVBoxLayout(grp_timeline)
        self.tbl_events = QTableWidget()
        self.tbl_events.setColumnCount(5)
        self.tbl_events.setHorizontalHeaderLabels(["시간 (Time)", "키 (Key)", "상태 (Action)", "유지/간격 (Duration)", "실시간 진단 (Diagnostics)"])
        self.tbl_events.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tbl_events.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tbl_events.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tbl_events.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.tbl_events.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        t_layout.addWidget(self.tbl_events)
        r_layout.addWidget(grp_timeline)

        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 6)
        main_layout.addWidget(splitter, 1)

        # Bottom Diagnosis Banner
        self.grp_diag = QGroupBox("🚨 실시간 AI 진단 결과")
        d_layout = QVBoxLayout(self.grp_diag)
        self.lbl_diagnosis = QLabel("키 입력을 시작하면 여기에 실시간 정밀 분석 결과가 나타납니다.")
        self.lbl_diagnosis.setWordWrap(True)
        self.lbl_diagnosis.setStyleSheet("color: #7ee787; font-size: 13px; font-weight: bold;")
        d_layout.addWidget(self.lbl_diagnosis)
        main_layout.addWidget(self.grp_diag)

        # Action Buttons
        h_btns = QHBoxLayout()
        h_btns.setSpacing(8)

        self.btn_clear = QPushButton("🗑️ 기록 지우기")
        self.btn_clear.clicked.connect(self.clear_all)
        h_btns.addWidget(self.btn_clear)

        self.btn_save_log = QPushButton("💾 진단 로그 파일 저장 (AI 분석 전달용)")
        self.btn_save_log.setStyleSheet("background-color: #238636; color: white;")
        self.btn_save_log.clicked.connect(self.save_log)
        h_btns.addWidget(self.btn_save_log)

        self.btn_copy = QPushButton("📋 결과 복사")
        self.btn_copy.clicked.connect(self.copy_to_clipboard)
        h_btns.addWidget(self.btn_copy)

        h_btns.addStretch()
        main_layout.addLayout(h_btns)

    def _start_hook(self):
        try:
            keyboard.hook(low_level_key_hook)
        except Exception as e:
            QMessageBox.critical(self, "오류", f"키보드 후크 등록 실패: {e}")

    def closeEvent(self, event):
        try:
            keyboard.unhook_all()
        except Exception:
            pass
        super().closeEvent(event)

    def _process_queue(self):
        updated = False
        while not event_queue.empty():
            t, ev_type, key_name, scan_code = event_queue.get()
            if self.start_time is None:
                self.start_time = t

            rel_ms = (t - self.start_time) * 1000.0
            self._handle_event(t, rel_ms, ev_type, key_name, scan_code)
            updated = True

        if updated:
            self.tbl_events.scrollToBottom()

    def _handle_event(self, t, rel_ms, ev_type, key_name, scan_code):
        is_down = (ev_type == 'down')
        is_shift = ('shift' in key_name)
        is_space = (key_name == 'space')

        diag_msg = ""
        diag_color = "#c9d1d9"
        duration_str = "-"

        # Han label mapping
        han_label = ""
        if key_name in KOREAN_CONSONANTS:
            han_label = f" ({KOREAN_CONSONANTS[key_name]})"
        elif key_name in KOREAN_VOWELS:
            han_label = f" ({KOREAN_VOWELS[key_name]})"

        display_name = f"{key_name.upper()}{han_label}"

        if is_down:
            self.active_keys[key_name] = t

            if is_shift:
                self.shift_down_time = t
                diag_msg = "Shift 누름 시작"

            elif is_space:
                self.last_space_down_time = t
                if self.last_space_up_time is not None:
                    delta_ms = (t - self.last_space_up_time) * 1000.0
                    duration_str = f"이전 뗌 후 +{delta_ms:.1f}ms"
                    if delta_ms < 200.0:
                        diag_msg = f"⚠️ [Quick Tap Term 락 위험!] 이전 Space 뗌 후 {delta_ms:.1f}ms 만에 재입력됨! (200ms 이내 ➔ 레이어2 씹히고 스페이스 연타로 고정됨)"
                        diag_color = "#f85149"
                        self.set_banner(diag_msg, is_error=True)
                    else:
                        diag_msg = f"✅ 정상 Space 누름 (+{delta_ms:.1f}ms ➔ 200ms 초과이므로 정상 레이어2 진입)"
                        diag_color = "#7ee787"
                else:
                    diag_msg = "Space 누름"

            else:
                # Other normal keys
                if self.shift_down_time is not None:
                    # Key pressed while Shift is still held!
                    shift_held_ms = (t - self.shift_down_time) * 1000.0
                    if key_name in KOREAN_VOWELS:
                        han_char = KOREAN_VOWELS[key_name]
                        if self.last_consonant_shift_time is not None:
                            consonant_diff = (t - self.last_consonant_shift_time) * 1000.0
                            if consonant_diff < 300.0:
                                diag_msg = f"🚨 [시프트 롤오버 오타 발생!] 자음({self.last_consonant_name}) 친 후 {consonant_diff:.1f}ms 뒤 모음 '{han_char}' 입력 시점에 Shift가 아직 눌려있음! (원인: 엄지 뗌 딜레이 ➔ '꺠' 오타 유발)"
                                diag_color = "#f85149"
                                self.set_banner(diag_msg, is_error=True)
                        else:
                            diag_msg = f"Shift + 모음 '{han_char}' 조합 중 (Shift 유지: {shift_held_ms:.1f}ms)"
                    elif key_name in KOREAN_CONSONANTS:
                        self.last_consonant_shift_time = t
                        self.last_consonant_name = f"{key_name.upper()}({KOREAN_CONSONANTS[key_name]})"
                        diag_msg = f"Shift + 자음 '{KOREAN_CONSONANTS[key_name]}' ➔ 쌍자음 입력 (정상)"
                        diag_color = "#58a6ff"
                else:
                    diag_msg = "일반 키 입력"

        else: # is_up
            press_t = self.active_keys.pop(key_name, None)
            if press_t is not None:
                hold_ms = (t - press_t) * 1000.0
                duration_str = f"{hold_ms:.1f}ms 유지"

            if is_shift:
                self.shift_down_time = None
                diag_msg = "Shift 손에서 뗌 (해제 완료)"
                diag_color = "#8b949e"

            elif is_space:
                self.last_space_up_time = t
                diag_msg = "Space 손에서 뗌"

        # Add to table
        row = self.tbl_events.rowCount()
        self.tbl_events.insertRow(row)

        item_time = QTableWidgetItem(f"{rel_ms:+.1f} ms")
        item_key = QTableWidgetItem(display_name)
        item_act = QTableWidgetItem("🔻 누름 (DOWN)" if is_down else "🔺 뗌 (UP)")
        item_dur = QTableWidgetItem(duration_str)
        item_diag = QTableWidgetItem(diag_msg)

        item_time.setTextAlignment(QtCore.Qt.AlignCenter)
        item_key.setTextAlignment(QtCore.Qt.AlignCenter)
        item_act.setTextAlignment(QtCore.Qt.AlignCenter)
        item_dur.setTextAlignment(QtCore.Qt.AlignCenter)

        if diag_color != "#c9d1d9":
            brush = QtGui.QBrush(QtGui.QColor(diag_color))
            item_diag.setForeground(brush)
            if is_down and ("🚨" in diag_msg or "⚠️" in diag_msg):
                item_key.setForeground(brush)

        self.tbl_events.setItem(row, 0, item_time)
        self.tbl_events.setItem(row, 1, item_key)
        self.tbl_events.setItem(row, 2, item_act)
        self.tbl_events.setItem(row, 3, item_dur)
        self.tbl_events.setItem(row, 4, item_diag)

        self.events_history.append({
            "rel_ms": rel_ms,
            "key": display_name,
            "action": "DOWN" if is_down else "UP",
            "duration": duration_str,
            "diagnostic": diag_msg
        })

    def set_banner(self, text, is_error=False):
        color = "#f85149" if is_error else "#7ee787"
        self.lbl_diagnosis.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: bold; line-height: 1.4;")
        self.lbl_diagnosis.setText(text)

    def clear_all(self):
        self.start_time = None
        self.events_history.clear()
        self.active_keys.clear()
        self.shift_down_time = None
        self.last_consonant_shift_time = None
        self.last_space_up_time = None
        self.last_space_down_time = None
        self.tbl_events.setRowCount(0)
        self.txt_input.clear()
        self.set_banner("기록이 초기화되었습니다. 다시 타이핑해 보세요.")

    def copy_to_clipboard(self):
        if not self.events_history:
            return
        lines = [f"{e['rel_ms']:+8.1f}ms | {e['key']:<12} | {e['action']:<4} | {e['duration']:<15} | {e['diagnostic']}" for e in self.events_history]
        QApplication.clipboard().setText("\n".join(lines))
        QMessageBox.information(self, "완료", "진단 로그가 클립보드에 복사되었습니다!")

    def save_log(self):
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        filepath = os.path.join(desktop, "typing_diagnostic_log.txt")
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("=== Charybdis 실시간 타이핑 & 롤오버 정밀 진단 로그 ===\n")
                f.write(f"생성 일시: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write(f"{'시간':<12} | {'키':<14} | {'상태':<6} | {'유지/간격':<16} | {'진단 내용'}\n")
                f.write("-" * 80 + "\n")
                for e in self.events_history:
                    f.write(f"{e['rel_ms']:+8.1f}ms | {e['key']:<14} | {e['action']:<6} | {e['duration']:<16} | {e['diagnostic']}\n")
            QMessageBox.information(self, "저장 완료", f"바탕화면에 진단 로그가 성공적으로 저장되었습니다!\n\n파일 경로:\n{filepath}")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"로그 파일 저장 실패: {e}")

def main():
    app = QApplication(sys.argv)
    win = TypingMonitorWindow()
    win.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
