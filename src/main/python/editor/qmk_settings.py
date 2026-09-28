# SPDX-License-Identifier: GPL-2.0-or-later
import json
from collections import defaultdict

from PyQt5 import QtCore
from PyQt5.QtCore import pyqtSignal, QObject
from PyQt5.QtWidgets import QVBoxLayout, QCheckBox, QGridLayout, QLabel, QWidget, QSizePolicy, QTabWidget, QSpinBox, \
    QHBoxLayout, QPushButton, QMessageBox

from editor.basic_editor import BasicEditor
from protocol.constants import VIAL_PROTOCOL_QMK_SETTINGS
from util import tr, make_scrollable
from vial_device import VialKeyboard


QMK_TAB_TRANSLATIONS = {
    "Tap-Hold": "⏱️ 탭/홀드 판정 (Tap-Hold)",
    "Auto Shift": "🔤 오토 시프트 (Auto Shift)",
    "Magic": "🔮 매직 키 (Magic)",
    "Grave Escape": "⚡ 스마트 ESC (Grave Escape)",
    "Combo": "🧩 콤보 판정 (Combo)",
    "One Shot Keys": "🎯 원샷 키 (One Shot)",
    "Mouse keys": "🖱️ 마우스 키 (Mouse Keys)",
    "General": "기본 설정 (General)",
    "Debounce": "디바운스 (Debounce)",
    "Tapping": "탭 판정 (Tapping)",
    "Dynamic Macro": "다이나믹 매크로",
}

QMK_TAB_GUIDES = {
    "Tap-Hold": """
    <div style="background-color: #161b22; border: 1px solid #30363d; border-left: 4px solid #58a6ff; padding: 10px 14px; border-radius: 6px; font-size: 12px; line-height: 1.5; color: #e6edf3;">
        <b style="color: #79c0ff; font-size: 13px;">⏱️ 탭/홀드 (Tap-Hold) 핵심 가이드</b><br>
        • <b>Tapping Term:</b> 짧게 누르면 일반 키, 길게 누르면 수식키/레이어로 작동하는 기준 시간 (기본 200ms, 타건이 빠르면 160~180ms 추천)<br>
        • <b>Permissive Hold:</b> 탭홀드 키를 누른 채 다른 키를 치고 떼면 즉시 홀드로 판정하여 롤오버 오입력 방지<br>
        • <b>Chordal Hold:</b> 반대 손 키와 함께 눌릴 때만 모디파이어로 판정하여 홈로우 모드(Home Row Mods) 타이핑 시 오입력을 획기적으로 차단<br>
        • 수정한 후 하단의 <b>[💾 설정 저장 (Save)]</b> 버튼을 누르면 키보드 메모리에 영구 저장됩니다.
    </div>
    """,
    "Auto Shift": """
    <div style="background-color: #161b22; border: 1px solid #30363d; border-left: 4px solid #3fb950; padding: 10px 14px; border-radius: 6px; font-size: 12px; line-height: 1.5; color: #e6edf3;">
        <b style="color: #56d364; font-size: 13px;">🔤 오토 시프트 (Auto Shift) 가이드</b><br>
        • Shift 키를 따로 누르지 않고도 키를 살짝 길게 누르면 대문자나 특수문자가 자동 입력되는 스마트 기능입니다.<br>
        • <b>Timeout:</b> 길게 누름 판정 시간 (기본 175ms, 타이핑 속도에 맞춰 130~200ms 사이 조절)<br>
        • 영문 알파벳뿐만 아니라 숫자(1 → !), 기호(- → _)에도 적용 가능하며, 원하는 키군만 선택하여 제외할 수 있습니다.
    </div>
    """,
    "Magic": """
    <div style="background-color: #161b22; border: 1px solid #30363d; border-left: 4px solid #bc8cff; padding: 10px 14px; border-radius: 6px; font-size: 12px; line-height: 1.5; color: #e6edf3;">
        <b style="color: #d2a8ff; font-size: 13px;">🔮 매직 키 (Magic) 시스템 스왑 가이드</b><br>
        • 키맵 전체를 다시 수정하지 않고도 OS나 사용 환경에 맞춰 주요 특수 키들을 원클릭으로 맞바꿉니다.<br>
        • <b>Swap Alt & GUI:</b> Mac과 Windows를 번갈아 쓸 때 Command/Option 위치 즉시 교체<br>
        • <b>Disable GUI:</b> 게임 플레이 중 윈도우 키로 인한 튕김 방지 | <b>NKRO:</b> 무한 동시입력 활성화
    </div>
    """,
    "Grave Escape": """
    <div style="background-color: #161b22; border: 1px solid #30363d; border-left: 4px solid #d29922; padding: 10px 14px; border-radius: 6px; font-size: 12px; line-height: 1.5; color: #e6edf3;">
        <b style="color: #e3b341; font-size: 13px;">⚡ 스마트 ESC (Grave Escape) 가이드</b><br>
        • 단일 키로 `ESC`와 물결/백틱(`~`, `)을 스마트하게 공유하는 설정입니다.<br>
        • 단독으로 누르면 ESC, 수식키(Ctrl, Alt, GUI, Shift)와 함께 누를 때의 동작 방식을 지정합니다.
    </div>
    """,
    "Combo": """
    <div style="background-color: #161b22; border: 1px solid #30363d; border-left: 4px solid #f0883e; padding: 10px 14px; border-radius: 6px; font-size: 12px; line-height: 1.5; color: #e6edf3;">
        <b style="color: #ffa657; font-size: 13px;">🧩 콤보 (Combo) 동시입력 시간 가이드</b><br>
        • 2개 이상의 키를 동시에 눌렀을 때 콤보 기능이 발동되는 최대 시간차(ms)입니다.<br>
        • <b>타이핑 중 콤보가 의도치 않게 발동할 때:</b> 30~40ms로 낮춤<br>
        • <b>콤보를 누를 때 자꾸 씹히고 개별 글자가 나올 때:</b> 50~70ms로 늘림
    </div>
    """,
    "One Shot Keys": """
    <div style="background-color: #161b22; border: 1px solid #30363d; border-left: 4px solid #f778ba; padding: 10px 14px; border-radius: 6px; font-size: 12px; line-height: 1.5; color: #e6edf3;">
        <b style="color: #ff9bce; font-size: 13px;">🎯 원샷 키 (One Shot Keys) 가이드</b><br>
        • Shift나 레이어 키를 누른 채 유지하지 않고 '한 번 탭'한 뒤 다음 키를 누르면 1회 적용되는 기능입니다.<br>
        • <b>Tap Toggle:</b> 빠르게 연속 탭했을 때 영구 고정(락)되는 연타 횟수 (보통 2~3회)<br>
        • <b>Timeout:</b> 원샷 키를 탭한 후 다음 키를 누르지 않았을 때 자동으로 풀리는 대기 시간(ms)
    </div>
    """,
    "Mouse keys": """
    <div style="background-color: #161b22; border: 1px solid #30363d; border-left: 4px solid #388bfd; padding: 10px 14px; border-radius: 6px; font-size: 12px; line-height: 1.5; color: #e6edf3;">
        <b style="color: #58a6ff; font-size: 13px;">🖱️ 마우스 키 (Mouse Keys) 속도 & 가속 가이드</b><br>
        • 키보드 키로 마우스 커서 이동 및 휠 스크롤을 조작할 때의 반응 속도와 가속도를 조절합니다.<br>
        • <b>Delay:</b> 키를 누른 후 커서가 움직이기 시작할 때까지의 지연 (기본 0~10ms)<br>
        • <b>Interval / Step size:</b> 커서 이동 갱신 주기와 1보당 픽셀 크기 (수치가 적절할수록 부드럽고 정확함)
    </div>
    """,
}

QMK_SETTINGS_INFO = {
    # Tap-Hold
    "Tapping Term": (
        "탭/홀드 판정 기준 시간 (Tapping Term, ms)",
        "키를 눌렀다 뗄 때 '단순 탭 입력'과 '수식키/레이어 홀드'를 구분하는 판정 시간입니다.",
        "기본값 200ms. 타건이 빠른 편이거나 롤오버 시 수식키가 오입력되면 160~180ms 권장, 홀드가 너무 빨리 풀리면 220~250ms."
    ),
    "Permissive Hold": (
        "허용 홀드 (Permissive Hold - 빠른 키 롤오버 허용)",
        "탭홀드 키를 누른 상태에서 다른 키를 눌렀다 떼면, Tapping Term이 끝나지 않았어도 즉시 홀드로 판정합니다.",
        "Shift/Z 탭홀드 키를 누른 채 A를 빠르게 타이핑했을 때 'za' 대신 대문자 'A'가 정확히 입력됩니다."
    ),
    "Hold On Other Key Press": (
        "다른 키 누름 시 즉시 홀드 (Hold On Other Key Press)",
        "탭홀드 키를 누르고 있는 도중 다른 키를 '누르는 순간(Key Down)' 즉시 홀드로 확정합니다.",
        "엄지 레이어 키를 누르고 즉시 다른 키를 입력할 때 레이어 반응 지연을 0ms로 없애줍니다."
    ),
    "Ignore Mod Tap Interrupt": (
        "모드탭 끼어들기 무시 (Ignore Mod Tap Interrupt)",
        "타이핑 중 다른 키가 끼어들어도 Tapping Term이 만료되기 전까지는 탭(일반 키)으로 처리합니다.",
        "빠른 연타 중 수식키 오작동을 줄여주는 레거시 QMK 옵션 (최신 QMK는 Permissive Hold 권장)."
    ),
    "Tapping Force Hold": (
        "연타 후 홀드 강제 (Tapping Force Hold)",
        "탭홀드 키를 탭한 뒤 빠르게 다시 길게 누를 때, 반복 연속 입력 대신 홀드 동작을 발동합니다.",
        "스페이스/레이어 키를 더블탭 후 길게 누르면 스페이스 연타 대신 레이어 전환 기능이 활성화됩니다."
    ),
    "Retro Tapping": (
        "레트로 탭 (Retro Tapping - 다른 키 미입력 시 탭)",
        "Tapping Term보다 오래 누르고 있었더라도, 그 사이 다른 어떤 키도 누르지 않고 뗐다면 탭으로 처리합니다.",
        "스페이스/레이어 키를 누른 채 잠깐 고민하다 뗐을 때 아무것도 안 나오는 대신 스페이스가 정상 입력됩니다."
    ),
    "Quick Tap Term": (
        "빠른 재입력 탭 유지 시간 (Quick Tap Term, ms)",
        "탭홀드 키를 탭한 직후 다시 길게 누를 때, 홀드 대신 해당 탭 키의 연속 입력(반복)을 유지하는 유효 시간입니다.",
        "기본 200ms. A(탭)/Ctrl(홀드)일 때 'A' 탭 후 길게 눌러 AAAAA 연속 타이핑 허용 (0으로 설정 시 연속입력 차단)."
    ),
    "Tap Code Delay": (
        "탭 키코드 전송 딜레이 (Tap Code Delay, ms)",
        "키를 누르고(Press) 뗄(Release) 때 OS가 인식할 수 있도록 사이에 주는 최소 대기 시간입니다.",
        "일부 원격 데스크톱, 게임, 가상머신에서 키 신호가 씹히지 않도록 5~10ms 설정."
    ),
    "Tap Hold Caps Delay": (
        "Caps Lock 탭홀드 딜레이 (Tap Hold Caps Delay, ms)",
        "Caps Lock이 포함된 탭홀드 키 처리 시 OS의 Caps Lock 토글 딜레이와 동기화하는 대기 시간입니다.",
        "Caps Lock 상태 LED 및 대소문자 전환이 안정적으로 동기화됩니다."
    ),
    "Tapping Toggle": (
        "탭 토글 연타 횟수 (Tapping Toggle Count)",
        "TT(layer) 탭 토글 키를 이 횟수만큼 빠르게 연타하면 누르고 있지 않아도 해당 레이어로 고정(토글)됩니다.",
        "기본 5회 -> 2회 또는 3회로 설정하면 마우스 더블클릭하듯 편하게 특정 레이어를 고정할 수 있습니다."
    ),
    "Chordal Hold": (
        "코드 홀드 (Chordal Hold - 스마트 반대손 모디파이어 판정)",
        "홈로우 모드(Home Row Mods) 사용 시 반대편 손 키와 함께 눌릴 때만 모디파이어로 판정하는 최신 알고리즘입니다.",
        "한 손으로 단어를 빠르게 칠 때 수식키 오입력 발생률을 90% 이상 획기적으로 차단합니다."
    ),
    "Flow Tap": (
        "플로우 탭 감지 시간 (Flow Tap, ms)",
        "자연스러운 타이핑 흐름(연속 타건) 속에서는 모디파이어보다 탭(글자) 입력을 우선시하는 지능형 시간입니다.",
        "빠른 영문/한글 타건 중 모디파이어가 튀어나오지 않고 물 흐르듯 부드러운 타이핑을 보장합니다."
    ),

    # Auto Shift
    "Enable": (
        "오토 시프트 활성화 (Enable Auto Shift)",
        "Shift 키를 따로 누르지 않고도 키를 살짝 길게 누르면 대문자/특수기호가 자동 입력됩니다.",
        "[a] 짧게 = a, 길게 = A  |  [1] 짧게 = 1, 길게 = !  |  [;] 짧게 = ;, 길게 = :"
    ),
    "Enable for modifiers": (
        "수식키 조합 시에도 오토 시프트 적용 (Enable for Modifiers)",
        "Ctrl, Alt 등 다른 수식키를 누른 상태에서도 키를 길게 누르면 Shift가 함께 적용됩니다.",
        "Ctrl을 누른 채 [c]를 길게 누르면 Ctrl + Shift + C 가 입력됩니다."
    ),
    "Timeout": (
        "오토 시프트 인식 시간 (Auto Shift Timeout, ms)",
        "키를 몇 ms 이상 누르고 있어야 시프트된 대문자/기호로 변환될지 결정합니다.",
        "기본값 175ms. 타건이 빠르면 135~150ms 추천, 대문자가 자꾸 오입력되면 185~220ms 추천."
    ),
    "Do not Auto Shift special keys": (
        "특수 기호 키 오토 시프트 제외 (Exclude Special Keys)",
        "-, =, [, ], ;, ', ,, ., / 같은 기호 키는 오토 시프트를 끄고 영문 알파벳에만 적용합니다.",
        "코딩 시 따옴표(')나 세미콜론(;)을 길게 눌러도 큰따옴표나 콜론으로 바뀌지 않음."
    ),
    "Do not Auto Shift numeric keys": (
        "숫자 키 오토 시프트 제외 (Exclude Numeric Keys)",
        "1~0 숫자 키는 오토 시프트를 끕니다.",
        "숫자를 길게 꾹 누르고 있어도 !@#$% 특수문자가 나오지 않고 숫자만 입력됩니다."
    ),
    "Do not Auto Shift alpha characters": (
        "알파벳 키 오토 시프트 제외 (Exclude Alpha Characters)",
        "영문 알파벳(A~Z)은 오토 시프트를 끄고 숫자나 기호 키에만 적용합니다.",
        "대문자는 평소처럼 Shift 키로 치고, 기호만 길게 눌러 입력하고 싶을 때 유용합니다."
    ),
    "Enable keyrepeat": (
        "키 반복 입력 허용 (Enable Key Repeat)",
        "키를 꾹 누르고 있으면 대문자가 연속으로 타이핑됩니다.",
        "A를 길게 누르고 있으면 AAAAAAAA... 연속 입력."
    ),
    "Disable keyrepeat when timeout is exceeded": (
        "타임아웃 초과 시 키 반복 차단 (Disable Repeat on Timeout)",
        "키를 길게 눌러 대문자가 1번 입력된 후에는 손을 뗄 때까지 추가 입력되지 않습니다.",
        "대문자 1자만 깔끔하게 입력하고 실수로 글자가 연타되는 현상을 방지합니다."
    ),

    # Magic
    "Swap Caps Lock and Left Control": (
        "Caps Lock과 왼쪽 Control 맞바꾸기 (Swap Caps & LCtrl)",
        "새끼손가락 옆 Caps Lock 위치를 왼쪽 Control 키와 교체합니다.",
        "HHKB 또는 개발자 환경에서 Control을 홈로우 바로 옆에서 편하게 사용."
    ),
    "Treat Caps Lock as Control": (
        "Caps Lock을 Control로 동작 (Caps as Control)",
        "Caps Lock을 눌렀을 때 Control 키코드를 전송합니다.",
        "Caps Lock을 거의 쓰지 않고 Ctrl 전용으로 통일하여 사용할 때 유용."
    ),
    "Swap Left Alt and GUI": (
        "왼쪽 Alt와 윈도우키(GUI) 맞바꾸기 (Swap LAlt & LGUI)",
        "왼쪽 Alt와 Windows(Cmd) 키 위치를 서로 변경합니다.",
        "Mac(macOS)에 연결하여 Command / Option 배열을 맥 키보드처럼 맞출 때 필수."
    ),
    "Swap Right Alt and GUI": (
        "오른쪽 Alt와 윈도우키(GUI) 맞바꾸기 (Swap RAlt & RGUI)",
        "오른쪽 Alt와 Windows 키 위치를 서로 변경합니다.",
        "한/영 전환 키(오른쪽 Alt) 또는 우측 수식키 배열 변경 시 유용."
    ),
    "Disable the GUI keys": (
        "윈도우 키(GUI 키) 비활성화 (Disable GUI / Gaming Mode)",
        "Windows(GUI) 키 입력이 시스템으로 전달되지 않도록 차단합니다.",
        "FPS나 AOS 게임 플레이 중 윈도우 키 오입력으로 바탕화면 튕김 완벽 방지."
    ),
    "Swap ` and Escape": (
        "물결/백틱(`)과 ESC 맞바꾸기 (Swap ` and Escape)",
        "숫자 1 왼쪽의 백틱(`) 키와 ESC 키의 물리적 위치를 교체합니다.",
        "미니배열에서 ESC를 최상단 왼쪽에 두고 백틱을 보조로 쓸 때 편리."
    ),
    "Swap \\ and Backspace": (
        "역슬래시(\\)와 백스페이스 맞바꾸기 (Swap \\ and Backspace)",
        "역슬래시(\\) 키와 백스페이스 키의 위치를 서로 교체합니다.",
        "HHKB 스타일처럼 엔터 바로 윗줄에 백스페이스를 가깝게 두고 싶을 때."
    ),
    "Enable N-key rollover": (
        "N키 무한 동시입력 활성화 (Enable N-Key Rollover / NKRO)",
        "USB 규격 기본 6키 동시입력 제한을 풀고 무제한 동시 입력을 지원합니다.",
        "리듬 게임이나 빠른 동시 키 연타 시 키 씹힘 현상을 완벽 방지."
    ),
    "Swap Left Control and GUI": (
        "왼쪽 Control과 윈도우키(GUI) 맞바꾸기 (Swap LCtrl & LGUI)",
        "왼쪽 Control 키와 Windows(GUI) 키 위치를 서로 변경합니다.",
        "Emacs 사용자 또는 특정 커스텀 OS 환경에서 모디파이어 재배치."
    ),
    "Swap Right Control and GUI": (
        "오른쪽 Control과 윈도우키(GUI) 맞바꾸기 (Swap RCtrl & RGUI)",
        "오른쪽 Control 키와 Windows(GUI) 키 위치를 서로 변경합니다.",
        "우측 한/영 키 또는 방향키 인근 수식키 스왑 시 유용."
    ),

    # Grave Escape
    "Always send Escape if Alt is pressed": (
        "Alt 누른 상태에서는 항상 ESC 전송 (Escape on Alt)",
        "Alt 키를 누르고 있는 도중에는 물결표 대신 반드시 ESC 키를 출력합니다.",
        "Alt + Escape (윈도우 창 전환 단축키) 정상 발동 보장."
    ),
    "Always send Escape if Control is pressed": (
        "Control 누른 상태에서는 항상 ESC 전송 (Escape on Ctrl)",
        "Control 키를 누르고 있는 도중에는 물결표 대신 반드시 ESC 키를 출력합니다.",
        "Ctrl + Escape (윈도우 시작 메뉴 열기 단축키) 정상 발동 보장."
    ),
    "Always send Escape if GUI is pressed": (
        "GUI(윈도우키) 누른 상태에서는 항상 ESC 전송 (Escape on GUI)",
        "GUI 키를 누르고 있는 도중에는 물결표 대신 반드시 ESC 키를 출력합니다.",
        "Win + Escape 단축키(돋보기 종료 등) 정상 작동."
    ),
    "Always send Escape if Shift is pressed": (
        "Shift 누른 상태에서도 항상 ESC 전송 (Escape on Shift)",
        "일반적으로 Shift+Grave는 물결(~)이 입력되지만, 켜면 Shift 조합 시에도 무조건 ESC를 전송합니다.",
        "물결표 대신 강력한 취소(Shift+ESC) 기능을 최우선으로 매핑할 때."
    ),

    # Combo
    "Time out period for combos": (
        "콤보 동시 입력 판정 시간 (Combo Term, ms)",
        "등록된 2개 이상의 키를 동시에 눌렀다고 판정하는 최대 허용 시간 간격입니다.",
        "기본값 50ms. 일반 타건 시 콤보가 잘못 발동되면 30~40ms로 단축, 콤보 키가 씹히면 55~70ms로 연장."
    ),

    # One Shot Keys
    "Tapping this number of times holds the key until tapped once again": (
        "원샷 키 고정(락) 연타 횟수 (One Shot Tap Toggle)",
        "Shift 등 원샷 키를 이 횟수만큼 빠르게 연타하면 누르고 있지 않아도 계속 고정(Lock)됩니다.",
        "2회로 설정 시 Shift 더블탭으로 Caps Lock처럼 영구 대문자 고정, 다시 1번 누르면 해제."
    ),
    "Time (in ms) before the one shot key is released": (
        "원샷 키 자동 해제 대기 시간 (One Shot Timeout, ms)",
        "원샷 키를 탭한 후 다음 키를 누르지 않고 대기할 때, 원샷이 자동으로 풀리는 유효 시간입니다.",
        "기본 2000ms(2초). 탭한 뒤 2초 안에 다른 키를 안 누르면 일반 상태로 안전 복귀."
    ),

    # Mouse keys
    "Delay between pressing a movement key and cursor movement": (
        "마우스 이동 키 입력 반응 지연 (Cursor Delay, ms)",
        "방향 키를 누른 후 커서가 이동을 시작하기 전까지의 대기 시간입니다.",
        "0~10ms 설정 시 누르자마자 딜레이 없이 즉각 반응."
    ),
    "Time between cursor movements in milliseconds": (
        "커서 이동 갱신 주기 (Cursor Interval, ms)",
        "커서가 연속 이동할 때 위치를 업데이트하는 주기입니다.",
        "기본 10~20ms. 낮을수록 고주사율 모니터처럼 커서가 부드럽게 미끄러지듯 이동."
    ),
    "Step size": (
        "커서 1회 이동 단위 거리 (Cursor Step Size, px)",
        "초기 이동 시 한 번에 이동하는 픽셀 크기입니다.",
        "정밀한 클릭 조작을 원하면 1~2px, 빠른 이동을 원하면 3~5px."
    ),
    "Maximum cursor speed at which acceleration stops": (
        "커서 최대 가속 속도 (Cursor Max Speed)",
        "가속도가 붙었을 때 도달하는 최대 커서 이동 속도입니다.",
        "키를 계속 누르고 있을 때 화면 끝까지 빠르게 이동할 수 있는 최고 속도."
    ),
    "Time until maximum cursor speed is reached": (
        "최대 속도 도달 가속 시간 (Time to Max Speed, ms)",
        "초기 속도에서 최대 속도까지 가속되는 데 걸리는 시간입니다.",
        "기본 300~500ms. 짧을수록 빠르게 최대 속도에 도달."
    ),
    "Delay between pressing a wheel key and wheel movement": (
        "휠 스크롤 반응 지연 (Wheel Delay, ms)",
        "휠 키를 누른 후 스크롤이 시작되기 전까지의 대기 시간입니다.",
        "0~10ms 설정 시 즉각적인 스크롤 반응."
    ),
    "Time between wheel movements": (
        "휠 스크롤 갱신 주기 (Wheel Interval, ms)",
        "스크롤이 연속될 때 틱을 전송하는 주기입니다.",
        "낮을수록 휠 스크롤이 부드럽고 촘촘하게 동작."
    ),
    "Maximum number of scroll steps per scroll action": (
        "휠 스크롤 최대 가속 속도 (Wheel Max Speed)",
        "스크롤 키를 계속 누르고 있을 때 한 번에 넘어가는 최대 줄 수입니다.",
        "긴 웹페이지나 문서를 빠르게 넘길 때 조절."
    ),
    "Time until maximum scroll speed is reached": (
        "휠 최대 속도 도달 가속 시간 (Wheel Time to Max, ms)",
        "휠 스크롤이 최고 속도까지 가속되는 데 걸리는 시간입니다.",
        "기본 200~400ms."
    ),
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
        info = QMK_SETTINGS_INFO.get(orig_title)
        if info:
            display_title, desc, example = info
        else:
            display_title = orig_title
            desc = ""
            example = ""

        self.cell_widget = QWidget()
        vbox = QVBoxLayout(self.cell_widget)
        vbox.setContentsMargins(4, 5, 12, 5)
        vbox.setSpacing(3)

        self.lbl_title = QLabel(f"<b>{display_title}</b>")
        self.lbl_title.setStyleSheet("font-size: 13px; color: #f0f6fc;")
        vbox.addWidget(self.lbl_title)

        if desc or example:
            sub_text = ""
            if desc:
                sub_text += f"<span style='color: #8b949e; font-size: 11px;'><b>설명:</b> {desc}</span>"
            if example:
                if sub_text:
                    sub_text += "<br>"
                sub_text += f"<span style='color: #58a6ff; font-size: 11px;'><b>💡 예시/권장:</b> {example}</span>"
            self.lbl_desc = QLabel(sub_text)
            self.lbl_desc.setWordWrap(True)
            self.lbl_desc.setTextFormat(QtCore.Qt.RichText)
            vbox.addWidget(self.lbl_desc)
        else:
            self.lbl_desc = None

        tooltip_text = f"<b>{display_title}</b>"
        if desc:
            tooltip_text += f"<br><br><b>설명:</b> {desc}"
        if example:
            tooltip_text += f"<br><br><b>예시/권장:</b> {example}"
        self.cell_widget.setToolTip(tooltip_text)

        self.container.addWidget(self.cell_widget, self.row, 0)

    def reload(self, keyboard):
        return keyboard.settings.get(self.qsid)

    def delete(self):
        self.cell_widget.hide()
        self.cell_widget.deleteLater()

    def on_change(self):
        self.changed.emit()


class BooleanOption(GenericOption):

    def __init__(self, option, container):
        super().__init__(option, container)

        self.qsid_bit = self.option.get("bit", 0)

        self.checkbox = QCheckBox()
        self.checkbox.setStyleSheet("QCheckBox::indicator { width: 20px; height: 20px; }")
        self.checkbox.stateChanged.connect(self.on_change)
        self.checkbox.setToolTip(self.cell_widget.toolTip())
        self.container.addWidget(self.checkbox, self.row, 1, QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)

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
        self.spinbox.setFixedHeight(28)
        self.spinbox.setMinimumWidth(90)
        self.spinbox.setStyleSheet("font-size: 12px; font-weight: bold; padding: 2px 6px;")
        self.spinbox.valueChanged.connect(self.on_change)
        self.spinbox.setToolTip(self.cell_widget.toolTip())
        self.container.addWidget(self.spinbox, self.row, 1, QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)

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
            container = QGridLayout()
            container.setSpacing(12)
            container.setColumnStretch(0, 1)
            container.setColumnStretch(1, 0)
            w.setLayout(container)

            l = QVBoxLayout()
            l.setContentsMargins(16, 12, 16, 16)
            l.setSpacing(14)

            guide_html = QMK_TAB_GUIDES.get(tab["name"], "")
            if guide_html:
                guide_box = QLabel(guide_html)
                guide_box.setTextFormat(QtCore.Qt.RichText)
                guide_box.setWordWrap(True)
                l.addWidget(guide_box)

            l.addWidget(w)
            l.addStretch()

            scroll_widget = make_scrollable(l)
            self.misc_widgets += [w, scroll_widget]
            display_tab_name = QMK_TAB_TRANSLATIONS.get(tab["name"], tab["name"])
            self.tabs_widget.addTab(scroll_widget, display_tab_name)
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
