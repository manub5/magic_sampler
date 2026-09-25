import sys

from PySide6.QtWidgets import QApplication, QMainWindow


def build_window() -> QMainWindow:
    window = QMainWindow()
    window.setWindowTitle("Choppeur")
    window.resize(800, 600)
    return window


def main() -> None:
    app = QApplication(sys.argv)
    window = build_window()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
