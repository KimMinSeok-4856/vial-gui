# SPDX-License-Identifier: GPL-2.0-or-later
import sys
import time
import random
import statistics
from collections import deque

from PyQt5 import QtCore, QtGui
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QWidget, QFrame, QProgressBar, QSizePolicy, QSpinBox, QApplication
)

from editor.basic_editor import BasicEditor
from util import make_scrollable
from vial_device import VialKeyboard

# Win32 RawInput definitions
IS_WINDOWS = sys.platform.startswith("win")
if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    class RAWINPUTDEVICE(ctypes.Structure):
        _fields_ = [
            ("usUsagePage", wintypes.USHORT),
            ("usUsage", wintypes.USHORT),
            ("dwFlags", wintypes.DWORD),
            ("hwndTarget", wintypes.HWND)
        ]

    class RAWINPUTHEADER(ctypes.Structure):
        _fields_ = [
            ("dwType", wintypes.DWORD),
            ("dwSize", wintypes.DWORD),
            ("hDevice", wintypes.HANDLE),
            ("wParam", wintypes.WPARAM)
        ]

    class RAWKEYBOARD(ctypes.Structure):
        _fields_ = [
            ("MakeCode", wintypes.USHORT),
            ("Flags", wintypes.USHORT),
            ("Reserved", wintypes.USHORT),
            ("VKey", wintypes.USHORT),
            ("Message", wintypes.UINT),
            ("ExtraInformation", wintypes.ULONG)
        ]

    class RAWMOUSE(ctypes.Structure):
        _fields_ = [
            ("usFlags", wintypes.USHORT),
            ("usButtonFlags", wintypes.USHORT),
            ("usButtonData", wintypes.USHORT),
            ("ulRawButtons", wintypes.ULONG),
            ("lLastX", wintypes.LONG),
            ("lLastY", wintypes.LONG),
            ("ulExtraInformation", wintypes.ULONG)
        ]


class PerformanceInputListener(QWidget):
    """
    High-performance RawInput and Qt event listener that captures
    microsecond-accurate hardware reports from Keyboard and Mouse/Trackball.
    """
    key_packet_signal = pyqtSignal(float, str, bool) # timestamp, key_name, is_down
    mouse_packet_signal = pyqtSignal(float, int, int) # timestamp, dx, dy

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)
        self.raw_input_registered = False

    def register_raw_input(self):
        if not IS_WINDOWS or self.raw_input_registered:
            return
        try:
            # 0x01, 0x02 = Mouse / Trackball | 0x01, 0x06 = Keyboard
            # RIDEV_INPUTSINK (0x00000100) allows receiving input even when not focused
            devices = (RAWINPUTDEVICE * 2)(
                RAWINPUTDEVICE(0x01, 0x02, 0x00000100, int(self.winId())),
                RAWINPUTDEVICE(0x01, 0x06, 0x00000100, int(self.winId()))
            )
            ctypes.windll.user32.RegisterRawInputDevices(devices, 2, ctypes.sizeof(RAWINPUTDEVICE))
            self.raw_input_registered = True
        except Exception:
            self.raw_input_registered = False

    def unregister_raw_input(self):
        if not IS_WINDOWS or not self.raw_input_registered:
            return
        try:
            un_devs = (RAWINPUTDEVICE * 2)(
                RAWINPUTDEVICE(0x01, 0x02, 0x00000001, None),
                RAWINPUTDEVICE(0x01, 0x06, 0x00000001, None)
            )
            ctypes.windll.user32.RegisterRawInputDevices(un_devs, 2, ctypes.sizeof(RAWINPUTDEVICE))
            self.raw_input_registered = False
        except Exception:
            pass

    def nativeEvent(self, eventType, message):
        if IS_WINDOWS:
            msg = wintypes.MSG.from_address(message.__int__())
            if msg.message == 0x00FF: # WM_INPUT
                now = time.perf_counter()
                header = RAWINPUTHEADER()
                size = wintypes.UINT(ctypes.sizeof(header))
                res = ctypes.windll.user32.GetRawInputData(
                    msg.lParam, 0x10000005, ctypes.byref(header), ctypes.byref(size), ctypes.sizeof(RAWINPUTHEADER)
                )
                if res != -1:
                    if header.dwType == 0: # Mouse / Trackball
                        self.mouse_packet_signal.emit(now, 0, 0)
                    elif header.dwType == 1: # Keyboard
                        self.key_packet_signal.emit(now, "", True)
        return super().nativeEvent(eventType, message)

    def keyPressEvent(self, event):
        now = time.perf_counter()
        key_name = QtGui.QKeySequence(event.key()).toString()
        if not key_name or event.key() == Qt.Key_Space:
            key_name = "Space" if event.key() == Qt.Key_Space else f"Key_{event.key()}"
        self.key_packet_signal.emit(now, key_name, True)
        event.accept()

    def keyReleaseEvent(self, event):
        now = time.perf_counter()
        key_name = QtGui.QKeySequence(event.key()).toString()
        if not key_name or event.key() == Qt.Key_Space:
            key_name = "Space" if event.key() == Qt.Key_Space else f"Key_{event.key()}"
        self.key_packet_signal.emit(now, key_name, False)
        event.accept()

    def mouseMoveEvent(self, event):
        now = time.perf_counter()
        self.mouse_packet_signal.emit(now, event.x(), event.y())
        super().mouseMoveEvent(event)


class ReactionBenchmarkWidget(QFrame):
    """ Interactive Reaction Time Benchmark mini-game """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(140)
        self.setStyleSheet("""
            QFrame {
                background-color: #161b22;
                border: 2px solid #30363d;
                border-radius: 8px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        self.lbl_title = QLabel("🎯 반응속도(Reaction Time) 벤치마크")
        self.lbl_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #58a6ff; border: none;")
        self.lbl_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_title)

        self.lbl_sub = QLabel("여기를 클릭하여 테스트를 시작하세요.\n화면이 초록색으로 변할 때 아무 키나 누르세요!")
        self.lbl_sub.setStyleSheet("font-size: 12px; color: #8b949e; border: none;")
        self.lbl_sub.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_sub)

        self.lbl_record = QLabel("기록: 아직 측정되지 않음")
        self.lbl_record.setStyleSheet("font-size: 11px; color: #3fb950; font-weight: bold; border: none;")
        self.lbl_record.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_record)

        self.state = "idle" # idle -> waiting -> ready -> result
        self.start_timer = QTimer(self)
        self.start_timer.setSingleShot(True)
        self.start_timer.timeout.connect(self._turn_green)
        self.green_time = 0
        self.attempts = []

    def mousePressEvent(self, event):
        self._handle_input()

    def keyPressEvent(self, event):
        self._handle_input()

    def _handle_input(self):
        now = time.perf_counter()
        if self.state == "idle" or self.state == "result":
            # Start new trial
            self.state = "waiting"
            self.setStyleSheet("background-color: #8b1818; border: 2px solid #f85149; border-radius: 8px;")
            self.lbl_title.setText("⏳ 대기하세요...")
            self.lbl_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #ffffff; border: none;")
            self.lbl_sub.setText("화면이 초록색으로 바뀌는 순간 즉시 누르세요!")
            self.lbl_sub.setStyleSheet("font-size: 12px; color: #ffbcbc; border: none;")

            # Random wait between 1.5 and 4.0 seconds
            delay_ms = random.randint(1500, 4000)
            self.start_timer.start(delay_ms)

        elif self.state == "waiting":
            # Clicked too early!
            self.start_timer.stop()
            self.state = "result"
            self.setStyleSheet("background-color: #8a6507; border: 2px solid #d29922; border-radius: 8px;")
            self.lbl_title.setText("⚠️ 너무 일찍 눌렀습니다!")
            self.lbl_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #ffffff; border: none;")
            self.lbl_sub.setText("초록색으로 바뀌기 전에 눌렸습니다. 클릭하여 다시 시도하세요.")
            self.lbl_sub.setStyleSheet("font-size: 12px; color: #ffe3a3; border: none;")

        elif self.state == "ready":
            # Success! Calculate latency
            reaction_ms = (now - self.green_time) * 1000.0
            self.attempts.append(reaction_ms)
            if len(self.attempts) > 10:
                self.attempts.pop(0)

            avg_ms = sum(self.attempts) / len(self.attempts)
            best_ms = min(self.attempts)

            rank = ""
            if reaction_ms < 180:
                rank = "🏆 프로게이머급 초인적 반응속도! (God-tier)"
            elif reaction_ms < 220:
                rank = "⚡ 상위 1% 최상급 게이밍 반응속도! (Elite)"
            elif reaction_ms < 260:
                rank = "🎯 매우 빠른 반응속도! (Fast)"
            elif reaction_ms < 320:
                rank = "👍 준수한 평균 반응속도 (Normal)"
            else:
                rank = "☕ 여유로운 반응속도"

            self.state = "result"
            self.setStyleSheet("background-color: #1f6feb; border: 2px solid #58a6ff; border-radius: 8px;")
            self.lbl_title.setText(f"⚡ 반응속도: {reaction_ms:.1f} ms  ({rank})")
            self.lbl_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff; border: none;")
            self.lbl_sub.setText("클릭하면 다음 측정을 진행합니다.")
            self.lbl_sub.setStyleSheet("font-size: 12px; color: #e6edf3; border: none;")
            self.lbl_record.setText(f"최근 {len(self.attempts)}회 평균: {avg_ms:.1f} ms | 최고 기록: {best_ms:.1f} ms")

    def _turn_green(self):
        self.state = "ready"
        self.green_time = time.perf_counter()
        self.setStyleSheet("background-color: #238636; border: 2px solid #3fb950; border-radius: 8px;")
        self.lbl_title.setText("⚡ 지금 누르세요! (PRESS NOW!)")
        self.lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff; border: none;")
        self.lbl_sub.setText("아무 키나 마우스를 빠르게 누르세요!")
        self.lbl_sub.setStyleSheet("font-size: 12px; color: #d2fedb; border: none;")

    def reset(self):
        self.start_timer.stop()
        self.state = "idle"
        self.attempts.clear()
        self.setStyleSheet("""
            QFrame {
                background-color: #161b22;
                border: 2px solid #30363d;
                border-radius: 8px;
            }
        """)
        self.lbl_title.setText("🎯 반응속도(Reaction Time) 벤치마크")
        self.lbl_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #58a6ff; border: none;")
        self.lbl_sub.setText("여기를 클릭하여 테스트를 시작하세요.\n화면이 초록색으로 변할 때 아무 키나 누르세요!")
        self.lbl_record.setText("기록: 아직 측정되지 않음")


class PerformanceTester(BasicEditor):
    """
    Comprehensive Keyboard & Trackball Performance Benchmark Suite
    - USB Polling Rate (Hz)
    - Input Interval & Latency (ms)
    - Jitter & Stability
    - Trackball Polling Rate (PMW3360)
    - Debounce & Switch Chatter Detection
    - Clicks Per Second (CPS) & NKRO Rollover
    - Reaction Time Benchmark
    """
    def __init__(self):
        super().__init__()
        self.keyboard = None
        self.device = None
        self.is_active = False

        # Key polling metrics
        self.last_key_packet_time = None
        self.key_intervals = deque(maxlen=150)
        self.peak_key_hz = 0.0
        self.current_key_hz = 0.0
        self.key_packet_count = 0

        # Trackball polling metrics
        self.last_mouse_packet_time = None
        self.mouse_intervals = deque(maxlen=150)
        self.peak_mouse_hz = 0.0
        self.current_mouse_hz = 0.0
        self.mouse_reports_in_second = 0
        self.mouse_rps_display = 0
        self.last_sec_timestamp = time.perf_counter()

        # Keyboard rollover & CPS & Chatter
        self.pressed_keys = set()
        self.max_rollover = 0
        self.key_down_times = {} # key_name -> last_down_time
        self.key_up_times = {}   # key_name -> last_up_time
        self.recent_clicks = deque(maxlen=200) # timestamps of down events
        self.peak_cps = 0
        self.chatter_count = 0
        self.clean_press_count = 0
        self.recent_key_tags = deque(maxlen=8)

        # Build UI
        self._init_ui()

        # UI Refresh timer (25 FPS)
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self._update_ui)

    def _init_ui(self):
        guide_box = QLabel("""
        <div style="background-color: #161b22; border: 1px solid #30363d; border-left: 4px solid #58a6ff; padding: 12px 16px; border-radius: 6px; font-size: 12px; line-height: 1.6; color: #e6edf3;">
            <b style="color: #79c0ff; font-size: 14px;">⚡ 키보드 & 트랙볼 실시간 성능 벤치마크 (Performance & Polling Rate)</b><br>
            키를 빠르게 누르거나 내장 트랙볼을 굴리면 <b>실제 USB 전송 주기(Hz)</b>와 <b>신호 지연시간(ms)</b>, <b>스위치 채터링</b>을 실시간 측정합니다.<br>
            • <b>폴링레이트(Polling Rate):</b> 1초 동안 PC와 주고받는 신호 횟수 (1000Hz = 1.0ms 주기, 500Hz = 2.0ms, 125Hz = 8.0ms)<br>
            • <b>지터(Jitter):</b> 신호 간격의 흔들림(표준편차) — 0에 가까울수록 신호가 매우 일정하고 균일하게 전송됨<br>
            • <b>채터링(Chatter) 감지:</b> 스위치 접점 바운싱으로 15ms 이내 비정상적인 초고속 중복 입력이 발생하는지 실시간 감시
        </div>
        """)
        guide_box.setTextFormat(Qt.RichText)

        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(12, 10, 12, 16)
        content_layout.setSpacing(14)
        content_layout.addWidget(guide_box)

        # Row 1: Two Big Metric Cards (Keyboard Polling + Trackball Polling)
        row1 = QHBoxLayout()
        row1.setSpacing(14)

        # Card 1: Keyboard Polling Rate
        self.card_key = self._create_card("⌨️ 키보드 폴링레이트 & 반응 주기")
        c1_layout = QVBoxLayout(self.card_key)

        h_top1 = QHBoxLayout()
        self.lbl_key_hz = QLabel("0 Hz")
        self.lbl_key_hz.setStyleSheet("font-size: 32px; font-weight: bold; color: #3fb950; border: none;")
        self.lbl_key_status = QLabel("대기 중 (Idle)")
        self.lbl_key_status.setStyleSheet("font-size: 12px; color: #8b949e; background: #21262d; padding: 4px 8px; border-radius: 4px; border: 1px solid #30363d;")
        h_top1.addWidget(self.lbl_key_hz)
        h_top1.addStretch()
        h_top1.addWidget(self.lbl_key_status)
        c1_layout.addLayout(h_top1)

        self.bar_key_hz = QProgressBar()
        self.bar_key_hz.setRange(0, 1000)
        self.bar_key_hz.setValue(0)
        self.bar_key_hz.setTextVisible(False)
        self.bar_key_hz.setFixedHeight(8)
        self.bar_key_hz.setStyleSheet("""
            QProgressBar { background-color: #21262d; border-radius: 4px; border: none; }
            QProgressBar::chunk { background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1f6feb, stop:1 #3fb950); border-radius: 4px; }
        """)
        c1_layout.addWidget(self.bar_key_hz)

        grid1 = QGridLayout()
        grid1.setSpacing(6)
        self.lbl_key_peak = QLabel("최고: 0 Hz")
        self.lbl_key_avg = QLabel("평균: 0 Hz")
        self.lbl_key_min_dt = QLabel("최소 간격: - ms")
        self.lbl_key_jitter = QLabel("지터: ±0.00 ms")
        for lbl in [self.lbl_key_peak, self.lbl_key_avg, self.lbl_key_min_dt, self.lbl_key_jitter]:
            lbl.setStyleSheet("font-size: 11px; color: #c9d1d9; border: none;")
        grid1.addWidget(self.lbl_key_peak, 0, 0)
        grid1.addWidget(self.lbl_key_avg, 0, 1)
        grid1.addWidget(self.lbl_key_min_dt, 1, 0)
        grid1.addWidget(self.lbl_key_jitter, 1, 1)
        c1_layout.addLayout(grid1)

        row1.addWidget(self.card_key, 1)

        # Card 2: Charybdis Trackball Polling Rate
        self.card_mouse = self._create_card("🖱️ Charybdis 트랙볼 센서 폴링레이트")
        c2_layout = QVBoxLayout(self.card_mouse)

        h_top2 = QHBoxLayout()
        self.lbl_mouse_hz = QLabel("0 Hz")
        self.lbl_mouse_hz.setStyleSheet("font-size: 32px; font-weight: bold; color: #58a6ff; border: none;")
        self.lbl_mouse_status = QLabel("트랙볼 굴림 감지 대기")
        self.lbl_mouse_status.setStyleSheet("font-size: 12px; color: #8b949e; background: #21262d; padding: 4px 8px; border-radius: 4px; border: 1px solid #30363d;")
        h_top2.addWidget(self.lbl_mouse_hz)
        h_top2.addStretch()
        h_top2.addWidget(self.lbl_mouse_status)
        c2_layout.addLayout(h_top2)

        self.bar_mouse_hz = QProgressBar()
        self.bar_mouse_hz.setRange(0, 1000)
        self.bar_mouse_hz.setValue(0)
        self.bar_mouse_hz.setTextVisible(False)
        self.bar_mouse_hz.setFixedHeight(8)
        self.bar_mouse_hz.setStyleSheet("""
            QProgressBar { background-color: #21262d; border-radius: 4px; border: none; }
            QProgressBar::chunk { background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8957e5, stop:1 #58a6ff); border-radius: 4px; }
        """)
        c2_layout.addWidget(self.bar_mouse_hz)

        grid2 = QGridLayout()
        grid2.setSpacing(6)
        self.lbl_mouse_peak = QLabel("최고: 0 Hz")
        self.lbl_mouse_avg = QLabel("평균: 0 Hz")
        self.lbl_mouse_rps = QLabel("초당 리포트: 0 rps")
        self.lbl_mouse_sensor = QLabel("센서: PMW3360 광학 센서")
        for lbl in [self.lbl_mouse_peak, self.lbl_mouse_avg, self.lbl_mouse_rps, self.lbl_mouse_sensor]:
            lbl.setStyleSheet("font-size: 11px; color: #c9d1d9; border: none;")
        grid2.addWidget(self.lbl_mouse_peak, 0, 0)
        grid2.addWidget(self.lbl_mouse_avg, 0, 1)
        grid2.addWidget(self.lbl_mouse_rps, 1, 0)
        grid2.addWidget(self.lbl_mouse_sensor, 1, 1)
        c2_layout.addLayout(grid2)

        row1.addWidget(self.card_mouse, 1)
        content_layout.addLayout(row1)

        # Row 2: Interactive Typing Zone & Debounce / Chatter & CPS
        self.card_type = self._create_card("🛡️ 스위치 디바운스 & 채터링(중복입력) 감지 및 실시간 타건 테스트")
        c3_layout = QVBoxLayout(self.card_type)

        top_stats = QHBoxLayout()
        self.lbl_cps = QLabel("⚡ 타건 속도: 0 CPS (최고: 0 CPS)")
        self.lbl_cps.setStyleSheet("font-size: 13px; font-weight: bold; color: #f0883e; border: none;")
        self.lbl_nkro = QLabel("🎹 동시입력: 0 키 (최고: 0 키 / NKRO)")
        self.lbl_nkro.setStyleSheet("font-size: 13px; font-weight: bold; color: #a371f7; border: none;")
        self.lbl_chatter = QLabel("✅ 채터링 감지: 0건 (정상)")
        self.lbl_chatter.setStyleSheet("font-size: 13px; font-weight: bold; color: #3fb950; border: none;")
        top_stats.addWidget(self.lbl_cps)
        top_stats.addStretch()
        top_stats.addWidget(self.lbl_nkro)
        top_stats.addStretch()
        top_stats.addWidget(self.lbl_chatter)
        c3_layout.addLayout(top_stats)

        # Input listener widget embedded as interactive typing field
        self.listener = PerformanceInputListener()
        self.listener.setFixedHeight(75)
        self.listener.setStyleSheet("""
            QWidget {
                background-color: #0d1117;
                border: 2px dashed #30363d;
                border-radius: 6px;
            }
            QWidget:focus {
                border: 2px solid #58a6ff;
                background-color: #161b22;
            }
        """)
        l_layout = QVBoxLayout(self.listener)
        l_layout.setAlignment(Qt.AlignCenter)
        self.lbl_listener_hint = QLabel("⌨️ 여기를 클릭하거나 아무 키나 누르며 연속 타건해 보세요!\n(실시간 키패킷, CPS, 동시입력, 스위치 떨림 채터링 자동 검사)")
        self.lbl_listener_hint.setAlignment(Qt.AlignCenter)
        self.lbl_listener_hint.setStyleSheet("font-size: 12px; color: #8b949e; border: none;")
        l_layout.addWidget(self.lbl_listener_hint)
        c3_layout.addWidget(self.listener)

        # Connect signals
        self.listener.key_packet_signal.connect(self._on_key_packet)
        self.listener.mouse_packet_signal.connect(self._on_mouse_packet)

        # Recent key tags stream
        h_stream = QHBoxLayout()
        h_stream.setSpacing(6)
        self.lbl_stream_title = QLabel("최근 입력 스트림:")
        self.lbl_stream_title.setStyleSheet("font-size: 11px; color: #8b949e; border: none;")
        h_stream.addWidget(self.lbl_stream_title)
        self.lbl_key_tags = QLabel("입력 대기 중...")
        self.lbl_key_tags.setStyleSheet("font-size: 11px; color: #e6edf3; border: none;")
        h_stream.addWidget(self.lbl_key_tags, 1)
        c3_layout.addLayout(h_stream)

        content_layout.addWidget(self.card_type)

        # Row 3: Reaction Time Benchmark
        self.reaction_widget = ReactionBenchmarkWidget()
        content_layout.addWidget(self.reaction_widget)

        # Bottom Button bar
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_copy = QPushButton("📋 결과 요약 복사 (Copy)")
        btn_copy.setFixedHeight(30)
        btn_copy.setStyleSheet("font-size: 12px; padding: 0 12px;")
        btn_copy.clicked.connect(self._copy_results)
        btn_layout.addWidget(btn_copy)

        btn_reset = QPushButton("🔄 모든 측정 기록 초기화 (Reset)")
        btn_reset.setFixedHeight(30)
        btn_reset.setStyleSheet("background-color: #21262d; border: 1px solid #30363d; font-size: 12px; padding: 0 14px; border-radius: 4px; font-weight: bold;")
        btn_reset.clicked.connect(self.reset_all)
        btn_layout.addWidget(btn_reset)

        content_layout.addLayout(btn_layout)

        # Wrap in scrollable container
        scroll = make_scrollable(content_layout)
        self.addWidget(scroll)

    def _create_card(self, title):
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 8px;
            }
        """)
        return card

    def _on_key_packet(self, timestamp, key_name, is_down):
        # Calculate interval between hardware packet reports
        if self.last_key_packet_time is not None:
            dt = timestamp - self.last_key_packet_time
            if 0.0002 <= dt <= 0.060: # 16Hz to 5000Hz packet window
                hz = 1.0 / dt
                self.key_intervals.append(dt)
                self.current_key_hz = hz
                if hz > self.peak_key_hz:
                    self.peak_key_hz = min(hz, 2000.0) # Sanity clamp
        self.last_key_packet_time = timestamp
        self.key_packet_count += 1

        if key_name:
            if is_down:
                self.pressed_keys.add(key_name)
                if len(self.pressed_keys) > self.max_rollover:
                    self.max_rollover = len(self.pressed_keys)

                # CPS tracking
                self.recent_clicks.append(timestamp)

                # Chatter / Debounce check: check time since last UP of the SAME key
                if key_name in self.key_up_times:
                    repress_delta_ms = (timestamp - self.key_up_times[key_name]) * 1000.0
                    # If pressed again in under 12ms, suspect physical switch chatter
                    if repress_delta_ms < 12.0:
                        self.chatter_count += 1
                        self.recent_key_tags.append(f"<span style='color:#f85149; font-weight:bold;'>⚠️{key_name} ({repress_delta_ms:.1f}ms 채터링)</span>")
                    else:
                        self.clean_press_count += 1
                        self.recent_key_tags.append(f"<span style='color:#58a6ff;'>[{key_name}]</span>")
                else:
                    self.clean_press_count += 1
                    self.recent_key_tags.append(f"<span style='color:#58a6ff;'>[{key_name}]</span>")

                self.key_down_times[key_name] = timestamp
            else:
                self.pressed_keys.discard(key_name)
                self.key_up_times[key_name] = timestamp
                if key_name in self.key_down_times:
                    hold_dur_ms = (timestamp - self.key_down_times[key_name]) * 1000.0
                    self.recent_key_tags.append(f"<span style='color:#8b949e;'>[{key_name} 뗌: {hold_dur_ms:.0f}ms]</span>")

    def _on_mouse_packet(self, timestamp, dx, dy):
        if self.last_mouse_packet_time is not None:
            dt = timestamp - self.last_mouse_packet_time
            if 0.0002 <= dt <= 0.060:
                hz = 1.0 / dt
                self.mouse_intervals.append(dt)
                self.current_mouse_hz = hz
                if hz > self.peak_mouse_hz:
                    self.peak_mouse_hz = min(hz, 2000.0)
        self.last_mouse_packet_time = timestamp
        self.mouse_reports_in_second += 1

    def _update_ui(self):
        now = time.perf_counter()

        # Decay instantaneous Hz if no input in last 250ms
        if self.last_key_packet_time is None or (now - self.last_key_packet_time) > 0.25:
            self.current_key_hz = 0.0

        if self.last_mouse_packet_time is None or (now - self.last_mouse_packet_time) > 0.25:
            self.current_mouse_hz = 0.0

        # Calculate reports per second for mouse
        if now - self.last_sec_timestamp >= 1.0:
            self.mouse_rps_display = self.mouse_reports_in_second
            self.mouse_reports_in_second = 0
            self.last_sec_timestamp = now

        # Update Keyboard Polling Card
        self.lbl_key_hz.setText(f"{int(round(self.current_key_hz))} Hz")
        self.bar_key_hz.setValue(int(min(self.current_key_hz, 1000)))

        if self.current_key_hz >= 900:
            self.lbl_key_status.setText("🚀 1000Hz 최고 성능 (Ultra-Fast)")
            self.lbl_key_status.setStyleSheet("font-size: 11px; color: #3fb950; background: #1c3222; padding: 4px 8px; border-radius: 4px; border: 1px solid #238636;")
        elif self.current_key_hz >= 450:
            self.lbl_key_status.setText("⚡ 500Hz 고속 게이밍 (Fast)")
            self.lbl_key_status.setStyleSheet("font-size: 11px; color: #58a6ff; background: #1c2738; padding: 4px 8px; border-radius: 4px; border: 1px solid #1f6feb;")
        elif self.current_key_hz > 50:
            self.lbl_key_status.setText(f"🟢 {int(round(self.current_key_hz))}Hz 전송 중")
            self.lbl_key_status.setStyleSheet("font-size: 11px; color: #d29922; background: #2f2515; padding: 4px 8px; border-radius: 4px; border: 1px solid #9e6a03;")
        else:
            self.lbl_key_status.setText("대기 중 (Idle)")
            self.lbl_key_status.setStyleSheet("font-size: 11px; color: #8b949e; background: #21262d; padding: 4px 8px; border-radius: 4px; border: 1px solid #30363d;")

        if self.key_intervals:
            avg_dt = statistics.mean(self.key_intervals)
            avg_hz = 1.0 / avg_dt if avg_dt > 0 else 0
            min_dt_ms = min(self.key_intervals) * 1000.0
            jitter_ms = (statistics.stdev(self.key_intervals) * 1000.0) if len(self.key_intervals) >= 2 else 0.0

            self.lbl_key_peak.setText(f"최고: <b>{int(round(self.peak_key_hz))} Hz</b>")
            self.lbl_key_avg.setText(f"평균: <b>{int(round(avg_hz))} Hz</b>")
            self.lbl_key_min_dt.setText(f"최소 간격: <b>{min_dt_ms:.2f} ms</b>")
            self.lbl_key_jitter.setText(f"지터: <b>±{jitter_ms:.2f} ms</b>")

        # Update Trackball Polling Card
        self.lbl_mouse_hz.setText(f"{int(round(self.current_mouse_hz))} Hz")
        self.bar_mouse_hz.setValue(int(min(self.current_mouse_hz, 1000)))

        if self.current_mouse_hz >= 900:
            self.lbl_mouse_status.setText("✨ 1000Hz 광학 센서 최대 성능")
            self.lbl_mouse_status.setStyleSheet("font-size: 11px; color: #58a6ff; background: #1c2738; padding: 4px 8px; border-radius: 4px; border: 1px solid #1f6feb;")
        elif self.current_mouse_hz >= 450:
            self.lbl_mouse_status.setText("⚡ 500Hz 안정적 추적")
            self.lbl_mouse_status.setStyleSheet("font-size: 11px; color: #3fb950; background: #1c3222; padding: 4px 8px; border-radius: 4px; border: 1px solid #238636;")
        elif self.current_mouse_hz > 50:
            self.lbl_mouse_status.setText(f"트랙볼 이동 감지 중 ({int(round(self.current_mouse_hz))}Hz)")
            self.lbl_mouse_status.setStyleSheet("font-size: 11px; color: #d2a8ff; background: #261f38; padding: 4px 8px; border-radius: 4px; border: 1px solid #8957e5;")
        else:
            self.lbl_mouse_status.setText("트랙볼 굴림 감지 대기")
            self.lbl_mouse_status.setStyleSheet("font-size: 11px; color: #8b949e; background: #21262d; padding: 4px 8px; border-radius: 4px; border: 1px solid #30363d;")

        if self.mouse_intervals:
            avg_m_dt = statistics.mean(self.mouse_intervals)
            avg_m_hz = 1.0 / avg_m_dt if avg_m_dt > 0 else 0
            self.lbl_mouse_peak.setText(f"최고: <b>{int(round(self.peak_mouse_hz))} Hz</b>")
            self.lbl_mouse_avg.setText(f"평균: <b>{int(round(avg_m_hz))} Hz</b>")
            self.lbl_mouse_rps.setText(f"초당 리포트: <b>{self.mouse_rps_display} rps</b>")

        # Update CPS
        # Remove clicks older than 1.0 sec
        while self.recent_clicks and (now - self.recent_clicks[0]) > 1.0:
            self.recent_clicks.popleft()
        current_cps = len(self.recent_clicks)
        if current_cps > self.peak_cps:
            self.peak_cps = current_cps
        self.lbl_cps.setText(f"⚡ 타건 속도: <b>{current_cps} CPS</b> (최고: {self.peak_cps} CPS)")

        # Update NKRO
        current_rollover = len(self.pressed_keys)
        self.lbl_nkro.setText(f"🎹 동시입력: <b>{current_rollover} 키</b> (최고: {self.max_rollover} 키 / NKRO)")

        # Update Chatter status
        if self.chatter_count == 0:
            self.lbl_chatter.setText("✅ 채터링 감지: <b>0건 (스위치 정상)</b>")
            self.lbl_chatter.setStyleSheet("font-size: 13px; font-weight: bold; color: #3fb950; border: none;")
        else:
            self.lbl_chatter.setText(f"⚠️ 채터링 의심: <b>{self.chatter_count}건 감지됨!</b>")
            self.lbl_chatter.setStyleSheet("font-size: 13px; font-weight: bold; color: #f85149; border: none;")

        # Update stream tags
        if self.recent_key_tags:
            self.lbl_key_tags.setText(" &nbsp;".join(list(self.recent_key_tags)))
            self.lbl_key_tags.setTextFormat(Qt.RichText)

    def reset_all(self):
        self.key_intervals.clear()
        self.mouse_intervals.clear()
        self.peak_key_hz = 0.0
        self.current_key_hz = 0.0
        self.peak_mouse_hz = 0.0
        self.current_mouse_hz = 0.0
        self.pressed_keys.clear()
        self.max_rollover = 0
        self.recent_clicks.clear()
        self.peak_cps = 0
        self.chatter_count = 0
        self.clean_press_count = 0
        self.recent_key_tags.clear()
        self.lbl_key_tags.setText("초기화 완료. 입력 대기 중...")
        self.reaction_widget.reset()
        self._update_ui()

    def _copy_results(self):
        avg_k_hz = int(round(1.0 / statistics.mean(self.key_intervals))) if self.key_intervals else 0
        avg_m_hz = int(round(1.0 / statistics.mean(self.mouse_intervals))) if self.mouse_intervals else 0
        min_dt = min(self.key_intervals) * 1000.0 if self.key_intervals else 0.0

        summary = (
            f"=== Charybdis 키보드 성능 벤치마크 결과 ===\n"
            f"• 키보드 폴링레이트: 최고 {int(round(self.peak_key_hz))}Hz / 평균 {avg_k_hz}Hz (최소 간격: {min_dt:.2f}ms)\n"
            f"• 트랙볼 폴링레이트: 최고 {int(round(self.peak_mouse_hz))}Hz / 평균 {avg_m_hz}Hz\n"
            f"• 최고 타건 속도: {self.peak_cps} CPS | 최대 동시입력: {self.max_rollover} Keys\n"
            f"• 스위치 채터링: {self.chatter_count}건 (정상 타건: {self.clean_press_count}건)\n"
        )
        if self.reaction_widget.attempts:
            avg_rx = sum(self.reaction_widget.attempts) / len(self.reaction_widget.attempts)
            best_rx = min(self.reaction_widget.attempts)
            summary += f"• 실전 반응속도: 평균 {avg_rx:.1f}ms / 최고 {best_rx:.1f}ms\n"

        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(summary)
            self.lbl_stream_title.setText("📋 결과가 클립보드에 복사되었습니다!")
            QTimer.singleShot(2500, lambda: self.lbl_stream_title.setText("최근 입력 스트림:"))

    def rebuild(self, device):
        super().rebuild(device)

    def valid(self):
        return isinstance(self.device, VialKeyboard)

    def activate(self):
        self.is_active = True
        self.listener.register_raw_input()
        self.refresh_timer.start(40) # 25 FPS
        self.listener.setFocus()

    def deactivate(self):
        self.is_active = False
        self.refresh_timer.stop()
        self.listener.unregister_raw_input()
