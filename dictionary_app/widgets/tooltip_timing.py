from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import QHelpEvent
from PySide6.QtWidgets import QProxyStyle, QStyle, QToolTip, QWidget

from dictionary_app.theme.layout_constants import TOOLTIP_WAKE_UP_DELAY

_keep_alive = []


class TooltipDelayStyle(QProxyStyle):
    def styleHint(self, hint, option=None, widget=None, returnData=None):
        if hint == QStyle.StyleHint.SH_ToolTip_WakeUpDelay:
            return TOOLTIP_WAKE_UP_DELAY
        return super().styleHint(hint, option, widget, returnData)


class TooltipShowFilter(QObject):
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.ToolTip and isinstance(obj, QWidget):
            text = obj.toolTip()
            if text and isinstance(event, QHelpEvent):
                QToolTip.showText(event.globalPos(), text, obj, obj.rect())
                return True
        return False


def configure_tooltips(app):
    style = TooltipDelayStyle(app.style())
    app.setStyle(style)
    tooltip_filter = TooltipShowFilter(app)
    app.installEventFilter(tooltip_filter)
    _keep_alive.append((style, tooltip_filter))
