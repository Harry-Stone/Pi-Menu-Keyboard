#!/usr/bin/env python3
# -*- coding: shift_jis -*-
import math
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable, Optional

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QApplication, QWidget

from input_reader import ControllerInput, deadzone


@dataclass
class PieItem:
    label: str
    callback: Optional[Callable[[], None]] = None


@dataclass
class KanaToken:
    romaji: str
    label: str
    delete_units: int = 1


class KeyboardTyper:
    """Send keystrokes to the currently focused application/IME."""

    def __init__(self):
        self.backend = self._detect_backend()
        self.warned = False
        if self.backend:
            print(f"[KEYBOARD] Using {self.backend} for keyboard output")
        else:
            print("[KEYBOARD] No keyboard output backend found. Install xdotool on X11: sudo apt install xdotool")

    def _detect_backend(self) -> Optional[str]:
        if shutil.which("xdotool"):
            return "xdotool"
        if shutil.which("wtype"):
            return "wtype"
        return None

    def _run(self, args: list[str]):
        try:
            subprocess.run(
                args,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            print(f"[KEYBOARD] Failed to run {' '.join(args)}: {exc}")

    def _warn_missing_backend(self):
        if not self.warned:
            print("[KEYBOARD] Cannot type: install xdotool, or wtype if using a compatible Wayland session")
            self.warned = True

    def type_text(self, text: str):
        if not text:
            return

        if self.backend == "xdotool":
            self._run(["xdotool", "type", "--clearmodifiers", "--delay", "0", "--", text])
        elif self.backend == "wtype":
            self._run(["wtype", text])
        else:
            self._warn_missing_backend()

    def key(self, key_name: str, repeat: int = 1):
        if repeat <= 0:
            return

        if self.backend == "xdotool":
            self._run(["xdotool", "key", "--clearmodifiers"] + [key_name] * repeat)
        elif self.backend == "wtype":
            for _ in range(repeat):
                self._run(["wtype", "-k", key_name])
        else:
            self._warn_missing_backend()

    def backspace(self, repeat: int = 1):
        self.key("BackSpace", repeat)


ROMAJI_TO_KANA = {
    "a": "あ", "i": "い", "u": "う", "e": "え", "o": "お",
    "ka": "か", "ki": "き", "ku": "く", "ke": "け", "ko": "こ",
    "ga": "が", "gi": "ぎ", "gu": "ぐ", "ge": "げ", "go": "ご",
    "sa": "さ", "si": "し", "su": "す", "se": "せ", "so": "そ",
    "za": "ざ", "ji": "じ", "zu": "ず", "ze": "ぜ", "zo": "ぞ",
    "ta": "た", "ti": "ち", "tu": "つ", "te": "て", "to": "と",
    "da": "だ", "de": "で", "do": "ど",
    "na": "な", "ni": "に", "nu": "ぬ", "ne": "ね", "no": "の",
    "ha": "は", "hi": "ひ", "hu": "ふ", "he": "へ", "ho": "ほ",
    "ba": "ば", "bi": "び", "bu": "ぶ", "be": "べ", "bo": "ぼ",
    "pa": "ぱ", "pi": "ぴ", "pu": "ぷ", "pe": "ぺ", "po": "ぽ",
    "ma": "ま", "mi": "み", "mu": "む", "me": "め", "mo": "も",
    "ya": "や", "yu": "ゆ", "yo": "よ",
    "ra": "ら", "ri": "り", "ru": "る", "re": "れ", "ro": "ろ",
    "wa": "わ", "wo": "を", "n": "ん",
}

DAKUTEN_MAP = {
    "ka": "ga", "ki": "gi", "ku": "gu", "ke": "ge", "ko": "go",
    "sa": "za", "si": "ji", "su": "zu", "se": "ze", "so": "zo",
    "ta": "da", "ti": "ji", "tu": "zu", "te": "de", "to": "do",
    "ha": "ba", "hi": "bi", "hu": "bu", "he": "be", "ho": "bo",
}

HANDAKUTEN_MAP = {
    "ha": "pa", "hi": "pi", "hu": "pu", "he": "pe", "ho": "po",
    "ba": "pa", "bi": "pi", "bu": "pu", "be": "pe", "bo": "po",
}

YOOON_PREFIX_MAP = {
    "ki": "ky", "gi": "gy",
    "si": "sh", "ji": "j",
    "ti": "ch",
    "ni": "ny",
    "hi": "hy", "bi": "by", "pi": "py",
    "mi": "my",
    "ri": "ry",
}

YOOON_VOWEL_MAP = {"ya": "a", "yu": "u", "yo": "o"}
SMALL_Y_LABEL_MAP = {"ya": "ゃ", "yu": "ゅ", "yo": "ょ"}
SMALL_KANA_MAP = {
    "a": ("xa", "ぁ"),
    "i": ("xi", "ぃ"),
    "u": ("xu", "ぅ"),
    "e": ("xe", "ぇ"),
    "o": ("xo", "ぉ"),
    "ya": ("xya", "ゃ"),
    "yu": ("xyu", "ゅ"),
    "yo": ("xyo", "ょ"),
    "tu": ("xtu", "っ"),
}


class PieMenu:
    def __init__(
        self,
        items: list[PieItem],
        centre: QPointF,
        inner_radius: float = 45,
        outer_radius: float = 145,
        first_item_angle_deg: float = 90,
    ):
        self.items = items
        self.centre = centre
        self.inner_radius = inner_radius
        self.outer_radius = outer_radius
        self.first_item_angle_deg = first_item_angle_deg
        self.hover_index: Optional[int] = None

    def set_centre(self, centre: QPointF):
        self.centre = centre

    def contains_point(self, point: QPointF) -> bool:
        dx = point.x() - self.centre.x()
        dy = point.y() - self.centre.y()
        r = math.hypot(dx, dy)
        return self.inner_radius <= r <= self.outer_radius

    def index_at(self, point: QPointF) -> Optional[int]:
        if not self.contains_point(point):
            return None

        dx = point.x() - self.centre.x()
        dy = point.y() - self.centre.y()
        angle = math.degrees(math.atan2(-dy, dx)) % 360

        n = len(self.items)
        slice_angle = 360 / n
        start_angle = self.first_item_angle_deg - slice_angle / 2
        relative = (angle - start_angle) % 360
        return int(relative // slice_angle)

    def index_at_angle(self, angle: float) -> Optional[int]:
        n = len(self.items)
        if n == 0:
            return None

        slice_angle = 360 / n
        start_angle = self.first_item_angle_deg - slice_angle / 2
        relative = (angle - start_angle) % 360
        return int(relative // slice_angle)

    def trigger_hovered(self):
        if self.hover_index is None:
            return

        item = self.items[self.hover_index]
        print(f"Selected: {item.label}")
        if item.callback:
            item.callback()

    def _wedge_path(self, index: int) -> QPainterPath:
        n = len(self.items)
        slice_angle = 360 / n

        start_angle = self.first_item_angle_deg - slice_angle / 2 + index * slice_angle
        sweep_angle = slice_angle

        outer = QRectF(
            self.centre.x() - self.outer_radius,
            self.centre.y() - self.outer_radius,
            self.outer_radius * 2,
            self.outer_radius * 2,
        )

        inner = QRectF(
            self.centre.x() - self.inner_radius,
            self.centre.y() - self.inner_radius,
            self.inner_radius * 2,
            self.inner_radius * 2,
        )

        path = QPainterPath()
        path.arcMoveTo(outer, start_angle)
        path.arcTo(outer, start_angle, sweep_angle)
        path.arcTo(inner, start_angle + sweep_angle, -sweep_angle)
        path.closeSubpath()
        return path

    def draw(self, painter: QPainter):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        n = len(self.items)
        slice_angle = 360 / n

        base_colour = QColor(30, 30, 30, 150)
        hover_colour = QColor(80, 130, 220, 220)
        outline_colour = QColor(230, 230, 230, 150)
        text_colour = QColor(255, 255, 255, 235)

        painter.setPen(QPen(outline_colour, 1.5))

        for i, item in enumerate(self.items):
            path = self._wedge_path(i)
            painter.setBrush(hover_colour if i == self.hover_index else base_colour)
            painter.drawPath(path)

            centre_angle = self.first_item_angle_deg + i * slice_angle
            rad = math.radians(centre_angle)
            label_radius = (self.inner_radius + self.outer_radius) / 2
            x = self.centre.x() + math.cos(rad) * label_radius
            y = self.centre.y() - math.sin(rad) * label_radius
            label_rect = QRectF(x - 45, y - 18, 90, 36)

            painter.setPen(text_colour)
            painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, item.label)
            painter.setPen(QPen(outline_colour, 1.5))

        painter.setBrush(QColor(10, 10, 10, 170))
        painter.setPen(QPen(outline_colour, 1.5))
        painter.drawEllipse(self.centre, self.inner_radius, self.inner_radius)


class OverlayWindow(QWidget):
    WINDOW_WIDTH = 760
    WINDOW_HEIGHT = 360
    WINDOW_MARGIN = 16

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Pie Menu Overlay")

        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        no_focus_flag = getattr(Qt.WindowType, "WindowDoesNotAcceptFocus", None)
        if no_focus_flag is not None:
            flags |= no_focus_flag
        self.setWindowFlags(flags)

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        show_without_activating = getattr(Qt.WidgetAttribute, "WA_ShowWithoutActivating", None)
        if show_without_activating is not None:
            self.setAttribute(show_without_activating, True)
        x11_no_focus = getattr(Qt.WidgetAttribute, "WA_X11DoNotAcceptFocus", None)
        if x11_no_focus is not None:
            self.setAttribute(x11_no_focus, True)

        self.setWindowOpacity(0.92)
        self.setMouseTracking(True)
        self.resize(self.WINDOW_WIDTH, self.WINDOW_HEIGHT)

        self.keyboard = KeyboardTyper()
        self.kana_buffer: list[KanaToken] = []

        self.primary_kana = PieMenu(
            items=[
                PieItem("あ", lambda: self.action("a")),
                PieItem("か", lambda: self.action("ka")),
                PieItem("さ", lambda: self.action("sa")),
                PieItem("た", lambda: self.action("ta")),
                PieItem("な", lambda: self.action("na")),
                PieItem("は", lambda: self.action("ha")),
                PieItem("ま", lambda: self.action("ma")),
                PieItem("や", lambda: self.action("ya")),
                PieItem("ら", lambda: self.action("ra")),
                PieItem("わ", lambda: self.action("wa")),
            ],
            centre=QPointF(300, 300),
        )

        self.a_menu = PieMenu(
            items=[
                PieItem("あ", lambda: self.action("a")),
                PieItem("い", lambda: self.action("i")),
                PieItem("う", lambda: self.action("u")),
                PieItem("え", lambda: self.action("e")),
                PieItem("お", lambda: self.action("o")),
            ],
            centre=QPointF(300, 300),
        )

        self.ka_menu = PieMenu(
            items=[
                PieItem("か", lambda: self.action("ka")),
                PieItem("き", lambda: self.action("ki")),
                PieItem("く", lambda: self.action("ku")),
                PieItem("け", lambda: self.action("ke")),
                PieItem("こ", lambda: self.action("ko")),
            ],
            centre=QPointF(300, 300),
        )

        self.sa_menu = PieMenu(
            items=[
                PieItem("さ", lambda: self.action("sa")),
                PieItem("し", lambda: self.action("si")),
                PieItem("す", lambda: self.action("su")),
                PieItem("せ", lambda: self.action("se")),
                PieItem("そ", lambda: self.action("so")),
            ],
            centre=QPointF(900, 300),
        )

        self.ta_menu = PieMenu(
            items=[
                PieItem("た", lambda: self.action("ta")),
                PieItem("ち", lambda: self.action("ti")),
                PieItem("つ", lambda: self.action("tu")),
                PieItem("て", lambda: self.action("te")),
                PieItem("と", lambda: self.action("to")),
            ],
            centre=QPointF(900, 300),
        )

        self.na_menu = PieMenu(
            items=[
                PieItem("な", lambda: self.action("na")),
                PieItem("に", lambda: self.action("ni")),
                PieItem("ぬ", lambda: self.action("nu")),
                PieItem("ね", lambda: self.action("ne")),
                PieItem("の", lambda: self.action("no")),
            ],
            centre=QPointF(900, 300),
        )

        self.ha_menu = PieMenu(
            items=[
                PieItem("は", lambda: self.action("ha")),
                PieItem("ひ", lambda: self.action("hi")),
                PieItem("ふ", lambda: self.action("hu")),
                PieItem("へ", lambda: self.action("he")),
                PieItem("ほ", lambda: self.action("ho")),
            ],
            centre=QPointF(900, 300),
        )

        self.ma_menu = PieMenu(
            items=[
                PieItem("ま", lambda: self.action("ma")),
                PieItem("み", lambda: self.action("mi")),
                PieItem("む", lambda: self.action("mu")),
                PieItem("め", lambda: self.action("me")),
                PieItem("も", lambda: self.action("mo")),
            ],
            centre=QPointF(900, 300),
        )

        self.ya_menu = PieMenu(
            items=[
                PieItem("や", lambda: self.action("ya")),
                PieItem("ゆ", lambda: self.action("yu")),
                PieItem("よ", lambda: self.action("yo")),
            ],
            centre=QPointF(900, 300),
        )

        self.ra_menu = PieMenu(
            items=[
                PieItem("ら", lambda: self.action("ra")),
                PieItem("り", lambda: self.action("ri")),
                PieItem("る", lambda: self.action("ru")),
                PieItem("れ", lambda: self.action("re")),
                PieItem("ろ", lambda: self.action("ro")),
            ],
            centre=QPointF(900, 300),
        )

        self.wa_menu = PieMenu(
            items=[
                PieItem("わ", lambda: self.action("wa")),
                PieItem("を", lambda: self.action("wo")),
                PieItem("ん", lambda: self.action("n")),
            ],
            centre=QPointF(900, 300),
        )

        self.aux_menu = PieMenu(
            items=[
                PieItem("変換", lambda: self.action("Auto IME")),
                PieItem("EN / JA", lambda: self.action("Change IME")),
                PieItem("Left", lambda: self.action("Left")),
                PieItem("゛", lambda: self.action("Dakuten")),
                PieItem("大/小", lambda: self.action("Size Toggle")),
                PieItem("゜", lambda: self.action("Handakuten")),
                PieItem("Right", lambda: self.action("Right")),
                PieItem("Mouse", lambda: self.action("Mouse Mode")),
            ],
            centre=QPointF(900, 300),
        )

        self.kana_menus = [
            self.a_menu,
            self.ka_menu,
            self.sa_menu,
            self.ta_menu,
            self.na_menu,
            self.ha_menu,
            self.ma_menu,
            self.ya_menu,
            self.ra_menu,
            self.wa_menu,
        ]

        self.left_menu = self.primary_kana
        self.right_menu = self.aux_menu
        self.menus = [self.left_menu, self.right_menu]

        self.left_candidate_index: Optional[int] = None
        self.right_candidate_index: Optional[int] = None
        self.left_stick_active = False
        self.right_stick_active = False

        self.controller = ControllerInput(deadzone=deadzone)
        self.prev_r1_state = False

        self.stick_activate_threshold = 35.0
        self.stick_release_threshold = self.controller.deadzone
        self.release_confirm_polls = 4

        self.left_used_as_modifier = False
        self.right_active_menu: Optional[PieMenu] = None

        self.left_release_count = 0
        self.right_release_count = 0

        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.poll_controller)
        self.poll_timer.start(16)

    def position_top_right(self, screen_rect: QRectF):
        x = screen_rect.right() - self.WINDOW_WIDTH - self.WINDOW_MARGIN + 1
        y = screen_rect.top() + self.WINDOW_MARGIN
        self.setGeometry(int(x), int(y), self.WINDOW_WIDTH, self.WINDOW_HEIGHT)

    def poll_controller(self):
        left_state, right_state, r1_state = self.controller.get_controller_state()

        if r1_state and not self.prev_r1_state:
            QApplication.quit()

        self.prev_r1_state = r1_state

        changed = False
        changed |= self.on_left_stick(*left_state)
        changed |= self.on_right_stick(*right_state)

        if changed:
            self.update()

    def action(self, name: str):
        print(f"Action fired: {name}")

        if name in ROMAJI_TO_KANA:
            self.type_kana(name, ROMAJI_TO_KANA[name])
            return

        if name == "Dakuten":
            self.apply_dakuten()
        elif name == "Handakuten":
            self.apply_handakuten()
        elif name == "Size Toggle":
            self.apply_size_toggle()
        elif name == "Auto IME":
            self.keyboard.key("space")
        elif name == "Change IME":
            self.keyboard.key("Zenkaku_Hankaku")
        elif name == "Left":
            self.keyboard.key("Left")
        elif name == "Right":
            self.keyboard.key("Right")
        elif name == "Mouse Mode":
            print("[AUX] Mouse Mode selected, no action bound yet")
        else:
            print(f"[AUX] No action bound for {name}")

    def type_kana(self, romaji: str, label: str):
        self.keyboard.type_text(romaji)
        self._push_kana(KanaToken(romaji=romaji, label=label, delete_units=1))
        self._print_buffer()

    def _push_kana(self, token: KanaToken):
        self.kana_buffer.append(token)
        self.kana_buffer = self.kana_buffer[-2:]

    def _print_buffer(self):
        text = " ".join(f"{t.label}/{t.romaji}" for t in self.kana_buffer)
        print(f"[BUFFER] {text}")

    def _replace_last_token(self, new_romaji: str, new_label: str):
        if not self.kana_buffer:
            return
        old = self.kana_buffer[-1]
        self.keyboard.backspace(old.delete_units)
        self.keyboard.type_text(new_romaji)
        self.kana_buffer[-1] = KanaToken(new_romaji, new_label, delete_units=1)
        self._print_buffer()

    def apply_dakuten(self):
        if not self.kana_buffer:
            print("[DAKUTEN] No kana in buffer")
            return

        old = self.kana_buffer[-1]
        new_romaji = DAKUTEN_MAP.get(old.romaji)
        if not new_romaji:
            print(f"[DAKUTEN] Cannot voice {old.label}/{old.romaji}")
            return

        self._replace_last_token(new_romaji, ROMAJI_TO_KANA.get(new_romaji, new_romaji))

    def apply_handakuten(self):
        if not self.kana_buffer:
            print("[HANDAKUTEN] No kana in buffer")
            return

        old = self.kana_buffer[-1]
        new_romaji = HANDAKUTEN_MAP.get(old.romaji)
        if not new_romaji:
            print(f"[HANDAKUTEN] Cannot handaku {old.label}/{old.romaji}")
            return

        self._replace_last_token(new_romaji, ROMAJI_TO_KANA.get(new_romaji, new_romaji))

    def apply_size_toggle(self):
        if len(self.kana_buffer) >= 2:
            base = self.kana_buffer[-2]
            y = self.kana_buffer[-1]
            prefix = YOOON_PREFIX_MAP.get(base.romaji)
            vowel = YOOON_VOWEL_MAP.get(y.romaji)

            if prefix and vowel:
                combo_romaji = prefix + vowel
                combo_label = base.label + SMALL_Y_LABEL_MAP[y.romaji]
                backspaces = base.delete_units + y.delete_units
                print(
                    f"[SIZE] Combine {base.romaji} + {y.romaji}: "
                    f"BackSpace x{backspaces}, type {combo_romaji}"
                )
                self.keyboard.backspace(backspaces)
                self.keyboard.type_text(combo_romaji)
                self.kana_buffer = [KanaToken(combo_romaji, combo_label, delete_units=2)]
                self._print_buffer()
                return

        if self.kana_buffer:
            old = self.kana_buffer[-1]
            small = SMALL_KANA_MAP.get(old.romaji)
            if small:
                new_romaji, new_label = small
                print(
                    f"[SIZE] Small kana {old.romaji}: "
                    f"BackSpace x{old.delete_units}, type {new_romaji}"
                )
                self.keyboard.backspace(old.delete_units)
                self.keyboard.type_text(new_romaji)
                self.kana_buffer[-1] = KanaToken(new_romaji, new_label, delete_units=1)
                self._print_buffer()
                return

        print("[SIZE] No valid small-kana or yoon combination in buffer")

    def _stick_index(self, menu: PieMenu, stateX: float, stateY: float, previous_index: Optional[int]) -> Optional[int]:
        angle = math.degrees(math.atan2(-stateY, stateX)) % 360
        new_index = menu.index_at_angle(angle)

        if previous_index is not None and 0 <= previous_index < len(menu.items):
            slice_angle = 360 / len(menu.items)
            centre_angle = (menu.first_item_angle_deg + previous_index * slice_angle) % 360
            delta = abs((angle - centre_angle + 180) % 360 - 180)
            if delta <= (slice_angle / 2) + 8.0:
                return previous_index

        return new_index

    def on_left_stick(self, stateX: float, stateY: float) -> bool:
        magnitude = math.hypot(stateX, stateY)

        if not self.left_stick_active and magnitude < self.stick_activate_threshold:
            return False

        if magnitude >= self.stick_release_threshold:
            changed = False

            if not self.left_stick_active:
                self.left_stick_active = True
                self.left_used_as_modifier = False
                self.left_release_count = 0

            hover_index = self._stick_index(self.left_menu, stateX, stateY, self.left_candidate_index)

            if hover_index != self.left_menu.hover_index:
                self.left_menu.hover_index = hover_index
                changed = True

                if hover_index is not None and not self.right_stick_active:
                    self.right_menu = self.kana_menus[hover_index]
                    self.right_menu.hover_index = None
                    self.right_candidate_index = None
                    self.right_release_count = 0
                    self.right_active_menu = None
                    self.menus = [self.left_menu, self.right_menu]
                    changed = True

            self.left_candidate_index = hover_index
            self.left_release_count = 0
            return changed

        if not self.left_stick_active:
            return False

        self.left_release_count += 1
        if self.left_release_count < self.release_confirm_polls:
            return False

        self.left_stick_active = False
        self.left_candidate_index = None
        self.left_menu.hover_index = None
        self.left_release_count = 0

        if not self.right_stick_active:
            self.right_menu = self.aux_menu
            self.menus = [self.left_menu, self.right_menu]
            self.right_candidate_index = None
            self.right_release_count = 0
            self.right_active_menu = None
            self.left_used_as_modifier = False

        return True

    def on_right_stick(self, stateX: float, stateY: float) -> bool:
        magnitude = math.hypot(stateX, stateY)

        if not self.right_stick_active and magnitude < self.stick_activate_threshold:
            return False

        if magnitude >= self.stick_release_threshold:
            changed = False

            if not self.right_stick_active:
                self.right_stick_active = True
                self.right_release_count = 0
                self.right_active_menu = self.right_menu

                if self.left_stick_active and self.right_active_menu is not self.aux_menu:
                    self.left_used_as_modifier = True

            active_menu = self.right_active_menu or self.right_menu
            hover_index = self._stick_index(active_menu, stateX, stateY, self.right_candidate_index)

            if hover_index != active_menu.hover_index:
                active_menu.hover_index = hover_index
                changed = True

            self.right_candidate_index = hover_index
            self.right_release_count = 0
            return changed

        if not self.right_stick_active:
            return False

        self.right_release_count += 1
        if self.right_release_count < self.release_confirm_polls:
            return False

        active_menu = self.right_active_menu or self.right_menu
        idx = self.right_candidate_index

        if idx is not None:
            label = active_menu.items[idx].label if 0 <= idx < len(active_menu.items) else None
            print(f"[CTRL] Right select idx={idx} label={label}")
            active_menu.hover_index = idx
            active_menu.trigger_hovered()

        self.right_stick_active = False
        self.right_candidate_index = None
        active_menu.hover_index = None
        self.right_release_count = 0
        self.right_active_menu = None

        if not self.left_stick_active:
            self.right_menu = self.aux_menu
            self.menus = [self.left_menu, self.right_menu]
            self.left_used_as_modifier = False

        return True

    def resizeEvent(self, event):
        w = self.width()
        h = self.height()

        self.left_menu.set_centre(QPointF(w * 0.28, h * 0.52))
        right_centre = QPointF(w * 0.72, h * 0.52)

        self.aux_menu.set_centre(right_centre)
        for menu in self.kana_menus:
            menu.set_centre(right_centre)

        super().resizeEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setFont(QFont("Sans Serif", 11))

        for menu in self.menus:
            menu.draw(painter)

    def mouseMoveEvent(self, event):
        pos = event.position()
        changed = False

        old_hover = self.left_menu.hover_index
        self.left_menu.hover_index = self.left_menu.index_at(pos)

        if old_hover != self.left_menu.hover_index:
            changed = True
            if self.left_menu.hover_index is not None:
                self.right_menu = self.kana_menus[self.left_menu.hover_index]
                self.menus = [self.left_menu, self.right_menu]

        old_hover = self.right_menu.hover_index
        self.right_menu.hover_index = self.right_menu.index_at(pos)

        if old_hover != self.right_menu.hover_index:
            changed = True

        if changed:
            self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            for menu in self.menus:
                if menu.hover_index is not None:
                    menu.trigger_hovered()
                    return

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            QApplication.quit()
        super().keyPressEvent(event)

    def closeEvent(self, event):
        self.controller.close()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    window = OverlayWindow()

    screen = app.primaryScreen()
    if screen:
        window.position_top_right(screen.availableGeometry())

    window.show()
    window.raise_()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
