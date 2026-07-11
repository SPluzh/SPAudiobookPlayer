import re
import string
from dataclasses import dataclass
from typing import List, Optional
from pathlib import Path
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextBrowser
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QTimer, QRect
from PyQt6.QtGui import QTextCursor, QTextCharFormat, QColor
from translations import tr
from subtitle_translator import TranslationPopup
from utils import get_icon


@dataclass
class SRTEntry:
    index: int
    start: float   # seconds from start of current file
    end: float
    text: str      # clean text without HTML tags


def _parse_srt_time(s: str) -> float:
    """Convert '00:01:23,456' -> 83.456 seconds"""
    try:
        s = s.strip().replace(',', '.')
        h, m, rest = s.split(':')
        if '.' in rest:
            sec, ms = rest.split('.')
            return int(h) * 3600 + int(m) * 60 + int(sec) + int(ms) / (10 ** len(ms))
        else:
            return int(h) * 3600 + int(m) * 60 + int(rest)
    except Exception:
        return 0.0


def parse_srt(path: str) -> List[SRTEntry]:
    """Parse SRT file -> list of SRTEntry"""
    entries = []
    try:
        raw_bytes = Path(path).read_bytes()
        try:
            # Try decoding as UTF-8 (with BOM handling)
            text = raw_bytes.decode('utf-8-sig')
        except UnicodeDecodeError:
            # Fallback to cp1251 for Windows Cyrillic files
            text = raw_bytes.decode('cp1251', errors='replace')
    except OSError:
        return entries

    # Split by empty lines
    for block in re.split(r'\n\s*\n', text.strip()):
        lines = block.strip().splitlines()
        if len(lines) < 3:
            continue
        try:
            idx = int(lines[0].strip())
            m = re.match(
                r'(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})',
                lines[1].strip()
            )
            if not m:
                continue
            start = _parse_srt_time(m.group(1))
            end = _parse_srt_time(m.group(2))
            raw = '\n'.join(lines[2:])
            clean = re.sub(r'<[^>]+>', '', raw).strip()
            entries.append(SRTEntry(index=idx, start=start, end=end, text=clean))
        except (ValueError, IndexError):
            continue
    return entries


def find_srt_for_audio(audio_abs_path: str) -> Optional[str]:
    """
    Find SRT file for the audio file.
    Search order:
      1. {audio_dir}/{audio_stem}.srt          <- priority
      2. {audio_dir}/subtitles/{audio_stem}.srt
      3. {audio_dir}/subtitles/{folder_name}.srt  <- fallback
    """
    if not audio_abs_path or audio_abs_path.startswith(('http://', 'https://')):
        return None
    p = Path(audio_abs_path)
    candidates = [
        p.with_suffix('.srt'),
        p.parent / 'subtitles' / p.with_suffix('.srt').name,
        p.parent / 'subtitles' / f'{p.parent.name}.srt',
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return None


class InteractiveSubBrowser(QTextBrowser):
    wordHovered = pyqtSignal(str, QPoint)      # (word, global_pos)
    selectionSelected = pyqtSignal(str, QPoint) # (text, global_pos)
    hoverCleared = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        
        self.hover_timer = QTimer(self)
        self.hover_timer.setSingleShot(True)
        self.hover_timer.timeout.connect(self._on_hover_timeout)

        self.current_hovered_word = ""
        self.current_hovered_cursor = None
        self.hover_pos = QPoint()
        self.translation_on_hover = True

    def _on_hover_timeout(self):
        try:
            if self.current_hovered_word and self.current_hovered_cursor:
                self.highlight_word(self.current_hovered_cursor)
                self.wordHovered.emit(self.current_hovered_word, self.hover_pos)
        except Exception as e:
            import logging
            logging.error(f"Error in _on_hover_timeout: {e}", exc_info=True)

    def highlight_word(self, cursor):
        try:
            selection = QTextBrowser.ExtraSelection()
            selection.cursor = cursor
            
            format = QTextCharFormat()
            # Premium highlight: gold semi-transparent background
            format.setBackground(QColor(255, 215, 0, 80)) 
            selection.format = format
            self.setExtraSelections([selection])
        except Exception as e:
            import logging
            logging.error(f"Error in highlight_word: {e}", exc_info=True)

    def clear_highlight(self):
        try:
            self.setExtraSelections([])
            self.current_hovered_word = ""
            self.current_hovered_cursor = None
            self.hoverCleared.emit()
        except Exception as e:
            import logging
            logging.error(f"Error in clear_highlight: {e}", exc_info=True)

    def mouseMoveEvent(self, event):
        try:
            super().mouseMoveEvent(event)

            if not getattr(self, "translation_on_hover", True):
                self.hover_timer.stop()
                if self.current_hovered_word:
                    self.clear_highlight()
                return

            pos = event.position().toPoint()

            if event.buttons() & Qt.MouseButton.LeftButton:
                self.hover_timer.stop()
                return

            if self.textCursor().hasSelection():
                self.hover_timer.stop()
                return

            cursor = self.cursorForPosition(pos)

            if not cursor.isNull():
                rect = self.cursorRect(cursor)
                char_width = 12
                char_height = rect.height()
                expanded_rect = QRect(rect.x() - char_width, rect.y(), char_width * 2, char_height)
                
                if expanded_rect.contains(pos):
                    cursor.select(QTextCursor.SelectionType.WordUnderCursor)
                    word = cursor.selectedText()
                    cleaned_word = word.strip(string.punctuation + " \n\r\t»«“”‘’")
                    
                    if cleaned_word and cleaned_word.isalpha():
                        if cleaned_word != self.current_hovered_word:
                            self.current_hovered_word = cleaned_word
                            self.current_hovered_cursor = cursor
                            
                            start_cursor = QTextCursor(cursor)
                            start_cursor.setPosition(cursor.selectionStart())
                            end_cursor = QTextCursor(cursor)
                            end_cursor.setPosition(cursor.selectionEnd())
                            
                            r_start = self.cursorRect(start_cursor)
                            r_end = self.cursorRect(end_cursor)
                            
                            if abs(r_start.top() - r_end.top()) < 5:
                                x = (r_start.left() + r_end.left()) // 2
                            else:
                                x = r_start.left()
                            y = r_start.top()
                            
                            self.hover_pos = self.viewport().mapToGlobal(QPoint(x, y))
                            self.hover_timer.start(300) # 300ms debounce
                        return

            self.hover_timer.stop()
            if self.current_hovered_word:
                self.clear_highlight()
        except Exception as e:
            import logging
            logging.error(f"Error in mouseMoveEvent: {e}", exc_info=True)

    def mouseReleaseEvent(self, event):
        try:
            super().mouseReleaseEvent(event)
            cursor = self.textCursor()
            if cursor.hasSelection():
                selected_text = cursor.selectedText().strip()
                if selected_text:
                    start_cursor = QTextCursor(cursor)
                    start_cursor.setPosition(cursor.selectionStart())
                    end_cursor = QTextCursor(cursor)
                    end_cursor.setPosition(cursor.selectionEnd())
                    
                    r_start = self.cursorRect(start_cursor)
                    r_end = self.cursorRect(end_cursor)
                    
                    if abs(r_start.top() - r_end.top()) < 5:
                        x = (r_start.left() + r_end.left()) // 2
                    else:
                        x = r_start.left()
                    y = r_start.top()
                    
                    global_pos = self.viewport().mapToGlobal(QPoint(x, y))
                    self.selectionSelected.emit(selected_text, global_pos)
        except Exception as e:
            import logging
            logging.error(f"Error in mouseReleaseEvent: {e}", exc_info=True)

    def leaveEvent(self, event):
        try:
            self.hover_timer.stop()
            cursor = self.textCursor()
            if cursor.hasSelection():
                cursor.clearSelection()
                self.setTextCursor(cursor)
            self.clear_highlight()
            super().leaveEvent(event)
        except Exception as e:
            import logging
            logging.error(f"Error in leaveEvent: {e}", exc_info=True)


class SubtitlePanel(QWidget):
    """Subtitle panel with active line highlighting and auto-scrolling"""
    font_size_changed = pyqtSignal(int)
    translation_on_hover_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("subtitlePanel")
        self._entries: List[SRTEntry] = []
        self._current_idx: int = -1
        self._font_size: int = 15
        self._translation_on_hover: bool = True
        self._setup_ui()
        self.translation_on_hover = True
        
        # Instantiate Translation Popup
        self.translation_popup = TranslationPopup(self)
        self.browser.wordHovered.connect(self._on_word_hovered)
        self.browser.selectionSelected.connect(self._on_selection_selected)
        self.browser.hoverCleared.connect(self._on_hover_cleared)

    def _setup_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Controls row above the subtitles
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(6, 0, 6, 6)
        controls_layout.setSpacing(6)
        controls_layout.addStretch()

        self.btn_zoom_out = QPushButton("-")
        self.btn_zoom_out.setFixedWidth(24)
        self.btn_zoom_out.setObjectName("subSizeMinusBtn")
        self.btn_zoom_out.clicked.connect(self.decrease_font_size)
        controls_layout.addWidget(self.btn_zoom_out)

        self.btn_zoom_in = QPushButton("+")
        self.btn_zoom_in.setFixedWidth(24)
        self.btn_zoom_in.setObjectName("subSizePlusBtn")
        self.btn_zoom_in.clicked.connect(self.increase_font_size)
        controls_layout.addWidget(self.btn_zoom_in)

        self.btn_translation_toggle = QPushButton()
        self.btn_translation_toggle.setFixedWidth(24)
        self.btn_translation_toggle.setCheckable(True)
        self.btn_translation_toggle.setObjectName("subTranslationToggleBtn")
        self.btn_translation_toggle.setIcon(get_icon("languages"))
        self.btn_translation_toggle.clicked.connect(self._on_translation_toggle_clicked)
        controls_layout.addWidget(self.btn_translation_toggle)

        lay.addLayout(controls_layout)

        # Use the interactive browser class instead of standard QTextBrowser
        self.browser = InteractiveSubBrowser()
        self.browser.setObjectName("subtitleText")
        self.browser.setReadOnly(True)
        self.browser.setOpenLinks(False)
        self.browser.setMinimumHeight(100)
        lay.addWidget(self.browser)

        self.update_texts()

    def _on_word_hovered(self, word, global_pos):
        self.translation_popup.hide_timer.stop()
        self.translation_popup.show_translation(word, target_lang="ru", anchor_pos=global_pos)

    def _on_selection_selected(self, text, global_pos):
        self.translation_popup.hide_timer.stop()
        self.translation_popup.show_translation(text, target_lang="ru", anchor_pos=global_pos)

    def _on_hover_cleared(self):
        self.translation_popup.hide_timer.start(500)

    @property
    def font_size(self) -> int:
        return self._font_size

    @font_size.setter
    def font_size(self, size: int):
        self._font_size = max(10, min(size, 40))
        self._render()

    @property
    def translation_on_hover(self) -> bool:
        return self._translation_on_hover

    @translation_on_hover.setter
    def translation_on_hover(self, enabled: bool):
        self._translation_on_hover = enabled
        self.btn_translation_toggle.setChecked(enabled)
        self.browser.translation_on_hover = enabled
        if not enabled:
            self.browser.clear_highlight()

    def _on_translation_toggle_clicked(self, checked: bool):
        self.translation_on_hover = checked
        self.translation_on_hover_changed.emit(checked)

    def decrease_font_size(self):
        new_size = max(10, self._font_size - 1)
        if new_size != self._font_size:
            self.font_size = new_size
            self.font_size_changed.emit(self._font_size)

    def increase_font_size(self):
        new_size = min(40, self._font_size + 1)
        if new_size != self._font_size:
            self.font_size = new_size
            self.font_size_changed.emit(self._font_size)

    def update_texts(self):
        """Update tooltips for control buttons on language change"""
        self.btn_zoom_in.setToolTip(tr("player.zoom_in"))
        self.btn_zoom_out.setToolTip(tr("player.zoom_out"))
        self.btn_translation_toggle.setToolTip(tr("player.translation_on_hover", "Translation on hover"))

    # -- Public API ---------------------------------------------

    def load_srt(self, srt_path: str) -> bool:
        """Load SRT file. Returns True on success."""
        entries = parse_srt(srt_path)
        if not entries:
            return False
        self._entries = entries
        self._current_idx = -1
        self._render()
        return True

    def clear(self):
        """Clear subtitles"""
        self._entries = []
        self._current_idx = -1
        self.browser.clear()

    def update_position(self, position_sec: float):
        """Update active line highlighting. Call from update_ui()."""
        if not self._entries:
            return
        new_idx = self._binary_search(position_sec)
        if new_idx == self._current_idx:
            return
        self._current_idx = new_idx
        self._render()

    # -- Private ------------------------------------------------

    def _binary_search(self, pos: float) -> int:
        """Find the active entry index by playback position in seconds"""
        lo, hi, result = 0, len(self._entries) - 1, -1
        while lo <= hi:
            mid = (lo + hi) // 2
            e = self._entries[mid]
            if e.start <= pos <= e.end:
                return mid
            elif pos < e.start:
                hi = mid - 1
            else:
                result = mid
                lo = mid + 1
        return result

    def _render(self):
        """Render HTML with current line highlighting and scroll to it"""
        parts = []
        for i, e in enumerate(self._entries):
            safe = (e.text
                    .replace('&', '&amp;')
                    .replace('<', '&lt;')
                    .replace('\n', '<br/>'))
            cls = ' class="active"' if i == self._current_idx else ''
            parts.append(f'<p id="s{e.index}"{cls}>{safe}</p>')

        css = f"""<style>
body {{ margin: 6px; }}
p {{ margin: 2px 0; padding: 2px 6px; border-radius: 3px; line-height: 1.5; color: #a0a0a0; font-size: {self._font_size}px; }}
p.active {{ color: #ffffff; font-weight: 600; }}
</style>"""
        self.browser.setHtml(
            f'<html><head>{css}</head><body>{"".join(parts)}</body></html>'
        )
        if self._current_idx >= 0:
            entry = self._entries[self._current_idx]
            
            block = None
            first_line = entry.text.split('\n')[0].strip()
            if first_line:
                cursor = self.browser.document().find(first_line)
                if not cursor.isNull():
                    block = cursor.block()
            
            if not block or not block.isValid():
                block = self.browser.document().findBlockByNumber(self._current_idx)
                
            if block and block.isValid():
                rect = self.browser.document().documentLayout().blockBoundingRect(block)
                view_h = self.browser.viewport().height()
                sb = self.browser.verticalScrollBar()
                target_scroll = int(rect.top() + rect.height() / 2.0 - view_h / 2.0)
                sb.setValue(max(sb.minimum(), min(sb.maximum(), target_scroll)))
