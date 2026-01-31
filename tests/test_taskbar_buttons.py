"""Тест добавления кнопок в таскбар"""
import sys
import time
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton
from PyQt6.QtCore import QTimer

from taskbar_progress import TaskbarProgress, TaskbarThumbnailButtons, COMTYPES_AVAILABLE

class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Тест кнопок таскбара")
        self.resize(400, 200)
        
        self.taskbar_progress = TaskbarProgress()
        self.thumbnail_buttons = None
        self.icons_dir = Path(__file__).parent / 'resources' / 'icons'
        
        btn = QPushButton("Добавить кнопки", self)
        btn.setGeometry(100, 80, 200, 40)
        btn.clicked.connect(self.add_buttons_manually)
    
    def showEvent(self, event):
        super().showEvent(event)
        
        hwnd = int(self.winId())
        print(f"HWND: {hwnd}")
        self.taskbar_progress.set_hwnd(hwnd)
        
        if self.taskbar_progress.taskbar:
            print("Taskbar interface available")
            self.thumbnail_buttons = TaskbarThumbnailButtons(
                self.taskbar_progress.taskbar,
                hwnd,
                self.icons_dir
            )
            # Добавляем с небольшой задержкой для стабильности
            QTimer.singleShot(500, self.add_buttons_delayed)
        else:
            print("Taskbar interface NOT available!")
    
    def add_buttons_delayed(self):
        print("Adding buttons after delay...")
        self.add_buttons_manually()
    
    def add_buttons_manually(self):
        if self.thumbnail_buttons:
            print(f"Icons dir: {self.icons_dir}")
            print(f"Icons exist: prev.ico={Path(self.icons_dir/'prev.ico').exists()}, play.ico={Path(self.icons_dir/'play.ico').exists()}")
            
            self.thumbnail_buttons.add_buttons()
            print(f"Buttons added: {self.thumbnail_buttons._buttons_added}")
        else:
            print("Thumbnail buttons not initialized!")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec())
