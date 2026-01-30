# Merged main.py file
# Contains: utils, settings_dialog, multiline_delegate,
# playback_controller, player_widget, library_widget, main

import sys
import os
import io
import subprocess
import sqlite3
import configparser
import update_ffmpeg
import threading
import shutil
from pathlib import Path
from typing import Dict, List, Tuple, Optional

ROOT_DIR = Path(__file__).parent
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QSplitter, QApplication, QMessageBox,
    QTreeWidget, QTreeWidgetItem, QHBoxLayout, QLineEdit, QMenu, QStyle,
    QPushButton, QButtonGroup, QDialog, QDialogButtonBox, QGroupBox,
    QLabel, QFileDialog, QSlider, QProgressBar, QListWidget, QListWidgetItem,
    QFrame, QStyledItemDelegate, QTextEdit, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, QSize, pyqtSignal, QRect, QRectF, QPoint, QPointF, QThread
from PyQt6.QtGui import (
    QIcon, QAction, QPixmap, QBrush, QColor, QFont, QPen, QPainter, QPolygon,
    QTextCursor, QPainterPath
)

from bass_player import BassPlayer
from database import DatabaseManager
from styles import DARK_STYLE
from taskbar_progress import TaskbarProgress, TaskbarThumbnailButtons
import ctypes
from ctypes import wintypes
from translations import tr, trf, set_language, get_language, Language

# ======================================================================
# UTILITY FUNCTIONS
# ======================================================================

def format_duration(seconds):
    """Форматирование длительности для отображения в дереве"""
    if not seconds:
        return ""
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return trf("formats.duration_hours", hours=hours, minutes=minutes)
    return trf("formats.duration_minutes", minutes=minutes) if minutes else trf("formats.duration_seconds", seconds=secs)

def format_time(seconds):
    """Форматирование времени HH:MM:SS"""
    if seconds < 0:
        seconds = 0
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return trf("formats.time_hms", hours=hours, minutes=minutes, seconds=secs)

def format_time_short(seconds):
    """Форматирование времени MM:SS"""
    if seconds < 0:
        seconds = 0
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return trf("formats.time_ms", minutes=minutes, seconds=secs)

def load_icon(file_path: Path, target_size: int) -> QIcon:
    """Загрузка и масштабирование иконки"""
    if file_path.exists() and file_path.is_file():
        pixmap = QPixmap(str(file_path))
        if not pixmap.isNull():
            pixmap = pixmap.scaled(
                int(target_size * 1.5), 
                int(target_size * 1.5),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            icon = QIcon()
            icon.addPixmap(pixmap)
            return icon
    return None

def resize_icon(icon: QIcon, size: int) -> QIcon:
    """Изменение размера иконки"""
    return QIcon(icon.pixmap(QSize(size, size)))

def get_base_path():
    """Возвращает базовый путь к ресурсам приложения"""
    if getattr(sys, 'frozen', False):
        # Если запущено как exe
        if hasattr(sys, '_MEIPASS'):
            # One-file mode
            return Path(sys._MEIPASS)
        # One-dir mode
        return Path(sys.executable).parent
    # Dev mode
    return Path(__file__).parent

def get_icon(name: str, icons_dir: Path = None) -> QIcon:
    """
    Загружает иконку по имени
    
    Args:
        name: Имя иконки (без расширения)
        icons_dir: Путь к папке с иконками (по умолчанию ./icons)
    
    Returns:
        QIcon или пустая иконка если файл не найден
    """
    if icons_dir is None:
        icons_dir = get_base_path() / "resources" / "icons"
    
    # Поддержка разных форматов
    for ext in ['.png', '.svg', '.ico']:
        path = icons_dir / f"{name}{ext}"
        if path.exists():
            return QIcon(str(path))
    
    # Возвращаем пустую иконку если не найдено
    return QIcon()
    
class OutputCapture(io.StringIO):
    """Перехватывает вывод print и отправляет его через сигналы"""
    def __init__(self, signal):
        super().__init__()
        self.signal = signal
        self._real_stdout = sys.__stdout__
    
    def write(self, text):
        if text:
            # Отправляем в сигнал
            self.signal.emit(text)
            # Также дублируем в настоящий stdout для отладки
            if self._real_stdout:
                try:
                    self._real_stdout.write(text)
                except UnicodeEncodeError:
                    # Если консоль не поддерживает кодировку (например, Windows 1251/1252)
                    # Пишем в безопасном режиме
                    try:
                        safe_text = text.encode(self._real_stdout.encoding or 'utf-8', errors='replace').decode(self._real_stdout.encoding or 'utf-8')
                        self._real_stdout.write(safe_text)
                    except Exception:
                        pass # Если совсем всё плохо, просто не пишем в консоль
    
    def flush(self):
        if self._real_stdout:
            self._real_stdout.flush()


class ScannerThread(QThread):
    """Фоновый поток для сканирования директории"""
    progress = pyqtSignal(str)          # Сообщение лога
    finished_scan = pyqtSignal(int)     # Количество найденных аудиокниг
    
    def __init__(self, root_path):
        super().__init__()
        self.root_path = root_path
    
    def run(self):
        try:
            # Перенаправляем stdout
            old_stdout = sys.stdout
            sys.stdout = OutputCapture(self.progress)
            
            from scanner import AudiobookScanner
            scanner = AudiobookScanner('settings.ini') # AudiobookScanner handles resources/ internally
            count = scanner.scan_directory(self.root_path)
            
            # Возвращаем stdout
            sys.stdout = old_stdout
            self.finished_scan.emit(count)
        except Exception as e:
            print(f"Scanner error: {e}")
            self.finished_scan.emit(0)


class ScanProgressDialog(QDialog):
    """Диалог сканирования с консольным выводом"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("scan_dialog.title"))
        self.setMinimumSize(700, 500)
        self.setModal(True)
        
        layout = QVBoxLayout(self)
        
        # Статус
        self.status_label = QLabel(tr("scan_dialog.scanning"))
        self.status_label.setObjectName("scanStatusLabel")
        layout.addWidget(self.status_label)
        
        # Прогресс бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("scanProgressBar")
        self.progress_bar.setRange(0, 0) # Indeterminate
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Консоль
        self.console = QTextEdit()
        self.console.setObjectName("scanConsole")
        self.console.setReadOnly(True)
        # Устанавливаем моноширинный шрифт программно на всякий случай
        font = QFont("Consolas", 10)
        if font.exactMatch():
            self.console.setFont(font)
        layout.addWidget(self.console, 1)
        
        # Кнопка закрытия
        self.close_btn = QPushButton(tr("scan_dialog.close"))
        self.close_btn.setEnabled(False)
        self.close_btn.clicked.connect(self.accept)
        layout.addWidget(self.close_btn)
        
        self.thread = None
    
    def start_scan(self, root_path):
        self.thread = ScannerThread(root_path)
        self.thread.progress.connect(self.append_log)
        self.thread.finished_scan.connect(self.on_finished)
        self.thread.start()
    
    def append_log(self, text):
        self.console.insertPlainText(text)
        # Авто-скролл
        self.console.verticalScrollBar().setValue(
            self.console.verticalScrollBar().maximum()
        )
    
    def on_finished(self, count):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("100%")
        self.status_label.setText(trf("scan_dialog.complete", count=count))
        self.close_btn.setEnabled(True)

    def closeEvent(self, event):
        if self.thread and self.thread.isRunning():
            event.ignore()
        else:
            super().closeEvent(event)



class UpdateThread(QThread):
    progress = pyqtSignal(str)
    finished_update = pyqtSignal(bool)

    def run(self):
        capture = OutputCapture(self.progress)
        # capture.text_written.connect(self.progress.emit) - OutputCapture emits to signal directly
        original_stdout = sys.stdout
        sys.stdout = capture
        
        success = False
        try:
            # Force update to ensure we get the latest
            success = update_ffmpeg.download_ffmpeg(force=True)
        except Exception as e:
            print(f"UpdateThread Error: {e}")
        finally:
            sys.stdout = original_stdout
            self.finished_update.emit(success)

class UpdateProgressDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("ffmpeg_updater.dialog_title"))
        self.setMinimumSize(600, 400)
        self.setup_ui()
        self.thread = None
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        self.status_label = QLabel(tr("ffmpeg_updater.check_dir"))
        self.status_label.setObjectName("scanStatusLabel")
        layout.addWidget(self.status_label)
        
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setObjectName("scanConsole")
        # Reuse scan console font
        from PyQt6.QtGui import QFont # Ensure import or use exiting
        font = QFont("Consolas", 10)
        if not font.exactMatch():
            font = QFont("Courier New", 10)
        self.console.setFont(font)
        layout.addWidget(self.console)
        
        self.close_btn = QPushButton(tr("scan_dialog.close"))
        self.close_btn.setEnabled(False)
        self.close_btn.clicked.connect(self.accept)
        layout.addWidget(self.close_btn)
        
    def start_update(self):
        self.thread = UpdateThread()
        self.thread.progress.connect(self.update_console)
        self.thread.finished_update.connect(self.on_finished)
        self.thread.start()
        
    def update_console(self, text):
        from PyQt6.QtGui import QTextCursor
        cursor = self.console.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        
        # Если пришел \r, обрабатываем
        if '\r' in text:
            parts = text.split('\r')
            
            for i, part in enumerate(parts):
                if i > 0: # Это часть после \r
                    # Выделяем всё от начала текущего блока (строки)
                    cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock, QTextCursor.MoveMode.KeepAnchor)
                    cursor.removeSelectedText()
                
                cursor.insertText(part)
        else:
            cursor.insertText(text)
            
        self.console.setTextCursor(cursor)
        self.console.verticalScrollBar().setValue(
            self.console.verticalScrollBar().maximum()
        )
        
    def on_finished(self, success):
        self.status_label.setText(tr("ffmpeg_updater.success") if success else tr("ffmpeg_updater.error"))
        self.close_btn.setEnabled(True)

    def closeEvent(self, event):
        if self.thread and self.thread.isRunning():
            event.ignore()
        else:
            super().closeEvent(event)


# ======================================================================
# DIALOGS
# ======================================================================

class AboutDialog(QDialog):
    """Custom About Dialog with dark theme"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setup_ui()

    def showEvent(self, event):
        self.adjustSize()
        self.center_window()
        super().showEvent(event)

    def get_app_version(self):
        try:
            version_file = get_base_path() / "resources" / "version.txt"
            if version_file.exists():
                return version_file.read_text("utf-8").strip()
        except Exception:
            pass
        return "1.0.0"

    def setup_ui(self):
        # Main layout with dark background
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Container frame
        self.container = QFrame()
        self.container.setObjectName("aboutContainer")
        
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(30, 40, 30, 30)
        container_layout.setSpacing(15)
        
        # Title
        title = QLabel(tr('window.title'))
        title.setObjectName("aboutTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container_layout.addWidget(title)
        
        # Version
        version_text = self.get_app_version()
        version = QLabel(trf('about.version', version=version_text))
        version.setObjectName("aboutVersion")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container_layout.addWidget(version)
        
        # Separator
        line = QFrame()
        line.setObjectName("aboutLine")
        line.setFrameShape(QFrame.Shape.HLine)
        container_layout.addWidget(line)
        
        # Description
        desc = QLabel(tr('about.description'))
        desc.setObjectName("aboutDesc")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        container_layout.addWidget(desc)
        
        container_layout.addSpacing(10)
        
        # Close Button
        close_btn = QPushButton(tr('about.close'))
        close_btn.setObjectName("aboutCloseBtn")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setFixedWidth(120)
        close_btn.clicked.connect(self.accept)
        container_layout.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(self.container)

    def center_window(self):
        if self.parent():
            parent_geo = self.parent().frameGeometry()
            self_geo = self.frameGeometry()
            self_geo.moveCenter(parent_geo.center())
            self.move(self_geo.topLeft())
        else:
            # Если родителя нет, центрируем по экрану
            screen = QApplication.primaryScreen().geometry()
            self_geo = self.frameGeometry()
            self_geo.moveCenter(screen.center())
            self.move(self_geo.topLeft())

class SettingsDialog(QDialog):
    """Диалог настроек аудиокнижного плеера"""
    
    # Сигналы
    path_saved = pyqtSignal(str)  # Путь сохранён
    scan_requested = pyqtSignal(str)  # Сканирование с новым путём
    data_reset_requested = pyqtSignal()  # Запрос на полный сброс данных
    closed = pyqtSignal()  # Диалог закрыт
    
    def __init__(self, parent=None, current_path="", ffprobe_path=None):
        super().__init__(parent)  # ← Только parent
        self.setWindowTitle(tr("settings.title"))
        self.setMinimumSize(720, 300)
        self.current_path = current_path
        self.ffprobe_path = ffprobe_path
        self.settings_path_edit = None
        self.init_ui()
    
    def init_ui(self):
        # Главный вертикальный слой
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)

        # Горизонтальный слой для контента (настройки и инструменты)
        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)

        # --- Левая колонка: Основные настройки ---
        left_layout = QVBoxLayout()
        left_layout.setSpacing(20)

        # Путь к библиотеке
        path_group = QGroupBox(tr("settings.library_path_group"))
        path_layout = QVBoxLayout(path_group)
        
        path_edit_layout = QHBoxLayout()
        self.settings_path_edit = QLineEdit(self.current_path)
        self.settings_path_edit.setPlaceholderText(tr("settings.library_path_placeholder"))
        path_edit_layout.addWidget(self.settings_path_edit, 1)
        
        browse_btn = QPushButton(tr("settings.browse"))
        browse_btn.setObjectName("browseBtn")
        browse_btn.clicked.connect(self.browse_directory)
        path_edit_layout.addWidget(browse_btn)
        
        path_layout.addLayout(path_edit_layout)
        left_layout.addWidget(path_group)

        # Обновление библиотеки
        scan_group = QGroupBox(tr("settings.scan_group"))
        scan_layout = QVBoxLayout(scan_group)
        
        rescan_btn = QPushButton(tr("settings.scan_button"))
        rescan_btn.setObjectName("scanBtn")
        rescan_btn.clicked.connect(self.on_scan_requested)
        scan_layout.addWidget(rescan_btn)
        
        scan_info = QLabel(tr("settings.scan_info"))
        scan_info.setWordWrap(True)
        scan_layout.addWidget(scan_info)
        
        left_layout.addWidget(scan_group)
        left_layout.addStretch()
        
        content_layout.addLayout(left_layout, 3)

        # --- Правая колонка: Инструменты ---
        tools_group = QGroupBox(tr("settings.tools_group"))
        tools_layout = QVBoxLayout(tools_group)
        
        self.update_btn = QPushButton(tr("ffmpeg_updater.settings_btn"))
        self.update_btn.clicked.connect(self.on_update_ffmpeg)
        tools_layout.addWidget(self.update_btn)
        
        tools_info = QLabel(tr("ffmpeg_updater.settings_info"))
        tools_info.setWordWrap(True)
        tools_info.setStyleSheet("color: #888; font-size: 11px;")
        tools_layout.addWidget(tools_info)
        
        # Сброс данных
        tools_layout.addSpacing(10)
        reset_btn = QPushButton(tr("settings.reset_data_btn"))
        reset_btn.setObjectName("resetBtn")
        reset_btn.clicked.connect(self.on_reset_data)
        tools_layout.addWidget(reset_btn)
        
        reset_info = QLabel(tr("settings.reset_data_info"))
        reset_info.setWordWrap(True)
        reset_info.setStyleSheet("color: #888; font-size: 11px;")
        tools_layout.addWidget(reset_info)
        
        tools_layout.addStretch()
        
        content_layout.addWidget(tools_group, 1)
        
        main_layout.addLayout(content_layout)

        # Проверка статуса ffprobe при открытии
        self.update_ffprobe_status()

        # --- Кнопка "Сохранить" снизу во всю ширину ---
        save_button = QPushButton(tr("settings.save"))
        save_button.setObjectName("saveBtn")
        save_button.setMinimumHeight(40)
        save_button.clicked.connect(self.on_save)
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )
        main_layout.addWidget(save_button)
    
    def get_path(self):
        return self.settings_path_edit.text().strip()
    
    def browse_directory(self):
        directory = QFileDialog.getExistingDirectory(
            self, 
            tr("settings.choose_directory"), 
            self.settings_path_edit.text()
        )
        if directory:
            self.settings_path_edit.setText(directory)
    
    def on_save(self):
        new_path = self.get_path()
        if new_path:
            self.path_saved.emit(new_path)
        self.accept()
    
    def on_scan_requested(self):
        new_path = self.get_path()
        if new_path:
            self.scan_requested.emit(new_path)

    def update_ffprobe_status(self):
        """Проверяет наличие ffprobe и обновляет текст кнопки"""
        ffprobe_exe = self.ffprobe_path
        
        if ffprobe_exe.exists():
            self.update_btn.setText(tr("ffmpeg_updater.settings_btn_installed"))
        else:
            self.update_btn.setText(tr("ffmpeg_updater.settings_btn"))

    def on_update_ffmpeg(self):
        dialog = UpdateProgressDialog(self)
        dialog.start_update()
        dialog.exec()
        # Обновляем статус после закрытия диалога
        self.update_ffprobe_status()

    def on_reset_data(self):
        """Сброс всей базы данных и обложек"""
        reply = QMessageBox.question(
            self,
            tr("settings.reset_confirm_title"),
            tr("settings.reset_confirm_msg"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.data_reset_requested.emit()
            self.accept()

class StyleLabel(QLabel):
    """Вспомогательный виджет для получения стилей из QSS"""
    def __init__(self, object_name: str, parent: QWidget = None):
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setVisible(False)

class MultiLineDelegate(QStyledItemDelegate):
    """Делегат с поддержкой стилизации через QSS и локализации"""
    
    STYLE_NAMES = [
        'delegate_author',
        'delegate_title', 
        'delegate_narrator',
        'delegate_info',
        'delegate_folder',
        'delegate_progress',
        'delegate_duration',
        'delegate_file_count'
    ]
    
    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        
        self.audiobook_row_height = 120
        self.folder_row_height = 30
        self.audiobook_icon_size = 100
        self.horizontal_padding = 10
        self.vertical_padding = 8
        self.line_spacing = 4
        
        # Состояние воспроизведения
        self.playing_path = None
        self.is_paused = True
        
        # Состояние мыши для кнопки Play
        self.hovered_index = None
        self.mouse_pos = None
        
        self._style_labels: dict[str, StyleLabel] = {}
        self._create_style_widgets(parent)
        
        self.format_duration = self._default_format_duration

    def _create_style_widgets(self, parent: QWidget):
        """Создаёт скрытые виджеты для чтения стилей из QSS"""
        for name in self.STYLE_NAMES:
            label = StyleLabel(name, parent)
            self._style_labels[name] = label
    
    def _get_style(self, style_name: str) -> tuple[QFont, QColor]:
        """Получает шрифт и цвет из QSS для указанного стиля"""
        label = self._style_labels.get(style_name)
        if label:
            label.ensurePolished()
            font = label.font()
            color = label.palette().color(label.foregroundRole())
            return font, color
        return QFont(), QColor(Qt.GlobalColor.white)
    
    def _default_format_duration(self, seconds: int) -> str:
        """Форматирование длительности по умолчанию"""
        return format_time(seconds)
    
    def update_styles(self):
        """Обновляет стили (вызывать после изменения QSS)"""
        for label in self._style_labels.values():
            label.style().unpolish(label)
            label.style().polish(label)
            label.update()
    
    def sizeHint(self, option, index) -> QSize:
        size = super().sizeHint(option, index)
        item_type = index.data(Qt.ItemDataRole.UserRole + 1)
        
        if item_type == 'folder':
            size.setHeight(self.folder_row_height)
        elif item_type == 'audiobook':
            size.setHeight(self.audiobook_row_height)
            
        return size
    
    def paint(self, painter, option, index):
        item_type = index.data(Qt.ItemDataRole.UserRole + 1)
        
        if item_type == 'folder':
            self._paint_folder(painter, option, index)
        elif item_type == 'audiobook':
            self._paint_audiobook(painter, option, index)
        else:
            super().paint(painter, option, index)
    
    def _paint_folder(self, painter, option, index):
        """Отрисовка папки"""
        painter.save()
        
        font, color = self._get_style('delegate_folder')
        painter.setFont(font)
        painter.setPen(color)
        
        icon = index.data(Qt.ItemDataRole.DecorationRole)
        icon_size = 20
        icon_rect = QRect(
            option.rect.left() + self.horizontal_padding,
            option.rect.top() + (option.rect.height() - icon_size) // 2,
            icon_size, icon_size
        )
        if icon:
            icon.paint(painter, icon_rect)
        
        text = index.data(Qt.ItemDataRole.DisplayRole)
        text_rect = QRect(
            icon_rect.right() + 8,
            option.rect.top(),
            option.rect.right() - icon_rect.right() - 18,
            option.rect.height()
        )
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter, text or "")
        
        painter.restore()
    
    def get_play_button_rect(self, icon_rect: QRectF) -> QRectF:
        """Возвращает область кнопки Play в центре иконки (высокая точность)"""
        btn_size = 40.0
        center = icon_rect.center()
        return QRectF(
            center.x() - btn_size / 2.0,
            center.y() - btn_size / 2.0,
            btn_size,
            btn_size
        )

    def _paint_audiobook(self, painter, option, index):
        """Отрисовка аудиокниги"""
        painter.save()
        
        icon = index.data(Qt.ItemDataRole.DecorationRole)
        icon_rect = QRect(
            option.rect.left() + self.horizontal_padding,
            option.rect.top() + self.vertical_padding,
            self.audiobook_icon_size,
            self.audiobook_icon_size
        )
        data = index.data(Qt.ItemDataRole.UserRole + 2)
        if not data:
            painter.restore()
            return
            
        author, title, narrator, file_count, duration, listened_duration, progress_percent = data
        
        if icon:
            # --- ОБЛАСТЬ ОБЛОЖКИ (с общим скруглением 3px) ---
            painter.save()
            path = QPainterPath()
            path.addRoundedRect(QRectF(icon_rect), 3.0, 3.0)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setClipPath(path)
            
            # 1. Сама иконка
            icon.paint(painter, icon_rect)
            
            # 2. Прогрессбар (теперь автоматически обрезается по углам)
            if progress_percent > 0:
                pb_h = 5
                pb_margin = 0
                pb_rect = QRect(icon_rect.left() + pb_margin, 
                                icon_rect.bottom() - pb_h - pb_margin,
                                icon_rect.width() - pb_margin * 2, 
                                pb_h)
                
                # Фон
                painter.fillRect(pb_rect, QColor(0, 0, 0, 150))
                
                # Заполнение
                fill_w = int(pb_rect.width() * progress_percent / 100)
                if fill_w > 0:
                    fill_rect = QRect(pb_rect.left(), pb_rect.top(), fill_w, pb_rect.height())
                    painter.fillRect(fill_rect, QColor("#018574")) # Тот же зеленый
            
            # 3. Полупрозрачный фон при наведении (теперь тоже по клипу)
            playing_file = index.data(Qt.ItemDataRole.UserRole)
            is_playing_this = (self.playing_path and playing_file == self.playing_path)
            
            if self.hovered_index == index:
                painter.fillRect(icon_rect, QColor(0, 0, 0, 100))
            
            painter.restore()
            # --- КОНЕЦ ОБЛАСТИ ОБЛОЖКИ ---
            
            # 4. Отрисовка рамки для текущей книги (поверх или вокруг)
            if is_playing_this:
                # Зеленая рамка 8px для запущенной книги.
                # Чтобы внутренний радиус был 3px при толщине пера 8px (4px внутрь),
                # радиус отрисовки должен быть 3 + 4 = 7px.
                pen = QPen(QColor("#018574"), 8)
                painter.setPen(pen)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.drawRoundedRect(QRectF(icon_rect).adjusted(-4, -4, 4, 4), 7, 7)

            # 5. Отрисовка кнопки Play/Pause
            if self.hovered_index == index or is_playing_this:
                play_btn_rect = self.get_play_button_rect(QRectF(icon_rect))
                
                # Проверяем наведение конкретно на кнопку
                is_over_btn = False
                if self.mouse_pos and play_btn_rect.contains(QPointF(self.mouse_pos)):
                    is_over_btn = True
                
                painter.save()
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                
                # Сама кнопка
                btn_color = QColor(1, 133, 116) # Тот же зеленый
                if not is_over_btn:
                    btn_color.setAlpha(200)
                else:
                    btn_color = btn_color.lighter(110)
                
                painter.setBrush(btn_color)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(play_btn_rect)
                
                # Иконка Play или Pause
                painter.setBrush(Qt.GlobalColor.white)
                if is_playing_this and not self.is_paused:
                    # Рисуем две полоски паузы
                    w = play_btn_rect.width() // 5
                    h = play_btn_rect.height() // 2
                    gap = w // 2
                    
                    total_w = w * 2 + gap
                    start_x = play_btn_rect.left() + (play_btn_rect.width() - total_w) // 2
                    start_y = play_btn_rect.top() + (play_btn_rect.height() - h) // 2
                    
                    painter.drawRect(QRectF(start_x, start_y, w, h))
                    painter.drawRect(QRectF(start_x + w + gap, start_y, w, h))
                else:
                    # Рисуем треугольник Play
                    side = play_btn_rect.width() // 2
                    # Используем QPointF для субпиксельной точности
                    center_f = QPointF(play_btn_rect.center())
                    
                    # Для оптического баланса по горизонтали треугольник должен быть чуть правее центра круга
                    h_offset = play_btn_rect.width() / 20.0
                    
                    tri_path = QPainterPath()
                    # Вертикально центрируем по center_f.y()
                    tri_path.moveTo(center_f.x() - side / 3.0 + h_offset, center_f.y() - side / 2.0)
                    tri_path.lineTo(center_f.x() - side / 3.0 + h_offset, center_f.y() + side / 2.0)
                    tri_path.lineTo(center_f.x() + side / 2.0 + h_offset, center_f.y())
                    tri_path.closeSubpath()
                    
                    painter.fillPath(tri_path, Qt.GlobalColor.white)
                
                painter.restore()
        
        text_x = icon_rect.right() + 15
        text_y = option.rect.top() + self.vertical_padding
        available_width = option.rect.right() - text_x - self.horizontal_padding
        
        # АВТОР
        if author:
            font, color = self._get_style('delegate_author')
            painter.setFont(font)
            painter.setPen(color)
            
            line_height = painter.fontMetrics().height()
            rect = QRect(text_x, text_y, available_width, line_height)
            painter.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, author)
            text_y += line_height + self.line_spacing
        
        # НАЗВАНИЕ
        font, color = self._get_style('delegate_title')
        painter.setFont(font)
        painter.setPen(color)
        
        line_height = painter.fontMetrics().height()
        rect = QRect(text_x, text_y, available_width, line_height)
        
        elided_title = painter.fontMetrics().elidedText(
            title or tr("delegate.no_title"), 
            Qt.TextElideMode.ElideRight, 
            available_width
        )
        painter.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided_title)
        text_y += line_height + self.line_spacing
        
        # РАССКАЗЧИК
        if narrator:
            font, color = self._get_style('delegate_narrator')
            painter.setFont(font)
            painter.setPen(color)
            
            line_height = painter.fontMetrics().height()
            rect = QRect(text_x, text_y, available_width, line_height)
            narrator_text = f"{tr('delegate.narrator_prefix')} {narrator}"
            painter.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, narrator_text)
            text_y += line_height + self.line_spacing
        
        # ИНФОРМАЦИОННАЯ СТРОКА
        info_parts = []
        
        # Количество файлов
        if file_count:
            font_fc, color_fc = self._get_style('delegate_file_count')
            files_text = f"{tr('delegate.files_prefix')} {file_count}"
            info_parts.append((files_text, font_fc, color_fc))
        
        # Длительность
        if duration:
            font_dur, color_dur = self._get_style('delegate_duration')
            duration_text = f"{tr('delegate.duration_prefix')} {self.format_duration(duration)}"
            info_parts.append((duration_text, font_dur, color_dur))
        
        # Прогресс
        font_prog, color_prog = self._get_style('delegate_progress')
        progress_text = trf("delegate.progress", percent=int(progress_percent))
        info_parts.append((progress_text, font_prog, color_prog))
        
        # Рисуем информационную строку
        if info_parts:
            current_x = text_x
            for i, (text, font, color) in enumerate(info_parts):
                painter.setFont(font)
                painter.setPen(color)
                
                text_width = painter.fontMetrics().horizontalAdvance(text)
                line_height = painter.fontMetrics().height()
                
                rect = QRect(current_x, text_y, text_width + 10, line_height)
                painter.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)
                
                current_x += text_width + 15
                
                # Разделитель
                if i < len(info_parts) - 1:
                    painter.setPen(QColor(100, 100, 100))
                    painter.drawText(QRect(current_x - 10, text_y, 10, line_height),
                                   Qt.AlignmentFlag.AlignCenter, tr("delegate.separator"))
        
        painter.restore()
class PlaybackController:
    def __init__(self, player: BassPlayer, db_manager: DatabaseManager):
        self.player = player
        self.db = db_manager
        self.library_root: Optional[Path] = None
        
        # Состояние воспроизведения
        self.current_audiobook_id: Optional[int] = None
        self.current_audiobook_path: str = "" # Относительный путь (как в БД)
        self.current_file_index: int = 0
        self.files_list: List[Dict] = []
        self.global_position: float = 0.0
        self.total_duration: float = 0.0
        self.use_id3_tags: bool = True # Добавлено
        
        # Сохранённые значения для восстановления
        self.saved_file_index: Optional[int] = None
        self.saved_position: Optional[float] = None
    
    def load_audiobook(self, audiobook_path: str) -> bool:
        """Загрузка аудиокниги"""
        self.player.pause()
        
        # Сохраняем прогресс предыдущей книги
        self.save_current_progress()
        
        # Получаем информацию об аудиокниге
        audiobook_info = self.db.get_audiobook_info(audiobook_path)
        if not audiobook_info:
            return False
        
        audiobook_id, abook_name, author, title, saved_file_index, \
        saved_position, total_dur, saved_speed, use_id3_tags = audiobook_info
        
        # Обновляем состояние
        self.current_audiobook_id = audiobook_id
        self.current_audiobook_path = audiobook_path
        self.total_duration = total_dur or 0
        self.saved_file_index = saved_file_index
        self.saved_position = saved_position
        self.use_id3_tags = bool(use_id3_tags)
        
        # Загружаем файлы
        files = self.db.get_audiobook_files(audiobook_id)
        self.files_list = []
        
        for file_path, file_name, duration, track_num, tag_title in files:
            self.files_list.append({
                'path': file_path,
                'name': file_name,
                'tag_title': tag_title or '',
                'duration': duration or 0
            })
        
        # Устанавливаем скорость
        self.player.set_speed(int(saved_speed * 10))
        
        # Загружаем первый (или сохранённый) файл
        if self.files_list:
            self.current_file_index = max(0, min(saved_file_index or 0, len(self.files_list) - 1))
            self.calculate_global_position()
            
            # Разрешаем путь относительно корня библиотеки
            rel_file_path = self.files_list[self.current_file_index]['path']
            if self.library_root:
                abs_file_path = str(self.library_root / rel_file_path)
            else:
                abs_file_path = rel_file_path
                
            if self.player.load(abs_file_path):
                if saved_position and saved_position > 0:
                    self.player.set_position(saved_position)
                return True
        
        return False
    
    def play_file_at_index(self, index: int, start_playing: bool = True) -> bool:
        """Воспроизведение файла по индексу"""
        if not (0 <= index < len(self.files_list)):
            return False
        
        was_playing = self.player.is_playing()
        self.current_file_index = index
        self.calculate_global_position()
        
        file_info = self.files_list[index]
        # Разрешаем путь относительно корня библиотеки
        if self.library_root:
            abs_file_path = str(self.library_root / file_info['path'])
        else:
            abs_file_path = file_info['path']
            
        if self.player.load(abs_file_path):
            if start_playing or was_playing:
                self.player.play()
            return True
        return False
    
    def next_file(self, auto_next: bool = True) -> bool:
        """Переход к следующему файлу"""
        if self.current_file_index < len(self.files_list) - 1:
            self.play_file_at_index(
                self.current_file_index + 1, 
                self.player.is_playing() or auto_next
            )
            self.save_current_progress()
            return True
        else:
            # Последний файл - аудиокнига завершена
            self.player.stop()
            
            if self.current_audiobook_id and self.total_duration > 0:
                self.db.mark_audiobook_completed(
                    self.current_audiobook_id, 
                    self.total_duration
                )
            return False
    
    def prev_file(self) -> bool:
        """Переход к предыдущему файлу"""
        if self.player.get_position() > 3:
            # Если прошло больше 3 секунд - перематываем в начало текущего
            self.player.set_position(0)
            return True
        elif self.current_file_index > 0:
            # Иначе переходим к предыдущему
            self.play_file_at_index(
                self.current_file_index - 1, 
                self.player.is_playing()
            )
            self.save_current_progress()
            return True
        return False
    
    def calculate_global_position(self):
        """Расчёт глобальной позиции в аудиокниге"""
        self.global_position = sum(
            f['duration'] for f in self.files_list[:self.current_file_index]
        )
    
    def get_current_position(self) -> float:
        """Получение текущей позиции в аудиокниге"""
        return self.global_position + self.player.get_position()
    
    def get_progress_percent(self) -> int:
        """Получение процента прогресса"""
        if self.total_duration <= 0:
            return 0
            
        current = self.get_current_position()
        
        if current >= self.total_duration - 1:
            return 100
        
        return int((current / self.total_duration) * 100)
    
    def save_current_progress(self):
        """Сохранение текущего прогресса"""
        if not self.current_audiobook_id:
            return
        
        position = self.player.get_position()
        speed = self.player.speed_pos / 10.0
        listened_duration = self.get_current_position()
        progress_percent = self.get_progress_percent()
        
        self.db.save_progress(
            self.current_audiobook_id,
            self.current_file_index,
            position,
            speed,
            listened_duration,
            progress_percent
        )
    
    def get_audiobook_title(self) -> str:
        """Получение названия текущей аудиокниги"""
        if not self.current_audiobook_path:
            return "Audiobook Player"
            
        info = self.db.get_audiobook_info(self.current_audiobook_path)
        if info:
            # info теперь содержит 9 полей (добавлено use_id3_tags)
            _, name, author, title, _, _, _, _, _ = info
            return name
        return "Audiobook Player"
class PlayerWidget(QWidget):
    """Виджет плеера с элементами управления"""
    
    # Сигналы
    play_clicked = pyqtSignal()
    next_clicked = pyqtSignal()
    prev_clicked = pyqtSignal()
    rewind_clicked = pyqtSignal(int)
    position_changed = pyqtSignal(float)
    volume_changed = pyqtSignal(int)
    speed_changed = pyqtSignal(int)
    file_selected = pyqtSignal(int)
    id3_toggled_signal = pyqtSignal(bool)
    
    def __init__(self):
        super().__init__()
        self.show_id3 = False
        self.slider_dragging = False
        
        # Иконки
        self.play_icon = None
        self.pause_icon = None
        
        self.setup_ui()
        self.load_icons()
    
    def setup_ui(self):
        """Создание интерфейса плеера"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 0, 0, 0)
        layout.setSpacing(15)
        
        # Frame для плеера
        player_frame = QFrame()
        player_layout = QVBoxLayout(player_frame)
        
        # === Громкость и скорость ===
        settings_layout = QHBoxLayout()
        settings_layout.setSpacing(10)
        
        # Громкость
        vol_box = QHBoxLayout()
        vol_box.setSpacing(5)
        
        # ID3 Toggle
        self.id3_btn = QPushButton("ID3")
        self.id3_btn.setCheckable(True)
        self.id3_btn.setFixedWidth(40)
        self.id3_btn.setObjectName("id3Btn")
        self.id3_btn.setToolTip(tr("player.show_id3"))
        self.id3_btn.toggled.connect(self.on_id3_toggled)
        vol_box.addWidget(self.id3_btn)
        
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setObjectName("volumeSlider")
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.volume_slider.setMinimumWidth(80)
        self.volume_slider.setToolTip(tr("player.volume"))
        self.volume_slider.valueChanged.connect(self.on_volume_changed)
        vol_box.addWidget(self.volume_slider)
        
        self.volume_label = QLabel(trf("formats.percent", value=100))
        self.volume_label.setMinimumWidth(45)
        vol_box.addWidget(self.volume_label)
        
        settings_layout.addLayout(vol_box)
        
        settings_layout.addStretch()
        
        # Скорость
        speed_widget = QWidget()
        speed_layout = QHBoxLayout(speed_widget)
        speed_layout.setContentsMargins(0, 0, 0, 0)
        speed_layout.setSpacing(5)
        
        self.speed_label = QLabel(trf("formats.speed", value=1.0))
        self.speed_label.setFixedWidth(35)
        speed_layout.addWidget(self.speed_label)
        
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(5, 30)
        self.speed_slider.setValue(10)
        self.speed_slider.setMinimumWidth(80)
        self.speed_slider.setToolTip(tr("player.speed"))
        self.speed_slider.valueChanged.connect(self.on_speed_changed)
        speed_layout.addWidget(self.speed_slider)
        
        speed_widget.setMinimumWidth(120)
        settings_layout.addWidget(speed_widget)
        
        player_layout.addLayout(settings_layout)
        
        # === Кнопки управления ===
        controls = QHBoxLayout()
        controls.setSpacing(5)

        
        icon_size = QSize(24, 24)
        
        # Кнопки управления
        self.btn_prev = self.create_button("navBtn", tr("player.prev_track"), icon_size)
        self.btn_prev.clicked.connect(self.prev_clicked)
        controls.addWidget(self.btn_prev)
        
        self.btn_rw60 = self.create_button("rewindBtn", tr("player.rewind_60"), icon_size)
        self.btn_rw60.clicked.connect(lambda: self.rewind_clicked.emit(-60))
        controls.addWidget(self.btn_rw60)
        
        self.btn_rw10 = self.create_button("rewindBtn", tr("player.rewind_10"), icon_size)
        self.btn_rw10.clicked.connect(lambda: self.rewind_clicked.emit(-10))
        controls.addWidget(self.btn_rw10)
        
        # Play/Pause - главная кнопка
        self.play_btn = self.create_button("playBtn", tr("player.play"), QSize(32, 32))
        self.play_btn.clicked.connect(self.play_clicked)
        self.play_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )
        controls.addWidget(self.play_btn)
        
        self.btn_ff10 = self.create_button("rewindBtn", tr("player.forward_10"), icon_size)
        self.btn_ff10.clicked.connect(lambda: self.rewind_clicked.emit(10))
        controls.addWidget(self.btn_ff10)
        
        self.btn_ff60 = self.create_button("rewindBtn", tr("player.forward_60"), icon_size)
        self.btn_ff60.clicked.connect(lambda: self.rewind_clicked.emit(60))
        controls.addWidget(self.btn_ff60)
        
        self.btn_next = self.create_button("navBtn", tr("player.next_track"), icon_size)
        self.btn_next.clicked.connect(self.next_clicked)
        controls.addWidget(self.btn_next)
        

        player_layout.addLayout(controls)
        
        # === Позиция в файле ===
        file_box = QVBoxLayout()
        
        file_times = QHBoxLayout()
        self.time_current = QLabel("0:00")
        self.time_current.setObjectName("timeLabel")
        self.time_duration = QLabel("0:00")
        self.time_duration.setObjectName("timeLabel")
        file_times.addWidget(self.time_current)
        file_times.addStretch()
        file_times.addWidget(self.time_duration)
        file_box.addLayout(file_times)
        
        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setRange(0, 1000)
        self.position_slider.sliderPressed.connect(self.on_position_pressed)
        self.position_slider.sliderReleased.connect(self.on_position_released)
        self.position_slider.sliderMoved.connect(self.on_position_moved)
        file_box.addWidget(self.position_slider)
        
        player_layout.addLayout(file_box)
        
        # === Общий прогресс ===
        total_box = QVBoxLayout()
        total_box.setSpacing(8)
        
        total_times = QHBoxLayout()
        self.total_percent_label = QLabel(trf("formats.percent", value=0))
        self.total_percent_label.setObjectName("timeLabel")
        self.total_time_label = QLabel("0:00:00")
        self.total_time_label.setObjectName("timeLabel")
        self.total_duration_label = QLabel("0:00:00")
        self.total_duration_label.setObjectName("timeLabel")
        self.time_left_label = QLabel(tr("player.time_left_unknown"))
        self.time_left_label.setObjectName("timeLabel")
        
        total_times.addWidget(self.total_time_label)
        total_times.addWidget(QLabel(tr("player.of"), objectName="timeLabel"))
        total_times.addWidget(self.total_duration_label)
        total_times.addStretch()
        total_times.addWidget(self.total_percent_label)
        total_times.addStretch()
        total_times.addWidget(self.time_left_label)
        total_box.addLayout(total_times)
        
        self.total_progress_bar = QProgressBar()
        self.total_progress_bar.setTextVisible(False)
        total_box.addWidget(self.total_progress_bar)
        
        player_layout.addLayout(total_box)
        layout.addWidget(player_frame)
        
        # === Список файлов ===
        self.file_list = QListWidget()
        self.file_list.setObjectName("fileList")
        self.file_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.file_list.itemDoubleClicked.connect(self.on_file_double_clicked)
        layout.addWidget(self.file_list)
    
    def create_button(self, object_name: str, tooltip: str, icon_size: QSize) -> QPushButton:
        """Создание кнопки"""
        btn = QPushButton()
        btn.setObjectName(object_name)
        btn.setToolTip(tooltip)
        btn.setIconSize(icon_size)
        return btn
    
    def load_icons(self):
        """Загрузка иконок"""
        # Загрузка иконок
        self.play_icon = get_icon("play")
        self.pause_icon = get_icon("pause")
        
        # Установка иконок на кнопки
        self.play_btn.setIcon(self.play_icon)
        self.btn_prev.setIcon(get_icon("prev"))
        self.btn_next.setIcon(get_icon("next"))
        self.btn_rw10.setIcon(get_icon("rewind_10"))
        self.btn_rw60.setIcon(get_icon("rewind_60"))
        self.btn_ff10.setIcon(get_icon("forward_10"))
        self.btn_ff60.setIcon(get_icon("forward_60"))
    
    def on_volume_changed(self, value: int):
        """Изменение громкости"""
        self.volume_label.setText(trf("formats.percent", value=value))
        self.volume_changed.emit(value)
    
    def on_speed_changed(self, value: int):
        """Изменение скорости"""
        self.speed_label.setText(trf("formats.speed", value=value/10))
        self.speed_changed.emit(value)
    
    def on_position_pressed(self):
        """Начало перетаскивания позиции"""
        self.slider_dragging = True
    
    def on_position_released(self):
        """Окончание перетаскивания позиции"""
        self.slider_dragging = False
        self.position_changed.emit(self.position_slider.value() / 1000.0)
    
    def on_position_moved(self, value: int):
        """Перетаскивание позиции"""
        # Можно обновить отображение времени
        pass
    
    def on_file_double_clicked(self, item):
        """Двойной клик по файлу"""
        index = self.file_list.row(item)
        self.file_selected.emit(index)
    
    def set_playing(self, is_playing: bool):
        """Установка состояния воспроизведения"""
        self.play_btn.setIcon(self.pause_icon if is_playing else self.play_icon)
        self.play_btn.setToolTip(tr("player.pause") if is_playing else tr("player.play"))
    
    def update_file_progress(self, position: float, duration: float):
        """Обновление прогресса файла"""
        if not self.slider_dragging:
            if duration >= 3600:
                self.time_current.setText(format_time(position))
            else:
                self.time_current.setText(format_time_short(position))
                
            if duration > 0:
                self.position_slider.setValue(int((position / duration) * 1000))
        
        if duration >= 3600:
            self.time_duration.setText(format_time(duration))
        else:
            self.time_duration.setText(format_time_short(duration))
    
    def update_total_progress(self, current: float, total: float, speed: float = 1.0):
        """Обновление общего прогресса"""
        self.total_time_label.setText(format_time(current))
        self.total_duration_label.setText(format_time(total))
        
        if total > 0:
            percent = int((current / total) * 100)
            self.total_progress_bar.setValue(percent)
            self.total_percent_label.setText(trf("formats.percent", value=percent))
            
            time_left = (total - current) / speed
            self.time_left_label.setText(trf("player.time_left", time=format_time(time_left)))
        else:
            self.time_left_label.setText(tr("player.time_left_unknown"))
    
    def on_id3_toggled(self, checked):
        """Переключение отображения ID3 тегов"""
        self.show_id3 = checked
        
        # Перезагружаем список файлов если он есть
        if hasattr(self, 'last_files_list') and self.last_files_list:
            current_row = self.file_list.currentRow()
            self.load_files(self.last_files_list, current_row)
            
        # Испускаем сигнал для сохранения
        self.id3_toggled_signal.emit(checked)
    
    def load_files(self, files_list: list, current_index: int = 0):
        """Загрузка списка файлов"""
        self.last_files_list = files_list
        self.file_list.clear()
        
        for i, file_info in enumerate(files_list):
            duration = file_info.get('duration', 0)
            if duration >= 3600:
                dur_str = format_time(duration)
            else:
                dur_str = format_time_short(duration)
            display_name = file_info['name']
            
            if self.show_id3 and file_info.get('tag_title'):
                display_name = file_info['tag_title']
            
            list_item = QListWidgetItem(
                trf("formats.file_number", 
                    number=i+1, 
                    name=display_name, 
                    duration=dur_str)
            )
            list_item.setData(Qt.ItemDataRole.UserRole, file_info['path'])
            self.file_list.addItem(list_item)
        
        if 0 <= current_index < len(files_list):
            self.file_list.setCurrentRow(current_index)
            self.highlight_current_file(current_index)
    
    def highlight_current_file(self, index: int):
        """Выделение текущего файла"""
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            
            # Восстанавливаем оригинальный текст
            original_text = item.data(Qt.ItemDataRole.UserRole + 1)
            if not original_text and i == index:
                original_text = item.text()
                item.setData(Qt.ItemDataRole.UserRole + 1, original_text)
            
            if i == index:
                # Текущий файл
                item.setText(trf("formats.playing_indicator", text=original_text))
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            else:
                # Остальные файлы
                if original_text:
                    item.setText(original_text)
                    item.setData(Qt.ItemDataRole.UserRole + 1, None)
                
                font = item.font()
                font.setBold(False)
                item.setFont(font)
    
    def set_speed(self, value: int):
        """Установка скорости"""
        self.speed_slider.setValue(value)
        self.speed_label.setText(trf("formats.speed", value=value/10))
    
    def set_volume(self, value: int):
        """Установка громкости"""
        self.volume_slider.setValue(value)
        self.volume_label.setText(trf("formats.percent", value=value))
    
    def update_texts(self):
        """Обновление текстов после смены языка"""
        # Обновляем метки
        speed_value = self.speed_slider.value() / 10
        self.speed_label.setText(trf("formats.speed", value=speed_value))
        self.volume_label.setText(trf("formats.percent", value=self.volume_slider.value()))
        
        # Обновляем tooltips кнопок
        self.btn_prev.setToolTip(tr("player.prev_track"))
        self.btn_next.setToolTip(tr("player.next_track"))
        self.btn_rw60.setToolTip(tr("player.rewind_60"))
        self.btn_rw10.setToolTip(tr("player.rewind_10"))
        self.btn_ff10.setToolTip(tr("player.forward_10"))
        self.btn_ff60.setToolTip(tr("player.forward_60"))
        self.play_btn.setToolTip(tr("player.play"))
        self.id3_btn.setToolTip(tr("player.show_id3"))


class LibraryTree(QTreeWidget):
    """Кастомное дерево для обработки наведения и кликов по кнопке Play"""
    play_button_clicked = pyqtSignal(str) # Передает путь к аудиокниге

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)

    def leaveEvent(self, event):
        delegate = self.itemDelegate()
        if delegate and hasattr(delegate, 'hovered_index'):
            delegate.hovered_index = None
            delegate.mouse_pos = None
            self.viewport().update()
        super().leaveEvent(event)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        index = self.indexAt(event.pos())
        
        delegate = self.itemDelegate()
        if delegate and hasattr(delegate, 'get_play_button_rect'):
             delegate.hovered_index = index if index.isValid() else None
             delegate.mouse_pos = event.pos()
             self.viewport().update()
             
             if index.isValid():
                 item_type = index.data(Qt.ItemDataRole.UserRole + 1)
                 if item_type == 'audiobook':
                     rect = self.visualRect(index)
                     icon_size = delegate.audiobook_icon_size
                     icon_rect = QRect(
                         rect.left() + delegate.horizontal_padding,
                         rect.top() + delegate.vertical_padding,
                         icon_size, icon_size
                     )
                     play_rect = delegate.get_play_button_rect(QRectF(icon_rect))
                     if play_rect.contains(QPointF(event.pos())):
                         self.setCursor(Qt.CursorShape.PointingHandCursor)
                         return
             
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            index = self.indexAt(event.pos())
            if index.isValid():
                item_type = index.data(Qt.ItemDataRole.UserRole + 1)
                if item_type == 'audiobook':
                    delegate = self.itemDelegate()
                    if delegate and hasattr(delegate, 'get_play_button_rect'):
                        rect = self.visualRect(index)
                        icon_size = delegate.audiobook_icon_size
                        icon_rect = QRect(
                            rect.left() + delegate.horizontal_padding,
                            rect.top() + delegate.vertical_padding,
                            icon_size, icon_size
                        )
                        play_rect = delegate.get_play_button_rect(QRectF(icon_rect))
                        if play_rect.contains(QPointF(event.pos())):
                            path = index.data(Qt.ItemDataRole.UserRole)
                            self.play_button_clicked.emit(path)
                            return
        super().mousePressEvent(event)


class LibraryWidget(QWidget):
    """Виджет библиотеки аудиокниг"""
    
    audiobook_selected = pyqtSignal(str)
    
    FILTER_CONFIG = {
        'all': {'label': "library.filter_all", 'icon': "filter_all"},
        'not_started': {'label': "library.filter_not_started", 'icon': "filter_not_started"},
        'in_progress': {'label': "library.filter_in_progress", 'icon': "filter_in_progress"},
        'completed': {'label': "library.filter_completed", 'icon': "filter_completed"},
    }
    
    def __init__(self, db_manager: DatabaseManager, config: dict, delegate=None):
        super().__init__()
        self.db = db_manager
        self.config = config
        self.delegate = delegate
        self.default_audiobook_icon = None
        self.folder_icon = None
        self.current_playing_item = None
        self.highlight_color = QColor(1, 133, 116)
        self.highlight_text_color = QColor(255, 255, 255)
        self.current_filter = 'all'  # Текущий фильтр
        self.setup_ui()
        self.load_icons()
    
    def setup_ui(self):
        """Создание интерфейса"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 10, 0)
        layout.setSpacing(10)
        
        # Поле поиска
        search_layout = QHBoxLayout()
        search_layout.setSpacing(5)
        
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(tr("library.search_placeholder"))
        self.search_edit.textChanged.connect(self.filter_audiobooks)
        self.search_edit.setClearButtonEnabled(True)
        search_layout.addWidget(self.search_edit)
        
        layout.addLayout(search_layout)

        # Кнопки фильтров
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(2)
        
        self.filter_group = QButtonGroup(self)
        self.filter_group.setExclusive(True)
        
        self.filter_buttons = {}
        for filter_id, config in self.FILTER_CONFIG.items():
            btn = QPushButton(tr(config['label']))
            btn.setObjectName("filterBtn")
            btn.setCheckable(True)
            btn.setProperty('filter_type', filter_id)
            
            # Установка иконки
            if 'icon' in config:
                btn.setIcon(get_icon(config['icon']))
                
            btn.clicked.connect(lambda checked, f=filter_id: self.apply_filter(f))
            self.filter_group.addButton(btn)
            self.filter_buttons[filter_id] = btn
            filter_layout.addWidget(btn)
            
            if filter_id == self.current_filter:
                btn.setChecked(True)
        
        layout.addLayout(filter_layout)
        
        # Дерево аудиокниг
        self.tree = LibraryTree()
        self.tree.setHeaderHidden(True)
        self.tree.setIconSize(QSize(
            self.config.get('audiobook_icon_size', 100),
            self.config.get('audiobook_icon_size', 100)
        ))
        self.tree.setIndentation(20)
        self.tree.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.tree.itemExpanded.connect(self.on_item_expanded)
        self.tree.itemCollapsed.connect(self.on_item_collapsed)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_context_menu)
        
        if self.delegate:
            self.tree.setItemDelegate(self.delegate)
        
        layout.addWidget(self.tree)
    
    def load_icons(self):
        """Загрузка иконок"""
        script_dir = Path(__file__).parent
        
        # Иконка по умолчанию для аудиокниги
        default_cover = self.config.get('default_cover_file', 'resources/icons/default_cover.png')
        self.default_audiobook_icon = load_icon(
            get_base_path() / default_cover,
            self.config.get('audiobook_icon_size', 100)
        )
        
        if not self.default_audiobook_icon:
            self.default_audiobook_icon = self.style().standardIcon(
                QStyle.StandardPixmap.SP_FileIcon
            )
        
        # Иконка папки
        folder_cover = self.config.get('folder_cover_file', 'resources/icons/folder_cover.png')
        self.folder_icon = load_icon(
            get_base_path() / folder_cover,
            self.config.get('folder_icon_size', 35)
        )
        
        if not self.folder_icon:
            self.folder_icon = resize_icon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon),
                self.config.get('folder_icon_size', 35)
            )
    
    def apply_filter(self, filter_type: str):
        """Применение фильтра к библиотеке"""
        self.current_filter = filter_type
        self.search_edit.clear()  # Сброс поиска при смене фильтра
        self.current_playing_item = None
        self.load_audiobooks()
    
    def load_audiobooks(self):
        """Загрузка аудиокниг из БД с применением текущего фильтра"""
        self.current_playing_item = None
        self.tree.clear()
        data_by_parent = self.db.load_audiobooks_from_db(self.current_filter)
        self.add_items_from_db(self.tree, '', data_by_parent)
    
    def add_items_from_db(self, parent_item, parent_path: str, data_by_parent: dict):
        """Рекурсивное добавление элементов в дерево"""
        if parent_path not in data_by_parent:
            return
        
        for data in data_by_parent[parent_path]:
            item = QTreeWidgetItem(parent_item)
            item.setData(0, Qt.ItemDataRole.UserRole, data['path'])
            
            if data['is_folder']:
                item.setText(0, data['name'])
                item.setData(0, Qt.ItemDataRole.UserRole + 1, 'folder')
                item.setIcon(0, self.folder_icon)
                # Восстанавливаем состояние развернутости
                if data.get('is_expanded'):
                    item.setExpanded(True)
            else:
                # Для аудиокниг делегат сам отрисует всю информацию
                # Устанавливаем пустой текст, чтобы делегат полностью контролировал отрисовку
                item.setText(0, "")
                item.setData(0, Qt.ItemDataRole.UserRole + 1, 'audiobook')
                item.setData(0, Qt.ItemDataRole.UserRole + 2, (
                    data['author'],
                    data['title'],
                    data['narrator'],
                    data['file_count'],
                    data['duration'],
                    data['listened_duration'],
                    data['progress_percent']
                ))
                
                # Загрузка обложки
                cover_icon = None
                if data['cover_path']:
                    cover_p = Path(data['cover_path'])
                    # Если путь относительный, разрешаем его от корня библиотеки
                    if not cover_p.is_absolute() and self.config.get('default_path'):
                        cover_p = Path(self.config.get('default_path')) / cover_p
                        
                    cover_icon = load_icon(
                        cover_p,
                        self.config.get('audiobook_icon_size', 100)
                    )
                item.setIcon(0, cover_icon or self.default_audiobook_icon)
            
            # Рекурсивно добавляем детей
            self.add_items_from_db(item, data['path'], data_by_parent)
    
    def filter_audiobooks(self):
        """Фильтрация аудиокниг по поисковому запросу"""
        search_text = self.search_edit.text().lower().strip()
        
        if not search_text:
            self.show_all_items(self.tree.invisibleRootItem())
            return
        
        self.filter_tree_items(self.tree.invisibleRootItem(), search_text)
    
    def show_all_items(self, parent_item):
        """Показать все элементы дерева"""
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            child.setHidden(False)
            self.show_all_items(child)
    
    def filter_tree_items(self, parent_item, search_text: str) -> bool:
        """Рекурсивная фильтрация элементов"""
        has_visible = False
        
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            item_type = child.data(0, Qt.ItemDataRole.UserRole + 1)
            
            if item_type == 'folder':
                has_children = self.filter_tree_items(child, search_text)
                folder_name = child.text(0).lower()
                matches = search_text in folder_name
                child.setHidden(not (matches or has_children))
                if not child.isHidden():
                    has_visible = True
                    
            elif item_type == 'audiobook':
                data = child.data(0, Qt.ItemDataRole.UserRole + 2)
                matches = False
                if data:
                    author, title, narrator, _, _, _, _ = data
                    if author and search_text in author.lower():
                        matches = True
                    if title and search_text in title.lower():
                        matches = True
                    if narrator and search_text in narrator.lower():
                        matches = True
                
                child.setHidden(not matches)
                if not child.isHidden():
                    has_visible = True
        
        return has_visible
    

    
    def on_item_expanded(self, item):
        """Обработка разворачивания папки"""
        if item.data(0, Qt.ItemDataRole.UserRole + 1) == 'folder':
            path = item.data(0, Qt.ItemDataRole.UserRole)
            if path:
                self.db.update_folder_expanded_state(path, True)
    
    def on_item_collapsed(self, item):
        """Обработка сворачивания папки"""
        if item.data(0, Qt.ItemDataRole.UserRole + 1) == 'folder':
            path = item.data(0, Qt.ItemDataRole.UserRole)
            if path:
                self.db.update_folder_expanded_state(path, False)

    def show_context_menu(self, pos):
        """Контекстное меню"""
        item = self.tree.itemAt(pos)
        if not item or item.data(0, Qt.ItemDataRole.UserRole + 1) != 'audiobook':
            return
        
        path = item.data(0, Qt.ItemDataRole.UserRole)
        # Получаем ID книги
        info = self.db.get_audiobook_info(path)
        if not info:
            return
        audiobook_id = info[0]
        duration = item.data(0, Qt.ItemDataRole.UserRole + 2)[4] # Индекс 4 это duration

        menu = QMenu()
        play_action = QAction(tr("library.context_play"), self)
        play_action.setIcon(get_icon("context_play"))
        play_action.triggered.connect(lambda _: self.on_item_double_clicked(item, 0))
        menu.addAction(play_action)
        
        menu.addSeparator()

        # Отметить прочитанной
        mark_read_action = QAction(tr("library.menu_mark_read"), self)
        mark_read_action.setIcon(get_icon("context_mark_read"))
        mark_read_action.triggered.connect(lambda _: self.mark_as_read(audiobook_id, duration, path))
        menu.addAction(mark_read_action)

        # Отметить не начатой (сброс)
        mark_unread_action = QAction(tr("library.menu_mark_unread"), self)
        mark_unread_action.setIcon(get_icon("context_mark_unread"))
        mark_unread_action.triggered.connect(lambda _: self.mark_as_unread(audiobook_id, path))
        menu.addAction(mark_unread_action)
        
        menu.addSeparator()
        
        open_folder_action = QAction(tr("library.menu_open_folder"), self)
        open_folder_action.setIcon(get_icon("context_open_folder"))
        open_folder_action.triggered.connect(lambda _: self.open_folder(path))
        menu.addAction(open_folder_action)
        
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def mark_as_read(self, audiobook_id, duration, path):
        """Отметить книгу как прочитанную"""
        self.db.mark_audiobook_completed(audiobook_id, duration)
        self.load_audiobooks()
        # Если эта книга сейчас играет или загружена - обновим UI
        window = self.window()
        if hasattr(window, 'playback_controller') and window.playback_controller.current_audiobook_id == audiobook_id:
            window.update_ui_for_audiobook()

    def mark_as_unread(self, audiobook_id, path):
        """Отметить книгу как не начатую"""
        self.db.reset_audiobook_status(audiobook_id)
        self.load_audiobooks()
        window = self.window()
        if hasattr(window, 'playback_controller') and window.playback_controller.current_audiobook_id == audiobook_id:
            # Сбрасываем и в контроллере
            window.playback_controller.saved_file_index = 0
            window.playback_controller.saved_position = 0
            window.update_ui_for_audiobook()
    
    def open_folder(self, path: str):
        """Открыть папку в проводнике"""
        if not path:
            return
            
        try:
            # Разрешаем путь относительно корня библиотеки
            default_path = self.config.get('default_path', '')
            
            if default_path:
                abs_path = Path(default_path) / path
            else:
                abs_path = Path(path)
                
            # Если это файл, берем родительскую папку. 
            # Если это уже папка, открываем её саму.
            if abs_path.exists() and abs_path.is_file():
                folder_path = abs_path.parent
            else:
                folder_path = abs_path
                
            if folder_path.exists():
                folder_path_str = str(folder_path.absolute())
                
                if sys.platform == 'win32':
                    import ctypes
                    # ShellExecuteW: (hwnd, operation, file, parameters, directory, show)
                    # 1 = SW_SHOWNORMAL
                    ctypes.windll.shell32.ShellExecuteW(None, "open", folder_path_str, None, None, 1)
                elif sys.platform == 'darwin':
                    subprocess.run(['open', folder_path_str], check=False)
                else:
                    subprocess.run(['xdg-open', folder_path_str], check=False)
            else:
                QMessageBox.warning(self, tr("window.title"), f"Path not found: {folder_path}")
        except Exception as e:
            QMessageBox.critical(self, tr("window.title"), f"Error opening folder: {e}")
    
    def on_item_double_clicked(self, item, column):
        """Обработка двойного клика"""
        if item.data(0, Qt.ItemDataRole.UserRole + 1) == 'audiobook':
            path = item.data(0, Qt.ItemDataRole.UserRole)
            self.audiobook_selected.emit(path)
    
    def highlight_audiobook(self, audiobook_path: str):
        """Выделение текущей аудиокниги"""
        # Сброс предыдущего выделения
        if self.current_playing_item:
            try:
                # Проверяем, существует ли элемент
                self.current_playing_item.text(0)
                self.reset_item_colors(self.current_playing_item)
            except RuntimeError:
                # Элемент был удалён при перезагрузке дерева
                self.current_playing_item = None
        
        # Поиск элемента
        item = self.find_item_by_path(self.tree.invisibleRootItem(), audiobook_path)
        if item:
            self.current_playing_item = item
            
            # Выделяем цветом
            item.setBackground(0, QBrush(self.highlight_color))
            item.setForeground(0, QBrush(self.highlight_text_color))
            
            # Делаем жирным
            font = item.font(0)
            font.setBold(True)
            item.setFont(0, font)
            
            # Прокручиваем к элементу
            self.tree.scrollToItem(item)

    
    def find_item_by_path(self, parent_item, path: str):
        """Поиск элемента по пути"""
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            if child.data(0, Qt.ItemDataRole.UserRole) == path:
                return child
            result = self.find_item_by_path(child, path)
            if result:
                return result
        return None
    
    def reset_item_colors(self, item):
        """Сброс цветов элемента"""
        try:
            item.setBackground(0, QBrush(Qt.GlobalColor.transparent))
            font = item.font(0)
            font.setBold(False)
            item.setFont(0, font)
        except RuntimeError:
            # Элемент уже удалён
            pass

    
    def refresh_audiobook_item(self, audiobook_path: str):
        """Обновление данных элемента после изменения прогресса (из БД)"""
        item = self.find_item_by_path(self.tree.invisibleRootItem(), audiobook_path)
        if not item:
            return
        
        # Загружаем свежие данные
        data = self.db.get_audiobook_by_path(audiobook_path)
        if data:
            item.setData(0, Qt.ItemDataRole.UserRole + 2, (
                data['author'],
                data['title'],
                data['narrator'],
                data['file_count'],
                data['duration'],
                data['listened_duration'],
                data['progress_percent']
            ))
            # Триггерим перерисовку
            item.setText(0, item.text(0))

    def update_item_progress(self, audiobook_path: str, listened_duration: float, progress_percent: int):
        """Живое обновление прогресса без обращения к БД"""
        item = self.find_item_by_path(self.tree.invisibleRootItem(), audiobook_path)
        if not item:
            return
            
        data = item.data(0, Qt.ItemDataRole.UserRole + 2)
        if data and len(data) >= 7:
            # Создаем новый кортеж с обновленным прогрессом
            new_data = list(data)
            new_data[5] = listened_duration
            new_data[6] = progress_percent
            
            item.setData(0, Qt.ItemDataRole.UserRole + 2, tuple(new_data))
            # Триггерим перерисовку только вьюпорта, чтобы не дергать дерево целиком
            self.tree.viewport().update()
    
    def update_texts(self):
        """Обновление текстов после смены языка"""
        # Обновляем кнопки фильтров
        # Обновляем кнопки фильтров
        for filter_id, config in self.FILTER_CONFIG.items():
            if filter_id in self.filter_buttons:
                self.filter_buttons[filter_id].setText(tr(config['label']))
        
        # Обновляем placeholder поиска
        self.search_edit.setPlaceholderText(tr("library.search_placeholder"))


class AudiobookPlayerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Пути и файлы
        self.script_dir = get_base_path()
        self.config_dir = self.script_dir / 'resources'
        self.data_dir = self.script_dir / 'data'
        
        self.config_file = self.config_dir / 'settings.ini'
        self.db_file = self.data_dir / 'audiobooks.db'
        self.icons_dir = self.config_dir / "icons"
        
        # Создаем папки если их нет
        self.config_dir.mkdir(exist_ok=True)
        self.data_dir.mkdir(exist_ok=True)
        
        # Загрузка настроек и языка
        self.load_settings()
        self.load_language_preference()
        
        # Установка заголовка и иконки
        self.setWindowTitle(tr("window.title"))
        self.setWindowIcon(get_icon("app_icon", self.icons_dir))
        
        # Инициализация компонентов
        self.db_manager = DatabaseManager(self.db_file)
        self.player = BassPlayer()
        self.playback_controller = PlaybackController(self.player, self.db_manager)
        if self.default_path:
            self.playback_controller.library_root = Path(self.default_path)
            
        self.taskbar_progress = TaskbarProgress()
        
        # Делегат для дерева
        self.delegate = None
        try:
            self.delegate = MultiLineDelegate(self)
            self.delegate.audiobook_row_height = self.audiobook_row_height
            self.delegate.folder_row_height = self.folder_row_height
            self.delegate.audiobook_icon_size = self.audiobook_icon_size
        except Exception as e:
            print(f"Failed to create delegate: {e}")
        
        # Создание UI
        self.setup_ui()
        self.setup_menu()
        self.connect_signals()
        
        # Инициализация
        self.library_widget.load_audiobooks()
        self.restore_last_session()
        
        # Таймер обновления
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_ui)
        self.timer.start(100)
        
        # Установка геометрии окна
        self.setGeometry(self.window_x, self.window_y, self.window_width, self.window_height)
        self.setMinimumSize(450, 450)
        self.statusBar().showMessage(tr("status.load_library"))
    
    def load_language_preference(self):
        """Загрузка сохранённого языка"""
        config = configparser.ConfigParser()
        config.read(self.config_file, encoding='utf-8')
        
        lang_code = config.get('Display', 'language', fallback='ru')
        try:
            language = Language(lang_code)
            set_language(language)
        except ValueError:
            set_language(Language.RUSSIAN)
    
    def save_language_preference(self):
        """Сохранение выбранного языка"""
        config = configparser.ConfigParser()
        config.read(self.config_file, encoding='utf-8')
        
        if 'Display' not in config:
            config['Display'] = {}
        
        config['Display']['language'] = get_language().value
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            config.write(f)
    
    def setup_ui(self):
        """Создание интерфейса"""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # Разделитель
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(True)
        
        # Библиотека
        self.library_widget = LibraryWidget(
            self.db_manager,
            {
                'audiobook_icon_size': self.audiobook_icon_size,
                'folder_icon_size': self.folder_icon_size,
                'default_cover_file': self.default_cover_file,
                'folder_cover_file': self.folder_cover_file,
                'default_path': self.default_path,
                'ffprobe_path': self.ffprobe_path
            },
            self.delegate
        )
        self.library_widget.setMinimumWidth(200)
        self.splitter.addWidget(self.library_widget)
        
        # Плеер
        self.player_widget = PlayerWidget()
        self.player_widget.setMinimumWidth(400)
        self.player_widget.id3_btn.setChecked(self.show_id3)
        self.player_widget.on_id3_toggled(self.show_id3)
        self.player_widget.id3_toggled_signal.connect(self.on_id3_state_toggled)
        self.splitter.addWidget(self.player_widget)
        
        #self.splitter.setSizes([700, 300])
        main_layout.addWidget(self.splitter, 1)
    
    def setup_menu(self):
        """Создание меню"""
        menubar = self.menuBar()
        
        # --- Меню "Библиотека" ---
        library_menu = menubar.addMenu(tr("menu.library"))
        
        # Настройки
        settings_action = QAction(tr("menu.settings"), self)
        settings_action.setIcon(get_icon("menu_settings"))
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self.show_settings)
        library_menu.addAction(settings_action)

        library_menu.addSeparator()
        
        # Сканирование
        scan_action = QAction(tr("menu.scan"), self)
        scan_action.setIcon(get_icon("menu_scan"))
        scan_action.setShortcut("Ctrl+R")
        scan_action.triggered.connect(self.rescan_directory)
        library_menu.addAction(scan_action)
        
        # --- Меню "Вид" ---
        view_menu = menubar.addMenu(tr("menu.view"))
        
        # Меню языка (подменю)
        language_menu = view_menu.addMenu(tr("menu.language"))
        
        # Русский
        russian_action = QAction(tr("menu.russian"), self)
        russian_action.setCheckable(True)
        russian_action.setChecked(get_language() == Language.RUSSIAN)
        russian_action.triggered.connect(lambda _: self.change_language(Language.RUSSIAN))
        language_menu.addAction(russian_action)
        
        # Английский
        english_action = QAction(tr("menu.english"), self)
        english_action.setCheckable(True)
        english_action.setChecked(get_language() == Language.ENGLISH)
        english_action.triggered.connect(lambda _: self.change_language(Language.ENGLISH))
        language_menu.addAction(english_action)
        
        self.language_actions = {
            Language.RUSSIAN: russian_action,
            Language.ENGLISH: english_action
        }
        
        view_menu.addSeparator()
        
        # Перезагрузка стилей
        reload_styles_action = QAction(tr("menu.reload_styles"), self)
        reload_styles_action.setIcon(get_icon("menu_reload"))
        reload_styles_action.setShortcut("Ctrl+Q")
        reload_styles_action.triggered.connect(self.reload_styles)
        view_menu.addAction(reload_styles_action)
        
        # --- Меню "Справка" ---
        help_menu = menubar.addMenu(tr("menu.help"))
        
        # О программе
        about_action = QAction(tr("menu.about"), self)
        about_action.setIcon(get_icon("menu_about"))
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def change_language(self, language: Language):
        """Изменение языка интерфейса без перезапуска"""
        if get_language() == language:
            return
        
        set_language(language)
        self.save_language_preference()
        
        # Обновляем галочки в меню
        for lang, action in self.language_actions.items():
            action.setChecked(lang == language)
        
        # Обновляем все тексты в интерфейсе
        self.update_all_texts()
    
    
    def update_all_texts(self):
        """Обновление всех текстов в интерфейсе после смены языка"""
        # Обновляем заголовок окна
        if hasattr(self, 'playback_controller') and self.playback_controller.current_audiobook_path:
            book_title = self.playback_controller.get_audiobook_title()
            self.setWindowTitle(trf("window.title_with_book", title=book_title))
        else:
            self.setWindowTitle(tr("window.title"))
        
        # Пересоздаем меню
        self.menuBar().clear()
        self.setup_menu()
        
        # Обновляем тексты в виджете плеера
        if hasattr(self, 'player_widget'):
            self.player_widget.update_texts()
        
        # Обновляем тексты в библиотеке (кнопки фильтров и поиск)
        if hasattr(self, 'library_widget'):
            self.library_widget.update_texts()
        
        # Перезагружаем библиотеку для обновления делегата
        if hasattr(self, 'library_widget'):
            self.library_widget.load_audiobooks()
    
    def connect_signals(self):
        """Подключение сигналов"""
        # Сигналы библиотеки
        self.library_widget.audiobook_selected.connect(self.on_audiobook_selected)
        self.library_widget.tree.play_button_clicked.connect(self.on_library_play_clicked)

        
        # Сигналы плеера
        self.player_widget.play_clicked.connect(self.toggle_play)
        self.player_widget.next_clicked.connect(self.on_next_clicked)
        self.player_widget.prev_clicked.connect(self.on_prev_clicked)
        self.player_widget.rewind_clicked.connect(self.player.rewind)
        self.player_widget.position_changed.connect(self.on_position_changed)
        self.player_widget.volume_changed.connect(self.player.set_volume)
        self.player_widget.speed_changed.connect(self.on_speed_changed)
        self.player_widget.file_selected.connect(self.on_file_selected)
    
    def load_settings(self):
        """Загрузка настроек из файла"""
        if not self.config_file.exists():
            self.create_default_settings()
        
        config = configparser.ConfigParser()
        config.read(self.config_file, encoding='utf-8')
        
        # Чтение размеров и позиции окна
        self.window_x = config.getint('Display', 'window_x', fallback=100)
        self.window_y = config.getint('Display', 'window_y', fallback=100)
        self.window_width = config.getint('Display', 'window_width', fallback=1200)
        self.window_height = config.getint('Display', 'window_height', fallback=800)
        
        # Пути
        self.default_path = config.get('Paths', 'default_path', fallback="")
        ff_path_str = config.get('Paths', 'ffprobe_path', fallback=str(self.script_dir / 'resources' / 'bin' / 'ffprobe.exe'))
        self.ffprobe_path = Path(ff_path_str)
        if not self.ffprobe_path.is_absolute():
            self.ffprobe_path = self.script_dir / self.ffprobe_path
            
        covers_dir_str = config.get('Paths', 'covers_dir', fallback='data/extracted_covers')
        self.covers_dir = Path(covers_dir_str)
        if not self.covers_dir.is_absolute():
            self.covers_dir = self.script_dir / self.covers_dir
            
        self.default_cover_file = config.get('Paths', 'default_cover_file', fallback='resources/icons/default_cover.png')
        self.folder_cover_file = config.get('Paths', 'folder_cover_file', fallback='resources/icons/folder_cover.png')
        
        # Стили отображения
        self.audiobook_icon_size = config.getint('Audiobook_Style', 'icon_size', fallback=100)
        self.audiobook_row_height = config.getint('Audiobook_Style', 'row_height', fallback=120)
        self.folder_icon_size = config.getint('Folder_Style', 'icon_size', fallback=35)
        self.folder_row_height = config.getint('Folder_Style', 'row_height', fallback=45)
        
        # Размеры сплиттера
        self.splitter_state = config.get('Layout', 'splitter_state', fallback="")
        
        # Настройки плеера
        self.show_id3 = config.getboolean('Player', 'show_id3', fallback=False)
        
        # Обновляем корень библиотеки в контроллере если он уже создан
        if hasattr(self, 'playback_controller'):
            if self.default_path:
                self.playback_controller.library_root = Path(self.default_path)
            else:
                self.playback_controller.library_root = None

    def create_default_settings(self):
        """Создание файла настроек по умолчанию"""
        config = configparser.ConfigParser()
        config['Paths'] = {
            'default_path': '',
            'ffprobe_path': 'resources/bin/ffprobe.exe',
            'covers_dir': 'data/extracted_covers',
            'default_cover_file': 'resources/icons/default_cover.png',
            'folder_cover_file': 'resources/icons/folder_cover.png'
        }
        config['Display'] = {
            'window_width': '1200',
            'window_height': '800',
            'window_x': '100',
            'window_y': '100',
            'language': 'ru'
        }
        config['Audiobook_Style'] = {
            'icon_size': '100',
            'row_height': '120'
        }
        config['Folder_Style'] = {
            'icon_size': '35',
            'row_height': '45'
        }
        config['Layout'] = {
            'splitter_state': ''
        }
        config['Player'] = {
            'show_id3': 'False'
        }
        config['LastSession'] = {
            'last_audiobook_id': '0',
            'last_file_index': '0',
            'last_position': '0.0'
        }
        with open(self.config_file, 'w', encoding='utf-8') as f:
            config.write(f)

    def save_settings(self):
        """Сохранение всех настроек"""
        config = configparser.ConfigParser()
        # Читаем текущий файл, чтобы не потерять другие секции (например, LastSession)
        if self.config_file.exists():
            config.read(self.config_file, encoding='utf-8')
        
        # Размеры и позиция окна
        rect = self.geometry()
        if 'Display' not in config: config['Display'] = {}
        config['Display']['window_x'] = str(rect.x())
        config['Display']['window_y'] = str(rect.y())
        config['Display']['window_width'] = str(rect.width())
        config['Display']['window_height'] = str(rect.height())
        
        # Пути
        if 'Paths' not in config: config['Paths'] = {}
        config['Paths']['default_path'] = self.default_path
        config['Paths']['default_cover_file'] = self.default_cover_file
        config['Paths']['folder_cover_file'] = self.folder_cover_file
        
        # Layout
        if 'Layout' not in config: config['Layout'] = {}
        if hasattr(self, 'splitter'):
            config['Layout']['splitter_state'] = self.splitter.saveState().toHex().data().decode()
        
        # Настройки плеера
        if 'Player' not in config: config['Player'] = {}
        if hasattr(self, 'player_widget'):
            config['Player']['show_id3'] = str(self.player_widget.show_id3)
        
        # Стили (сохраняем текущие значения в объекте)
        if 'Audiobook_Style' not in config: config['Audiobook_Style'] = {}
        config['Audiobook_Style']['icon_size'] = str(self.audiobook_icon_size)
        config['Audiobook_Style']['row_height'] = str(self.audiobook_row_height)
        
        if 'Folder_Style' not in config: config['Folder_Style'] = {}
        config['Folder_Style']['icon_size'] = str(self.folder_icon_size)
        config['Folder_Style']['row_height'] = str(self.folder_row_height)
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            config.write(f)
    
    def save_last_session(self):
        """Сохранение последней сессии"""
        config = configparser.ConfigParser()
        config.read(self.config_file, encoding='utf-8')
        
        if 'LastSession' not in config:
            config['LastSession'] = {}
        
        config['LastSession']['last_audiobook_id'] = str(self.playback_controller.current_audiobook_id or 0)
        config['LastSession']['last_file_index'] = str(self.playback_controller.current_file_index)
        config['LastSession']['last_position'] = str(self.player.get_position())
        
        if 'Display' not in config:
            config['Display'] = {}
        
        config['Display']['window_width'] = str(self.width())
        config['Display']['window_height'] = str(self.height())
        config['Display']['window_x'] = str(self.x())
        config['Display']['window_y'] = str(self.y())
        
        # Сохранение положения разделителя
        if hasattr(self, 'splitter'):
            sizes = self.splitter.sizes()
            config['Display']['splitter_sizes'] = ",".join(map(str, sizes))
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            config.write(f)
    
    def restore_last_session(self):
        """Восстановление последней сессии"""
        config = configparser.ConfigParser()
        config.read(self.config_file, encoding='utf-8')
        
        audiobook_id = config.getint('LastSession', 'last_audiobook_id', fallback=0)
        file_index = config.getint('LastSession', 'last_file_index', fallback=0)
        position = config.getfloat('LastSession', 'last_position', fallback=0.0)
        
        # Восстановление положения разделителя
        splitter_sizes_str = config.get('Display', 'splitter_sizes', fallback='')
        if splitter_sizes_str and hasattr(self, 'splitter'):
            try:
                sizes = [int(s) for s in splitter_sizes_str.split(',')]
                if len(sizes) == 2:
                    self.splitter.setSizes(sizes)
            except (ValueError, TypeError):
                pass
        
        if audiobook_id <= 0:
            return
        
        # Получаем путь аудиокниги по ID
        import sqlite3
        connection = sqlite3.connect(self.db_file)
        cursor = connection.cursor()
        cursor.execute('SELECT path FROM audiobooks WHERE id = ?', (audiobook_id,))
        row = cursor.fetchone()
        connection.close()
        
        if row:
            audiobook_path = row[0]
            if self.playback_controller.load_audiobook(audiobook_path):
                # Обновляем состояние делегата
                if self.delegate:
                    self.delegate.playing_path = audiobook_path
                
                # Восстанавливаем позицию
                self.playback_controller.current_file_index = file_index
                self.playback_controller.play_file_at_index(file_index, False)
                if position > 0:
                    self.player.set_position(position)
                
                # Обновляем UI
                self.update_ui_for_audiobook()
                
                # Принудительная перерисовка библиотеки
                self.library_widget.tree.viewport().update()
                self.statusBar().showMessage(tr("status.restored_session"))
    
    def on_id3_state_toggled(self, state: bool):
        """Сохранение состояния ID3 тегов для текущей книги"""
        if self.playback_controller.current_audiobook_id:
            self.db_manager.update_audiobook_id3_state(
                self.playback_controller.current_audiobook_id,
                state
            )

    def on_audiobook_selected(self, audiobook_path: str):
        """Обработка выбора аудиокниги"""
        if self.playback_controller.load_audiobook(audiobook_path):
            # Отмечаем книгу как начатую
            if self.playback_controller.current_audiobook_id:
                self.db_manager.mark_audiobook_started(
                    self.playback_controller.current_audiobook_id
                )
            
            # Обновляем состояние делегата
            if self.delegate:
                self.delegate.playing_path = audiobook_path
            
            self.update_ui_for_audiobook()
            self.toggle_play()
            
            # Обновляем библиотеку (чтобы книга перешла в "В процессе")
            self.library_widget.load_audiobooks()

    
    def update_ui_for_audiobook(self):
        """Обновление UI для загруженной аудиокниги"""
        # Обновляем заголовок окна
        title = self.playback_controller.get_audiobook_title()
        self.setWindowTitle(trf("window.title_with_book", title=title))
        
        # Загружаем файлы в список
        self.player_widget.load_files(
            self.playback_controller.files_list,
            self.playback_controller.current_file_index
        )
        
        # Устанавливаем положение переключателя ID3
        self.player_widget.id3_btn.setChecked(self.playback_controller.use_id3_tags)
        
        # Выделяем в дереве
        self.library_widget.highlight_audiobook(
            self.playback_controller.current_audiobook_path
        )
        
        # Устанавливаем скорость
        self.player_widget.set_speed(self.player.speed_pos)
    
    def toggle_play(self):
        """Переключение воспроизведения"""
        if self.player.is_playing():
            self.player.pause()
            self.taskbar_progress.set_paused()
        else:
            self.player.play()
            self.taskbar_progress.set_normal()
        
        # Обновляем состояние делегата
        if self.delegate:
            self.delegate.is_paused = not self.player.is_playing()
            self.library_widget.tree.viewport().update()
            
        self.player_widget.set_playing(self.player.is_playing())
        
        # Обновляем иконку в таскбаре
        if hasattr(self, 'thumbnail_buttons'):
            self.thumbnail_buttons.update_play_state(self.player.is_playing())
            
        self.playback_controller.save_current_progress()
        self.save_last_session()
    
    def on_next_clicked(self):
        """Следующий файл"""
        if self.playback_controller.next_file():
            self.player_widget.highlight_current_file(
                self.playback_controller.current_file_index
            )
        else:
            self.statusBar().showMessage(tr("status.audiobook_complete"))
        self.save_last_session()
        self.refresh_audiobook_in_tree()
    
    def on_prev_clicked(self):
        """Предыдущий файл"""
        if self.playback_controller.prev_file():
            self.player_widget.highlight_current_file(
                self.playback_controller.current_file_index
            )
            self.save_last_session()
            self.refresh_audiobook_in_tree()

    def on_rewind_10_clicked(self):
        """Перемотка назад на 10 сек"""
        pos = self.player.get_position()
        self.player.set_position(max(0, pos - 10))
        self.playback_controller.save_current_progress()
        
    def on_forward_10_clicked(self):
        """Перемотка вперед на 10 сек"""
        pos = self.player.get_position()
        duration = self.player.get_duration()
        if duration > 0:
            self.player.set_position(min(duration, pos + 10))
        self.playback_controller.save_current_progress()
    
    def on_file_selected(self, index: int):
        """Выбор файла из списка"""
        self.playback_controller.play_file_at_index(index)
        self.player_widget.highlight_current_file(index)
        self.save_last_session()
        self.refresh_audiobook_in_tree()
    
    def on_position_changed(self, normalized: float):
        """Изменение позиции"""
        duration = self.player.get_duration()
        if duration > 0:
            self.player.set_position(normalized * duration)
            self.playback_controller.save_current_progress()
    
    def on_speed_changed(self, value: int):
        """Изменение скорости"""
        self.player.set_speed(value)
        if self.playback_controller.current_audiobook_id:
            self.db_manager.update_audiobook_speed(
                self.playback_controller.current_audiobook_id,
                value / 10.0
            )

    def on_library_play_clicked(self, audiobook_path: str):
        """Обработка клика по кнопке Play в библиотеке"""
        if self.playback_controller.current_audiobook_path == audiobook_path:
            self.toggle_play()
        else:
            # Если кликнули на другую книгу - загружаем и играем сразу
            self.on_audiobook_selected(audiobook_path)
            if not self.player.is_playing():
                self.toggle_play()
        
        # Принудительная перерисовка чтобы иконка сменилась сразу
        self.library_widget.tree.viewport().update()
    
    def showEvent(self, event):
        """Инициализация при показе окна"""
        super().showEvent(event)
        
        # Устанавливаем HWND для taskbar progress
        hwnd = int(self.winId())
        self.taskbar_progress.set_hwnd(hwnd)
        
        # Инициализируем кнопки
        if self.taskbar_progress.taskbar:
            self.thumbnail_buttons = TaskbarThumbnailButtons(
                self.taskbar_progress.taskbar,
                hwnd,
                self.icons_dir
            )
            # Добавляем кнопки с задержкой, чтобы окно успело зарегистрироваться в таскбаре
            QTimer.singleShot(1000, self.thumbnail_buttons.add_buttons)
            
            # Устанавливаем текущее состояние
            self.thumbnail_buttons.update_play_state(self.player.is_playing())



    def refresh_audiobook_in_tree(self):
        """Обновление элемента в дереве"""
        self.library_widget.refresh_audiobook_item(
            self.playback_controller.current_audiobook_path
        )
    
    def update_ui(self):
        """Обновление интерфейса (вызывается по таймеру)"""
        if self.player.chan == 0:
            return
        
        pos = self.player.get_position()
        duration = self.player.get_duration()
        
        # Обновляем прогресс файла
        self.player_widget.update_file_progress(pos, duration)
        
        # Обновляем общий прогресс
        total_pos = self.playback_controller.get_current_position()
        self.player_widget.update_total_progress(
            total_pos,
            self.playback_controller.total_duration,
            self.player.speed_pos / 10.0
        )
        
        # Живое обновление в библиотеке (раз в секунду для экономии ресурсов)
        if not hasattr(self, '_library_update_counter'):
            self._library_update_counter = 0
            
        self._library_update_counter += 1
        if self._library_update_counter >= 10: # Таймер срабатывает каждые 100мс, 10 * 100 = 1000мс
            self._library_update_counter = 0
            if self.playback_controller.current_audiobook_path:
                progress_percent = self.playback_controller.get_progress_percent()
                self.library_widget.update_item_progress(
                    self.playback_controller.current_audiobook_path,
                    total_pos,
                    progress_percent
                )
        
        # Обновляем состояние кнопки
        self.player_widget.set_playing(self.player.is_playing())
        
        # Обновляем таскбар
        if self.playback_controller.total_duration > 0:
            self.taskbar_progress.update_for_playback(
                is_playing=self.player.is_playing(),
                current=total_pos,
                total=self.playback_controller.total_duration
            )
        
        # Проверка окончания файла
        if duration > 0 and pos >= duration - 0.5 and not self.player.is_playing():
            self.on_next_clicked()
    
    def rescan_directory(self):
        """Сканирование директории с выводом в диалог"""
        if not self.default_path:
            QMessageBox.warning(self, tr("settings.title"), tr("settings.specify_path"))
            return

        def start_scanning_process():
            dialog = ScanProgressDialog(self)
            
            # Когда сканирование закончится, обновляем библиотеку
            def on_finished():
                self.library_widget.load_audiobooks()
                # Обновляем счётчик в статусе
                total_count = self.db_manager.get_audiobook_count()
                self.statusBar().showMessage(trf("status.library_count", count=total_count))
                
            dialog.finished.connect(on_finished)
            dialog.show()
            dialog.start_scan(self.default_path)

        # Check for ffprobe
        ffprobe_exe = self.ffprobe_path
        
        if not ffprobe_exe.exists():
            update_dialog = UpdateProgressDialog(self)
            
            def on_update_finished():
                if ffprobe_exe.exists():
                    start_scanning_process()
            
            # Connect to finished signal of dialog (works when dialog closes)
            # But we want to auto-proceed?
            # UpdateProgressDialog keeps open until user closes.
            # User wants "launch download, and AFTER scanning".
            # If we wait for user close, it is fine.
            # If we want auto-close, we need to modify UpdateProgressDialog.
            # Let's assume user closes it.
            
            update_dialog.finished.connect(on_update_finished)
            update_dialog.show()
            update_dialog.start_update()
        else:
            start_scanning_process()
    
    def reload_styles(self):
        """Перезагрузка стилей"""
        try:
            from styles import StyleManager, DARK_QSS_PATH
            StyleManager.apply_style(QApplication.instance(), path=DARK_QSS_PATH)
            
            # Обновляем делегат
            if self.delegate:
                self.delegate.update_styles()
            
            self.statusBar().showMessage(tr("status.styles_reloaded"))
        except Exception as e:
            self.statusBar().showMessage(trf("status.styles_error", error=str(e)))
    
    def show_settings(self):
        """Показ диалога настроек"""
        dialog = SettingsDialog(self, self.default_path, self.ffprobe_path)
        
        def on_path_saved(new_path):
            if new_path != self.default_path:
                self.default_path = new_path
                self.save_settings() # save_settings already handles everything
                # Синхронизируем коренную папку в контроллере
                if hasattr(self, 'playback_controller'):
                    self.playback_controller.library_root = Path(new_path)
                self.library_widget.load_audiobooks()
                self.statusBar().showMessage(tr("status.path_saved"))
        
        def on_scan_requested(new_path):
            if new_path != self.default_path:
                self.default_path = new_path
                self.save_settings()
                if hasattr(self, 'playback_controller'):
                    self.playback_controller.library_root = Path(new_path)
            self.rescan_directory()
        
        dialog.path_saved.connect(on_path_saved)
        dialog.scan_requested.connect(on_scan_requested)
        dialog.data_reset_requested.connect(self.perform_full_reset)
        dialog.exec()

    def perform_full_reset(self):
        """Полный сброс данных библиотеки без закрытия приложения"""
        try:
            # 1. Останавливаем плеер
            self.player.pause()
            
            # 2. Очищаем состояние контроллера
            self.playback_controller.current_audiobook_id = None
            self.playback_controller.current_audiobook_path = None
            self.playback_controller.files_list = []
            self.playback_controller.saved_file_index = 0
            self.playback_controller.saved_position = 0
            
            # 3. Очищаем дерево (важно для снятия блокировок с файлов обложек)
            self.library_widget.tree.clear()
            
            # 4. Очищаем БД (через SQL, так как файл может быть занят)
            self.db_manager.clear_all_data()
            
            # 5. Удаляем обложки
            if self.covers_dir.exists():
                try:
                    shutil.rmtree(self.covers_dir)
                except Exception as e:
                    print(f"Could not delete covers dir: {e}")
                
            # 6. Обновляем UI
            self.update_ui_for_audiobook() # Очистит подписи и прогресс плеера
            if self.delegate:
                self.delegate.playing_path = None # Сбрасываем подсветку в дереве
            self.library_widget.load_audiobooks() # Загрузит пустое дерево
            
            self.statusBar().showMessage("✅ Библиотека успешно очищена")
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось полностью очистить данные: {e}")

    def show_about(self):
        """Показ диалога О программе"""
        dialog = AboutDialog(self)
        dialog.exec()
    
    def save_setting(self, section: str, key: str, value: str):
        """Сохранение настройки"""
        config = configparser.ConfigParser()
        config.read(self.config_file, encoding='utf-8')
        
        if section not in config:
            config[section] = {}
        
        config[section][key] = value
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            config.write(f)
    
    
    def closeEvent(self, event):
        """При закрытии окна"""
        self.playback_controller.save_current_progress()
        self.save_last_session()
        self.taskbar_progress.clear()
        self.player.free()
        event.accept()

from PyQt6.QtCore import QAbstractNativeEventFilter

class TaskbarEventFilter(QAbstractNativeEventFilter):
    def __init__(self, window):
        super().__init__()
        self.window = window

    def nativeEventFilter(self, eventType, message):
        if eventType == b"windows_generic_MSG" and message:
            try:
                msg_ptr = int(message)
                if msg_ptr:
                    msg = wintypes.MSG.from_address(msg_ptr)
                    if msg.message == 0x0111:  # WM_COMMAND
                        if (msg.wParam >> 16) & 0xFFFF == 0x1800:  # THBN_CLICKED
                            button_id = msg.wParam & 0xFFFF
                            if button_id == 0:
                                self.window.on_prev_clicked()
                                return True, 0
                            elif button_id == 1:
                                self.window.toggle_play()
                                return True, 0
                            elif button_id == 2:
                                self.window.on_next_clicked()
                                return True, 0
                            elif button_id == 3:
                                self.window.on_rewind_10_clicked()
                                return True, 0
                            elif button_id == 4:
                                self.window.on_forward_10_clicked()
                                return True, 0
            except Exception:
                pass
        return False, 0

def main():
    """Точка входа"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setStyleSheet(DARK_STYLE)
    
    window = AudiobookPlayerWindow()
    
    # Регистрация фильтра нативных событий для кнопок таскбара
    event_filter = TaskbarEventFilter(window)
    app.installNativeEventFilter(event_filter)
    
    window.show()
    
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
