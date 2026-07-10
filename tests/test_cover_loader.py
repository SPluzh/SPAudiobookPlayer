import pytest
import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QEventLoop, QTimer
from PyQt6.QtGui import QImage

sys.path.append(str(Path(__file__).parent.parent / "src"))

from library import CoverLoader

def test_cover_loader_non_square(temp_dir):
    app = QApplication.instance() or QApplication([])
    
    # 1. Create a landscape cover (e.g., 200x100)
    landscape_path = temp_dir / "landscape_cover.png"
    landscape_img = QImage(200, 100, QImage.Format.Format_RGB32)
    landscape_img.fill(0xFF0000) # Red
    # Draw some pattern to ensure edge values are distinct
    for x in range(200):
        landscape_img.setPixelColor(x, 0, landscape_img.pixelColor(x, 10))
    landscape_img.save(str(landscape_path))
    
    # 2. Create a portrait cover (e.g., 100x200)
    portrait_path = temp_dir / "portrait_cover.png"
    portrait_img = QImage(100, 200, QImage.Format.Format_RGB32)
    portrait_img.fill(0x00FF00) # Green
    portrait_img.save(str(portrait_path))

    # 3. Setup CoverLoader
    loader = CoverLoader()
    
    loaded_results = {}
    
    def on_cover_loaded(path, size, image):
        loaded_results[Path(path).name] = (size, image)
        if len(loaded_results) == 2:
            loop.quit()
            
    loader.cover_loaded.connect(on_cover_loaded)
    loader.start()
    
    # 4. Queue loads
    physical_size = 150
    loader.queue_load(str(landscape_path), physical_size)
    loader.queue_load(str(portrait_path), physical_size)
    
    # Run event loop to wait for loads
    loop = QEventLoop()
    # Failsafe timeout
    timer = QTimer()
    timer.timeout.connect(loop.quit)
    timer.start(5000)
    
    loop.exec()
    
    # Stop loader
    loader.stop()
    loader.wait()
    
    # 5. Assertions
    assert "landscape_cover.png" in loaded_results
    size, img = loaded_results["landscape_cover.png"]
    assert size == physical_size
    assert img.width() == physical_size
    assert img.height() == physical_size
    
    assert "portrait_cover.png" in loaded_results
    size2, img2 = loaded_results["portrait_cover.png"]
    assert size2 == physical_size
    assert img2.width() == physical_size
    assert img2.height() == physical_size
