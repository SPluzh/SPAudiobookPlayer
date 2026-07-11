import urllib.request
import urllib.parse
import json
import logging
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QLabel, QHBoxLayout, QPushButton
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPoint, QTimer, QRect
from PyQt6.QtGui import QFont, QPalette, QColor
from utils import get_icon

def tr_def(key, english_default, russian_default=None):
    from translations import tr, get_language
    val = tr(key)
    if val != key:
        return val
    if get_language() == "ru" and russian_default is not None:
        return russian_default
    return english_default

class TranslationWorker(QThread):
    finished = pyqtSignal(str, dict)  # (original, translation_details)
    error = pyqtSignal(str)

    def __init__(self, text, target_lang="ru", provider="google"):
        super().__init__()
        self.text = text
        self.target_lang = target_lang
        self.provider = provider

    def run(self):
        try:
            cleaned = self.text.strip()
            if not cleaned:
                self.finished.emit(self.text, {"translation": ""})
                return

            import ssl
            context = ssl._create_unverified_context()

            # Default to google
            url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={self.target_lang}&dt=t&dt=bd&dt=ss&q={urllib.parse.quote(cleaned)}"
            req = urllib.request.Request(
                url,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            )
            with urllib.request.urlopen(req, timeout=5, context=context) as response:
                data = json.loads(response.read().decode('utf-8'))
                if data and data[0]:
                    translated = "".join([part[0] for part in data[0] if part[0]])
                    
                    parts_of_speech = {}
                    if len(data) > 1 and data[1]:
                        for entry in data[1]:
                            if len(entry) >= 2:
                                pos = entry[0]
                                words = entry[1]
                                if pos and words:
                                    parts_of_speech[pos] = words
                                    
                    synonyms = {}
                    if len(data) > 11 and data[11]:
                        for entry in data[11]:
                            if len(entry) >= 2:
                                pos = entry[0]
                                syn_list = []
                                for item in entry[1]:
                                    if item and isinstance(item, list) and len(item) > 0:
                                        syn_list.extend(item[0])
                                if pos and syn_list:
                                    synonyms[pos] = syn_list

                    result = {
                        "translation": translated,
                        "parts_of_speech": parts_of_speech,
                        "synonyms": synonyms
                    }
                    self.finished.emit(cleaned, result)
                else:
                    self.error.emit("Empty response from translation API")
        except Exception as e:
            logging.error(f"Translation error: {e}")
            self.error.emit(str(e))


class TranslationPopup(QFrame):
    mouseLeft = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        # Main Layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(12, 10, 12, 10)
        self.layout.setSpacing(6)

        self.setObjectName("TranslationPopup")

        self.current_original = None
        self.current_translation = None

        # Top row layout for original text and dictionary button
        self.top_layout = QHBoxLayout()
        self.top_layout.setContentsMargins(0, 0, 0, 0)
        self.top_layout.setSpacing(6)
        self.layout.addLayout(self.top_layout)

        # Original Text Label
        self.original_label = QLabel(self)
        self.original_label.setObjectName("translationPopupOriginalLabel")
        self.original_label.setWordWrap(True)
        # Apply premium styling
        self.original_label.setStyleSheet("color: #ffffff; font-size: 11pt; font-weight: bold;")
        self.top_layout.addWidget(self.original_label, 1)

        # Listen pronunciation button
        self.pronounce_btn = QPushButton(self)
        self.pronounce_btn.setObjectName("pronounceBtn")
        self.pronounce_btn.setFixedSize(30, 30)
        self.pronounce_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.pronounce_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pronounce_btn.setIcon(get_icon("volume_medium"))
        self.top_layout.addWidget(self.pronounce_btn, 0, Qt.AlignmentFlag.AlignTop)
        self.pronounce_btn.clicked.connect(self._on_pronounce_btn_clicked)
        self.pronounce_btn.hide()

        # Add to dictionary button
        self.dict_btn = QPushButton(self)
        self.dict_btn.setObjectName("dictBtn")
        self.dict_btn.setFixedSize(30, 30)
        self.dict_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.dict_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.top_layout.addWidget(self.dict_btn, 0, Qt.AlignmentFlag.AlignTop)
        self.dict_btn.clicked.connect(self._on_dict_btn_clicked)
        self.dict_btn.hide()

        # Translation Text Label
        self.translation_label = QLabel(self)
        self.translation_label.setObjectName("translationPopupTranslationLabel")
        self.translation_label.setWordWrap(True)
        self.translation_label.setTextFormat(Qt.TextFormat.RichText)
        self.translation_label.setStyleSheet("font-size: 10.5pt;")
        self.layout.addWidget(self.translation_label)

        self.active_workers = []
        self._memory_cache = {}
        self.last_anchor_pos = QPoint()
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide)

    def paintEvent(self, event):
        from PyQt6.QtGui import QPainter, QPen
        from styles import StyleManager
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Try to get background and border color dynamically from StyleManager
        try:
            _, bg_color = StyleManager.get_theme_property("popup_background")
            _, border_color = StyleManager.get_theme_property("popup_border")
        except Exception:
            bg_color = QColor(55, 55, 55) # Fallback to a solid dark gray
            border_color = QColor(128, 128, 128)
            
        # Ensure they are opaque
        bg_color = QColor(bg_color.red(), bg_color.green(), bg_color.blue(), 255)
        border_color = QColor(border_color.red(), border_color.green(), border_color.blue(), 255)
        
        painter.setBrush(bg_color)
        painter.setPen(QPen(border_color, 1))
        
        rect = self.rect()
        adjusted_rect = QRect(rect.x(), rect.y(), rect.width() - 1, rect.height() - 1)
        painter.drawRoundedRect(adjusted_rect, 3.0, 3.0)


    def _get_db(self):
        """Retrieve the database manager from parent elements."""
        p = self.parent()
        while p:
            if hasattr(p, "db_manager") and p.db_manager:
                return p.db_manager
            if hasattr(p, "db") and p.db:
                return p.db
            if hasattr(p, "player_window") and p.player_window:
                player = p.player_window
                if player and hasattr(player, "db_manager") and player.db_manager:
                    return player.db_manager
                if player and hasattr(player, "db") and player.db:
                    return player.db
            p = p.parent()
        return None

    def show_translation(self, text, target_lang="ru", provider="google", anchor_pos=QPoint()):
        """Starts asynchronous translation and positions the popup above anchor_pos."""
        logging.debug(f"show_translation called with text='{text}', target_lang='{target_lang}', provider='{provider}'")
        
        # Clean up old running workers by disconnecting signals to avoid updates
        for worker in list(self.active_workers):
            if worker.isRunning():
                try:
                    worker.finished.disconnect()
                    worker.error.disconnect()
                except TypeError:
                    pass
            else:
                try:
                    self.active_workers.remove(worker)
                except ValueError:
                    pass

        self.last_anchor_pos = anchor_pos
        cleaned = text.strip()
        if not cleaned:
            self.original_label.setText(text)
            self.translation_label.setText("")
            self.dict_btn.hide()
            self.pronounce_btn.hide()
            self.adjustSize()
            self.position_popup(anchor_pos)
            self.show()
            self.raise_()
            return

        cache_key = (cleaned, target_lang, provider)

        # 1. Check L1 Memory Cache
        if cache_key in self._memory_cache:
            logging.info(f"Translation cache hit (L1 memory) for: '{cleaned}' -> '{target_lang}' ({provider})")
            self.original_label.setText(text)
            self.show()
            self.raise_()
            self._on_translation_success(text, self._memory_cache[cache_key])
            return

        # 2. Check L2 Database Cache
        db = self._get_db()
        if db:
            cached_result = db.get_cached_translation(cleaned, target_lang)
            if cached_result:
                logging.info(f"Translation cache hit (L2 database) for: '{cleaned}' -> '{target_lang}'")
                self._memory_cache[cache_key] = cached_result
                self.original_label.setText(text)
                self.show()
                self.raise_()
                self._on_translation_success(text, cached_result)
                return

        # Cache miss - proceed to async translation
        self.original_label.setText(text)
        self.translation_label.setText("...")
        self.dict_btn.hide()
        self.pronounce_btn.hide()
        self.adjustSize()
        self.position_popup(anchor_pos)
        self.show()
        self.raise_()

        worker = TranslationWorker(text, target_lang, provider)
        
        # Create safe wrappers for connection
        def on_success(orig, trans, w=worker):
            try:
                if w in self.active_workers:
                    self.active_workers.remove(w)
            except ValueError:
                pass
            
            # Save to L1 and L2 caches
            self._memory_cache[cache_key] = trans
            db_inst = self._get_db()
            if db_inst:
                db_inst.save_cached_translation(cleaned, target_lang, trans)

            self._on_translation_success(orig, trans)
            
        def on_error(err, w=worker):
            try:
                if w in self.active_workers:
                    self.active_workers.remove(w)
            except ValueError:
                pass
            self._on_translation_error(err)

        worker.finished.connect(on_success)
        worker.error.connect(on_error)
        self.active_workers.append(worker)
        worker.start()

    def _on_translation_success(self, original, result_dict):
        translation = result_dict.get("translation", "")
        parts_of_speech = result_dict.get("parts_of_speech", {})
        synonyms = result_dict.get("synonyms", {})
        
        # Build HTML content
        html = f"<div style='color: #FFD700; font-weight: bold;'>{translation}</div>"
        
        # 1. Parts of Speech translations
        pos_lines = []
        for pos_name, words in parts_of_speech.items():
            translated_pos = tr_def(f"translator.{pos_name}", pos_name.capitalize(), pos_name.capitalize())
            word_list_str = ", ".join(words[:5])
            pos_lines.append(
                f"<tr>"
                f"<td style='color: #888888; font-weight: bold; padding-right: 8px; vertical-align: top; font-size: 9.5pt;'>{translated_pos}:</td>"
                f"<td style='color: #eaeaea; font-size: 9.5pt;'>{word_list_str}</td>"
                f"</tr>"
            )
            
        if pos_lines:
            html += f"<table style='margin-top: 6px; margin-bottom: 6px; font-size: 9.5pt; width: 100%;'>"
            html += "".join(pos_lines)
            html += "</table>"
            
        # 2. Synonyms
        all_synonyms = []
        for pos_name, syn_list in synonyms.items():
            all_synonyms.extend(syn_list)
            
        # Remove duplicates while maintaining order
        seen = set()
        unique_synonyms = [x for x in all_synonyms if not (x in seen or seen.add(x))]
        
        if unique_synonyms:
            label_synonyms = tr_def("translator.synonyms", "Synonyms", "Синонимы")
            syn_str = ", ".join(unique_synonyms[:8])
            
            if pos_lines:
                html += f"<hr style='border: 0; border-top: 1px solid #555555; margin: 4px 0;'/>"
            html += f"<div style='font-size: 9pt; color: #a0a0a0; margin-top: 4px;'>"
            html += f"<b style='color: #888888;'>{label_synonyms}:</b> {syn_str}"
            html += f"</div>"

        self.translation_label.setText(html)
        
        # Dictionary button configuration
        self.current_original = original.strip()
        self.current_translation = translation.strip()
        
        db = self._get_db()
        is_added = False
        if db and self.current_original:
            is_added = db.is_in_dictionary(self.current_original)
            
        if is_added:
            self.dict_btn.setIcon(get_icon("check"))
            self.dict_btn.setToolTip(tr_def("translator.already_in_dictionary", "Already in dictionary", "Уже в словаре"))
            self.dict_btn.setProperty("added", "true")
        else:
            self.dict_btn.setIcon(get_icon("add"))
            self.dict_btn.setToolTip(tr_def("translator.add_to_dictionary", "Add to dictionary", "Добавить в словарь"))
            self.dict_btn.setProperty("added", "false")
            
        self.dict_btn.style().unpolish(self.dict_btn)
        self.dict_btn.style().polish(self.dict_btn)
        self.dict_btn.show()

        tooltip_pronounce = tr_def("translator.listen_pronunciation", "Listen pronunciation", "Прослушать произношение")
        self.pronounce_btn.setToolTip(tooltip_pronounce)
        self.pronounce_btn.show()

        self.adjustSize()
        if hasattr(self, "last_anchor_pos") and self.last_anchor_pos:
            self.position_popup(self.last_anchor_pos)
        self.raise_()

    def _on_translation_error(self, err_msg):
        self.translation_label.setText("Translation failed")
        self.current_original = None
        self.current_translation = None
        self.dict_btn.hide()
        self.pronounce_btn.hide()
        self.adjustSize()
        if hasattr(self, "last_anchor_pos") and self.last_anchor_pos:
            self.position_popup(self.last_anchor_pos)
        self.raise_()

    def _on_dict_btn_clicked(self):
        db = self._get_db()
        if not db or not self.current_original:
            return
        
        is_added = db.is_in_dictionary(self.current_original)
        if is_added:
            db.remove_from_dictionary(self.current_original)
            self.dict_btn.setIcon(get_icon("add"))
            self.dict_btn.setToolTip(tr_def("translator.add_to_dictionary", "Add to dictionary", "Добавить в словарь"))
            self.dict_btn.setProperty("added", "false")
        else:
            db.add_to_dictionary(self.current_original, self.current_translation)
            self.dict_btn.setIcon(get_icon("check"))
            self.dict_btn.setToolTip(tr_def("translator.already_in_dictionary", "Already in dictionary", "Уже в словаре"))
            self.dict_btn.setProperty("added", "true")
            
        self.dict_btn.style().unpolish(self.dict_btn)
        self.dict_btn.style().polish(self.dict_btn)
        self.dict_btn.update()
        
        self.adjustSize()
        if hasattr(self, "last_anchor_pos") and self.last_anchor_pos:
            self.position_popup(self.last_anchor_pos)

    def _on_pronounce_btn_clicked(self):
        if not self.current_original:
            return
        
        if not hasattr(self, "tts"):
            try:
                from PyQt6.QtTextToSpeech import QTextToSpeech
                self.tts = QTextToSpeech(self)
            except Exception as e:
                logging.error(f"Failed to initialize QTextToSpeech: {e}")
                self.tts = None
                
        if self.tts:
            try:
                self.tts.stop()
                
                # Check characters to determine locale (defaulting to English if Latin, Russian if Cyrillic)
                import re
                if re.search(r'[\u0400-\u04FF]', self.current_original):
                    from PyQt6.QtCore import QLocale
                    self.tts.setLocale(QLocale("ru_RU"))
                else:
                    from PyQt6.QtCore import QLocale
                    self.tts.setLocale(QLocale("en_US"))
                    
                self.tts.say(self.current_original)
            except Exception as e:
                logging.error(f"Error during speech synthesis: {e}")

    def position_popup(self, anchor_pos):
        """Move the popup to be centered horizontally above the anchor point."""
        self.adjustSize()
        w = self.width()
        h = self.height()
        
        # Determine current screen based on anchor point
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.screenAt(anchor_pos)
        if not screen:
            screen = QApplication.primaryScreen()
            
        screen_geo = screen.availableGeometry()

        target_x = anchor_pos.x() - w // 2
        # Align bottom of popup near the top of the word/phrase (with a tiny 4px safety gap)
        target_y = anchor_pos.y() - h - 4

        # Clamp inside screen boundary
        margin = 15
        target_x = max(screen_geo.left() + margin, min(target_x, screen_geo.right() - w - margin))
        target_y = max(screen_geo.top() + margin, min(target_y, screen_geo.bottom() - h - margin))

        self.move(target_x, target_y)

    def leaveEvent(self, event):
        from PyQt6.QtGui import QCursor
        # Only handle leave event if mouse is actually outside the popup geometry
        if not self.rect().contains(self.mapFromGlobal(QCursor.pos())):
            self.hide()
            self.mouseLeft.emit()
        super().leaveEvent(event)

    def enterEvent(self, event):
        self.hide_timer.stop()
        super().enterEvent(event)

    def hideEvent(self, event):
        super().hideEvent(event)
        parent = self.parent()
        if parent and hasattr(parent, "_apply_secondary_visibility"):
            parent._apply_secondary_visibility()
