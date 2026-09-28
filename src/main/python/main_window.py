# SPDX-License-Identifier: GPL-2.0-or-later
import logging
import platform
from json import JSONDecodeError

from PyQt5.QtCore import Qt, QSettings, QStandardPaths, QTimer, QRect, QT_VERSION_STR
from PyQt5.QtWidgets import QWidget, QComboBox, QToolButton, QHBoxLayout, QVBoxLayout, QMainWindow, QAction, qApp, \
    QFileDialog, QDialog, QTabWidget, QActionGroup, QMessageBox, QLabel, QPushButton, QTextBrowser

import os
import sys

from about_keyboard import AboutKeyboard
from autorefresh.autorefresh import Autorefresh
from editor.alt_repeat_key import AltRepeatKey
from editor.combos import Combos
from constants import WINDOW_WIDTH, WINDOW_HEIGHT
from widgets.editor_container import EditorContainer
from editor.firmware_flasher import FirmwareFlasher
from editor.key_override import KeyOverride
from protocol.keyboard_comm import ProtocolError
from editor.keymap_editor import KeymapEditor
from keymaps import KEYMAPS
from editor.layout_editor import LayoutEditor
from editor.macro_recorder import MacroRecorder
from editor.qmk_settings import QmkSettings
from editor.rgb_configurator import RGBConfigurator
from tabbed_keycodes import TabbedKeycodes
from editor.tap_dance import TapDance
from editor.charybdis_editor import CharybdisEditor
from unlocker import Unlocker
from util import tr, EXAMPLE_KEYBOARDS, KeycodeDisplay, EXAMPLE_KEYBOARD_PREFIX
from vial_device import VialKeyboard
from editor.matrix_test import MatrixTest

import themes


class MainWindow(QMainWindow):

    def __init__(self, appctx):
        super().__init__()
        self.appctx = appctx

        self.ui_lock_count = 0

        self.settings = QSettings("Vial", "Vial")
        if self.settings.value("size", None):
            self.resize(self.settings.value("size"))
        else:
            self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)

        _pos = self.settings.value("pos", None)
        # NOTE: QDesktopWidget is obsolete, but QApplication.screenAt only usable in Qt 5.10+
        if _pos and qApp.desktop().geometry().contains(QRect(_pos, self.size())):
        #if _pos and qApp.screenAt(_pos) and qApp.screenAt(_pos + (self.rect().bottomRight())):
            self.move(self.settings.value("pos"))

        if self.settings.value("maximized", False, bool):
            self.showMaximized()

        themes.Theme.set_theme(self.get_theme())

        self.combobox_devices = QComboBox()
        self.combobox_devices.currentIndexChanged.connect(self.on_device_selected)

        self.btn_refresh_devices = QToolButton()
        self.btn_refresh_devices.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.btn_refresh_devices.setText(tr("MainWindow", "Refresh"))
        self.btn_refresh_devices.clicked.connect(self.on_click_refresh)

        layout_combobox = QHBoxLayout()
        layout_combobox.addWidget(self.combobox_devices)
        if sys.platform != "emscripten":
            layout_combobox.addWidget(self.btn_refresh_devices)

        self.btn_guide = QPushButton("📖 탭별 기능 가이드 & 예시")
        self.btn_guide.setFixedHeight(26)
        self.btn_guide.setStyleSheet("""
            QPushButton {
                background-color: #1f6feb;
                color: white;
                font-weight: bold;
                font-size: 12px;
                border-radius: 4px;
                padding: 0 10px;
                border: 1px solid #388bfd;
            }
            QPushButton:hover {
                background-color: #388bfd;
            }
        """)
        self.btn_guide.clicked.connect(self.show_guide_dialog)
        layout_combobox.addWidget(self.btn_guide)

        self.btn_git_backup = QPushButton("☁️ Git에 레이아웃 백업")
        self.btn_git_backup.setFixedHeight(26)
        self.btn_git_backup.setStyleSheet("""
            QPushButton {
                background-color: #238636;
                color: white;
                font-weight: bold;
                font-size: 12px;
                border-radius: 4px;
                padding: 0 10px;
                border: 1px solid #2ea043;
            }
            QPushButton:hover {
                background-color: #2ea043;
            }
        """)
        self.btn_git_backup.clicked.connect(self.on_git_backup)
        layout_combobox.addWidget(self.btn_git_backup)

        self.btn_git_restore = QPushButton("📥 Git에서 불러오기")
        self.btn_git_restore.setFixedHeight(26)
        self.btn_git_restore.setStyleSheet("""
            QPushButton {
                background-color: #30363d;
                color: white;
                font-weight: bold;
                font-size: 12px;
                border-radius: 4px;
                padding: 0 10px;
                border: 1px solid #8b949e;
            }
            QPushButton:hover {
                background-color: #484f58;
            }
        """)
        self.btn_git_restore.clicked.connect(self.on_git_restore)
        layout_combobox.addWidget(self.btn_git_restore)

        self.layout_editor = LayoutEditor()
        self.keymap_editor = KeymapEditor(self.layout_editor)
        self.firmware_flasher = FirmwareFlasher(self)
        self.macro_recorder = MacroRecorder()
        self.tap_dance = TapDance()
        self.combos = Combos()
        self.key_override = KeyOverride()
        self.alt_repeat_key = AltRepeatKey()
        QmkSettings.initialize(appctx)
        self.qmk_settings = QmkSettings()
        self.matrix_tester = MatrixTest(self.layout_editor)
        self.rgb_configurator = RGBConfigurator()
        self.charybdis_settings = CharybdisEditor()

        self.editors = [(self.keymap_editor, "Keymap"), (self.layout_editor, "Layout"),
                        (self.charybdis_settings, "Charybdis"),
                        (self.macro_recorder, "Macros"), (self.rgb_configurator, "Lighting"),
                        (self.tap_dance, "Tap Dance"), (self.combos, "Combos"),
                        (self.key_override, "Key Overrides"), (self.alt_repeat_key, "Alt Repeat Key"),
                        (self.qmk_settings, "QMK Settings"), (self.matrix_tester, "Matrix tester"),
                        (self.firmware_flasher, "Firmware updater")]

        Unlocker.global_layout_editor = self.layout_editor
        Unlocker.global_main_window = self

        self.current_tab = None
        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self.on_tab_changed)
        self.refresh_tabs()

        no_devices = 'No devices detected. Connect a Vial-compatible device and press "Refresh"<br>' \
                     'or select "File" → "Download VIA definitions" in order to enable support for VIA keyboards.'
        if sys.platform.startswith("linux"):
            no_devices += '<br><br>On Linux you need to set up a custom udev rule for keyboards to be detected. ' \
                          'Follow the instructions linked below:<br>' \
                          '<a href="https://get.vial.today/manual/linux-udev.html">https://get.vial.today/manual/linux-udev.html</a>'
        self.lbl_no_devices = QLabel(tr("MainWindow", no_devices))
        self.lbl_no_devices.setTextFormat(Qt.RichText)
        self.lbl_no_devices.setAlignment(Qt.AlignCenter)

        layout = QVBoxLayout()
        layout.addLayout(layout_combobox)
        layout.addWidget(self.tabs, 1)
        layout.addWidget(self.lbl_no_devices)
        layout.setAlignment(self.lbl_no_devices, Qt.AlignHCenter)
        self.tray_keycodes = TabbedKeycodes()
        self.tray_keycodes.make_tray()
        layout.addWidget(self.tray_keycodes, 1)
        self.tray_keycodes.hide()
        w = QWidget()
        w.setLayout(layout)
        self.setCentralWidget(w)

        self.init_menu()

        self.autorefresh = Autorefresh()
        self.autorefresh.devices_updated.connect(self.on_devices_updated)

        # cache for via definition files
        self.cache_path = QStandardPaths.writableLocation(QStandardPaths.CacheLocation)
        if not os.path.exists(self.cache_path):
            os.makedirs(self.cache_path)

        # check if the via defitions already exist
        if os.path.isfile(os.path.join(self.cache_path, "via_keyboards.json")):
            with open(os.path.join(self.cache_path, "via_keyboards.json")) as vf:
                data = vf.read()
            try:
                self.autorefresh.load_via_stack(data)
            except JSONDecodeError as e:
                # the saved file is invalid - just ignore this
                logging.warning("Failed to parse stored via_keyboards.json: {}".format(e))

        # make sure initial state is valid
        self.on_click_refresh()

        if sys.platform == "emscripten":
            import vialglue
            QTimer.singleShot(100, vialglue.notify_ready)

    def init_menu(self):
        layout_load_act = QAction(tr("MenuFile", "Load saved layout..."), self)
        layout_load_act.setShortcut("Ctrl+O")
        layout_load_act.triggered.connect(self.on_layout_load)

        layout_save_act = QAction(tr("MenuFile", "Save current layout..."), self)
        layout_save_act.setShortcut("Ctrl+S")
        layout_save_act.triggered.connect(self.on_layout_save)

        sideload_json_act = QAction(tr("MenuFile", "Sideload VIA JSON..."), self)
        sideload_json_act.triggered.connect(self.on_sideload_json)

        download_via_stack_act = QAction(tr("MenuFile", "Download VIA definitions"), self)
        download_via_stack_act.triggered.connect(self.load_via_stack_json)

        load_dummy_act = QAction(tr("MenuFile", "Load dummy JSON..."), self)
        load_dummy_act.triggered.connect(self.on_load_dummy)

        exit_act = QAction(tr("MenuFile", "Exit"), self)
        exit_act.setShortcut("Ctrl+Q")
        exit_act.triggered.connect(self.close)

        file_menu = self.menuBar().addMenu(tr("Menu", "File"))
        file_menu.addAction(layout_load_act)
        file_menu.addAction(layout_save_act)

        if sys.platform != "emscripten":
            file_menu.addSeparator()
            file_menu.addAction(sideload_json_act)
            file_menu.addAction(download_via_stack_act)
            file_menu.addAction(load_dummy_act)
            file_menu.addSeparator()
            file_menu.addAction(exit_act)

        keyboard_unlock_act = QAction(tr("MenuSecurity", "Unlock"), self)
        keyboard_unlock_act.setShortcut("Ctrl+U")
        keyboard_unlock_act.triggered.connect(self.unlock_keyboard)

        keyboard_lock_act = QAction(tr("MenuSecurity", "Lock"), self)
        keyboard_lock_act.setShortcut("Ctrl+L")
        keyboard_lock_act.triggered.connect(self.lock_keyboard)

        keyboard_reset_act = QAction(tr("MenuSecurity", "Reboot to bootloader"), self)
        keyboard_reset_act.setShortcut("Ctrl+B")
        keyboard_reset_act.triggered.connect(self.reboot_to_bootloader)

        keyboard_layout_menu = self.menuBar().addMenu(tr("Menu", "Keyboard layout"))
        keymap_group = QActionGroup(self)
        selected_keymap = self.settings.value("keymap")
        for idx, keymap in enumerate(KEYMAPS):
            act = QAction(tr("KeyboardLayout", keymap[0]), self)
            act.triggered.connect(lambda checked, x=idx: self.change_keyboard_layout(x))
            act.setCheckable(True)
            if selected_keymap == keymap[0]:
                self.change_keyboard_layout(idx)
                act.setChecked(True)
            keymap_group.addAction(act)
            keyboard_layout_menu.addAction(act)
        # check "QWERTY" if nothing else is selected
        if keymap_group.checkedAction() is None:
            keymap_group.actions()[0].setChecked(True)

        self.security_menu = self.menuBar().addMenu(tr("Menu", "Security"))
        self.security_menu.addAction(keyboard_unlock_act)
        self.security_menu.addAction(keyboard_lock_act)
        self.security_menu.addSeparator()
        self.security_menu.addAction(keyboard_reset_act)

        if sys.platform != "emscripten":
            self.theme_menu = self.menuBar().addMenu(tr("Menu", "Theme"))
            theme_group = QActionGroup(self)
            selected_theme = self.get_theme()
            for name, _ in [("System", None)] + themes.themes:
                act = QAction(tr("MenuTheme", name), self)
                act.triggered.connect(lambda x,name=name: self.set_theme(name))
                act.setCheckable(True)
                act.setChecked(selected_theme == name)
                theme_group.addAction(act)
                self.theme_menu.addAction(act)
            # check "System" if nothing else is selected
            if theme_group.checkedAction() is None:
                theme_group.actions()[0].setChecked(True)

        about_vial_act = QAction(tr("MenuAbout", "About Vial..."), self)
        about_vial_act.triggered.connect(self.about_vial)
        self.about_keyboard_act = QAction("", self)
        self.about_keyboard_act.triggered.connect(self.about_keyboard)
        self.about_menu = self.menuBar().addMenu(tr("Menu", "About"))
        self.about_menu.addAction(self.about_keyboard_act)
        self.about_menu.addAction(about_vial_act)

    def on_layout_loaded(self, layout):
        """
        Receives a message from the JS bridge when a layout has
        been loaded via the JS File System API.
        """
        self.keymap_editor.restore_layout(layout)
        self.rebuild()

    def on_layout_load(self):
        if sys.platform == "emscripten":
            import vialglue
            # Tells the JS bridge to open a file selection dialog
            # so the user can load a layout.
            vialglue.load_layout()
        else:
            dialog = QFileDialog()
            dialog.setDefaultSuffix("vil")
            dialog.setAcceptMode(QFileDialog.AcceptOpen)
            dialog.setNameFilters(["Vial layout (*.vil)"])
            if dialog.exec_() == QDialog.Accepted:
                with open(dialog.selectedFiles()[0], "rb") as inf:
                    data = inf.read()
                self.keymap_editor.restore_layout(data)
                self.rebuild()

    def on_layout_save(self):
        if sys.platform == "emscripten":
            import vialglue
            layout = self.keymap_editor.save_layout()
            # Passes the current layout to the JS bridge so it can
            # open a file dialog and allow the user to save it to disk.
            vialglue.save_layout(layout)
        else:
            dialog = QFileDialog()
            dialog.setDefaultSuffix("vil")
            dialog.setAcceptMode(QFileDialog.AcceptSave)
            dialog.setNameFilters(["Vial layout (*.vil)"])
            if dialog.exec_() == QDialog.Accepted:
                with open(dialog.selectedFiles()[0], "wb") as outf:
                    outf.write(self.keymap_editor.save_layout())

    def on_click_refresh(self):
        self.autorefresh.update(quiet=False, hard=True)

    def on_devices_updated(self, devices, hard_refresh):
        self.combobox_devices.blockSignals(True)

        self.combobox_devices.clear()
        for dev in devices:
            self.combobox_devices.addItem(dev.title())
            if self.autorefresh.current_device and dev.desc["path"] == self.autorefresh.current_device.desc["path"]:
                self.combobox_devices.setCurrentIndex(self.combobox_devices.count() - 1)

        self.combobox_devices.blockSignals(False)

        if devices:
            self.lbl_no_devices.hide()
            self.tabs.show()
        else:
            self.lbl_no_devices.show()
            self.tabs.hide()

        if hard_refresh:
            self.on_device_selected()

    def on_device_selected(self):
        try:
            self.autorefresh.select_device(self.combobox_devices.currentIndex())
        except ProtocolError:
            QMessageBox.warning(self, "", "Unsupported protocol version!\n"
                                          "Please download latest Vial from https://get.vial.today/")
        except Exception as e:
            logging.error(f"Error selecting device: {e}")
            return

        if isinstance(self.autorefresh.current_device, VialKeyboard):
            keyboard_id = self.autorefresh.current_device.keyboard.keyboard_id
            if (keyboard_id in EXAMPLE_KEYBOARDS) or ((keyboard_id & 0xFFFFFFFFFFFFFF) == EXAMPLE_KEYBOARD_PREFIX):
                QMessageBox.warning(self, "", "An example keyboard UID was detected.\n"
                                              "Please change your keyboard UID to be unique before you ship!")

        self.rebuild()
        self.refresh_tabs()

    def rebuild(self):
        # don't show "Security" menu for bootloader mode, as the bootloader is inherently insecure
        self.security_menu.menuAction().setVisible(isinstance(self.autorefresh.current_device, VialKeyboard))

        self.about_keyboard_act.setVisible(False)
        if isinstance(self.autorefresh.current_device, VialKeyboard):
            self.about_keyboard_act.setText("About {}...".format(self.autorefresh.current_device.title()))
            self.about_keyboard_act.setVisible(True)

        # if unlock process was interrupted, we must finish it first
        if isinstance(self.autorefresh.current_device, VialKeyboard) and self.autorefresh.current_device.keyboard.get_unlock_in_progress():
            Unlocker.unlock(self.autorefresh.current_device.keyboard)
            self.autorefresh.current_device.keyboard.reload()

        for e in [self.layout_editor, self.keymap_editor, self.firmware_flasher, self.macro_recorder,
                  self.tap_dance, self.combos, self.key_override, self.alt_repeat_key,
                  self.qmk_settings, self.matrix_tester, self.rgb_configurator, self.charybdis_settings]:
            e.rebuild(self.autorefresh.current_device)

    TAB_NAMES = {
        "Keymap": ("⌨️ 키맵 (Keymap)", "기본 레이어 0~3의 모든 키 배치를 클릭하여 자유롭게 변경합니다."),
        "Layout": ("📐 레이아웃 (Layout)", "물리적 키보드 레이아웃 형상을 확인합니다."),
        "Charybdis": ("✨ Charybdis 설정", "레이어별 RGB 색상, 트랙볼 DPI 감도, 오토마우스를 설정하고 실시간 자동 저장합니다."),
        "Macros": ("⚡ 매크로 (Macros)", "한 번의 키 입력으로 긴 문자열이나 일련의 단축키 조합을 자동 타이핑합니다."),
        "Lighting": ("💡 전체 조명 (Lighting)", "전체 RGB 밝기, 조명 효과 모드, 기본 색상을 설정합니다."),
        "Tap Dance": ("💃 탭 댄스 (Tap Dance)", "키를 한 번 누를 때, 두 번 연타할 때, 길게 누를 때 각각 다른 동작을 수행하게 합니다."),
        "Combos": ("🧩 콤보 (Combos)", "두 개 이상의 키를 동시에 눌렀을 때 특정 키나 특수 기능을 발동합니다."),
        "Key Overrides": ("🔄 키 오버라이드 (Overrides)", "특정 조합(예: Shift + Backspace)을 다른 키(예: Delete)로 가로채어 변경합니다."),
        "Alt Repeat Key": ("🔁 키 반복 (Alt Repeat)", "이전에 누른 키를 반복하거나 특정 대체 키를 출력합니다."),
        "QMK Settings": ("⚙️ QMK 고급설정 (Settings)", "디바운스, 탭 홀드 시간, 자동 마우스 레이어 등 QMK 내부 변수를 조절합니다."),
        "Matrix tester": ("🧪 키 입력 테스트 (Tester)", "키보드의 각 스위치와 트랙볼이 정상적으로 입력되는지 시각적으로 테스트합니다."),
        "Firmware updater": ("🚀 펌웨어 업데이트 (Updater)", "부트로더 진입 및 펌웨어 업데이트를 수행합니다."),
    }

    def refresh_tabs(self):
        self.tabs.clear()
        for container, lbl in self.editors:
            if not container.valid():
                continue

            c = EditorContainer(container)
            display_title, tooltip = self.TAB_NAMES.get(lbl, (lbl, ""))
            idx = self.tabs.addTab(c, display_title)
            if tooltip:
                self.tabs.setTabToolTip(idx, tooltip)

    def show_guide_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Charybdis Vial 탭별 기능 가이드 & 활용 예시")
        dialog.resize(800, 650)
        d_layout = QVBoxLayout(dialog)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        guide_html = """
        <div style="font-family: 'Segoe UI', Malgun Gothic, sans-serif; font-size: 13px; line-height: 1.6; color: #e6edf3; background-color: #0d1117; padding: 12px;">
            <h1 style="color: #58a6ff; font-size: 20px; border-bottom: 2px solid #30363d; padding-bottom: 8px;">📖 Charybdis Vial 탭별 상세 가이드 & 활용 예시</h1>
            <p style="color: #8b949e;">각 탭의 역할과 미니멀 3x6 스플릿 인체공학 키보드에서 200% 활용할 수 있는 실전 예시 안내입니다.</p>

            <h2 style="color: #79c0ff; font-size: 16px; margin-top: 20px;">⌨️ 1. 키맵 (Keymap)</h2>
            <p><b>역할:</b> 레이어 0부터 레이어 3까지 각 스위치를 눌렀을 때 입력될 키코드를 자유롭게 변경합니다.</p>
            <div style="background-color: #161b22; border-left: 3px solid #58a6ff; padding: 8px 12px; margin-bottom: 12px; border-radius: 4px;">
                <b>💡 활용 예시:</b>
                <ul>
                    <li>엄지 클러스터 키에 <code>MO(1)</code>(누르는 동안 Layer 1 임시 이동), <code>TG(2)</code>(Layer 2 토글)를 지정하여 작은 키 개수로도 108키 풀배열의 모든 기능을 사용합니다.</li>
                    <li>Charybdis 전용 키코드인 <code>DRAG</code>(드래그 스크롤), <code>SNIPE</code>(스나이퍼 감도), <code>DPI+</code>, <code>DPI-</code>를 엄지 키에 배치하여 마우스 없이 손가락 하나로 모든 조작을 완성합니다.</li>
                </ul>
            </div>

            <h2 style="color: #79c0ff; font-size: 16px; margin-top: 20px;">✨ 2. Charybdis 설정</h2>
            <p><b>역할:</b> 카립디스 내장 트랙볼 감도와 레이어별 독립 RGB 색상을 제어합니다. 조절 즉시 키보드 메모리(EEPROM)에 자동 영구 저장됩니다.</p>
            <div style="background-color: #161b22; border-left: 3px solid #3fb950; padding: 8px 12px; margin-bottom: 12px; border-radius: 4px;">
                <b>💡 활용 예시:</b>
                <ul>
                    <li><b>레이어별 색상:</b> Layer 1(기능키) = 파랑, Layer 2(숫자패드) = 보라, Layer 3(마우스 모드) = 초록으로 지정하여 현재 어떤 레이어에 있는지 눈으로 직관적 확인.</li>
                    <li><b>스마트 감도 조절:</b> 평상시 웹서핑 시 Default DPI 800, 포토샵 누끼따기/정밀 그래픽 작업 시 Sniping DPI 200으로 설정.</li>
                </ul>
            </div>

            <h2 style="color: #79c0ff; font-size: 16px; margin-top: 20px;">⚡ 3. 매크로 (Macros)</h2>
            <p><b>역할:</b> 단 한 번의 키 입력으로 긴 문장이나 연속된 단축키 시퀀스를 자동으로 타이핑합니다.</p>
            <div style="background-color: #161b22; border-left: 3px solid #d29922; padding: 8px 12px; margin-bottom: 12px; border-radius: 4px;">
                <b>💡 활용 예시:</b>
                <ul>
                    <li>자주 쓰는 본인 이메일 주소나 로그인 아이디를 매크로 <code>M0</code>에 등록하고 특정 키에 할당하여 1초 만에 자동 완성.</li>
                    <li>개발 작업 시 자주 쓰는 깃 명령어 <code>git status && git pull</code> 또는 디렉터리 경로를 단축키 하나로 실행.</li>
                </ul>
            </div>

            <h2 style="color: #79c0ff; font-size: 16px; margin-top: 20px;">💡 4. 전체 조명 (Lighting)</h2>
            <p><b>역할:</b> QMK 내장 RGB Matrix 효과를 설정합니다. 전체 밝기, 애니메이션 효과, 속도를 제어합니다.</p>
            <div style="background-color: #161b22; border-left: 3px solid #f0883e; padding: 8px 12px; margin-bottom: 12px; border-radius: 4px;">
                <b>💡 활용 예시:</b>
                <ul>
                    <li>야간 작업 시 눈부심을 줄이기 위해 밝기를 낮추거나, 무지개(Rainbow) 및 브리딩(Breathing) 등 취향에 맞는 조명 효과 선택.</li>
                </ul>
            </div>

            <h2 style="color: #79c0ff; font-size: 16px; margin-top: 20px;">💃 5. 탭 댄스 (Tap Dance)</h2>
            <p><b>역할:</b> 같은 스위치 하나로 "1번 누름", "2번 연속 탭", "길게 누름(Hold)", "탭 후 길게 누름"에 각각 완전히 다른 4가지 동작을 할당합니다.</p>
            <div style="background-color: #161b22; border-left: 3px solid #a371f7; padding: 8px 12px; margin-bottom: 12px; border-radius: 4px;">
                <b>💡 활용 예시:</b>
                <ul>
                    <li><b>스페이스바 탭댄스:</b> 가볍게 1번 탭하면 <code>Space</code>(공백), 길게 꾹 누르고 있으면 <code>한/영 전환</code> 또는 <code>Shift</code>로 작동!</li>
                    <li><b>세미콜론 탭댄스:</b> 1번 탭 = <code>;</code> (세미콜론), 2번 연속 탭 = <code>:</code> (콜론), 길게 누르면 <code>Enter</code> 입력.</li>
                </ul>
            </div>

            <h2 style="color: #79c0ff; font-size: 16px; margin-top: 20px;">🧩 6. 콤보 (Combos)</h2>
            <p><b>역할:</b> 두 개 이상의 키를 "동시에" 딱 눌렀을 때 특정 키나 특수 기능을 발동합니다.</p>
            <div style="background-color: #161b22; border-left: 3px solid #58a6ff; padding: 8px 12px; margin-bottom: 12px; border-radius: 4px;">
                <b>💡 활용 예시:</b>
                <ul>
                    <li><code>Q</code> + <code>W</code>를 동시에 누르면 <code>ESC</code>가 입력되도록 설정 (ESC를 누르려고 새끼손가락을 멀리 뻗지 않아도 됨).</li>
                    <li><code>J</code> + <code>K</code>를 동시에 누르면 <code>Enter</code>가 입력되도록 설정 (홈로우를 벗어나지 않고 타이핑 지속).</li>
                </ul>
            </div>

            <h2 style="color: #79c0ff; font-size: 16px; margin-top: 20px;">🔄 7. 키 오버라이드 (Key Overrides)</h2>
            <p><b>역할:</b> 특정 보조키(Shift 등)와 함께 눌렸을 때 기본 출력을 가로채어 완전히 다른 키로 치환합니다.</p>
            <div style="background-color: #161b22; border-left: 3px solid #3fb950; padding: 8px 12px; margin-bottom: 12px; border-radius: 4px;">
                <b>💡 활용 예시:</b>
                <ul>
                    <li><code>Shift</code> + <code>Backspace</code>를 누르면 <code>Delete</code>가 입력되도록 설정 (별도의 Delete 키 자리를 만들 필요가 없어짐).</li>
                    <li><code>Shift</code> + <code>1</code>을 누르면 <code>!</code> 대신 다른 특수기호가 나오도록 커스텀.</li>
                </ul>
            </div>

            <h2 style="color: #79c0ff; font-size: 16px; margin-top: 20px;">🔁 8. 키 반복 (Alt Repeat Key)</h2>
            <p><b>역할:</b> 방금 직전에 입력한 키를 한 번 더 반복하거나, 특정 키 뒤에 올 때 다른 키로 교체 입력합니다.</p>
            <div style="background-color: #161b22; border-left: 3px solid #d29922; padding: 8px 12px; margin-bottom: 12px; border-radius: 4px;">
                <b>💡 활용 예시:</b>
                <ul>
                    <li>반복 타이핑(예: <code>..</code> 또는 <code>--</code>) 시 같은 손가락을 연타하지 않고 다른 편한 손가락의 반복 키를 눌러 피로도 절감.</li>
                </ul>
            </div>

            <h2 style="color: #79c0ff; font-size: 16px; margin-top: 20px;">⚙️ 9. QMK 고급설정 (QMK Settings)</h2>
            <p><b>역할:</b> 펌웨어 재컴파일 없이 디바운스, 탭 홀드 판정 시간, 오토마우스 지연 등 QMK 내부 코어 파라미터를 조절합니다.</p>
            <div style="background-color: #161b22; border-left: 3px solid #f0883e; padding: 8px 12px; margin-bottom: 12px; border-radius: 4px;">
                <b>💡 활용 예시:</b>
                <ul>
                    <li>탭댄스 판정 시간(<code>Tapping Term</code>)이 너무 길거나 짧다고 느껴질 때 기본 200ms를 175ms 등으로 본인의 타건 속도에 맞춰 미세 조정.</li>
                </ul>
            </div>

            <h2 style="color: #79c0ff; font-size: 16px; margin-top: 20px;">🧪 10. 키 입력 테스트 (Matrix Tester)</h2>
            <p><b>역할:</b> 키보드의 모든 스위치를 눌렀을 때 PC에 키 신호가 정상 전달되는지 실시간 그래픽 매트릭스로 확인합니다.</p>
            <div style="background-color: #161b22; border-left: 3px solid #a371f7; padding: 8px 12px; margin-bottom: 12px; border-radius: 4px;">
                <b>💡 활용 예시:</b>
                <ul>
                    <li>키보드 스위치 교체(핫스왑) 후 접점 핀이 휘었거나 인식이 안 되는 스위치가 있는지 즉시 진단.</li>
                </ul>
            </div>
        </div>
        """
        browser.setHtml(guide_html)
        d_layout.addWidget(browser)

        btn_close = QPushButton("확인 및 닫기")
        btn_close.setFixedHeight(34)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #238636;
                color: white;
                font-weight: bold;
                font-size: 13px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #2ea043;
            }
        """)
        btn_close.clicked.connect(dialog.accept)
        d_layout.addWidget(btn_close)

        dialog.exec_()

    def load_via_stack_json(self):
        from urllib.request import urlopen

        with urlopen("https://github.com/vial-kb/via-keymap-precompiled/raw/main/via_keyboard_stack.json") as resp:
            data = resp.read()
        self.autorefresh.load_via_stack(data)
        # write to cache
        with open(os.path.join(self.cache_path, "via_keyboards.json"), "wb") as cf:
            cf.write(data)

    def on_sideload_json(self):
        dialog = QFileDialog()
        dialog.setDefaultSuffix("json")
        dialog.setAcceptMode(QFileDialog.AcceptOpen)
        dialog.setNameFilters(["VIA layout JSON (*.json)"])
        if dialog.exec_() == QDialog.Accepted:
            with open(dialog.selectedFiles()[0], "rb") as inf:
                data = inf.read()
            self.autorefresh.sideload_via_json(data)

    def on_load_dummy(self):
        dialog = QFileDialog()
        dialog.setDefaultSuffix("json")
        dialog.setAcceptMode(QFileDialog.AcceptOpen)
        dialog.setNameFilters(["VIA layout JSON (*.json)"])
        if dialog.exec_() == QDialog.Accepted:
            with open(dialog.selectedFiles()[0], "rb") as inf:
                data = inf.read()
            self.autorefresh.load_dummy(data)

    def lock_ui(self):
        self.ui_lock_count += 1
        if self.ui_lock_count == 1:
            self.autorefresh._lock()
            self.tabs.setEnabled(False)
            self.combobox_devices.setEnabled(False)
            self.btn_refresh_devices.setEnabled(False)

    def unlock_ui(self):
        self.ui_lock_count -= 1
        if self.ui_lock_count == 0:
            self.autorefresh._unlock()
            self.tabs.setEnabled(True)
            self.combobox_devices.setEnabled(True)
            self.btn_refresh_devices.setEnabled(True)

    def unlock_keyboard(self):
        if isinstance(self.autorefresh.current_device, VialKeyboard):
            Unlocker.unlock(self.autorefresh.current_device.keyboard)

    def lock_keyboard(self):
        if isinstance(self.autorefresh.current_device, VialKeyboard):
            self.autorefresh.current_device.keyboard.lock()

    def reboot_to_bootloader(self):
        if isinstance(self.autorefresh.current_device, VialKeyboard):
            Unlocker.unlock(self.autorefresh.current_device.keyboard)
            self.autorefresh.current_device.keyboard.reset()

    def change_keyboard_layout(self, index):
        self.settings.setValue("keymap", KEYMAPS[index][0])
        KeycodeDisplay.set_keymap_override(KEYMAPS[index][1])

    def get_theme(self):
        return self.settings.value("theme", "Dark")

    def set_theme(self, theme):
        themes.Theme.set_theme(theme)
        self.settings.setValue("theme", theme)
        msg = QMessageBox()
        msg.setText(tr("MainWindow", "In order to fully apply the theme you should restart the application."))
        msg.exec_()

    def on_tab_changed(self, index):
        TabbedKeycodes.close_tray()
        old_tab = self.current_tab
        new_tab = None
        if index >= 0:
            new_tab = self.tabs.widget(index)

        if old_tab is not None:
            old_tab.editor.deactivate()
        if new_tab is not None:
            new_tab.editor.activate()

        self.current_tab = new_tab

    def about_vial(self):
        title = "About Vial"
        text = 'Vial {}<br><br>Python {}<br>Qt {}<br><br>' \
               'Licensed under the terms of the<br>GNU General Public License (version 2 or later)<br><br>' \
               '<a href="https://get.vial.today/">https://get.vial.today/</a>' \
               .format(qApp.applicationVersion(),
                       platform.python_version(), QT_VERSION_STR)

        if sys.platform == "emscripten":
            self.msg_about = QMessageBox()
            self.msg_about.setWindowTitle(title)
            self.msg_about.setText(text)
            self.msg_about.setModal(True)
            self.msg_about.show()
        else:
            QMessageBox.about(self, title, text)

    def about_keyboard(self):
        self.about_dialog = AboutKeyboard(self.autorefresh.current_device)
        self.about_dialog.setModal(True)
        self.about_dialog.show()

    def on_git_backup(self):
        dev = self.autorefresh.current_device
        if not dev or not getattr(dev, "keyboard", None):
            QMessageBox.warning(self, "백업 실패", "연결된 Charybdis 키보드가 없습니다. 키보드를 연결 후 시도하세요.")
            return

        import json, subprocess, datetime, os
        from PyQt5.QtWidgets import QInputDialog
        from editor.git_sync_dialogs import GitProgressDialog

        memo, ok = QInputDialog.getText(
            self, "☁️ GitHub 레이아웃 백업",
            "이번 백업에 기록할 메모/설명을 입력하세요 (선택 사항):\n(예: 기본 작업용, 코딩 모드, 게임 세팅, 단축키 추가 등)",
            text=""
        )
        if not ok:
            return
        memo = memo.strip()

        base_dir = r"C:\vial-gui"
        saved_dir = os.path.join(base_dir, "saved_layouts")
        os.makedirs(saved_dir, exist_ok=True)

        progress = GitProgressDialog(self, title="☁️ GitHub 레이아웃 백업 진행 중")
        progress.show()
        progress.set_progress(10, "현재 키보드 레이아웃 및 설정 캡처 중...", "키맵, 탭댄스, 콤보, DPI 읽는 중")

        try:
            # 1. Capture current layout
            raw_layout = self.keymap_editor.save_layout()
            layout_data = json.loads(raw_layout.decode("utf-8"))

            # 2. Add Charybdis trackball & RGB configuration
            charybdis_cfg = {
                "default_dpi": self.charybdis_settings.slider_default_dpi.value(),
                "sniping_dpi": self.charybdis_settings.slider_sniping_dpi.value(),
                "auto_mouse_enable": self.charybdis_settings.chk_auto_mouse.isChecked(),
                "auto_mouse_time": self.charybdis_settings.slider_auto_mouse_time.value(),
                "scroll_invert_y": self.charybdis_settings.chk_rev_y.isChecked(),
                "layer_colors": {
                    "1": self.charybdis_settings.layer_swatches[1].current_rgb,
                    "2": self.charybdis_settings.layer_swatches[2].current_rgb,
                    "3": self.charybdis_settings.layer_swatches[3].current_rgb,
                }
            }
            layout_data["charybdis_config"] = charybdis_cfg

            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            now_file_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            layout_data["backup_timestamp"] = now_str
            layout_data["backup_memo"] = memo if memo else "수동 백업"

            # 3. Write files
            progress.set_progress(35, "로컬 백업 파일(JSON) 생성 및 저장 중...", f"파일명: charybdis_layout_{now_file_str}.json")
            latest_path = os.path.join(saved_dir, "charybdis_layout_latest.json")
            history_path = os.path.join(saved_dir, f"charybdis_layout_{now_file_str}.json")

            json_text = json.dumps(layout_data, indent=2, ensure_ascii=False)
            with open(latest_path, "w", encoding="utf-8") as f:
                f.write(json_text)
            with open(history_path, "w", encoding="utf-8") as f:
                f.write(json_text)

            # Also backup into QMK firmware repo if present
            qmk_backup_dir = r"C:\qmk_firmware\saved_layouts"
            try:
                os.makedirs(qmk_backup_dir, exist_ok=True)
                with open(os.path.join(qmk_backup_dir, "charybdis_layout_latest.json"), "w", encoding="utf-8") as f:
                    f.write(json_text)
            except Exception:
                pass

            # 4. Git add, commit, push
            progress.set_progress(60, "Git 변경 사항 스테이징 및 커밋 생성 중...", f"커밋 메시지: backup(layout): save Charybdis layout ({now_str})")
            subprocess.run(["git", "add", "saved_layouts/"], cwd=base_dir, check=True)
            commit_msg = f"backup(layout): save Charybdis layout ({now_str}) - {memo if memo else '수동 백업'}"
            subprocess.run(["git", "commit", "-m", commit_msg], cwd=base_dir)

            progress.set_progress(80, "GitHub 원격 저장소로 푸시(push) 전송 중...", "KimMinSeok-4856/vial-gui (feature/minseok-charybdis-vial)")
            proc = subprocess.run(["git", "push", "origin", "feature/minseok-charybdis-vial"],
                                  cwd=base_dir, capture_output=True, text=True, timeout=30)

            progress.set_progress(100, "백업 완료!", "모든 설정이 안전하게 클라우드에 백업되었습니다.")
            progress.close()

            if proc.returncode == 0:
                QMessageBox.information(
                    self, "GitHub 백업 완료",
                    f"🎉 현재 키보드 레이아웃이 GitHub에 성공적으로 백업되었습니다!\n\n"
                    f"• 저장소: KimMinSeok-4856/vial-gui\n"
                    f"• 브랜치: feature/minseok-charybdis-vial\n"
                    f"• 백업 파일: charybdis_layout_{now_file_str}.json\n"
                    f"• 백업 일시: {now_str}\n"
                    f"• 메모: {memo if memo else '없음'}\n\n"
                    f"모든 레이어(0~3), 탭댄스, 콤보, 키 오버라이드, 매크로 및 트랙볼/RGB 설정이 모두 안전하게 저장되었습니다."
                )
            else:
                QMessageBox.warning(
                    self, "GitHub 푸시 경고",
                    f"로컬 파일(saved_layouts/) 저장은 완료되었으나, GitHub 푸시 중 메시지가 발생했습니다:\n{proc.stderr}\n{proc.stdout}"
                )
        except Exception as e:
            if 'progress' in locals() and progress.isVisible():
                progress.close()
            QMessageBox.critical(self, "백업 오류", f"레이아웃 백업 중 오류가 발생했습니다:\n{e}")

    def on_git_restore(self):
        dev = self.autorefresh.current_device
        if not dev or not getattr(dev, "keyboard", None):
            QMessageBox.warning(self, "복원 실패", "연결된 Charybdis 키보드가 없습니다. 키보드를 연결 후 시도하세요.")
            return

        import json, subprocess, os
        from keycodes.keycodes import Keycode
        from editor.git_sync_dialogs import GitProgressDialog, RestoreSelectDialog

        base_dir = r"C:\vial-gui"
        saved_dir = os.path.join(base_dir, "saved_layouts")

        # 1. Sync from GitHub with progress dialog
        progress = GitProgressDialog(self, title="GitHub 백업 동기화 중")
        progress.show()
        progress.set_progress(20, "GitHub에서 최신 백업 목록 동기화 중 (git pull)...", "원격 저장소(KimMinSeok-4856/vial-gui)와 통신 중")

        try:
            subprocess.run(["git", "pull", "origin", "feature/minseok-charybdis-vial"],
                           cwd=base_dir, capture_output=True, text=True, timeout=15)
        except Exception:
            pass

        progress.set_progress(100, "동기화 완료!", "백업 목록을 불러옵니다.")
        progress.close()

        if not os.path.exists(saved_dir) or not os.listdir(saved_dir):
            QMessageBox.warning(self, "복원 파일 없음", "GitHub에 저장된 레이아웃 백업 파일이 없습니다.\n먼저 'Git에 레이아웃 백업'을 실행하세요.")
            return

        # 2. Show historical backup selection dialog
        dlg = RestoreSelectDialog(self, saved_dir=saved_dir)
        if dlg.exec_() != QDialog.Accepted:
            return

        selected_file = dlg.selected_path
        if not selected_file or not os.path.exists(selected_file):
            return

        try:
            with open(selected_file, "r", encoding="utf-8") as f:
                layout_data = json.load(f)

            backup_time = layout_data.get("backup_timestamp", "알 수 없음")
            backup_memo = layout_data.get("backup_memo", "메모 없음")
            res = QMessageBox.question(
                self, "레이아웃 복원 확인",
                f"선택한 백업을 키보드에 복원하시겠습니까?\n\n"
                f"• 백업 일시: {backup_time}\n"
                f"• 백업 메모: {backup_memo}\n"
                f"• 파일명: {os.path.basename(selected_file)}\n\n"
                f"복원 대상: 키맵(0~3 레이어), 탭댄스, 콤보, 키 오버라이드, 매크로, 트랙볼 감도 & RGB\n"
                f"복원 시 현재 키보드의 설정이 백업 시점의 상태로 덮어쓰기됩니다.",
                QMessageBox.Yes | QMessageBox.No
            )
            if res != QMessageBox.Yes:
                return

            # 3. Step-by-step restoration with live progress dialog
            progress = GitProgressDialog(self, title="키보드 레이아웃 복원 진행 중")
            progress.show()

            # (1) Keymap (Layers 0~3)
            layout = layout_data.get("layout", [])
            total_layers = len(layout)
            for l, layer in enumerate(layout):
                pct = 10 + int(25 * (l + 1) / max(1, total_layers))
                progress.set_progress(pct, f"1/6 단계: 레이어 {l} 키 배치 전송 중...", f"총 {total_layers}개 레이어 중 {l+1}번째 복원")
                for r, row in enumerate(layer):
                    for c, code in enumerate(row):
                        if (l, r, c) in dev.keyboard.layout:
                            dev.keyboard.set_key(l, r, c, Keycode.serialize(Keycode.deserialize(code)))
                QApplication.processEvents()

            # (2) Encoders & Layout Options
            if "encoder_layout" in layout_data:
                for l, layer in enumerate(layout_data["encoder_layout"]):
                    for e, encoder in enumerate(layer):
                        dev.keyboard.set_encoder(l, e, 0, Keycode.serialize(Keycode.deserialize(encoder[0])))
                        dev.keyboard.set_encoder(l, e, 1, Keycode.serialize(Keycode.deserialize(encoder[1])))
            if "layout_options" in layout_data and layout_data["layout_options"] != -1:
                dev.keyboard.set_layout_options(layout_data["layout_options"])

            # (3) Macros
            progress.set_progress(45, "2/6 단계: 매크로(Macros) 설정 복원 중...", "매크로 시퀀스 키보드 메모리에 전송 중")
            dev.keyboard.restore_macros(layout_data.get("macro"))
            QApplication.processEvents()

            # (4) Tap Dance
            progress.set_progress(60, "3/6 단계: 탭 댄스(Tap Dance) 설정 복원 중...", "한번/연타/길게 누르기 동작 복원 중")
            dev.keyboard.restore_tap_dance(layout_data.get("tap_dance", []))
            QApplication.processEvents()

            # (5) Combos & Key Overrides
            progress.set_progress(72, "4/6 단계: 콤보 및 키 오버라이드 복원 중...", "동시 입력 및 단축키 변환 규칙 복원 중")
            dev.keyboard.restore_combo(layout_data.get("combo", []))
            dev.keyboard.restore_key_override(layout_data.get("key_override", []))
            dev.keyboard.restore_alt_repeat_key(layout_data.get("alt_repeat_key", []))
            QApplication.processEvents()

            # (6) QMK Settings
            progress.set_progress(82, "5/6 단계: QMK 고급 설정 복원 중...", "디바운스, 탭홀드 타이머 등 전송 중")
            from editor.qmk_settings import QmkSettings
            for qsid, value in layout_data.get("settings", dict()).items():
                qsid = int(qsid)
                if QmkSettings.is_qsid_supported(qsid):
                    dev.keyboard.qmk_settings_set(qsid, value)
            QApplication.processEvents()

            # (7) Charybdis Settings (Trackball DPI, Auto Mouse, Layer RGB)
            if "charybdis_config" in layout_data:
                progress.set_progress(92, "6/6 단계: Charybdis 트랙볼 및 조명 복원 중...", "트랙볼 DPI 및 레이어별 RGB EEPROM 영구 저장")
                cfg = layout_data["charybdis_config"]
                self.charybdis_settings.slider_default_dpi.setValue(cfg.get("default_dpi", 800))
                self.charybdis_settings.slider_sniping_dpi.setValue(cfg.get("sniping_dpi", 200))
                self.charybdis_settings.chk_auto_mouse.setChecked(cfg.get("auto_mouse_enable", True))
                self.charybdis_settings.slider_auto_mouse_time.setValue(cfg.get("auto_mouse_time", 650))
                self.charybdis_settings.chk_rev_y.setChecked(cfg.get("scroll_invert_y", True))
                colors = cfg.get("layer_colors", {})
                if "1" in colors: self.charybdis_settings.layer_swatches[1].set_color(tuple(colors["1"]))
                if "2" in colors: self.charybdis_settings.layer_swatches[2].set_color(tuple(colors["2"]))
                if "3" in colors: self.charybdis_settings.layer_swatches[3].set_color(tuple(colors["3"]))
                self.charybdis_settings.send_live_config(auto_save_delay=0)
                self.charybdis_settings.save_to_eeprom()
                QApplication.processEvents()

            # (8) Refresh all UI editors
            progress.set_progress(98, "마무리: 에디터 화면 새로고침 중...", "UI 동기화 진행 중")
            current_tab = self.tabs.currentIndex()
            self.rebuild()
            if 0 <= current_tab < self.tabs.count():
                self.tabs.setCurrentIndex(current_tab)
            QApplication.processEvents()

            progress.set_progress(100, "복원 완료!", "키보드와 화면이 최신 상태로 동기화되었습니다.")
            progress.close()

            QMessageBox.information(
                self, "복원 완료",
                f"🎉 선택한 레이아웃이 키보드에 성공적으로 복원 및 영구 저장되었습니다!\n\n"
                f"• 복원된 백업: {backup_time} ({backup_memo})\n"
                f"• 복원 파일: {os.path.basename(selected_file)}"
            )
        except Exception as e:
            if 'progress' in locals() and progress.isVisible():
                progress.close()
            QMessageBox.critical(self, "복원 오류", f"레이아웃 복원 중 오류가 발생했습니다:\n{e}")

    def closeEvent(self, e):
        self.settings.setValue("size", self.size())
        self.settings.setValue("pos", self.pos())
        self.settings.setValue("maximized", self.isMaximized())

        e.accept()
