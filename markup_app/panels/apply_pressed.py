def apply_pressed(button):
    button.setProperty("pressed", "true" if button.isChecked() else "false")
    button.style().unpolish(button)
    button.style().polish(button)
