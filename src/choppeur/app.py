import sys

from PySide6.QtWidgets import QApplication

from choppeur.core.cache import AnalysisCache
from choppeur.core.settings import Settings
from choppeur.gui.main_window import MainWindow


def build_window(settings: Settings | None = None, cache: AnalysisCache | None = None) -> MainWindow:
    return MainWindow(settings=settings, cache=cache)


def main() -> None:
    app = QApplication(sys.argv)
    window = build_window()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
