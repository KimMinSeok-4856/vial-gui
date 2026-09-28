# SPDX-License-Identifier: GPL-2.0-or-later
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QSlider, QCheckBox, QGroupBox, QColorDialog, QScrollArea,
    QWidget, QFrame, QMessageBox
)
from editor.basic_editor import BasicEditor


class ColorSwatchButton(QPushButton):
    def __init__(self, color=(255, 0, 0), parent=None):
        super().__init__(parent)
        self.setFixedHeight(34)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.set_color(color)

    def set_color(self, rgb):
        self.current_rgb = rgb
        r, g, b = rgb
        # Text color based on luminance
        lum = 0.299 * r + 0.587 * g + 0.114 * b
        text_color = "#000000" if lum > 140 else "#FFFFFF"
        hex_code = f"#{r:02X}{g:02X}{b:02X}"
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {hex_code};
                color: {text_color};
                border: 2px solid #555555;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton:hover {{
                border: 2px solid #FFFFFF;
            }}
        """)
        self.setText(f"{hex_code}  (클릭하여 색상 변경)")


class CharybdisEditor(BasicEditor):
    PRESETS = [
        ("🔴 빨강", (255, 0, 0)),
        ("🟠 주황", (255, 80, 0)),
        ("🟡 노랑", (255, 200, 0)),
        ("🟢 초록", (0, 255, 0)),
        ("🌐 청록", (0, 255, 255)),
        ("🔵 파랑", (0, 0, 255)),
        ("🟣 보라", (180, 0, 255)),
        ("🌸 핑크", (255, 0, 150)),
        ("⚪ 흰색", (255, 255, 255)),
        ("⚫ 끔", (0, 0, 0)),
    ]

    def __init__(self):
        super().__init__()
        self.is_valid = False
        self.config_data = {}

        # Auto-save timer (debounce)
        self.auto_save_timer = QtCore.QTimer()
        self.auto_save_timer.setSingleShot(True)
        self.auto_save_timer.timeout.connect(self._do_auto_save_eeprom)

        # Scroll area for clean look
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)

        self.content_widget = QWidget()
        self.layout_content = QVBoxLayout(self.content_widget)
        self.layout_content.setSpacing(16)
        self.layout_content.setContentsMargins(16, 16, 16, 16)

        # 1. Title Banner
        banner = QLabel("✨ Charybdis 컨트롤러 (트랙볼 감도 & 레이어 RGB)")
        banner.setStyleSheet("font-size: 17px; font-weight: bold; color: #58a6ff; margin-bottom: 4px;")
        self.layout_content.addWidget(banner)

        # 2. Lighting Group
        self.grp_lighting = self._create_lighting_group()
        self.layout_content.addWidget(self.grp_lighting)

        # 3. Trackball Group
        self.grp_trackball = self._create_trackball_group()
        self.layout_content.addWidget(self.grp_trackball)

        # 4. Action Buttons
        self.layout_actions = self._create_action_bar()
        self.layout_content.addLayout(self.layout_actions)

        self.layout_content.addStretch()
        self.scroll.setWidget(self.content_widget)
        self.addWidget(self.scroll)

    def _create_lighting_group(self):
        grp = QGroupBox("🎨 레이어별 RGB 조명 색상 (양손 자동 동기화)")
        grp.setStyleSheet("QGroupBox { font-size: 14px; font-weight: bold; }")
        vbox = QVBoxLayout(grp)
        vbox.setSpacing(12)

        self.layer_swatches = {}

        layer_names = [
            (1, "Layer 1 (기능키 / F1~F12, 네비게이션)"),
            (2, "Layer 2 (숫자 / 넘패드)"),
            (3, "Layer 3 (트랙볼 마우스 조작 모드)")
        ]

        for layer_num, layer_title in layer_names:
            box = QGroupBox(layer_title)
            b_layout = QVBoxLayout(box)

            # Swatch
            swatch = ColorSwatchButton((255, 0, 0))
            swatch.clicked.connect(lambda _, l=layer_num: self.on_pick_color(l))
            self.layer_swatches[layer_num] = swatch
            b_layout.addWidget(swatch)

            # Quick Preset buttons
            p_layout = QHBoxLayout()
            p_layout.setSpacing(4)
            for name, rgb in self.PRESETS:
                btn = QPushButton(name)
                btn.setFixedHeight(24)
                btn.setStyleSheet("font-size: 11px; padding: 2px 6px;")
                btn.clicked.connect(lambda _, l=layer_num, c=rgb: self.set_layer_color(l, c))
                p_layout.addWidget(btn)
            b_layout.addLayout(p_layout)

            vbox.addWidget(box)

        return grp

    def _create_trackball_group(self):
        grp = QGroupBox("🎯 트랙볼 센서 & DPI 감도 설정")
        grp.setStyleSheet("QGroupBox { font-size: 14px; font-weight: bold; }")
        grid = QGridLayout(grp)
        grid.setSpacing(12)

        # Default DPI
        grid.addWidget(QLabel("기본 커서 감도 (Default DPI):"), 0, 0)
        self.lbl_default_dpi = QLabel("800 DPI")
        self.lbl_default_dpi.setStyleSheet("font-weight: bold; color: #58a6ff;")
        grid.addWidget(self.lbl_default_dpi, 0, 1)

        self.slider_default_dpi = QSlider(QtCore.Qt.Horizontal)
        self.slider_default_dpi.setRange(200, 3200)
        self.slider_default_dpi.setSingleStep(50)
        self.slider_default_dpi.setValue(800)
        self.slider_default_dpi.valueChanged.connect(self._on_default_dpi_slider)
        grid.addWidget(self.slider_default_dpi, 0, 2)

        # Sniping DPI
        grid.addWidget(QLabel("스나이퍼 모드 감도 (Sniping DPI):"), 1, 0)
        self.lbl_sniping_dpi = QLabel("200 DPI")
        self.lbl_sniping_dpi.setStyleSheet("font-weight: bold; color: #f0883e;")
        grid.addWidget(self.lbl_sniping_dpi, 1, 1)

        self.slider_sniping_dpi = QSlider(QtCore.Qt.Horizontal)
        self.slider_sniping_dpi.setRange(100, 1200)
        self.slider_sniping_dpi.setSingleStep(50)
        self.slider_sniping_dpi.setValue(200)
        self.slider_sniping_dpi.valueChanged.connect(self._on_sniping_dpi_slider)
        grid.addWidget(self.slider_sniping_dpi, 1, 2)

        # Auto-Mouse Checkbox & Time
        self.chk_auto_mouse = QCheckBox("트랙볼 이동 시 마우스 레이어(Layer 3) 자동 활성화")
        self.chk_auto_mouse.setChecked(True)
        self.chk_auto_mouse.stateChanged.connect(self._on_config_changed)
        grid.addWidget(self.chk_auto_mouse, 2, 0, 1, 2)

        self.lbl_auto_mouse_time = QLabel("650 ms (복귀 대기시간)")
        self.slider_auto_mouse_time = QSlider(QtCore.Qt.Horizontal)
        self.slider_auto_mouse_time.setRange(100, 2000)
        self.slider_auto_mouse_time.setSingleStep(50)
        self.slider_auto_mouse_time.setValue(650)
        self.slider_auto_mouse_time.valueChanged.connect(self._on_auto_mouse_time_slider)
        grid.addWidget(self.slider_auto_mouse_time, 2, 2)

        # Drag Scroll Invert Y
        self.chk_rev_y = QCheckBox("드래그 스크롤 세로 방향 반전 (자연스러운 휠 스크롤)")
        self.chk_rev_y.setChecked(True)
        self.chk_rev_y.stateChanged.connect(self._on_config_changed)
        grid.addWidget(self.chk_rev_y, 3, 0, 1, 2)

        # Connect sliderReleased for instant auto-save upon release
        self.slider_default_dpi.sliderReleased.connect(self._do_auto_save_eeprom)
        self.slider_sniping_dpi.sliderReleased.connect(self._do_auto_save_eeprom)
        self.slider_auto_mouse_time.sliderReleased.connect(self._do_auto_save_eeprom)

        return grp

    def _create_action_bar(self):
        hbox = QHBoxLayout()
        hbox.setSpacing(12)

        self.chk_auto_save = QCheckBox("⚡ 변경 즉시 키보드(EEPROM)에 자동 저장")
        self.chk_auto_save.setChecked(True)
        self.chk_auto_save.setStyleSheet("font-weight: bold; color: #58a6ff;")
        hbox.addWidget(self.chk_auto_save)

        self.btn_save_eeprom = QPushButton("💾 지금 즉시 영구 저장")
        self.btn_save_eeprom.setFixedHeight(34)
        self.btn_save_eeprom.setStyleSheet("""
            QPushButton {
                background-color: #238636;
                color: white;
                font-weight: bold;
                font-size: 12px;
                border-radius: 6px;
                padding: 0 14px;
            }
            QPushButton:hover {
                background-color: #2ea043;
            }
        """)
        self.btn_save_eeprom.clicked.connect(self.save_to_eeprom)
        hbox.addWidget(self.btn_save_eeprom)

        self.btn_reload = QPushButton("🔄 키보드에서 다시 읽기")
        self.btn_reload.setFixedHeight(34)
        self.btn_reload.clicked.connect(self.load_from_keyboard)
        hbox.addWidget(self.btn_reload)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: #3fb950; font-weight: bold;")
        hbox.addWidget(self.lbl_status)
        hbox.addStretch()

        return hbox

    def valid(self):
        return self.is_valid

    def rebuild(self, device):
        super().rebuild(device)
        self.is_valid = (device is not None and getattr(device, "keyboard", None) is not None)
        if self.is_valid:
            self.load_from_keyboard()

    def on_pick_color(self, layer):
        cur_rgb = self.layer_swatches[layer].current_rgb
        init_color = QtGui.QColor(*cur_rgb)
        col = QColorDialog.getColor(init_color, None, f"Layer {layer} 조명 색상 선택")
        if col.isValid():
            self.set_layer_color(layer, (col.red(), col.green(), col.blue()))

    def set_layer_color(self, layer, rgb):
        self.layer_swatches[layer].set_color(rgb)
        self.send_live_config(auto_save_delay=50)
        self.set_status(f"⚡ Layer {layer} 색상 적용 및 자동 저장 완료")

    def _on_default_dpi_slider(self, val):
        self.lbl_default_dpi.setText(f"{val} DPI")
        self.send_live_config(auto_save_delay=400)

    def _on_sniping_dpi_slider(self, val):
        self.lbl_sniping_dpi.setText(f"{val} DPI")
        self.send_live_config(auto_save_delay=400)

    def _on_auto_mouse_time_slider(self, val):
        self.lbl_auto_mouse_time.setText(f"{val} ms")
        self.send_live_config(auto_save_delay=400)

    def _on_config_changed(self):
        self.send_live_config(auto_save_delay=50)

    def load_from_keyboard(self):
        if not self.device or not self.device.keyboard:
            return

        try:
            msg = [0xFC, 0x01] + [0x00] * 30
            self.device.send(bytes(msg))
            resp = list(self.device.recv(32))

            if resp[0] == 0xFC and resp[1] == 0x01:
                default_dpi = (resp[2] << 8) | resp[3]
                sniping_dpi = (resp[4] << 8) | resp[5]
                auto_mouse_en = resp[6]
                auto_mouse_time = (resp[8] << 8) | resp[9]
                rev_y = resp[11]

                l1 = (resp[12], resp[13], resp[14])
                l2 = (resp[15], resp[16], resp[17])
                l3 = (resp[18], resp[19], resp[20])

                # Block signals during load
                self.slider_default_dpi.blockSignals(True)
                self.slider_sniping_dpi.blockSignals(True)
                self.slider_auto_mouse_time.blockSignals(True)
                self.chk_auto_mouse.blockSignals(True)
                self.chk_rev_y.blockSignals(True)

                self.slider_default_dpi.setValue(default_dpi)
                self.lbl_default_dpi.setText(f"{default_dpi} DPI")

                self.slider_sniping_dpi.setValue(sniping_dpi)
                self.lbl_sniping_dpi.setText(f"{sniping_dpi} DPI")

                self.slider_auto_mouse_time.setValue(auto_mouse_time)
                self.lbl_auto_mouse_time.setText(f"{auto_mouse_time} ms")

                self.chk_auto_mouse.setChecked(bool(auto_mouse_en))
                self.chk_rev_y.setChecked(bool(rev_y))

                self.layer_swatches[1].set_color(l1)
                self.layer_swatches[2].set_color(l2)
                self.layer_swatches[3].set_color(l3)

                self.slider_default_dpi.blockSignals(False)
                self.slider_sniping_dpi.blockSignals(False)
                self.slider_auto_mouse_time.blockSignals(False)
                self.chk_auto_mouse.blockSignals(False)
                self.chk_rev_y.blockSignals(False)

                self.set_status("키보드에서 설정을 성공적으로 불러왔습니다.")
        except Exception as e:
            self.set_status(f"설정 읽기 오류: {e}")

    def send_live_config(self, auto_save_delay=400):
        if not self.device or not self.device.keyboard:
            return

        try:
            def_dpi = self.slider_default_dpi.value()
            snp_dpi = self.slider_sniping_dpi.value()
            auto_en = 1 if self.chk_auto_mouse.isChecked() else 0
            auto_layer = 3
            auto_time = self.slider_auto_mouse_time.value()
            buf = 20
            rev_y = 1 if self.chk_rev_y.isChecked() else 0

            l1 = self.layer_swatches[1].current_rgb
            l2 = self.layer_swatches[2].current_rgb
            l3 = self.layer_swatches[3].current_rgb

            pkt = [
                0xFC, 0x02,
                (def_dpi >> 8) & 0xFF, def_dpi & 0xFF,
                (snp_dpi >> 8) & 0xFF, snp_dpi & 0xFF,
                auto_en, auto_layer,
                (auto_time >> 8) & 0xFF, auto_time & 0xFF,
                buf, rev_y,
                l1[0], l1[1], l1[2],
                l2[0], l2[1], l2[2],
                l3[0], l3[1], l3[2]
            ]
            pkt += [0] * (32 - len(pkt))
            self.device.send(bytes(pkt))
            self.device.recv(32)

            # Auto-save trigger
            if getattr(self, "chk_auto_save", None) is None or self.chk_auto_save.isChecked():
                if auto_save_delay <= 0:
                    self._do_auto_save_eeprom()
                else:
                    self.auto_save_timer.start(auto_save_delay)
        except Exception as e:
            pass

    def _do_auto_save_eeprom(self):
        if not self.device or not self.device.keyboard:
            return

        try:
            self.auto_save_timer.stop()
            msg = [0xFC, 0x03] + [0x00] * 30
            self.device.send(bytes(msg))
            self.device.recv(32)
            self.set_status("⚡ 키보드(EEPROM)에 실시간 자동 저장 완료!")
        except Exception as e:
            self.set_status(f"자동 저장 오류: {e}")

    def save_to_eeprom(self):
        if not self.device or not self.device.keyboard:
            return

        try:
            self._do_auto_save_eeprom()
            self.set_status("✅ 키보드 메모리(EEPROM)에 영구 저장되었습니다!")
        except Exception as e:
            self.set_status(f"저장 오류: {e}")

    def set_status(self, text):
        self.lbl_status.setText(text)
        QtCore.QTimer.singleShot(4000, lambda: self.lbl_status.setText(""))
