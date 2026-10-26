def __getattr__(name):
    if name == 'MainWindow':
        from .main_window import MainWindow

        return MainWindow
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
