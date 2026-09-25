from choppeur.app import build_window


def test_build_window_creates_empty_main_window(qapp):
    window = build_window()
    assert window.windowTitle() == "Choppeur"
    window.close()
