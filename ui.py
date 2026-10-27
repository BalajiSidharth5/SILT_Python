"""Pilot console UI for the lakebed sampler.

Read-only layer. It never touches the controller or the socket.
main.py calls set_state() once per control pass with the values it already holds.
"""

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import QWidget

# ---------------------------------------------------------------- palette
BACKGROUND = QColor(11, 15, 20)
PANEL = QColor(18, 24, 33)
PANEL_TOP = QColor(22, 30, 41)
BORDER = QColor(30, 39, 51)
TEXT = QColor(230, 237, 243)
TEXT_DIM = QColor(139, 152, 169)
TEXT_FAINT = QColor(78, 92, 110)
ACCENT = QColor(47, 209, 197)
OK = QColor(61, 220, 132)
WARN = QColor(245, 165, 36)
FAULT = QColor(255, 77, 79)

# ---------------------------------------------------------------- layout
WIDTH, HEIGHT = 1280, 720
MARGIN = 16
GAP = 16
HEADER_H = 48
SIDEBAR_W = 320
RADIUS = 12
CONNECTION_H = 96
THRUST_H = 120
WINCH_H = 120

SANS = ["Inter", "Segoe UI", "SF Pro Display", "Helvetica Neue", "Arial", "DejaVu Sans"]
MONO = ["JetBrains Mono", "Consolas", "Menlo", "DejaVu Sans Mono", "Courier New"]

CAMERA_COMMANDS = {0: "STOP", 1: "UP", 2: "DOWN"}
DART_COMMANDS = {0: "STOP", 1: "UP"}


def font(families, px, weight=QFont.Weight.Normal, spacing=0.0):
    f = QFont()
    f.setFamilies(families)
    f.setPixelSize(px)
    f.setWeight(weight)
    if spacing:
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    return f


def with_alpha(color, alpha):
    c = QColor(color)
    c.setAlpha(alpha)
    return c


class PilotWindow(QWidget):
    def __init__(self, controller_name=None):
        super().__init__()
        self.setWindowTitle("Lakebed Sampler | Pilot Console")
        self.resize(WIDTH, HEIGHT)
        self.setMinimumSize(1100, 720)

        self.controller_name = controller_name

        # Live values, refreshed by set_state()
        self.thrust = 1500
        self.angle = {"current_angle": 90, "new_angle": 90, "mode": False}
        self.winch = {"camera": False, "cameraCommand": 0, "dart": False, "dartCommand": 0}

        # Link status. Static until the Pi replies. set_link() fills these later.
        self.link_connected = False
        self.link_last_packet = None   # text such as "42 ms"
        self.link_rejected = None      # integer

        # Video frame. set_video_frame() fills this later with a QImage.
        self.video_frame = None

    # ------------------------------------------------------------- inputs
    def set_state(self, thrust, angle, winch_selection):
        self.thrust = thrust
        self.angle = angle
        self.winch = winch_selection
        self.update()

    def set_controller(self, name):
        """Pass the controller name when connected, or None when not."""
        self.controller_name = name
        self.update()

    def set_link(self, connected, last_packet=None, rejected=None):
        self.link_connected = connected
        self.link_last_packet = last_packet
        self.link_rejected = rejected
        self.update()

    def set_video_frame(self, qimage):
        self.video_frame = qimage
        self.update()

    # ------------------------------------------------------------- layout
    def layout_rects(self):
        w, h = self.width(), self.height()
        header = QRectF(MARGIN, MARGIN, w - 2 * MARGIN, HEADER_H)
        top = header.bottom() + GAP
        content_h = h - MARGIN - top
        side_x = w - MARGIN - SIDEBAR_W
        camera = QRectF(MARGIN, top, side_x - GAP - MARGIN, content_h)

        servo_h = content_h - CONNECTION_H - THRUST_H - WINCH_H - 3 * GAP
        y = top
        connection = QRectF(side_x, y, SIDEBAR_W, CONNECTION_H)
        y = connection.bottom() + GAP
        thrust = QRectF(side_x, y, SIDEBAR_W, THRUST_H)
        y = thrust.bottom() + GAP
        servo = QRectF(side_x, y, SIDEBAR_W, servo_h)
        y = servo.bottom() + GAP
        winch = QRectF(side_x, y, SIDEBAR_W, WINCH_H)
        return header, camera, connection, thrust, servo, winch

    # ------------------------------------------------------------- paint
    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.TextAntialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
        )
        p.fillRect(self.rect(), BACKGROUND)

        if self.controller_name:
            self.draw_body(p)
        else:
            self.draw_body_grayed(p)
        self.draw_header(p, self.layout_rects()[0])
        p.end()

    def draw_body(self, p):
        _, camera, connection, thrust, servo, winch = self.layout_rects()
        self.draw_camera(p, camera)
        self.draw_connection(p, connection)
        self.draw_thrust(p, thrust)
        self.draw_servo(p, servo)
        self.draw_winches(p, winch)

    def draw_body_grayed(self, p):
        """Draw every panel off screen, strip the color, and lay it back dimmed."""
        ratio = self.devicePixelRatioF()
        img = QImage(int(self.width() * ratio), int(self.height() * ratio), QImage.Format.Format_RGB32)
        img.setDevicePixelRatio(ratio)
        img.fill(BACKGROUND)
        ip = QPainter(img)
        ip.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.TextAntialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
        )
        self.draw_body(ip)
        ip.end()
        gray = img.convertToFormat(QImage.Format.Format_Grayscale8)
        p.setOpacity(0.4)
        p.drawImage(0, 0, gray)
        p.setOpacity(1.0)

    # ---------------------------------------------------------- primitives
    def panel(self, p, rect, label, label_right=None, label_right_color=TEXT_FAINT):
        grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        grad.setColorAt(0.0, PANEL_TOP)
        grad.setColorAt(1.0, PANEL)
        p.setBrush(QBrush(grad))
        p.setPen(QPen(BORDER, 1))
        p.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), RADIUS, RADIUS)

        p.setFont(font(SANS, 11, QFont.Weight.DemiBold, 1.4))
        p.setPen(TEXT_DIM)
        p.drawText(
            QRectF(rect.x() + 16, rect.y() + 10, rect.width() - 32, 16),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            label,
        )
        if label_right:
            p.setFont(font(SANS, 11, QFont.Weight.Medium, 1.0))
            p.setPen(label_right_color)
            p.drawText(
                QRectF(rect.x() + 16, rect.y() + 10, rect.width() - 32, 16),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                label_right,
            )

    def glow_dot(self, p, center, radius, color):
        glow = QRadialGradient(center, radius * 3.2)
        glow.setColorAt(0.0, with_alpha(color, 110))
        glow.setColorAt(1.0, with_alpha(color, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(glow))
        p.drawEllipse(center, radius * 3.2, radius * 3.2)
        p.setBrush(color)
        p.drawEllipse(center, radius, radius)

    def chip(self, p, rect, text, color, filled=False):
        p.setPen(QPen(with_alpha(color, 150), 1))
        p.setBrush(with_alpha(color, 40) if filled else Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        p.setFont(font(SANS, 11, QFont.Weight.DemiBold, 1.0))
        p.setPen(color)
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

    # -------------------------------------------------------------- header
    def draw_header(self, p, rect):
        # accent mark
        mark = QRectF(rect.x(), rect.y() + 10, 6, rect.height() - 20)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(ACCENT)
        p.drawRoundedRect(mark, 3, 3)

        p.setFont(font(SANS, 18, QFont.Weight.Bold, 2.2))
        p.setPen(TEXT)
        p.drawText(
            QRectF(rect.x() + 20, rect.y(), 360, rect.height()),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "LAKEBED SAMPLER",
        )
        p.setFont(font(SANS, 12, QFont.Weight.Medium, 1.8))
        p.setPen(TEXT_FAINT)
        p.drawText(
            QRectF(rect.x() + 235, rect.y() + 2, 300, rect.height()),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "PILOT CONSOLE",
        )

        # right side chips
        link_text = "LINK ONLINE" if self.link_connected else "LINK OFFLINE"
        link_color = OK if self.link_connected else FAULT
        chip_h = 28
        cy = rect.center().y() - chip_h / 2
        link_rect = QRectF(rect.right() - 140, cy, 140, chip_h)
        self.chip(p, link_rect, link_text, link_color, filled=True)

        ctrl_rect = QRectF(link_rect.x() - 12 - 230, cy, 230, chip_h)
        if self.controller_name:
            name = self.controller_name
            if len(name) > 26:
                name = name[:25] + "..."
            self.chip(p, ctrl_rect, name.upper(), ACCENT)
        else:
            self.chip(p, ctrl_rect, "CONTROLLER NOT CONNECTED", WARN, filled=True)

    # -------------------------------------------------------------- camera
    def draw_camera(self, p, rect):
        self.panel(p, rect, "CAMERA", "DOWN-FACING")
        inner = rect.adjusted(12, 34, -12, -12)

        clip = QPainterPath()
        clip.addRoundedRect(inner, 8, 8)
        p.save()
        p.setClipPath(clip)

        if self.video_frame is not None:
            scaled = self.video_frame.scaled(
                int(inner.width()),
                int(inner.height()),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = inner.x() + (inner.width() - scaled.width()) / 2
            y = inner.y() + (inner.height() - scaled.height()) / 2
            p.fillRect(inner, QColor(5, 8, 12))
            p.drawImage(QPointF(x, y), scaled)
        else:
            bg = QLinearGradient(inner.topLeft(), inner.bottomLeft())
            bg.setColorAt(0.0, QColor(8, 12, 17))
            bg.setColorAt(1.0, QColor(6, 9, 13))
            p.fillRect(inner, QBrush(bg))

            # faint grid
            p.setPen(QPen(with_alpha(TEXT_FAINT, 40), 1))
            step = 48
            x = inner.x() + step
            while x < inner.right():
                p.drawLine(QPointF(x, inner.top()), QPointF(x, inner.bottom()))
                x += step
            y = inner.y() + step
            while y < inner.bottom():
                p.drawLine(QPointF(inner.left(), y), QPointF(inner.right(), y))
                y += step

            # centre crosshair
            c = inner.center()
            p.setPen(QPen(with_alpha(TEXT_FAINT, 120), 1.5))
            p.drawLine(QPointF(c.x() - 18, c.y() - 56), QPointF(c.x() + 18, c.y() - 56))
            p.drawEllipse(QPointF(c.x(), c.y() - 56), 3, 3)

            p.setFont(font(SANS, 30, QFont.Weight.Bold, 6))
            p.setPen(TEXT_FAINT)
            p.drawText(
                QRectF(inner.x(), c.y() - 30, inner.width(), 44),
                Qt.AlignmentFlag.AlignCenter,
                "NO SIGNAL",
            )
            p.setFont(font(SANS, 12, QFont.Weight.Medium, 1.6))
            p.setPen(with_alpha(TEXT_FAINT, 200))
            p.drawText(
                QRectF(inner.x(), c.y() + 18, inner.width(), 20),
                Qt.AlignmentFlag.AlignCenter,
                "WAITING FOR PI CAMERA STREAM",
            )
        p.restore()

        # viewfinder corner brackets
        p.setPen(QPen(with_alpha(ACCENT, 170), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        arm = 22
        pad = 14
        l, t = inner.left() + pad, inner.top() + pad
        r, b = inner.right() - pad, inner.bottom() - pad
        for (x0, y0, dx, dy) in ((l, t, 1, 1), (r, t, -1, 1), (l, b, 1, -1), (r, b, -1, -1)):
            p.drawLine(QPointF(x0, y0), QPointF(x0 + dx * arm, y0))
            p.drawLine(QPointF(x0, y0), QPointF(x0, y0 + dy * arm))

    # ---------------------------------------------------------- connection
    def draw_connection(self, p, rect):
        self.panel(p, rect, "CONNECTION")
        color = OK if self.link_connected else FAULT
        text = "CONNECTED" if self.link_connected else "NOT CONNECTED"

        self.glow_dot(p, QPointF(rect.x() + 26, rect.y() + 43), 6, color)
        p.setFont(font(SANS, 17, QFont.Weight.Bold, 1.0))
        p.setPen(color)
        p.drawText(
            QRectF(rect.x() + 44, rect.y() + 30, rect.width() - 60, 26),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            text,
        )

        col_w = (rect.width() - 32) / 2
        last = self.link_last_packet if self.link_last_packet is not None else "---"
        rej = str(self.link_rejected) if self.link_rejected is not None else "---"
        for i, (name, value) in enumerate((("LAST PACKET", last), ("REJECTED", rej))):
            x = rect.x() + 16 + i * col_w
            p.setFont(font(SANS, 10, QFont.Weight.DemiBold, 1.2))
            p.setPen(TEXT_FAINT)
            p.drawText(QRectF(x, rect.y() + 62, col_w, 14), Qt.AlignmentFlag.AlignLeft, name)
            p.setFont(font(MONO, 13, QFont.Weight.Medium))
            p.setPen(TEXT_DIM)
            p.drawText(QRectF(x, rect.y() + 74, col_w, 18), Qt.AlignmentFlag.AlignLeft, value)

    # -------------------------------------------------------------- thrust
    def draw_thrust(self, p, rect):
        pct = max(-100.0, min(100.0, (self.thrust - 1500) / 5.0))
        self.panel(p, rect, "THRUST")

        bar = QRectF(rect.x() + 16, rect.y() + 62, rect.width() - 32, 14)
        mid_x = bar.center().x()

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(10, 14, 20))
        p.drawRoundedRect(bar, 7, 7)

        half = bar.width() / 2
        if abs(pct) > 0.5:
            fill_w = half * abs(pct) / 100.0
            color = ACCENT if pct > 0 else WARN
            if pct > 0:
                fill = QRectF(mid_x, bar.y(), fill_w, bar.height())
            else:
                fill = QRectF(mid_x - fill_w, bar.y(), fill_w, bar.height())
            grad = QLinearGradient(fill.topLeft(), fill.topRight())
            if pct > 0:
                grad.setColorAt(0.0, with_alpha(color, 120))
                grad.setColorAt(1.0, color)
            else:
                grad.setColorAt(0.0, color)
                grad.setColorAt(1.0, with_alpha(color, 120))
            p.save()
            clip = QPainterPath()
            clip.addRoundedRect(bar, 7, 7)
            p.setClipPath(clip)
            p.fillRect(fill, QBrush(grad))
            p.restore()

        # ticks
        p.setPen(QPen(TEXT_FAINT, 1))
        for k in range(-4, 5):
            x = mid_x + k * half / 4
            tall = 6 if k == 0 else 3
            p.drawLine(QPointF(x, bar.bottom() + 4), QPointF(x, bar.bottom() + 4 + tall))
        p.setPen(QPen(TEXT, 2))
        p.drawLine(QPointF(mid_x, bar.top() - 4), QPointF(mid_x, bar.bottom() + 4))

        # end labels
        p.setFont(font(SANS, 10, QFont.Weight.DemiBold, 1.2))
        p.setPen(TEXT_FAINT)
        p.drawText(QRectF(bar.x(), bar.bottom() + 12, 60, 14), Qt.AlignmentFlag.AlignLeft, "REV")
        p.drawText(QRectF(bar.right() - 60, bar.bottom() + 12, 60, 14), Qt.AlignmentFlag.AlignRight, "FWD")

        # readout
        if pct > 0.5:
            value_color = ACCENT
        elif pct < -0.5:
            value_color = WARN
        else:
            value_color = TEXT
        p.setFont(font(MONO, 26, QFont.Weight.Bold))
        p.setPen(value_color)
        p.drawText(
            QRectF(rect.x() + 16, rect.y() + 24, 150, 34),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "0%" if round(pct) == 0 else f"{pct:+.0f}%",
        )
        p.setFont(font(MONO, 12, QFont.Weight.Medium))
        p.setPen(TEXT_DIM)
        p.drawText(
            QRectF(rect.right() - 16 - 120, rect.y() + 24, 120, 34),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            f"{self.thrust} µs",
        )

    # --------------------------------------------------------------- servo
    def angle_point(self, center, radius, degrees):
        """Dial geometry. 0 degrees points right, 90 up, 180 left (matches the sketch)."""
        rad = math.radians(degrees)
        return QPointF(center.x() + radius * math.cos(rad), center.y() - radius * math.sin(rad))

    def draw_servo(self, p, rect):
        editing = bool(self.angle["mode"])
        committed = self.angle["current_angle"]
        working = self.angle["new_angle"]

        self.panel(p, rect, "SERVO ANGLE")

        # edit light, top right
        light_color = WARN if editing else TEXT_FAINT
        if editing:
            self.glow_dot(p, QPointF(rect.right() - 74, rect.y() + 18), 5, WARN)
        else:
            p.setPen(QPen(TEXT_FAINT, 1.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(rect.right() - 74, rect.y() + 18), 5, 5)
        p.setFont(font(SANS, 11, QFont.Weight.DemiBold, 1.4))
        p.setPen(light_color)
        p.drawText(
            QRectF(rect.right() - 62, rect.y() + 10, 50, 16),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "EDIT",
        )

        radius = min((rect.width() - 64) / 2, rect.height() - 112)
        center = QPointF(rect.center().x(), rect.y() + 40 + radius)
        arc_rect = QRectF(center.x() - radius, center.y() - radius, 2 * radius, 2 * radius)

        # track (Qt arcs use 1/16 degree units, 0 at the right, counter-clockwise)
        track_w = 10
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(10, 14, 20), track_w + 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(arc_rect, 0, 180 * 16)
        p.setPen(QPen(BORDER, track_w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(arc_rect, 0, 180 * 16)

        # filled sweep from 0 (right) to the committed angle
        sweep_color = ACCENT
        p.setPen(QPen(with_alpha(sweep_color, 200), track_w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        if committed > 0:
            p.drawArc(arc_rect, 0, int(committed * 16))

        # ticks
        for deg in range(0, 181, 10):
            major = deg % 30 == 0
            r_out = radius - track_w / 2 - 6
            r_in = r_out - (9 if major else 5)
            p.setPen(QPen(TEXT_DIM if major else TEXT_FAINT, 1.5 if major else 1))
            p.drawLine(self.angle_point(center, r_in, deg), self.angle_point(center, r_out, deg))

        # scale labels
        p.setFont(font(MONO, 10, QFont.Weight.Medium))
        p.setPen(TEXT_FAINT)
        top_pos = self.angle_point(center, radius - track_w / 2 - 28, 90)
        p.drawText(QRectF(top_pos.x() - 18, top_pos.y() - 8, 36, 16), Qt.AlignmentFlag.AlignCenter, "90")
        for deg in (0, 180):
            end = self.angle_point(center, radius, deg)
            p.drawText(QRectF(end.x() - 18, end.y() + 10, 36, 16), Qt.AlignmentFlag.AlignCenter, str(deg))

        needle_len = radius - track_w / 2 - 36

        # working needle first so the committed needle draws on top
        if editing and working != committed:
            tip = self.angle_point(center, needle_len + 6, working)
            p.setPen(QPen(WARN, 2.5, Qt.PenStyle.DashLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(center, tip)
            self.glow_dot(p, tip, 3.5, WARN)

        tip = self.angle_point(center, needle_len, committed)
        p.setPen(QPen(TEXT, 3.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(center, tip)

        # hub
        p.setPen(QPen(BORDER, 2))
        p.setBrush(TEXT)
        p.drawEllipse(center, 9, 9)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(PANEL)
        p.drawEllipse(center, 3.5, 3.5)

        # readout
        shown = working if editing else committed
        shown_color = WARN if editing else TEXT
        p.setFont(font(SANS, 10, QFont.Weight.DemiBold, 1.4))
        p.setPen(TEXT_FAINT)
        p.drawText(
            QRectF(rect.x(), center.y() + 16, rect.width(), 14),
            Qt.AlignmentFlag.AlignCenter,
            "EXACT SERVO ANGLE",
        )
        p.setFont(font(MONO, 26, QFont.Weight.Bold))
        p.setPen(shown_color)
        p.drawText(
            QRectF(rect.x(), center.y() + 30, rect.width(), 34),
            Qt.AlignmentFlag.AlignCenter,
            f"{shown:03d}°",
        )
        if editing:
            p.setFont(font(MONO, 11, QFont.Weight.Medium))
            p.setPen(TEXT_DIM)
            p.drawText(
                QRectF(rect.x() + 16, center.y() + 38, 110, 18),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                f"SET {committed:03d}°",
            )

    # -------------------------------------------------------------- winches
    def draw_winches(self, p, rect):
        self.panel(p, rect, "WINCHES", "LB / RB SELECT")
        rows = (
            ("CAMERA", self.winch["camera"], CAMERA_COMMANDS.get(self.winch["cameraCommand"], "?"), self.winch["cameraCommand"]),
            ("DART", self.winch["dart"], DART_COMMANDS.get(self.winch["dartCommand"], "?"), self.winch["dartCommand"]),
        )
        for i, (name, selected, command, code) in enumerate(rows):
            row = QRectF(rect.x() + 12, rect.y() + 34 + i * 38, rect.width() - 24, 32)

            if selected:
                p.setPen(QPen(with_alpha(ACCENT, 160), 1))
                p.setBrush(with_alpha(ACCENT, 28))
            else:
                p.setPen(QPen(BORDER, 1))
                p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(row, 8, 8)

            # selection marker
            dot_center = QPointF(row.x() + 16, row.center().y())
            if selected:
                self.glow_dot(p, dot_center, 4, ACCENT)
            else:
                p.setPen(QPen(TEXT_FAINT, 1.5))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(dot_center, 4, 4)

            p.setFont(font(SANS, 13, QFont.Weight.DemiBold, 1.4))
            p.setPen(TEXT if selected else TEXT_DIM)
            p.drawText(
                QRectF(row.x() + 32, row.y(), 100, row.height()),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                name,
            )

            if code == 0:
                chip_color = TEXT_FAINT
            elif command == "UP":
                chip_color = OK
            else:
                chip_color = WARN
            chip_rect = QRectF(row.right() - 76, row.y() + 5, 66, row.height() - 10)
            self.chip(p, chip_rect, command, chip_color, filled=code != 0)
