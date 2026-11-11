import os
import sys
import subprocess
from pathlib import Path
import pytest

def test_close_event_clean_shutdown():
    """Verify that closing the application terminates cleanly with exit code 0 and no 0xC0000409 crash"""
    src_dir = str(Path(__file__).parent.parent / "src")
    test_code = f"""
import sys
from pathlib import Path
sys.path.insert(0, {repr(src_dir)})

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from main import AudiobookPlayerWindow
from single_instance import SingleInstanceManager

app = QApplication(sys.argv)
single_instance = SingleInstanceManager("SPAudiobookPlayer_test_close")
window = AudiobookPlayerWindow()
window.single_instance_manager = single_instance
window.show()

# Verify cover_loader was started
if hasattr(window.library_widget, 'tile_view') and hasattr(window.library_widget.tile_view, 'canvas') and hasattr(window.library_widget.tile_view.canvas, 'cover_loader'):
    cl = window.library_widget.tile_view.canvas.cover_loader
    assert cl.isRunning(), "CoverLoader should be running before close"

# Trigger close after short delay to let initialization settle
def do_close():
    window.close()
    app.quit()

QTimer.singleShot(200, do_close)
exit_code = app.exec()

# Verify that after window.close(), cover_loader is stopped
if hasattr(window.library_widget, 'tile_view') and hasattr(window.library_widget.tile_view, 'canvas') and hasattr(window.library_widget.tile_view.canvas, 'cover_loader'):
    assert not window.library_widget.tile_view.canvas.cover_loader.isRunning(), "CoverLoader should be stopped after close"

# Verify timer stopped
assert not window.timer.isActive(), "UI timer should be stopped after close"

# Clean exit
sys.exit(0)
"""
    # Run in a separate subprocess to verify OS process exit code
    result = subprocess.run(
        [sys.executable, "-c", test_code],
        capture_output=True,
        text=True,
        timeout=15,
    )
    
    assert result.returncode == 0, f"Process crashed or failed with code {result.returncode}. Stderr: {result.stderr}"
