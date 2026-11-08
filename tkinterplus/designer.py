"""Qt design surface; project models remain independent of the editor toolkit."""
from PyQt6.QtCore import QMimeData, QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QDrag, QFont, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsObject, QGraphicsRectItem, QGraphicsScene, QGraphicsView, QListWidget

from .project import SPECS
from .theme import PALETTES

MIME_WIDGET = "application/x-tkinterplus-widget"
A = Qt.AlignmentFlag


class PaletteList(QListWidget):
    def startDrag(self, supported_actions):
        item = self.currentItem()
        if item is None:
            return
        mime = QMimeData()
        mime.setData(MIME_WIDGET, item.data(Qt.ItemDataRole.UserRole).encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.CopyAction)


class Artboard(QGraphicsRectItem):
    def __init__(self, editor):
        super().__init__(0, 0, editor.project.width, editor.project.height)
        self.editor = editor
        self.setZValue(-1)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemUsesExtendedStyleOption)

    def paint(self, painter, option, widget=None):
        p = PALETTES[self.editor.project.theme]
        painter.fillRect(self.rect(), QColor(p.surface))
        if self.editor.snap_action.isChecked():
            exposed = option.exposedRect.intersected(self.rect())
            points = QPolygonF([QPointF(x, y)
                for x in range(max(8, int(exposed.left())//8*8), int(exposed.right()), 8)
                for y in range(max(8, int(exposed.top())//8*8), int(exposed.bottom()), 8)])
            grid = QColor(p.border)
            grid.setAlpha(95)
            painter.setPen(QPen(grid, 1))
            painter.drawPoints(points)
        painter.setPen(QPen(QColor(p.border), 1))
        painter.drawRect(self.rect())


class DesignScene(QGraphicsScene):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            hit = self.itemAt(event.scenePos(), self.editor.view.transform())
            if not isinstance(hit, DesignItem):
                self.editor.select(None)
        super().mousePressEvent(event)


class DesignItem(QGraphicsObject):
    def __init__(self, editor, model):
        super().__init__()
        self.editor = editor
        self.model = model
        self.before = None
        self.start = None
        self.original = None
        self.resizing = False
        self.setPos(model.x, model.y)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
                      QGraphicsItem.GraphicsItemFlag.ItemIsFocusable)
        self.setAcceptHoverEvents(True)
        self.setToolTip(f"{model.id} : {model.kind}")

    def boundingRect(self):
        return QRectF(-1, -1, self.model.width+2, self.model.height+2)

    def handle_rect(self):
        return QRectF(self.model.width-9, self.model.height-9, 10, 10)

    def hoverMoveEvent(self, event):
        resizing = self.isSelected() and self.handle_rect().contains(event.pos())
        self.setCursor(Qt.CursorShape.SizeFDiagCursor if resizing else Qt.CursorShape.SizeAllCursor)
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            return
        self.resizing = self.isSelected() and self.handle_rect().contains(event.pos())
        self.editor.select(self.model.id)
        self.setFocus()
        self.before = self.editor.project.to_dict()
        self.start = QPointF(event.scenePos())
        self.original = self.model.to_dict()
        event.accept()

    def mouseMoveEvent(self, event):
        if self.before is not None:
            self.transform_to(event.scenePos())
        event.accept()

    def transform_to(self, position):
        dx, dy = position.x()-self.start.x(), position.y()-self.start.y()
        m, original = self.model, self.original
        if self.resizing:
            self.prepareGeometryChange()
            m.width = max(16, min(self.editor.snap(original["width"]+dx), self.editor.project.width-m.x))
            m.height = max(2, min(self.editor.snap(original["height"]+dy), self.editor.project.height-m.y))
        else:
            m.x = max(0, min(self.editor.snap(original["x"]+dx), self.editor.project.width-m.width))
            m.y = max(0, min(self.editor.snap(original["y"]+dy), self.editor.project.height-m.height))
            self.setPos(m.x, m.y)
        self.update()
        self.editor.update_geometry_fields()
        self.editor.statusBar().showMessage(f"{m.id}   X: {m.x}  Y: {m.y}   {m.width} × {m.height} px")

    def mouseReleaseEvent(self, event):
        if self.before is not None:
            if event.scenePos() != self.start:
                self.transform_to(event.scenePos())
            before, self.before = self.before, None
            self.editor._commit(before, rebuild_scene=False)
        event.accept()

    def contextMenuEvent(self, event):
        self.editor.select(self.model.id)
        self.editor.context_menu(event.screenPos())
        event.accept()

    def paint(self, painter, option, widget=None):
        m, props = self.model, self.model.props
        p = PALETTES[self.editor.project.theme]
        w, h = m.width, m.height
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setClipRect(QRectF(0, 0, w, h))
        painter.setFont(QFont("Segoe UI", 10))
        painter.setPen(QColor(p.text))
        rect = QRectF(1, 1, max(0, w-2), max(0, h-2))

        def box(fill, border=None, radius=2):
            painter.setBrush(QColor(fill))
            painter.setPen(QPen(QColor(border or fill), 1))
            painter.drawRoundedRect(rect, radius, radius)

        def text(value, bounds=None, align=A.AlignLeft | A.AlignVCenter, color=None):
            painter.setPen(QColor(color or p.text))
            painter.drawText(bounds or QRectF(10, 0, max(0, w-20), h), int(align), str(value))

        kind = m.kind
        if kind == "Label":
            painter.fillRect(rect, QColor(p.surface))
            painter.setFont(QFont("Segoe UI", props["font_size"], QFont.Weight.Bold if props["weight"] == "bold" else QFont.Weight.Normal))
            alignment = {"w": A.AlignLeft, "center": A.AlignHCenter, "e": A.AlignRight}[props["anchor"]]
            text(props["text"], QRectF(1, 0, w-2, h), alignment | A.AlignVCenter,
                 p.muted if props["muted"] else p.text)
        elif kind == "Button":
            variant = props["variant"]
            fill = {"primary": p.accent, "secondary": p.panel, "danger": p.danger}[variant]
            box(fill, radius=8)
            painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            text(props["text"], align=A.AlignCenter | Qt.TextFlag.TextWordWrap,
                 color=p.text if variant == "secondary" else "#ffffff")
        elif kind in ("Entry", "Textbox", "ComboBox"):
            box(p.surface, p.border)
            if kind == "Textbox":
                text(props["value"], QRectF(10, 8, w-20, h-16), A.AlignLeft | A.AlignTop | Qt.TextFlag.TextWordWrap)
            else:
                text(props["value"], QRectF(10, 0, max(0, w-36), h))
            if kind == "ComboBox":
                painter.setPen(QPen(QColor(p.muted), 1.5))
                cx, cy = w-15, h/2
                painter.drawPolyline(QPolygonF([QPointF(cx-4, cy-2), QPointF(cx, cy+2), QPointF(cx+4, cy-2)]))
        elif kind in ("CheckBox", "Switch"):
            painter.fillRect(rect, QColor(p.surface))
            active = props["value"]
            cy = h/2
            if kind == "CheckBox":
                painter.setPen(QPen(QColor(p.accent if active else p.border), 1))
                painter.setBrush(QColor(p.accent if active else p.panel))
                painter.drawRect(QRectF(5, cy-7, 14, 14))
                if active:
                    painter.setPen(QPen(QColor("white"), 1.5))
                    painter.drawPolyline(QPolygonF([QPointF(8, cy), QPointF(11, cy+3), QPointF(17, cy-4)]))
                left = 27
            else:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(p.accent if active else p.border))
                painter.drawRoundedRect(QRectF(1, cy-11, 42, 22), 11, 11)
                painter.setBrush(QColor("white"))
                painter.drawEllipse(QPointF(32 if active else 12, cy), 8, 8)
                left = 53
            text(props["text"], QRectF(left, 0, max(0, w-left), h))
        elif kind == "Slider":
            painter.fillRect(rect, QColor(p.surface))
            painter.setPen(QPen(QColor(p.border), 4))
            painter.drawLine(QPointF(8, h/2), QPointF(w-8, h/2))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(p.accent))
            painter.drawEllipse(QPointF(8+(w-16)*props["value"]/100, h/2), 7, 7)
        elif kind == "ProgressBar":
            painter.fillRect(rect, QColor(p.panel))
            painter.fillRect(QRectF(1, 1, (w-2)*props["value"]/100, h-2), QColor(p.accent))
        elif kind == "Frame":
            painter.fillRect(rect, QColor(getattr(p, props["variant"])))
        elif kind == "Separator":
            painter.fillRect(QRectF(0, 0, w, h), QColor(p.border))
        if self.isSelected():
            painter.setClipping(False)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor("#007acc"), 1, Qt.PenStyle.DashLine))
            painter.drawRect(QRectF(0, 0, w, h))
            painter.setPen(QPen(QColor("#007acc"), 1))
            painter.setBrush(QColor("#ffffff"))
            for x, y in ((0, 0), (w-6, 0), (0, h-6), (w-6, h-6)):
                painter.drawRect(QRectF(x, y, 6, 6))


class DesignView(QGraphicsView):
    def __init__(self, editor):
        super().__init__()
        self.editor = editor
        self.setAcceptDrops(True)
        self.setAlignment(A.AlignLeft | A.AlignTop)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(MIME_WIDGET):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        self.dragEnterEvent(event)

    def add_drop(self, kind, position):
        if kind in SPECS and QRectF(0, 0, self.editor.project.width, self.editor.project.height).contains(position):
            self.editor.add_widget(kind, self.editor.snap(position.x()), self.editor.snap(position.y()))
            return True
        return False

    def dropEvent(self, event):
        if not event.mimeData().hasFormat(MIME_WIDGET):
            event.ignore()
            return
        try:
            kind = bytes(event.mimeData().data(MIME_WIDGET)).decode("utf-8")
        except UnicodeError:
            event.ignore()
            return
        if self.add_drop(kind, self.mapToScene(event.position().toPoint())):
            event.acceptProposedAction()
        else:
            event.ignore()

    def keyPressEvent(self, event):
        moves = {Qt.Key.Key_Left: (-1, 0), Qt.Key.Key_Right: (1, 0),
                 Qt.Key.Key_Up: (0, -1), Qt.Key.Key_Down: (0, 1)}
        if event.key() in moves and self.editor.selected:
            self.editor.nudge(*moves[event.key()])
            event.accept()
        elif event.key() == Qt.Key.Key_Escape:
            self.editor.select(None)
        else:
            super().keyPressEvent(event)
