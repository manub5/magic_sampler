import os
import sys
from collections.abc import Mapping

from PySide6.QtWidgets import QApplication

from choppeur.core.cache import AnalysisCache
from choppeur.core.settings import Settings
from choppeur.gui.main_window import MainWindow


def build_window(settings: Settings | None = None, cache: AnalysisCache | None = None) -> MainWindow:
    return MainWindow(settings=settings, cache=cache)


def default_platform_for_session(env: Mapping[str, str] | None = None) -> str | None:
    """
    Certaines sessions Wayland (observé sur KDE Plasma / Kubuntu) provoquent des
    artefacts d'affichage avec des applications Qt Widgets (zones mal
    rafraîchies, bandes). Si rien n'est explicitement demandé, on préfère XCB
    (X11 via XWayland), le chemin le plus éprouvé pour PySide6 côté widgets.

    Incertitude : non vérifié sur toutes les configurations (pilote GPU,
    version de KDE...). Si XCB pose un autre problème, forcer
    `QT_QPA_PLATFORM=wayland` (ou une autre valeur) avant de lancer l'appli
    annule cette valeur par défaut.
    """
    env = os.environ if env is None else env
    if env.get("QT_QPA_PLATFORM"):
        return None  # déjà choisi explicitement : ne pas interférer
    if env.get("XDG_SESSION_TYPE") == "wayland":
        return "xcb"
    return None


def main() -> None:
    platform = default_platform_for_session()
    if platform:
        os.environ["QT_QPA_PLATFORM"] = platform

    app = QApplication(sys.argv)
    window = build_window()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
