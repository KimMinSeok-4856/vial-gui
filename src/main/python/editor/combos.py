# SPDX-License-Identifier: GPL-2.0-or-later
from PyQt5 import QtCore
from PyQt5.QtCore import pyqtSignal, QObject
from PyQt5.QtWidgets import QWidget, QSizePolicy, QGridLayout, QVBoxLayout, QLabel

from protocol.constants import VIAL_PROTOCOL_DYNAMIC
from widgets.key_widget import KeyWidget
from vial_device import VialKeyboard
from editor.basic_editor import BasicEditor
from widgets.tab_widget_keycodes import TabWidgetWithKeycodes


class ComboEntryUI(QObject):

    key_changed = pyqtSignal()

    def __init__(self, idx):
        super().__init__()

        self.idx = idx
        self.container = QGridLayout()
        self.container.setSpacing(10)
        self.kc_inputs = []
        self.populate_container()

        guide_box = QLabel(f"""
        <div style="background-color: #161b22; border: 1px solid #30363d; border-left: 4px solid #3fb950; padding: 12px 16px; border-radius: 6px; font-size: 12px; line-height: 1.6; color: #e6edf3; max-width: 560px;">
            <b style="color: #7ee787; font-size: 13px;">💡 콤보 (Combo {self.idx + 1}) 설정 방법 & 실전 예시</b><br>
            두 개 이상의 키를 동시에 눌렀을 때 발동될 조합을 지정합니다.<br>
            • <b>ESC 콤보 예시:</b> Key 1 = <code>Q</code>, Key 2 = <code>W</code> ➔ Output = <code>ESC</code><br>
            • <b>엔터 콤보 예시:</b> Key 1 = <code>J</code>, Key 2 = <code>K</code> ➔ Output = <code>Enter</code><br>
            • <b>마우스 클릭:</b> Key 1 = <code>D</code>, Key 2 = <code>F</code> ➔ Output = <code>BTN1</code> (마우스 좌클릭)<br>
            (※ 2개 키만 사용하실 때는 Key 3, 4를 빈 칸으로 두시면 됩니다. 설정 즉시 실시간 반영됩니다.)
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
        for x in range(4):
            kc_widget = KeyWidget()
            kc_widget.changed.connect(self.on_key_changed)
            self.container.addWidget(QLabel(f"👉 동시 입력 키 {x + 1} (Key {x + 1}):"), x, 0)
            self.container.addWidget(kc_widget, x, 1)
            self.kc_inputs.append(kc_widget)

        self.kc_output = KeyWidget()
        self.kc_output.changed.connect(self.on_key_changed)
        self.container.addWidget(QLabel("🎯 최종 결과 출력 키 (Output key):"), 4, 0)
        self.container.addWidget(self.kc_output, 4, 1)

    def widget(self):
        return self.w2

    def load(self, data):
        objs = self.kc_inputs + [self.kc_output]
        for o in objs:
            o.blockSignals(True)

        for x in range(4):
            self.kc_inputs[x].set_keycode(data[x])
        self.kc_output.set_keycode(data[4])

        for o in objs:
            o.blockSignals(False)

    def save(self):
        return (
            self.kc_inputs[0].keycode,
            self.kc_inputs[1].keycode,
            self.kc_inputs[2].keycode,
            self.kc_inputs[3].keycode,
            self.kc_output.keycode
        )

    def on_key_changed(self):
        self.key_changed.emit()


class Combos(BasicEditor):

    def __init__(self):
        super().__init__()
        self.keyboard = None

        self.combo_entries = []
        self.combo_entries_available = []
        self.tabs = TabWidgetWithKeycodes()
        for x in range(128):
            entry = ComboEntryUI(x)
            entry.key_changed.connect(self.on_key_changed)
            self.combo_entries_available.append(entry)

        self.addWidget(self.tabs)

    def rebuild_ui(self):
        while self.tabs.count() > 0:
            self.tabs.removeTab(0)
        self.combo_entries = self.combo_entries_available[:self.keyboard.combo_count]
        for x, e in enumerate(self.combo_entries):
            self.tabs.addTab(e.widget(), str(x + 1))
        for x, e in enumerate(self.combo_entries):
            e.load(self.keyboard.combo_get(x))

    def rebuild(self, device):
        super().rebuild(device)
        if self.valid():
            self.keyboard = device.keyboard
            self.rebuild_ui()

    def valid(self):
        return isinstance(self.device, VialKeyboard) and \
               (self.device.keyboard and self.device.keyboard.vial_protocol >= VIAL_PROTOCOL_DYNAMIC
                and self.device.keyboard.combo_count > 0)

    def on_key_changed(self):
        for x, e in enumerate(self.combo_entries):
            self.keyboard.combo_set(x, self.combo_entries[x].save())
