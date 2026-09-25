from choppeur.core import rhythm


def test_resolve_device_forces_cpu():
    assert rhythm.resolve_device("cpu") == "cpu"


def test_resolve_device_auto_matches_default(monkeypatch):
    monkeypatch.setattr(rhythm, "default_device", lambda: "cuda")
    assert rhythm.resolve_device("auto") == "cuda"
