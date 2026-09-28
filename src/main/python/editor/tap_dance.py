# SPDX-License-Identifier: GPL-2.0-or-later
from PyQt5 import QtCore
from PyQt5.QtCore import pyqtSignal, QObject
from PyQt5.QtWidgets import QTabWidget, QWidget, QSizePolicy, QGridLayout, QVBoxLayout, QLabel, QHBoxLayout, \
    QPushButton, QSpinBox

from protocol.constants import VIAL_PROTOCOL_DYNAMIC
from widgets.key_widget import KeyWidget
from tabbed_keycodes import TabbedKeycodes
from util import tr
from vial_device import VialKeyboard
from editor.basic_editor import BasicEditor
from widgets.tab_widget_keycodes import TabWidgetWithKeycodes


class TapDanceEntryUI(QObject):

    key_changed = pyqtSignal()
    timing_changed = pyqtSignal()

    def __init__(self, idx):
        super().__init__()

        self.idx = idx
        self.container = QGridLayout()
        self.container.setSpacing(10)
        self.populate_container()

        guide_box = QLabel(f"""
        <div style="background-color: #161b22; border: 1px solid #30363d; border-left: 4px solid #58a6ff; padding: 12px 16px; border-radius: 6px; font-size: 12px; line-height: 1.6; color: #e6edf3; max-width: 560px;">
            <b style="color: #79c0ff; font-size: 13px;">💡 탭 댄스 (TD {self.idx}) 설정 방법 & 실전 예시</b><br>
            스위치 하나를 누르는 조작 패턴에 따라 최대 4가지 키를 할당합니다.<br>
            • <b>스페이스바 예시:</b> 1번 탭=<code>Space</code> | 길게 홀드=<code>한/영 전환</code> 또는 <code>Shift</code><br>
            • <b>세미콜론 예시:</b> 1번 탭=<code>;</code> | 2번 연타=<code>:</code> | 길게 홀드=<code>Enter</code><br>
            • <b>키맵 적용법:</b> 위 항목을 지정한 뒤, <b>[키맵(Keymap)]</b> 탭에서 원하는 키를 누르고 <code>TD({self.idx})</code>를 할당하세요!
        </div>
        """)
        guide_box.setTextFormat(QtCore.Qt.RichText)

        w = QWidget()
        w.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        w.setLayout(self.container)

        l = QVBoxLayout()
        l.addSpacing(6)
        l.addWidget(guide_box)
        l.setAlignment(guide_box, QtCore.Qt.AlignHCenter)
        l.addSpacing(14)
        l.addWidget(w)
        l.setAlignment(w, QtCore.Qt.AlignHCenter)
        l.addStretch()

        self.w2 = QWidget()
        self.w2.setLayout(l)

    def populate_container(self):
        self.container.addWidget(QLabel("1️⃣ 한 번 가볍게 탭할 때 (On tap):"), 0, 0)
        self.kc_on_tap = KeyWidget()
        self.kc_on_tap.changed.connect(self.on_key_changed)
        self.container.addWidget(self.kc_on_tap, 0, 1)

        self.container.addWidget(QLabel("2️⃣ 길게 꾹 누르고 있을 때 (On hold):"), 1, 0)
        self.kc_on_hold = KeyWidget()
        self.kc_on_hold.changed.connect(self.on_key_changed)
        self.container.addWidget(self.kc_on_hold, 1, 1)

        self.container.addWidget(QLabel("3️⃣ 두 번 빠르게 연타할 때 (On double tap):"), 2, 0)
        self.kc_on_double_tap = KeyWidget()
        self.kc_on_double_tap.changed.connect(self.on_key_changed)
        self.container.addWidget(self.kc_on_double_tap, 2, 1)

        self.container.addWidget(QLabel("4️⃣ 한 번 탭한 직후 길게 누를 때 (On tap + hold):"), 3, 0)
        self.kc_on_tap_hold = KeyWidget()
        self.kc_on_tap_hold.changed.connect(self.on_key_changed)
        self.container.addWidget(self.kc_on_tap_hold, 3, 1)

        self.container.addWidget(QLabel("⏱️ 탭 판정 시간 (Tapping term, ms / 0=기본값):"), 4, 0)
        self.txt_tapping_term = QSpinBox()
        self.txt_tapping_term.valueChanged.connect(self.on_timing_changed)
        self.txt_tapping_term.setMinimum(0)
        self.txt_tapping_term.setMaximum(10000)
        self.container.addWidget(self.txt_tapping_term, 4, 1)

    def widget(self):
        return self.w2

    def load(self, data):
        objs = [self.kc_on_tap, self.kc_on_hold, self.kc_on_double_tap, self.kc_on_tap_hold, self.txt_tapping_term]
        for o in objs:
            o.blockSignals(True)

        self.kc_on_tap.set_keycode(data[0])
        self.kc_on_hold.set_keycode(data[1])
        self.kc_on_double_tap.set_keycode(data[2])
        self.kc_on_tap_hold.set_keycode(data[3])
        self.txt_tapping_term.setValue(data[4])

        for o in objs:
            o.blockSignals(False)

    def save(self):
        return (
            self.kc_on_tap.keycode,
            self.kc_on_hold.keycode,
            self.kc_on_double_tap.keycode,
            self.kc_on_tap_hold.keycode,
            self.txt_tapping_term.value()
        )

    def on_key_changed(self):
        self.key_changed.emit()

    def on_timing_changed(self):
        self.timing_changed.emit()


class TapDance(BasicEditor):

    def __init__(self):
        super().__init__()
        self.keyboard = None

        self.tap_dance_entries = []
        self.tap_dance_entries_available = []
        self.tabs = TabWidgetWithKeycodes()
        for x in range(128):
            entry = TapDanceEntryUI(x)
            entry.key_changed.connect(self.on_key_changed)
            entry.timing_changed.connect(self.on_timing_changed)
            self.tap_dance_entries_available.append(entry)

        self.addWidget(self.tabs)
        buttons = QHBoxLayout()
        buttons.addStretch()
        self.btn_save = QPushButton(tr("TapDance", "Save"))
        self.btn_save.clicked.connect(self.on_save)
        self.btn_revert = QPushButton(tr("TapDance", "Revert"))
        self.btn_revert.clicked.connect(self.on_revert)
        buttons.addWidget(self.btn_save)
        buttons.addWidget(self.btn_revert)
        self.addLayout(buttons)

    def rebuild_ui(self):
        while self.tabs.count() > 0:
            self.tabs.removeTab(0)
        self.tap_dance_entries = self.tap_dance_entries_available[:self.keyboard.tap_dance_count]
        for x, e in enumerate(self.tap_dance_entries):
            self.tabs.addTab(e.widget(), str(x))
        self.reload_ui()

    def reload_ui(self):
        for x, e in enumerate(self.tap_dance_entries):
            e.load(self.keyboard.tap_dance_get(x))
        self.update_modified_state()

    def on_save(self):
        for x, e in enumerate(self.tap_dance_entries):
            self.keyboard.tap_dance_set(x, self.tap_dance_entries[x].save())
        self.update_modified_state()

    def on_revert(self):
        self.keyboard.reload_dynamic()
        self.reload_ui()

    def rebuild(self, device):
        super().rebuild(device)
        if self.valid():
            self.keyboard = device.keyboard
            self.rebuild_ui()

    def valid(self):
        return isinstance(self.device, VialKeyboard) and \
               (self.device.keyboard and self.device.keyboard.vial_protocol >= VIAL_PROTOCOL_DYNAMIC
                and self.device.keyboard.tap_dance_count > 0)

    def on_key_changed(self):
        self.on_save()

    def update_modified_state(self):
        """ Update indication of which tabs are modified, and keep Save button enabled only if it's needed """
        has_changes = False
        for x, e in enumerate(self.tap_dance_entries):
            if self.tap_dance_entries[x].save() != self.keyboard.tap_dance_get(x):
                has_changes = True
                self.tabs.setTabText(x, "{}*".format(x))
            else:
                self.tabs.setTabText(x, str(x))
        self.btn_save.setEnabled(has_changes)

    def on_timing_changed(self):
        self.update_modified_state()
