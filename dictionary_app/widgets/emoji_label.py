import html

from PySide6.QtCore import Qt

from dictionary_app.theme.styles import EMOJI_FONT_STACK


def set_emoji_prefixed_text(label, glyph, text):
    label.setTextFormat(Qt.RichText)
    label.setText(
        f'<span style="font-family: {EMOJI_FONT_STACK};">{glyph}</span> {html.escape(text)}'
    )
