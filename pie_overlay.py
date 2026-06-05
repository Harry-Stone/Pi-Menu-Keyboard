#!/usr/bin/env python3
# -*- coding: shift_jis -*-
import math
import sys
from dataclasses import dataclass
from typing import Callable, Optional

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QApplication, QWidget


@dataclass
class PieItem:
    label: str
    callback: Optional[Callable[[], None]] = None


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

        # Screen coords: +x right, +y down.
        # Convert to mathematical angle: 0 right, 90 up.
        angle = math.degrees(math.atan2(-dy, dx)) % 360

        n = len(self.items)
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

        base_colour = QColor(30, 30, 30, 185)
        hover_colour = QColor(80, 130, 220, 230)
        outline_colour = QColor(230, 230, 230, 170)
        text_colour = QColor(255, 255, 255)

        painter.setPen(QPen(outline_colour, 1.5))

        for i, item in enumerate(self.items):
            path = self._wedge_path(i)

            if i == self.hover_index:
                painter.setBrush(hover_colour)
            else:
                painter.setBrush(base_colour)

            painter.drawPath(path)

            # Draw label
            centre_angle = self.first_item_angle_deg + i * slice_angle
            rad = math.radians(centre_angle)

            label_radius = (self.inner_radius + self.outer_radius) / 2
            x = self.centre.x() + math.cos(rad) * label_radius
            y = self.centre.y() - math.sin(rad) * label_radius

            label_rect = QRectF(x - 45, y - 18, 90, 36)

            painter.setPen(text_colour)
            painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, item.label)
            painter.setPen(QPen(outline_colour, 1.5))

        # Draw centre circle
        painter.setBrush(QColor(10, 10, 10, 210))
        painter.setPen(QPen(outline_colour, 1.5))
        painter.drawEllipse(self.centre, self.inner_radius, self.inner_radius)


class OverlayWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Pie Menu Overlay")

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setMouseTracking(True)

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
                PieItem("\"", lambda: self.action("Dakuten")),
                PieItem("大/小", lambda: self.action("Size Toggle")),
                PieItem("。", lambda: self.action("Handakuten")),
                #PieItem("1 2 3", lambda: self.action("Numbers")),
                PieItem("Right", lambda: self.action("Right")),
                PieItem("Mouse", lambda: self.action("Mouse Mode")),
            ],
            centre=QPointF(900, 300),
        )

        # Mapping from left menu index to right menu
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

    def action(self, name: str):
        print(f"Action fired: {name}")

    def resizeEvent(self, event):
        w = self.width()
        h = self.height()

        self.left_menu.set_centre(QPointF(w * 0.30, h * 0.50))
        self.right_menu.set_centre(QPointF(w * 0.70, h * 0.50))
        
        # Update centres for all kana menus
        for menu in self.kana_menus:
            menu.set_centre(QPointF(w * 0.70, h * 0.50))

        super().resizeEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setFont(QFont("Sans Serif", 11))

        for menu in self.menus:
            menu.draw(painter)

    def mouseMoveEvent(self, event):
        pos = event.position()

        changed = False

        # Update left menu hover
        old_hover = self.left_menu.hover_index
        self.left_menu.hover_index = self.left_menu.index_at(pos)

        if old_hover != self.left_menu.hover_index:
            changed = True
            
            # Switch right menu based on left menu hover
            if self.left_menu.hover_index is not None:
                self.right_menu = self.kana_menus[self.left_menu.hover_index]
                self.menus = [self.left_menu, self.right_menu]

        # Update right menu hover
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


def main():
    app = QApplication(sys.argv)

    window = OverlayWindow()

    screen = app.primaryScreen()
    if screen:
        window.setGeometry(screen.geometry())

    window.showFullScreen()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()