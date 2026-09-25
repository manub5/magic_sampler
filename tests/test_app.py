from choppeur.app import build_window
from choppeur.core.cache import AnalysisCache
from choppeur.core.settings import Settings


def test_build_window_creates_the_main_window(qapp, tmp_path):
    window = build_window(settings=Settings(), cache=AnalysisCache(tmp_path / "cache.sqlite"))
    assert window.windowTitle() == "Choppeur"
    window.close()
