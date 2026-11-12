import faulthandler
import sys
import threading


def test_append_to_crash_log_and_rotation(tmp_path, monkeypatch):
    """Verify _append_to_crash_log writes entries and rotates oversized logs."""
    import main as main_mod

    monkeypatch.setattr(main_mod, "get_base_path", lambda: tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    crash_log = data_dir / "crash.log"

    # Write a log larger than max_size_bytes to trigger rotation
    crash_log.write_text("x" * 200, encoding="utf-8")

    main_mod._append_to_crash_log("Test Category", "Sample traceback", max_size_bytes=100)

    backup = data_dir / "crash.log.old"
    assert backup.exists()
    assert backup.read_text(encoding="utf-8") == "x" * 200
    assert crash_log.exists()
    content = crash_log.read_text(encoding="utf-8")
    assert "Test Category" in content
    assert "Sample traceback" in content


def test_setup_crash_guards_installs_hooks(tmp_path, monkeypatch):
    """Verify _setup_crash_guards enables faulthandler and registers all Python/Qt hooks."""
    import main as main_mod
    from PyQt6.QtCore import qInstallMessageHandler

    monkeypatch.setattr(main_mod, "get_base_path", lambda: tmp_path)

    orig_excepthook = sys.excepthook
    orig_thread_hook = threading.excepthook
    orig_unraisable_hook = sys.unraisablehook

    fp = main_mod._setup_crash_guards()
    try:
        assert sys.excepthook is not orig_excepthook
        assert threading.excepthook is not orig_thread_hook
        assert sys.unraisablehook is not orig_unraisable_hook
        assert (tmp_path / "data" / "native_crash.log").exists()
    finally:
        faulthandler.disable()
        if fp is not None:
            fp.close()
        sys.excepthook = orig_excepthook
        threading.excepthook = orig_thread_hook
        sys.unraisablehook = orig_unraisable_hook
        qInstallMessageHandler(None)


def test_safe_application_notify_catches_exception(tmp_path, monkeypatch):
    """Verify SafeApplication.notify logs Qt event exceptions instead of propagating them."""
    import main as main_mod
    from PyQt6.QtCore import QEvent, QObject
    from PyQt6.QtWidgets import QApplication

    monkeypatch.setattr(main_mod, "get_base_path", lambda: tmp_path)

    def raising_notify(self, receiver, event):
        raise RuntimeError("boom in Qt event")

    monkeypatch.setattr(QApplication, "notify", raising_notify)

    # Create a lightweight instance without calling QApplication.__init__ when one already exists
    safe_app = main_mod.SafeApplication.__new__(main_mod.SafeApplication)
    result = safe_app.notify(QObject(), QEvent(QEvent.Type.User))
    assert result is False

    crash_log = tmp_path / "data" / "crash.log"
    assert crash_log.exists()
    content = crash_log.read_text(encoding="utf-8")
    assert "Qt Event Exception" in content
    assert "boom in Qt event" in content
