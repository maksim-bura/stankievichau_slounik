from PySide6.QtCore import QPoint


def scrollbar_extent(scroll_area):
    return scroll_area.verticalScrollBar().sizeHint().width()


def vertical_scrollbar_shown(scroll_area):
    return scroll_area.verticalScrollBar().maximum() > 0


def overlay_right_inset(container, scroll_area):
    if not vertical_scrollbar_shown(scroll_area):
        return 0
    scroll_area_right = scroll_area.mapTo(container, QPoint(scroll_area.width(), 0)).x()
    return (
        container.width() - scroll_area_right
        + scroll_area.frameWidth()
        + scrollbar_extent(scroll_area)
    )
