# SPDX-License-Identifier: GPL-2.0-or-later
import time
import random
from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget, QFrame,
    QLineEdit, QButtonGroup, QScrollArea, QGraphicsDropShadowEffect,
    QSizePolicy, QGridLayout, QProgressBar
)
from PyQt5.QtCore import Qt, QTimer, QUrl, pyqtSignal, QEvent
from PyQt5.QtGui import QFont, QColor, QDesktopServices, QTextCursor, QTextCharFormat

from editor.basic_editor import BasicEditor

# =============================================================================
# 단어 데이터베이스
# =============================================================================
WORDS_ENGLISH = [
    "the", "be", "of", "and", "a", "to", "in", "he", "have", "it",
    "that", "for", "they", "with", "as", "not", "on", "she", "at", "by",
    "this", "we", "you", "do", "but", "from", "or", "which", "one", "would",
    "all", "will", "there", "say", "who", "make", "when", "can", "more", "if",
    "no", "man", "out", "other", "so", "what", "time", "up", "go", "about",
    "than", "into", "could", "state", "only", "new", "year", "some", "take", "come",
    "these", "know", "see", "use", "get", "like", "then", "first", "any", "work",
    "now", "may", "such", "give", "over", "think", "most", "even", "find", "day",
    "also", "after", "way", "many", "must", "look", "before", "great", "back", "through",
    "long", "where", "much", "should", "well", "people", "down", "own", "just", "because",
    "good", "each", "those", "feel", "seem", "how", "high", "too", "place", "little",
    "world", "very", "still", "nation", "hand", "old", "life", "tell", "write", "become",
    "here", "show", "house", "both", "between", "need", "mean", "call", "develop", "under",
    "last", "right", "move", "thing", "general", "school", "never", "same", "another", "begin",
    "while", "number", "part", "turn", "real", "leave", "might", "want", "point", "form"
]

WORDS_KOREAN = [
    "사람", "생각", "시간", "우리", "마음", "세상", "하늘", "바람", "바다", "오늘",
    "내일", "어제", "기억", "사랑", "친구", "가족", "컴퓨터", "키보드", "화면", "소리",
    "노래", "계절", "봄날", "여름", "가을", "겨울", "햇살", "구름", "나무", "꽃잎",
    "도시", "여행", "이야기", "행복", "기쁨", "평화", "미래", "과거", "희망", "도전",
    "변화", "성장", "지혜", "가치", "의미", "자유", "용기", "열정", "자연", "파도",
    "온도", "약속", "걸음", "선택", "결심", "순간", "미소", "감정", "향기", "찻잔",
    "창문", "열쇠", "지도", "나침반", "등대", "산책", "쉼표", "마침표", "편지", "기차",
    "신호등", "골목길", "별빛", "은하수", "우주", "행성", "탐험", "모험", "연필", "공책",
    "음악", "피아노", "기타", "멜로디", "리듬", "화음", "공명", "울림", "바램", "소망"
]

WORDS_SYMBOLS_SPLIT = [
    "!", "@", "#", "$", "%", "^", "&", "*", "(", ")",
    "-", "_", "=", "+", "[", "]", "{", "}", "\\", "|",
    ";", ":", "'", "\"", ",", ".", "<", ">", "/", "?",
    "`", "~", "()", "[]", "{}", "<>", "!=", "==", "+=",
    "-=", "*=", "/=", "->", "=>", "&&", "||", "/*", "*/",
    "$1", "$2", "@key", "#def", "%d", "%s", "&addr", "*ptr"
]

WORDS_CODE = [
    "def", "return", "import", "class", "function", "const", "let", "var",
    "if", "else", "for", "while", "try", "catch", "throw", "async", "await",
    "print()", "len()", "self", "this", "true", "false", "null", "None",
    "uint16_t", "uint8_t", "bool", "void", "static", "#define", "#include",
    "console.log", "record->event", "keycode", "keyrecord_t", "layer_state",
    "rgblight", "matrix_scan", "process_record", "eeconfig", "bootloader"
]


class MonkeytypeEditor(BasicEditor):
    def __init__(self, parent=None):
        super().__init__(parent)

        # 게임 설정 변수
        self.mode = "time"  # "time" 또는 "words"
        self.time_limit = 30  # 초
        self.word_limit = 25  # 단어 수
        self.dataset_type = "english"  # "english", "korean", "symbols", "code"

        # 게임 상태 변수
        self.is_running = False
        self.is_finished = False
        self.start_time = 0.0
        self.elapsed_time = 0.0
        self.target_words = []
        self.current_word_idx = 0
        self.correct_chars = 0
        self.incorrect_chars = 0
        self.total_keystrokes = 0
        self.history_records = []

        # 타이머
        self.timer = QTimer()
        self.timer.setInterval(100)
        self.timer.timeout.connect(self._on_tick)

        # UI 생성
        self._init_ui()
        self.reset_test()

    def valid(self):
        return True

    def rebuild(self, device):
        super().rebuild(device)

    def activate(self):
        super().activate()
        self.input_field.setFocus()

    def eventFilter(self, obj, event):
        if obj == self.input_field and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Tab:
                self.reset_test()
                return True
        return super().eventFilter(obj, event)

    def _init_ui(self):
        # 전체 스타일시트 (Monkeytype 시그니처 다크/골드 테마)
        self.container_widget = QWidget()
        self.container_widget.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                color: #d1d0c5;
                font-family: 'Segoe UI', 'Malgun Gothic', sans-serif;
            }
            QPushButton {
                background-color: #2c2e31;
                color: #8b949e;
                border: 1px solid #3c4043;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #383a40;
                color: #e2b714;
                border-color: #e2b714;
            }
            QPushButton:checked {
                background-color: #e2b714;
                color: #1e1e1e;
                border-color: #e2b714;
            }
        """)

        main_layout = QVBoxLayout(self.container_widget)
        main_layout.setContentsMargins(20, 15, 20, 20)
        main_layout.setSpacing(15)

        # -------------------------------------------------------------
        # 1. 상단 바: 로고, 모드 선택, 브라우저 오픈 버튼
        # -------------------------------------------------------------
        top_bar = QHBoxLayout()

        # 타이틀
        title_lbl = QLabel("🐵 Monkeytype Studio")
        title_lbl.setStyleSheet("color: #e2b714; font-size: 20px; font-weight: bold; letter-spacing: 1px;")
        top_bar.addWidget(title_lbl)

        sub_desc = QLabel("Charybdis 3x6 스플릿 인체공학 타자 연습")
        sub_desc.setStyleSheet("color: #646669; font-size: 12px; margin-left: 10px;")
        top_bar.addWidget(sub_desc)

        top_bar.addStretch()

        # 브라우저 열기 버튼
        self.btn_open_web = QPushButton("🌐 monkeytype.com 웹사이트 열기")
        self.btn_open_web.setStyleSheet("""
            QPushButton {
                background-color: #23272d;
                color: #58a6ff;
                border: 1px solid #30363d;
            }
            QPushButton:hover {
                background-color: #30363d;
                color: #79c0ff;
                border-color: #58a6ff;
            }
        """)
        self.btn_open_web.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://monkeytype.com/")))
        top_bar.addWidget(self.btn_open_web)

        main_layout.addLayout(top_bar)

        # -------------------------------------------------------------
        # 2. 제어 툴바: 언어/카테고리 선택 & 모드/시간 선택
        # -------------------------------------------------------------
        toolbar_frame = QFrame()
        toolbar_frame.setStyleSheet("""
            QFrame {
                background-color: #252628;
                border-radius: 8px;
                padding: 6px;
            }
        """)
        toolbar_layout = QHBoxLayout(toolbar_frame)
        toolbar_layout.setContentsMargins(10, 6, 10, 6)

        # 카테고리 그룹
        cat_lbl = QLabel("훈련 코스:")
        cat_lbl.setStyleSheet("color: #646669; font-weight: bold; font-size: 12px;")
        toolbar_layout.addWidget(cat_lbl)

        self.btn_eng = QPushButton("🔤 영문 (English)")
        self.btn_eng.setCheckable(True)
        self.btn_eng.setChecked(True)
        self.btn_eng.clicked.connect(lambda: self._set_dataset("english"))
        toolbar_layout.addWidget(self.btn_eng)

        self.btn_kor = QPushButton("🇰🇷 한글 (Korean)")
        self.btn_kor.setCheckable(True)
        self.btn_kor.clicked.connect(lambda: self._set_dataset("korean"))
        toolbar_layout.addWidget(self.btn_kor)

        self.btn_split = QPushButton("⚡ 3x6 스플릿 레이어 특수문자")
        self.btn_split.setCheckable(True)
        self.btn_split.clicked.connect(lambda: self._set_dataset("symbols"))
        toolbar_layout.addWidget(self.btn_split)

        self.btn_code = QPushButton("💻 코딩 구문 (Code)")
        self.btn_code.setCheckable(True)
        self.btn_code.clicked.connect(lambda: self._set_dataset("code"))
        toolbar_layout.addWidget(self.btn_code)

        toolbar_layout.addSpacing(20)
        toolbar_layout.addWidget(QLabel("|"))

        # 모드 선택 그룹
        mode_lbl = QLabel("모드:")
        mode_lbl.setStyleSheet("color: #646669; font-weight: bold; font-size: 12px;")
        toolbar_layout.addWidget(mode_lbl)

        self.btn_time15 = QPushButton("⏱️ 15초")
        self.btn_time15.setCheckable(True)
        self.btn_time15.clicked.connect(lambda: self._set_mode("time", 15))
        toolbar_layout.addWidget(self.btn_time15)

        self.btn_time30 = QPushButton("⏱️ 30초")
        self.btn_time30.setCheckable(True)
        self.btn_time30.setChecked(True)
        self.btn_time30.clicked.connect(lambda: self._set_mode("time", 30))
        toolbar_layout.addWidget(self.btn_time30)

        self.btn_time60 = QPushButton("⏱️ 60초")
        self.btn_time60.setCheckable(True)
        self.btn_time60.clicked.connect(lambda: self._set_mode("time", 60))
        toolbar_layout.addWidget(self.btn_time60)

        self.btn_words25 = QPushButton("📝 25단어")
        self.btn_words25.setCheckable(True)
        self.btn_words25.clicked.connect(lambda: self._set_mode("words", 25))
        toolbar_layout.addWidget(self.btn_words25)

        self.btn_words50 = QPushButton("📝 50단어")
        self.btn_words50.setCheckable(True)
        self.btn_words50.clicked.connect(lambda: self._set_mode("words", 50))
        toolbar_layout.addWidget(self.btn_words50)

        toolbar_layout.addStretch()

        self.btn_restart = QPushButton("🔄 다시 시작 (Tab)")
        self.btn_restart.setStyleSheet("""
            QPushButton {
                background-color: #2c2e31;
                color: #e2b714;
                border: 1px solid #e2b714;
            }
            QPushButton:hover {
                background-color: #e2b714;
                color: #1e1e1e;
            }
        """)
        self.btn_restart.clicked.connect(self.reset_test)
        toolbar_layout.addWidget(self.btn_restart)

        main_layout.addWidget(toolbar_frame)

        # -------------------------------------------------------------
        # 3. 실시간 HUD (WPM / 정확도 / 타이머 게이지)
        # -------------------------------------------------------------
        hud_frame = QFrame()
        hud_frame.setStyleSheet("background-color: transparent;")
        hud_layout = QHBoxLayout(hud_frame)
        hud_layout.setContentsMargins(10, 0, 10, 0)

        # 대형 WPM
        wpm_box = QVBoxLayout()
        self.lbl_hud_wpm_val = QLabel("0")
        self.lbl_hud_wpm_val.setStyleSheet("color: #e2b714; font-size: 38px; font-weight: bold; line-height: 1;")
        lbl_hud_wpm_title = QLabel("WPM (단어/분)")
        lbl_hud_wpm_title.setStyleSheet("color: #646669; font-size: 11px; font-weight: bold;")
        wpm_box.addWidget(self.lbl_hud_wpm_val)
        wpm_box.addWidget(lbl_hud_wpm_title)
        hud_layout.addLayout(wpm_box)

        hud_layout.addSpacing(30)

        # 정확도
        acc_box = QVBoxLayout()
        self.lbl_hud_acc_val = QLabel("100%")
        self.lbl_hud_acc_val.setStyleSheet("color: #58a6ff; font-size: 38px; font-weight: bold; line-height: 1;")
        lbl_hud_acc_title = QLabel("정확도 (Acc)")
        lbl_hud_acc_title.setStyleSheet("color: #646669; font-size: 11px; font-weight: bold;")
        acc_box.addWidget(self.lbl_hud_acc_val)
        acc_box.addWidget(lbl_hud_acc_title)
        hud_layout.addLayout(acc_box)

        hud_layout.addSpacing(30)

        # CPM (타수)
        cpm_box = QVBoxLayout()
        self.lbl_hud_cpm_val = QLabel("0")
        self.lbl_hud_cpm_val.setStyleSheet("color: #a371f7; font-size: 38px; font-weight: bold; line-height: 1;")
        lbl_hud_cpm_title = QLabel("CPM (타수/분)")
        lbl_hud_cpm_title.setStyleSheet("color: #646669; font-size: 11px; font-weight: bold;")
        cpm_box.addWidget(self.lbl_hud_cpm_val)
        cpm_box.addWidget(lbl_hud_cpm_title)
        hud_layout.addLayout(cpm_box)

        hud_layout.addStretch()

        # 남은 시간 / 진행도
        time_box = QVBoxLayout()
        self.lbl_hud_timer_val = QLabel("30s")
        self.lbl_hud_timer_val.setAlignment(Qt.AlignRight)
        self.lbl_hud_timer_val.setStyleSheet("color: #d1d0c5; font-size: 38px; font-weight: bold; line-height: 1;")
        self.lbl_hud_timer_title = QLabel("남은 시간")
        self.lbl_hud_timer_title.setAlignment(Qt.AlignRight)
        self.lbl_hud_timer_title.setStyleSheet("color: #646669; font-size: 11px; font-weight: bold;")
        time_box.addWidget(self.lbl_hud_timer_val)
        time_box.addWidget(self.lbl_hud_timer_title)
        hud_layout.addLayout(time_box)

        main_layout.addWidget(hud_frame)

        # -------------------------------------------------------------
        # 4. Monkeytype 타이핑 영역 (단어 표시 박스)
        # -------------------------------------------------------------
        self.typing_card = QFrame()
        self.typing_card.setStyleSheet("""
            QFrame {
                background-color: #2b2d30;
                border: 2px solid #3c4043;
                border-radius: 12px;
                padding: 20px;
            }
        """)
        typing_card_layout = QVBoxLayout(self.typing_card)
        typing_card_layout.setSpacing(15)

        # 텍스트 디스플레이 레이블
        self.lbl_text_display = QLabel()
        self.lbl_text_display.setWordWrap(True)
        self.lbl_text_display.setTextFormat(Qt.RichText)
        self.lbl_text_display.setStyleSheet("""
            QLabel {
                font-family: 'Consolas', 'Courier New', 'Malgun Gothic', monospace;
                font-size: 24px;
                line-height: 1.8;
                padding: 10px;
                background-color: transparent;
            }
        """)
        self.lbl_text_display.setMinimumHeight(150)
        typing_card_layout.addWidget(self.lbl_text_display)

        # 실제 입력창 (포커스 및 타건 감지)
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("여기를 클릭하거나 아무 키나 눌러 타이핑을 시작하세요...")
        self.input_field.setStyleSheet("""
            QLineEdit {
                background-color: #1e1e1e;
                color: #e2b714;
                border: 2px solid #3c4043;
                border-radius: 8px;
                font-size: 18px;
                font-weight: bold;
                padding: 10px 14px;
            }
            QLineEdit:focus {
                border-color: #e2b714;
                background-color: #232427;
            }
        """)
        self.input_field.textChanged.connect(self._on_input_changed)
        self.input_field.returnPressed.connect(self._on_return_pressed)
        self.input_field.installEventFilter(self)
        typing_card_layout.addWidget(self.input_field)

        main_layout.addWidget(self.typing_card)

        # -------------------------------------------------------------
        # 5. 결과 화면 (테스트 완료 시 표시)
        # -------------------------------------------------------------
        self.result_card = QFrame()
        self.result_card.setStyleSheet("""
            QFrame {
                background-color: #1e2228;
                border: 2px solid #e2b714;
                border-radius: 12px;
                padding: 20px;
            }
        """)
        result_layout = QVBoxLayout(self.result_card)

        res_title = QLabel("🎉 타이핑 테스트 완료!")
        res_title.setStyleSheet("color: #e2b714; font-size: 22px; font-weight: bold;")
        result_layout.addWidget(res_title)

        self.res_grid = QGridLayout()
        self.res_grid.setContentsMargins(10, 15, 10, 15)
        self.res_grid.setHorizontalSpacing(30)

        self.lbl_res_wpm = QLabel("0")
        self.lbl_res_wpm.setStyleSheet("color: #e2b714; font-size: 44px; font-weight: bold;")
        self.res_grid.addWidget(QLabel("최종 WPM"), 0, 0)
        self.res_grid.addWidget(self.lbl_res_wpm, 1, 0)

        self.lbl_res_acc = QLabel("100%")
        self.lbl_res_acc.setStyleSheet("color: #58a6ff; font-size: 44px; font-weight: bold;")
        self.res_grid.addWidget(QLabel("정확도"), 0, 1)
        self.res_grid.addWidget(self.lbl_res_acc, 1, 1)

        self.lbl_res_cpm = QLabel("0")
        self.lbl_res_cpm.setStyleSheet("color: #a371f7; font-size: 44px; font-weight: bold;")
        self.res_grid.addWidget(QLabel("CPM (분당 타수)"), 0, 2)
        self.res_grid.addWidget(self.lbl_res_cpm, 1, 2)

        self.lbl_res_errors = QLabel("0")
        self.lbl_res_errors.setStyleSheet("color: #f85149; font-size: 44px; font-weight: bold;")
        self.res_grid.addWidget(QLabel("오타 수"), 0, 3)
        self.res_grid.addWidget(self.lbl_res_errors, 1, 3)

        self.lbl_res_time = QLabel("0.0s")
        self.lbl_res_time.setStyleSheet("color: #7ee787; font-size: 44px; font-weight: bold;")
        self.res_grid.addWidget(QLabel("소요 시간"), 0, 4)
        self.res_grid.addWidget(self.lbl_res_time, 1, 4)

        result_layout.addLayout(self.res_grid)

        res_btn_layout = QHBoxLayout()
        res_retry_btn = QPushButton("🔄 다시 도전하기 (Enter)")
        res_retry_btn.setStyleSheet("""
            QPushButton {
                background-color: #e2b714;
                color: #1e1e1e;
                font-size: 15px;
                padding: 10px 20px;
                border: none;
            }
            QPushButton:hover {
                background-color: #f0c929;
            }
        """)
        res_retry_btn.clicked.connect(self.reset_test)
        res_btn_layout.addWidget(res_retry_btn)
        res_btn_layout.addStretch()

        result_layout.addLayout(res_btn_layout)
        self.result_card.hide()
        main_layout.addWidget(self.result_card)

        # -------------------------------------------------------------
        # 6. 세션 히스토리
        # -------------------------------------------------------------
        self.lbl_history = QLabel("최근 기록: 아직 완료된 테스트가 없습니다.")
        self.lbl_history.setStyleSheet("color: #646669; font-size: 12px; margin-top: 5px;")
        main_layout.addWidget(self.lbl_history)

        self.addWidget(self.container_widget)

    # -----------------------------------------------------------------
    # 모드 및 단어 세트 설정
    # -----------------------------------------------------------------
    def _set_dataset(self, d_type):
        self.dataset_type = d_type
        self.btn_eng.setChecked(d_type == "english")
        self.btn_kor.setChecked(d_type == "korean")
        self.btn_split.setChecked(d_type == "symbols")
        self.btn_code.setChecked(d_type == "code")
        self.reset_test()

    def _set_mode(self, m_type, val):
        self.mode = m_type
        if m_type == "time":
            self.time_limit = val
            self.lbl_hud_timer_title.setText("남은 시간")
        else:
            self.word_limit = val
            self.lbl_hud_timer_title.setText("남은 단어")

        self.btn_time15.setChecked(m_type == "time" and val == 15)
        self.btn_time30.setChecked(m_type == "time" and val == 30)
        self.btn_time60.setChecked(m_type == "time" and val == 60)
        self.btn_words25.setChecked(m_type == "words" and val == 25)
        self.btn_words50.setChecked(m_type == "words" and val == 50)

        self.reset_test()

    # -----------------------------------------------------------------
    # 테스트 초기화 및 단어 생성
    # -----------------------------------------------------------------
    def reset_test(self):
        self.timer.stop()
        self.is_running = False
        self.is_finished = False
        self.start_time = 0.0
        self.elapsed_time = 0.0
        self.current_word_idx = 0
        self.correct_chars = 0
        self.incorrect_chars = 0
        self.total_keystrokes = 0

        # 단어 풀 선택
        if self.dataset_type == "korean":
            pool = WORDS_KOREAN
        elif self.dataset_type == "symbols":
            pool = WORDS_SYMBOLS_SPLIT
        elif self.dataset_type == "code":
            pool = WORDS_CODE
        else:
            pool = WORDS_ENGLISH

        count = self.word_limit if self.mode == "words" else 80
        self.target_words = [random.choice(pool) for _ in range(count)]

        # HUD 초기화
        self.lbl_hud_wpm_val.setText("0")
        self.lbl_hud_acc_val.setText("100%")
        self.lbl_hud_cpm_val.setText("0")
        if self.mode == "time":
            self.lbl_hud_timer_val.setText(f"{self.time_limit}s")
        else:
            self.lbl_hud_timer_val.setText(f"{self.word_limit}")

        self.typing_card.show()
        self.result_card.hide()
        self.input_field.setEnabled(True)
        self.input_field.clear()
        self.input_field.setFocus()

        self._render_text()

    # -----------------------------------------------------------------
    # Monkeytype 텍스트 렌더링
    # -----------------------------------------------------------------
    def _render_text(self):
        current_input = self.input_field.text()
        html_parts = []

        # 현재 단어 주변 25개 단어만 보여줌 (너무 길지 않게 스크롤)
        start_idx = max(0, self.current_word_idx - 5)
        end_idx = min(len(self.target_words), start_idx + 22)

        for i in range(start_idx, end_idx):
            target = self.target_words[i]

            if i < self.current_word_idx:
                # 이미 지나간 단어 (완료)
                html_parts.append(f"<span style='color: #4e5052;'>{target}</span>")
            elif i == self.current_word_idx:
                # 현재 타이핑 중인 단어
                word_html = []
                for c_idx, target_ch in enumerate(target):
                    if c_idx < len(current_input):
                        typed_ch = current_input[c_idx]
                        if typed_ch == target_ch:
                            # 맞은 글자: 밝은 노란색/흰색
                            word_html.append(f"<span style='color: #e2b714; font-weight: bold;'>{target_ch}</span>")
                        else:
                            # 틀린 글자: 빨간색 + 밑줄
                            word_html.append(f"<span style='color: #ca4754; text-decoration: underline; font-weight: bold;'>{target_ch}</span>")
                    elif c_idx == len(current_input):
                        # 현재 커서 위치 (커서 표시 |)
                        word_html.append(f"<span style='color: #e2b714; border-left: 2px solid #e2b714;'>{target_ch}</span>")
                    else:
                        # 아직 입력 안 한 글자: 회색
                        word_html.append(f"<span style='color: #646669;'>{target_ch}</span>")

                # 만약 단어 길이보다 더 길게 초과 입력한 경우
                if len(current_input) > len(target):
                    extra = current_input[len(target):]
                    word_html.append(f"<span style='color: #7e2a33;'>{extra}</span>")

                html_parts.append(f"<span style='background-color: #35373b; border-radius: 4px; padding: 2px 4px;'>{''.join(word_html)}</span>")
            else:
                # 앞으로 입력할 단어: 은은한 회색
                html_parts.append(f"<span style='color: #646669;'>{target}</span>")

        self.lbl_text_display.setText(" ".join(html_parts))

    # -----------------------------------------------------------------
    # 키 입력 처리
    # -----------------------------------------------------------------
    def _on_input_changed(self, text):
        if not text:
            self._render_text()
            return

        # 첫 키 입력 시 타이머 시작
        if not self.is_running and not self.is_finished:
            self.is_running = True
            self.start_time = time.time()
            self.timer.start()

        # 스페이스바로 다음 단어 넘어가기 처리
        if text.endswith(" "):
            typed_word = text[:-1]
            target_word = self.target_words[self.current_word_idx]

            # 통계 계산
            for t_ch, u_ch in zip(target_word, typed_word):
                if t_ch == u_ch:
                    self.correct_chars += 1
                else:
                    self.incorrect_chars += 1

            diff = abs(len(target_word) - len(typed_word))
            self.incorrect_chars += diff
            self.total_keystrokes += len(typed_word) + 1
            if typed_word == target_word:
                self.correct_chars += 1  # 스페이스 성공

            self.current_word_idx += 1
            self.input_field.blockSignals(True)
            self.input_field.clear()
            self.input_field.blockSignals(False)

            # 단어수 모드 완료 체크
            if self.mode == "words" and self.current_word_idx >= self.word_limit:
                self._finish_test()
                return

            self._update_stats()
            self._render_text()
            return

        self._render_text()

    def _on_return_pressed(self):
        if self.is_finished:
            self.reset_test()
            return

        # 스페이스 대신 엔터로 단어 완료 가능
        cur = self.input_field.text()
        if cur:
            self._on_input_changed(cur + " ")

    # -----------------------------------------------------------------
    # 타이머 틱 및 진행도 계산
    # -----------------------------------------------------------------
    def _on_tick(self):
        if not self.is_running or self.is_finished:
            return

        self.elapsed_time = time.time() - self.start_time

        if self.mode == "time":
            remaining = max(0, int(self.time_limit - self.elapsed_time))
            self.lbl_hud_timer_val.setText(f"{remaining}s")
            if self.elapsed_time >= self.time_limit:
                self._finish_test()
                return
        else:
            remaining = max(0, self.word_limit - self.current_word_idx)
            self.lbl_hud_timer_val.setText(f"{remaining}")

        self._update_stats()

    def _update_stats(self):
        elapsed_min = max(0.001, self.elapsed_time / 60.0)

        # WPM: (올바른 문자수 / 5) / 경과분
        wpm = int((self.correct_chars / 5.0) / elapsed_min)
        cpm = int(self.correct_chars / elapsed_min)

        total_attempts = self.correct_chars + self.incorrect_chars
        acc = int((self.correct_chars / total_attempts) * 100) if total_attempts > 0 else 100

        self.lbl_hud_wpm_val.setText(str(wpm))
        self.lbl_hud_acc_val.setText(f"{acc}%")
        self.lbl_hud_cpm_val.setText(str(cpm))

    # -----------------------------------------------------------------
    # 테스트 완료
    # -----------------------------------------------------------------
    def _finish_test(self):
        self.timer.stop()
        self.is_running = False
        self.is_finished = True

        elapsed_sec = max(0.1, self.elapsed_time)
        elapsed_min = elapsed_sec / 60.0

        wpm = int((self.correct_chars / 5.0) / elapsed_min)
        cpm = int(self.correct_chars / elapsed_min)
        total_attempts = self.correct_chars + self.incorrect_chars
        acc = int((self.correct_chars / total_attempts) * 100) if total_attempts > 0 else 100

        # 결과창 업데이트
        self.lbl_res_wpm.setText(str(wpm))
        self.lbl_res_acc.setText(f"{acc}%")
        self.lbl_res_cpm.setText(str(cpm))
        self.lbl_res_errors.setText(str(self.incorrect_chars))
        self.lbl_res_time.setText(f"{elapsed_sec:.1f}s")

        self.typing_card.hide()
        self.result_card.show()

        # 히스토리 기록
        record_str = f"[{time.strftime('%H:%M:%S')}] {wpm} WPM | 정확도 {acc}% | {cpm} CPM ({self.dataset_type}, {elapsed_sec:.0f}초)"
        self.history_records.append(record_str)
        recent_text = " | ".join(self.history_records[-3:])
        self.lbl_history.setText(f"최근 기록: {recent_text}")
