# SPDX-License-Identifier: GPL-2.0-or-later
from PyQt5.QtWidgets import QVBoxLayout, QPushButton, QWidget, QHBoxLayout, QLabel
from PyQt5.QtCore import Qt, QTimer

import math

from editor.basic_editor import BasicEditor
from protocol.constants import VIAL_PROTOCOL_MATRIX_TESTER
from widgets.keyboard_widget import KeyboardWidget
from util import tr
from vial_device import VialKeyboard
from unlocker import Unlocker


class MatrixTest(BasicEditor):

    def __init__(self, layout_editor):
        super().__init__()

        self.layout_editor = layout_editor

        self.keyboardWidget = KeyboardWidget(layout_editor)
        self.keyboardWidget.set_enabled(False)

        guide_box = QLabel("""
        <div style="background-color: #161b22; border: 1px solid #30363d; border-left: 4px solid #a371f7; padding: 10px 14px; border-radius: 6px; font-size: 12px; line-height: 1.5; color: #e6edf3; max-width: 620px;">
            <b style="color: #d2a8ff; font-size: 13px;">🧪 실시간 키 입력 테스트 (Matrix Tester)</b><br>
            키보드의 스위치를 누르면 해당 위치가 실시간으로 밝게 켜집니다.<br>
            • <b>실시간 감지:</b> 누르고 있는 키는 밝은 파란색으로 켜지고, 손을 떼면 정상 입력되었음을 표시하는 색상으로 유지됩니다.<br>
            • <b>초기화:</b> 아래 <b>[🔄 테스트 기록 초기화]</b> 버튼을 누르면 이전 테스트 기록이 리셋됩니다.
        </div>
        """)
        guide_box.setTextFormat(Qt.RichText)

        self.unlock_btn = QPushButton("🔓 키보드 잠금 해제 (Unlock)")
        self.reset_btn = QPushButton("🔄 테스트 기록 초기화 (Reset)")

        layout = QVBoxLayout()
        layout.addSpacing(6)
        layout.addWidget(guide_box)
        layout.setAlignment(guide_box, Qt.AlignCenter)
        layout.addSpacing(10)
        layout.addWidget(self.keyboardWidget)
        layout.setAlignment(self.keyboardWidget, Qt.AlignCenter)

        self.addLayout(layout)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.unlock_lbl = QLabel("키 입력을 테스트하려면 먼저 잠금을 해제하세요:")
        btn_layout.addWidget(self.unlock_lbl)
        btn_layout.addWidget(self.unlock_btn)
        btn_layout.addWidget(self.reset_btn)
        self.addLayout(btn_layout)

        self.keyboard = None
        self.device = None
        self.polling = False
        self.unlocked = False
        self.prev_matrix_data = None

        self.timer = QTimer()
        self.timer.timeout.connect(self.matrix_poller)

        self.unlock_btn.clicked.connect(self.unlock)
        self.reset_btn.clicked.connect(self.reset_keyboard_widget)

        self.grabber = QWidget()

    def rebuild(self, device):
        super().rebuild(device)
        if self.valid():
            self.keyboard = device.keyboard
            self.keyboardWidget.set_keys(self.keyboard.keys, self.keyboard.encoders)
        self.keyboardWidget.setEnabled(self.valid())

    def valid(self):
        # Check if vial protocol is v3 or later
        return isinstance(self.device, VialKeyboard) and \
               (self.device.keyboard and self.device.keyboard.vial_protocol >= VIAL_PROTOCOL_MATRIX_TESTER) and \
               ((self.device.keyboard.cols // 8 + 1) * self.device.keyboard.rows <= 28)

    def reset_keyboard_widget(self):
        # reset keyboard widget
        for w in self.keyboardWidget.widgets:
            w.setPressed(False)
            w.setOn(False)
        self.prev_matrix_data = None
        self.keyboardWidget.update()

    def matrix_poller(self):
        if not self.valid():
            self.timer.stop()
            return

        if not self.unlocked:
            try:
                self.unlocked = bool(self.keyboard.get_unlock_status(3))
            except (RuntimeError, ValueError):
                self.timer.stop()
                return

            if not self.unlocked:
                self.unlock_btn.show()
                self.unlock_lbl.show()
                return

            # we're unlocked, so hide unlock button and label
            self.unlock_btn.hide()
            self.unlock_lbl.hide()

        # Get matrix data from keyboard
        try:
            data = self.keyboard.matrix_poll()
        except (RuntimeError, ValueError):
            self.timer.stop()
            return

        # Skip redraw if matrix state hasn't changed (saves 95% CPU)
        if not data or data == self.prev_matrix_data:
            return
        self.prev_matrix_data = data

        # Get size for matrix
        rows = self.keyboard.rows
        cols = self.keyboard.cols
        row_size = math.ceil(cols / 8)
        matrix = [[None] * cols for x in range(rows)]

        for row in range(rows):
            row_data_start = 2 + (row * row_size)
            row_data_end = row_data_start + row_size
            row_data = data[row_data_start:row_data_end]

            for col in range(cols):
                col_byte = len(row_data) - 1 - math.floor(col / 8)
                col_mod = (col % 8)
                matrix[row][col] = (row_data[col_byte] >> col_mod) & 1

        # write matrix state to keyboard widget
        for w in self.keyboardWidget.widgets:
            if w.desc.row is not None and w.desc.col is not None:
                row = w.desc.row
                col = w.desc.col

                if row < len(matrix) and col < len(matrix[row]):
                    w.setPressed(matrix[row][col])
                    if matrix[row][col]:
                        w.setOn(True)

        # High-speed paint only (no expensive layout reconstruction)
        self.keyboardWidget.update()

    def unlock(self):
        Unlocker.unlock(self.keyboard)
        self.unlocked = False

    def activate(self):
        self.unlocked = False
        self.prev_matrix_data = None
        self.grabber.grabKeyboard()
        self.timer.start(10)

    def deactivate(self):
        self.grabber.releaseKeyboard()
        self.timer.stop()
