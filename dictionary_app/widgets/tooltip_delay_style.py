from PySide6.QtWidgets import QProxyStyle, QStyle


class TooltipDelayStyle(QProxyStyle):
    def __init__(self, base_style, wake_up_delay):
        super().__init__(base_style)
        self._wake_up_delay = wake_up_delay

    def styleHint(self, hint, option=None, widget=None, returnData=None):
        if hint == QStyle.StyleHint.SH_ToolTip_WakeUpDelay:
            return self._wake_up_delay
        return super().styleHint(hint, option, widget, returnData)
