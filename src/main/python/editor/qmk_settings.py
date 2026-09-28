# SPDX-License-Identifier: GPL-2.0-or-later
import json
from collections import defaultdict

from PyQt5 import QtCore
from PyQt5.QtCore import pyqtSignal, QObject
from PyQt5.QtWidgets import QVBoxLayout, QCheckBox, QGridLayout, QLabel, QWidget, QSizePolicy, QTabWidget, QSpinBox, \
    QHBoxLayout, QPushButton, QMessageBox

from editor.basic_editor import BasicEditor
from protocol.constants import VIAL_PROTOCOL_QMK_SETTINGS
from util import tr
from vial_device import VialKeyboard


QMK_TITLE_TRANSLATIONS = {
    "Debounce": "디바운스 (스위치 튐 방지 시간, ms)",
    "Tapping term": "탭 판정 시간 (Tapping term, ms)",
    "Permissive hold": "허용 홀드 (Permissive hold - 빠른 타이핑 롤오버 허용)",
    "Hold on other key press": "다른 키 누름 시 즉시 홀드 판정 (Hold on other key press)",
    "Auto Shift": "오토 시프트 (길게 누르면 대문자/특수기호)",
    "Auto Shift timeout": "오토 시프트 지연 시간 (ms)",
    "Combo term": "콤보 동시입력 판정 시간 (Combo term, ms)",
    "Dynamic macro": "다이나믹 매크로",
    "Grave Escape": "스마트 물결표/ESC 전환 (Grave Escape)",
    "Mouse key delay": "마우스 키 반응 지연 (ms)",
    "Mouse key interval": "마우스 키 이동 간격 (ms)",
    "Mouse key max speed": "마우스 키 최대 속도",
    "Mouse key time to max": "마우스 키 가속 시간",
    "Mouse key wheel delay": "마우스 휠 반응 지연 (ms)",
    "Mouse key wheel interval": "마우스 휠 스크롤 간격 (ms)",
    "Mouse key wheel max speed": "마우스 휠 최대 속도",
    "Mouse key wheel time to max": "마우스 휠 가속 시간",
}

QMK_TAB_TRANSLATIONS = {
    "General": "기본 설정 (General)",
    "Debounce": "디바운스 (Debounce)",
    "Tapping": "탭 판정 (Tapping)",
    "Auto Shift": "오토 시프트 (Auto Shift)",
    "Combo": "콤보 (Combo)",
    "Mouse keys": "마우스 키 (Mouse keys)",
    "Dynamic Macro": "다이나믹 매크로",
}


class GenericOption(QObject):

    changed = pyqtSignal()

    def __init__(self, option, container):
        super().__init__()

        self.row = container.rowCount()
        self.option = option
        self.qsid = self.option["qsid"]
        self.container = container

        orig_title = option["title"]
        display_title = QMK_TITLE_TRANSLATIONS.get(orig_title, orig_title)
        self.lbl = QLabel(display_title)
        self.container.addWidget(self.lbl, self.row, 0)

    def reload(self, keyboard):
        return keyboard.settings.get(self.qsid)

    def delete(self):
        self.lbl.hide()
        self.lbl.deleteLater()

    def on_change(self):
        self.changed.emit()


class BooleanOption(GenericOption):

    def __init__(self, option, container):
        super().__init__(option, container)

        self.qsid_bit = self.option.get("bit", 0)

        self.checkbox = QCheckBox()
        self.checkbox.stateChanged.connect(self.on_change)
        self.container.addWidget(self.checkbox, self.row, 1)

    def reload(self, keyboard):
        value = super().reload(keyboard)
        checked = value & (1 << self.qsid_bit)

        self.checkbox.blockSignals(True)
        self.checkbox.setChecked(checked != 0)
        self.checkbox.blockSignals(False)

    def value(self):
        checked = int(self.checkbox.isChecked())
        return checked << self.qsid_bit

    def delete(self):
        super().delete()
        self.checkbox.hide()
        self.checkbox.deleteLater()


class IntegerOption(GenericOption):

    def __init__(self, option, container):
        super().__init__(option, container)

        self.spinbox = QSpinBox()
        self.spinbox.setMinimum(option["min"])
        self.spinbox.setMaximum(option["max"])
        self.spinbox.valueChanged.connect(self.on_change)
        self.container.addWidget(self.spinbox, self.row, 1)

    def reload(self, keyboard):
        value = super().reload(keyboard)
        self.spinbox.blockSignals(True)
        self.spinbox.setValue(value)
        self.spinbox.blockSignals(False)

    def value(self):
        return self.spinbox.value()

    def delete(self):
        super().delete()
        self.spinbox.hide()
        self.spinbox.deleteLater()


class QmkSettings(BasicEditor):

    def __init__(self):
        super().__init__()
        self.keyboard = None

        self.tabs_widget = QTabWidget()
        self.addWidget(self.tabs_widget)
        buttons = QHBoxLayout()
        buttons.addStretch()
        self.btn_save = QPushButton("💾 설정 저장 (Save)")
        self.btn_save.setFixedHeight(30)
        self.btn_save.setStyleSheet("background-color: #238636; color: white; font-weight: bold; padding: 0 14px; border-radius: 4px;")
        self.btn_save.clicked.connect(self.save_settings)
        buttons.addWidget(self.btn_save)
        self.btn_undo = QPushButton("🔄 되돌리기 (Undo)")
        self.btn_undo.setFixedHeight(30)
        self.btn_undo.clicked.connect(self.reload_settings)
        buttons.addWidget(self.btn_undo)
        btn_reset = QPushButton("⚠️ 기본값 초기화 (Reset)")
        btn_reset.setFixedHeight(30)
        btn_reset.clicked.connect(self.reset_settings)
        buttons.addWidget(btn_reset)
        self.addLayout(buttons)

        self.tabs = []
        self.misc_widgets = []

    def populate_tab(self, tab, container):
        options = []
        for field in tab["fields"]:
            if field["qsid"] not in self.keyboard.supported_settings:
                continue
            if field["type"] == "boolean":
                opt = BooleanOption(field, container)
                options.append(opt)
                opt.changed.connect(self.on_change)
            elif field["type"] == "integer":
                opt = IntegerOption(field, container)
                options.append(opt)
                opt.changed.connect(self.on_change)
            else:
                raise RuntimeError("unsupported field type: {}".format(field))
        return options

    def recreate_gui(self):
        # delete old GUI
        for tab in self.tabs:
            for field in tab:
                field.delete()
        self.tabs.clear()
        for w in self.misc_widgets:
            w.hide()
            w.deleteLater()
        self.misc_widgets.clear()
        while self.tabs_widget.count() > 0:
            self.tabs_widget.removeTab(0)

        # create new GUI
        for tab in self.settings_defs["tabs"]:
            # don't bother creating tabs that would be empty - i.e. at least one qsid in a tab should be supported
            use_tab = False
            for field in tab["fields"]:
                if field["qsid"] in self.keyboard.supported_settings:
                    use_tab = True
                    break
            if not use_tab:
                continue

            w = QWidget()
            w.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
            container = QGridLayout()
            container.setSpacing(10)
            w.setLayout(container)

            guide_box = QLabel("""
            <div style="background-color: #161b22; border: 1px solid #30363d; border-left: 4px solid #f0883e; padding: 10px 14px; border-radius: 6px; font-size: 12px; line-height: 1.5; color: #e6edf3; max-width: 580px;">
                <b style="color: #ffa657; font-size: 13px;">💡 QMK 고급 설정 안내 & 예시</b><br>
                • <b>Tapping term:</b> 탭댄스나 레이어 홀드 판정 시간 (기본 200ms, 빠른 타건 시 160~180ms 추천)<br>
                • <b>Debounce:</b> 스위치 튐으로 인한 중복 입력(채터링) 방지 시간 (기본 5ms)<br>
                • 값을 수정한 후 아래 <b>[💾 설정 저장 (Save)]</b> 버튼을 누르면 EEPROM에 영구 저장됩니다.
            </div>
            """)
            guide_box.setTextFormat(QtCore.Qt.RichText)

            l = QVBoxLayout()
            l.addSpacing(6)
            l.addWidget(guide_box)
            l.setAlignment(guide_box, QtCore.Qt.AlignHCenter)
            l.addSpacing(10)
            l.addWidget(w)
            l.setAlignment(w, QtCore.Qt.AlignHCenter)
            l.addStretch()

            w2 = QWidget()
            w2.setLayout(l)
            self.misc_widgets += [w, w2]
            display_tab_name = QMK_TAB_TRANSLATIONS.get(tab["name"], tab["name"])
            self.tabs_widget.addTab(w2, display_tab_name)
            self.tabs.append(self.populate_tab(tab, container))

    def reload_settings(self):
        self.keyboard.reload_settings()
        self.recreate_gui()

        for tab in self.tabs:
            for field in tab:
                field.reload(self.keyboard)

        self.on_change()

    def on_change(self):
        changed = False
        qsid_values = self.prepare_settings()

        for x, tab in enumerate(self.tabs):
            tab_changed = False
            for opt in tab:
                if qsid_values[opt.qsid] != self.keyboard.settings[opt.qsid]:
                    changed = True
                    tab_changed = True
            title = self.tabs_widget.tabText(x).rstrip("*")
            if tab_changed:
                self.tabs_widget.setTabText(x, title + "*")
            else:
                self.tabs_widget.setTabText(x, title)

        self.btn_save.setEnabled(changed)
        self.btn_undo.setEnabled(changed)

    def rebuild(self, device):
        super().rebuild(device)
        if self.valid():
            self.keyboard = device.keyboard
            self.reload_settings()

    def prepare_settings(self):
        qsid_values = defaultdict(int)
        for tab in self.tabs:
            for field in tab:
                qsid_values[field.qsid] |= field.value()
        return qsid_values

    def save_settings(self):
        qsid_values = self.prepare_settings()
        for qsid, value in qsid_values.items():
            self.keyboard.qmk_settings_set(qsid, value)
        self.on_change()

    def reset_settings(self):
        if QMessageBox.question(self.widget(), "",
                                tr("QmkSettings", "Reset all settings to default values?"),
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.keyboard.qmk_settings_reset()
            self.reload_settings()

    def valid(self):
        return isinstance(self.device, VialKeyboard) and \
               (self.device.keyboard and self.device.keyboard.vial_protocol >= VIAL_PROTOCOL_QMK_SETTINGS
                and len(self.device.keyboard.supported_settings))

    @classmethod
    def initialize(cls, appctx):
        cls.qsid_fields = defaultdict(list)
        with open(appctx.get_resource("qmk_settings.json"), "r") as inf:
            cls.settings_defs = json.load(inf)
        for tab in cls.settings_defs["tabs"]:
            for field in tab["fields"]:
                cls.qsid_fields[field["qsid"]].append(field)

    @classmethod
    def is_qsid_supported(cls, qsid):
        """ Return whether this qsid is supported by the settings editor """
        return qsid in cls.qsid_fields

    @classmethod
    def qsid_serialize(cls, qsid, data):
        """ Serialize from internal representation into binary that can be sent to the firmware """
        fields = cls.qsid_fields[qsid]
        if fields[0]["type"] == "boolean":
            assert isinstance(data, int)
            return data.to_bytes(fields[0].get("width", 1), byteorder="little")
        elif fields[0]["type"] == "integer":
            assert isinstance(data, int)
            assert len(fields) == 1
            return data.to_bytes(fields[0]["width"], byteorder="little")

    @classmethod
    def qsid_deserialize(cls, qsid, data):
        """ Deserialize from binary received from firmware into internal representation """
        fields = cls.qsid_fields[qsid]
        if fields[0]["type"] == "boolean":
            return int.from_bytes(data[0:fields[0].get("width", 1)], byteorder="little")
        elif fields[0]["type"] == "integer":
            assert len(fields) == 1
            return int.from_bytes(data[0:fields[0]["width"]], byteorder="little")
        else:
            raise RuntimeError("unsupported field")
