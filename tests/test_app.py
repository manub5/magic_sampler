import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from choppeur.app import build_window


def test_build_window_creates_empty_main_window():
    app = QApplication.instance() or QApplication([])
    window = build_window()
    assert window.windowTitle() == "Choppeur"
    window.close()
