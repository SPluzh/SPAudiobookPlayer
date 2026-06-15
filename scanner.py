import os
import sqlite3
import re
import time
from pathlib import Path
import configparser
import json
import sys
import hashlib
import shutil
from concurrent.futures import ThreadPoolExecutor

from database import init_database
from lang_detector import detect as detect_language
from PyQt6.QtGui import QImage
from PyQt6.QtCore import Qt

# Ensure correct UTF-8 output in Windows console
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass


class AudiobookScanner:
    """Library scanner for processing audiobook directories and metadata"""
    
    def _log(self, message: str, end: str = '\n'):
        """Helper to print formatted messages"""
        if getattr(self, '_last_was_progress', False) and not message.startswith('\r'):
            # Clear progress line from both console and GUI
            print("\r" + " " * 90 + "\r", end="", flush=True)
            self._last_was_progress = False
        if message.startswith('\r'):
            self._last_was_progress = True
        print(message, end=end, flush=True)

    def _log_header(self, title: str):
        """Print a centered header"""
        self._log("\n" + "=" * 60)
        self._log(f"{title:^60}")
        self._log("=" * 60)

    def _log_section(self, title: str):
        """Print a section header"""
        self._log("\n" + "-" * 60)
        self._log(f" {title}")
        self._log("-" * 60)

    def _log_item(self, key: str, value: str = '', indent: int = 1):
        """Print a key-value item"""
        prefix = "  " * indent
        if value:
            self._log(f"{prefix}• {key}: {value}")
        else:
            self._log(f"{prefix}• {key}")
            
    def _log_info(self, message: str, indent: int = 1):
        """Print an informational message"""
        prefix = "  " * indent
        self._log(f"{prefix}{message}")

    def _log_success(self, message: str, indent: int = 1):
        """Print a success message"""
        prefix = "  " * indent
        self._log(f"{prefix}[OK] {message}")

    def _log_warn(self, message: str, indent: int = 1):
        """Print a warning message"""
        prefix = "  " * indent
        self._log(f"{prefix}[!] {message}")

    def _log_error(self, message: str, indent: int = 1):
        """Print an error message"""
        prefix = "  " * indent
        self._log(f"{prefix}[ERROR] {message}")

    def __init__(self, config_file='settings.ini'):
        """Initialize scanner and load configurations"""
        self.script_dir = Path(__file__).parent
        
        config_path = Path(config_file)
        if config_path.is_absolute():
            self.config_file = config_path
        else:
            self.config_file = self.script_dir / 'resources' / config_file
        
        # Load settings
        self._load_settings()
        
        # Paths
        db_path_str = self.config.get('Paths', 'database', fallback='data/audiobooks.db')
        self.db_file = Path(db_path_str)
        if not self.db_file.is_absolute():
            self.db_file = self.script_dir / self.db_file
        
        covers_dir_str = self.config.get('Paths', 'covers_dir', fallback='data/extracted_covers')
        self.covers_dir = Path(covers_dir_str)
        if not self.covers_dir.is_absolute():
            self.covers_dir = self.script_dir / self.covers_dir
        
        # Load translations
        self._load_translations()
        
        self._log_header(self.tr("scanner.init_title"))
        
        # ffprobe path
        path_str = self.config.get('Paths', 'ffprobe_path', fallback=str(self.script_dir / 'resources' / 'bin' / 'ffprobe.exe'))
        self.ffprobe_path = Path(path_str)
        if not self.ffprobe_path.is_absolute():
            self.ffprobe_path = self.script_dir / self.ffprobe_path
        self.has_ffprobe = self.ffprobe_path.exists()
        
        self._log_section(self.tr("scanner.working_paths"))
        self._log_item("Script", str(self.script_dir))
        self._log_item("Config", str(self.config_file))
        self._log_item("Database", str(self.db_file))
        self._log_item("Covers", str(self.covers_dir))
        
        if self.has_ffprobe:
            self._log_success(self.tr("scanner.ffprobe_found", path=self.ffprobe_path))
        else:
            self._log_warn(self.tr("scanner.ffprobe_not_found"))
        
        self.covers_dir.mkdir(exist_ok=True)
        self._print_settings_summary()
        self._init_database()

    def _load_translations(self):
        """Load translation file based on configuration"""
        lang = self.config.get('Display', 'language', fallback='ru')
        trans_file = self.script_dir / 'resources' / 'translations' / f'{lang}.json'
        
        self.translations = {}
        if trans_file.exists():
            try:
                with open(trans_file, 'r', encoding='utf-8') as f:
                    self.translations = json.load(f)
            except Exception as e:
                print(f"Error loading translations: {e}")
                
    def tr(self, key: str, **kwargs) -> str:
        """Translate string by key"""
        parts = key.split('.')
        data = self.translations
        for p in parts:
            if isinstance(data, dict) and p in data:
                data = data[p]
            else:
                return key  # Return key if translation not found
        
        if isinstance(data, str):
            try:
                return data.format(**kwargs)
            except KeyError:
                return data
        return key


    def _load_settings(self):
        """Load scanner settings from config file"""
        config = configparser.ConfigParser()
        config.read(self.config_file, encoding='utf-8')
        self.config = config
        
        extensions = config.get(
            'Audio',
            'extensions',
            fallback='.mp3,.m4a,.m4b,.mp4,.ogg,.flac,.wav,.aac,.wma,.opus,.ape'
        )
        self.audio_extensions = {e.strip().lower() for e in extensions.split(',') if e.strip()}
        
        covers = config.get(
            'Covers',
            'names',
            fallback='cover.jpg,cover.png,cover.jpeg,cover.webp,folder.jpg,folder.png,folder.webp'
        )
        self.cover_names = [c.strip() for c in covers.split(',') if c.strip()]

    def _print_settings_summary(self):
        """Print summary of loaded settings"""
        self._log_section(self.tr("scanner.loading_settings"))
        
        self._log(f"  • {self.tr('scanner.audio_formats', count=len(self.audio_extensions))}")
        self._log(f"    {', '.join(sorted(self.audio_extensions))}")
        
        self._log(f"  • {self.tr('scanner.cover_names', count=len(self.cover_names))}")
        for name in self.cover_names:
            self._log(f"    - {name}")


    def _init_database(self):
        """Initialize database schema"""
        self._log_section(self.tr("scanner.db_init"))
        
        init_database(self.db_file)
        
        self._log_success(self.tr("scanner.db_tables_ready"))
        self._log_success(self.tr("scanner.db_indexes_ready"))
        self._log_success(self.tr("scanner.db_cascade_on"))


    @staticmethod
    def _fix_encoding(text):
        """Correct text encoding issues (e.g., CP1251 read as Latin-1)"""
        if not text or not isinstance(text, str):
            return text
            
        try:
            # Check for characters from extended Latin (128-255) often appearing 
            # if CP1251 is incorrectly read as Latin-1
            if any(128 <= ord(c) <= 255 for c in text):
                # Attempt to re-encode from Latin-1 and decode as CP1251
                fixed = text.encode('latin-1').decode('cp1251')
                # If Cyrillic characters appear, correction was likely successful
                if any(1040 <= ord(c) <= 1103 for c in fixed): # A-я in Unicode
                    # Ensure no single word contains both Latin and Cyrillic characters,
                    # which would indicate a false correction on accented Latin characters
                    words = re.findall(r'[A-Za-z\u0400-\u04FF\u0401\u0451]+', fixed)
                    has_mixed = False
                    for w in words:
                        has_latin = any(('a' <= c <= 'z') or ('A' <= c <= 'Z') for c in w)
                        has_cyrillic = any('\u0400' <= c <= '\u04FF' or c in '\u0401\u0451' for c in w)
                        if has_latin and has_cyrillic:
                            has_mixed = True
                            break
                    if not has_mixed:
                        return fixed
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
            
        return text

    @staticmethod
    def _parse_audiobook_name(folder_name):
        """Parse audiobook folder name into author, title, and narrator"""
        folder_name_clean = folder_name.strip()
        
        def extract_last_bracket(s):
            if not s:
                return None, s
            s = s.strip()
            if not (s.endswith(')') or s.endswith(']')):
                return None, s
            
            closing = s[-1]
            opening = '(' if closing == ')' else '['
            
            balance = 0
            for i in range(len(s) - 1, -1, -1):
                if s[i] == closing:
                    balance += 1
                elif s[i] == opening:
                    balance -= 1
                    if balance == 0:
                        # Found the matching opening bracket
                        bracket_content = s[i+1:-1]
                        remaining_content = s[:i].strip()
                        return bracket_content, remaining_content
            return None, s

        narrator_parts = []
        
        # Extract brackets from right to left
        while True:
            bracket_content, remaining = extract_last_bracket(folder_name_clean)
            if bracket_content is None:
                break
                
            folder_name_clean = remaining
            
            # Split by commas
            parts = [p.strip() for p in bracket_content.split(',')]
            
            cleaned_parts = []
            for part in parts:
                # Check if it's NOT technical info
                is_technical = (
                    re.match(r'^\d{4}$', part) or  # Year
                    any(kw in part.lower() for kw in ['kbps', 'mp3', 'm4b', 'flac', 'ogg', 'wav', 'opus', 'ape', 'aac'])
                )
                
                if not is_technical:
                    # Remove "narrated by" or equivalent prefixes
                    p_clean = re.sub(r'^(чит\.|читает)\s+', '', part, flags=re.IGNORECASE).strip()
                    
                    # Remove studio abbreviations in brackets if present
                    if re.search(r'\([А-ЯA-Z]{2,5}\)$', p_clean):
                        p_clean = re.sub(r'\s*\([А-ЯA-Z]{2,5}\)$', '', p_clean).strip()
                    
                    if p_clean:
                        cleaned_parts.append(p_clean)
            
            if cleaned_parts:
                # Insert at the beginning since we are extracting from right to left
                narrator_parts = cleaned_parts + narrator_parts
                
        narrator = ", ".join(narrator_parts)
        
        # Split author and title by dash/hyphen
        m2 = re.split(r'\s*[–—-]\s*', folder_name_clean, maxsplit=1)
        if len(m2) == 2:
            author, title = m2
        else:
            author = ''
            title = folder_name_clean
        
        return author.strip(), title.strip(), narrator.strip()

    @staticmethod
    def _detect_language(folder_name):
        """Detect audiobook language from folder name using lang_detector.
        
        Returns:
            ISO 639-1 language code (e.g. 'ru', 'en') or 'unknown'.
            Never raises exceptions.
        """
        try:
            return detect_language(folder_name)
        except Exception:
            return 'unknown'

    def _extract_orig_year(self, file_path):
        """Extract original publication year from audio file tags.
        
        Reads TDOR/TORY (MP3), ©opd/original_release_date (M4B),
        original_date (FLAC), Original Year (APE).
        
        Returns:
            Year string (e.g. '1978') or None if not found.
        """
        try:
            from mutagen import File
            audio = File(file_path)
            if not audio:
                return None

            suffix = Path(file_path).suffix.lower()
            orig_year = None

            if suffix == '.mp3':
                id3 = audio.tags
                if id3:
                    orig_year = id3.get('TDOR') or id3.get('TORY')
            elif suffix in ('.m4a', '.m4b', '.mp4'):
                orig_year = (audio.get('\xa9opd') or
                             audio.get('original_release_date') or
                             audio.get('original-release-date'))
            elif suffix == '.flac':
                orig_year = (audio.get('original_release_date') or
                             audio.get('original_date') or
                             audio.get('original_year') or
                             audio.get('ORIGINAL_RELEASE_DATE') or
                             audio.get('ORIGINAL_DATE') or
                             audio.get('ORIGINAL_YEAR'))
            elif suffix == '.ape':
                orig_year = (audio.get('Original Year') or
                             audio.get('original year'))

            if orig_year:
                return str(orig_year[0] if isinstance(orig_year, list) else orig_year).strip()
        except Exception:
            pass
        return None

    @staticmethod
    def _parse_years(folder_name, rec_tag, orig_tag):
        """Determine book writing year and audiobook recording year.

        Sources (all combined):
          1. rec_tag  — recording year from audio tags (TDRC, ©day, date, Year)
          2. orig_tag — original publication year from audio tags (TDOR, ©opd, original_date)
          3. folder_name — all 4-digit years found anywhere in the folder name

        Logic:
          - If ≥ 2 years found → smallest = year_written, largest = year_recorded.
          - If 1 year found:
              · year ≥ 2000 OR audio keyword nearby → year_recorded
              · otherwise → year_written

        Returns:
            (year_written, year_recorded) — strings like '2008' or None.
        """
        import datetime
        current_year = datetime.date.today().year

        tag_years = set()
        for tag in (rec_tag, orig_tag):
            if tag:
                for y in re.findall(r'\b\d{4}\b', tag):
                    if 1800 <= int(y) <= current_year:
                        tag_years.add(int(y))

        # Scan folder name for 4-digit years and detect audio context
        folder_years = []
        for match in re.finditer(r'\b\d{4}\b', folder_name):
            y_val = int(match.group(0))
            if 1800 <= y_val <= current_year:
                pos = match.start()
                context = folder_name[max(0, pos - 30):min(len(folder_name), pos + 30)]
                is_audio = any(kw in context.lower() for kw in [
                    'чит', 'гол', 'кня', 'клю', 'кир', 'ав', 'ауди', 'изд',
                    'kbps', 'mp3', 'm4b', 'flac', 'мелод'
                ])
                folder_years.append((y_val, is_audio))

        all_years = list(tag_years)
        for y, _ in folder_years:
            if y not in all_years:
                all_years.append(y)
        all_years.sort()

        year_written = None
        year_recorded = None

        if len(all_years) >= 2:
            year_written  = str(all_years[0])
            year_recorded = str(all_years[-1])
        elif len(all_years) == 1:
            single_year = all_years[0]
            is_aud = next((is_a for y, is_a in folder_years if y == single_year), False)
            if is_aud or single_year >= 2000:
                year_recorded = str(single_year)
            else:
                year_written = str(single_year)

        return year_written, year_recorded
    
    
    def _extract_file_tags(self, file_path):
        """Extract metadata tags from a specific audio file"""
        tags = {
            'title': '',
            'author': '',
            'album': '',
            'year': '',
            'genre': '',
            'comment': '',
            'narrator': '',
            'track': None
        }
        
        try:
            from mutagen import File
        except ImportError:
            return tags
            
        try:
            audio = File(file_path)
            if not audio:
                return tags
                
            suffix = file_path.suffix.lower()
            
            if suffix == '.mp3':
                # MP3 (ID3)
                id3 = audio.tags
                if id3:
                    tags['title'] = self._fix_encoding(str(id3.get('TIT2', ''))).strip()
                    tags['author'] = self._fix_encoding(str(id3.get('TPE1', ''))).strip()
                    tags['album'] = self._fix_encoding(str(id3.get('TALB', ''))).strip()
                    tags['year'] = self._fix_encoding(str(id3.get('TDRC', ''))).strip()
                    tags['genre'] = self._fix_encoding(str(id3.get('TCON', ''))).strip()
                    
                    # Narrator tags (TPE2 or TOPE)
                    narrator = id3.get('TPE2') or id3.get('TOPE')
                    if not narrator:
                        for tag in id3.values():
                            if hasattr(tag, 'desc') and tag.desc.lower() in ('narrator', 'reader', 'narrated by'):
                                narrator = tag.text[0]
                                break
                    if narrator:
                        tags['narrator'] = self._fix_encoding(str(narrator)).strip()
                    
                    # Comment
                    comm = id3.get('COMM::eng') or id3.get('COMM')
                    if comm:
                        tags['comment'] = self._fix_encoding(str(comm)).strip()
                        
                    # Track number
                    trck = str(id3.get('TRCK', ''))
                    if trck:
                        try:
                            # Handle "1/10" format
                            tags['track'] = int(trck.split('/')[0])
                        except:
                            pass
                            
            elif suffix in ('.m4a', '.m4b', '.mp4'):
                # MP4/M4B
                t_title = audio.get('\xa9nam')
                if t_title: tags['title'] = self._fix_encoding(str(t_title[0])).strip()
                
                t_author = audio.get('\xa9ART') or audio.get('\xa9alb')
                if t_author: tags['author'] = self._fix_encoding(str(t_author[0])).strip()
                
                t_album = audio.get('\xa9alb')
                if t_album: tags['album'] = self._fix_encoding(str(t_album[0])).strip()
                
                t_year = audio.get('\xa9day')
                if t_year: tags['year'] = self._fix_encoding(str(t_year[0])).strip()
                
                t_genre = audio.get('\xa9gen')
                if t_genre: tags['genre'] = self._fix_encoding(str(t_genre[0])).strip()
                
                t_comment = audio.get('\xa9cmt')
                if t_comment: tags['comment'] = self._fix_encoding(str(t_comment[0])).strip()
                
                t_narrator = audio.get('\xa9nrt') or audio.get('composer') or audio.get('aART')
                if t_narrator: tags['narrator'] = self._fix_encoding(str(t_narrator[0])).strip()
                
                # Track number
                trkn = audio.get('trkn')
                if trkn and isinstance(trkn, list) and len(trkn[0]) > 0:
                    tags['track'] = trkn[0][0]

            elif suffix == '.flac':
                # FLAC (Vorbis comments)
                tags['title'] = self._fix_encoding(str(audio.get('title', [''])[0])).strip()
                tags['author'] = self._fix_encoding(str(audio.get('artist', [''])[0])).strip()
                tags['album'] = self._fix_encoding(str(audio.get('album', [''])[0])).strip()
                tags['year'] = self._fix_encoding(str(audio.get('date', [''])[0])).strip()
                tags['genre'] = self._fix_encoding(str(audio.get('genre', [''])[0])).strip()
                tags['comment'] = self._fix_encoding(str(audio.get('comment', [''])[0])).strip()
                
                # Narrator (check common tags)
                narrator = audio.get('narrator') or audio.get('composer') or audio.get('performer')
                if narrator:
                    tags['narrator'] = self._fix_encoding(str(narrator[0])).strip()
                    
                # Track number
                track = audio.get('tracknumber')
                if track:
                    try:
                        tags['track'] = int(str(track[0]).split('/')[0])
                    except:
                        pass

            elif suffix == '.ape':
                # APE (APEv2)
                tags['title'] = self._fix_encoding(str(audio.get('Title', [''])[0])).strip()
                tags['author'] = self._fix_encoding(str(audio.get('Artist', [''])[0])).strip()
                tags['album'] = self._fix_encoding(str(audio.get('Album', [''])[0])).strip()
                tags['year'] = self._fix_encoding(str(audio.get('Year', [''])[0])).strip()
                tags['genre'] = self._fix_encoding(str(audio.get('Genre', [''])[0])).strip()
                tags['comment'] = self._fix_encoding(str(audio.get('Comment', [''])[0])).strip()
                
                # Narrator (check common tags)
                narrator = audio.get('Reader') or audio.get('Narrator') or audio.get('Composer')
                if narrator:
                    tags['narrator'] = self._fix_encoding(str(narrator[0])).strip()
                    
                # Track number
                track = audio.get('Track')
                if track:
                    try:
                        tags['track'] = int(str(track[0]).split('/')[0])
                    except:
                        pass

        except Exception:
            pass
            
        # Cleanup values
        for key in tags:
            if isinstance(tags[key], str) and tags[key].lower() in ('none', '[none]', 'unknown', ''):
                tags[key] = ''
                
        return tags

    def _extract_chapters(self, file_path):
        """Extract chapters from an audio file using ffprobe"""
        chapters = []
        if not self.has_ffprobe:
            return chapters
            
        try:
            import subprocess
            startupinfo = None
            if hasattr(subprocess, 'STARTUPINFO'):
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            cmd = [
                str(self.ffprobe_path),
                '-v', 'error',
                '-show_chapters',
                '-of', 'json',
                str(file_path)
            ]
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                encoding='utf-8', 
                timeout=10, 
                startupinfo=startupinfo
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                for chap in data.get('chapters', []):
                    # We need start_time, end_time, and tags (title)
                    start = float(chap.get('start_time', 0))
                    end = float(chap.get('end_time', 0))
                    title = chap.get('tags', {}).get('title', '')
                    
                    if end > start:
                        chapters.append({
                            'title': title,
                            'start': start,
                            'duration': end - start
                        })
        except Exception:
            pass
            
        return chapters

    def _parse_cue_file(self, cue_path):
        """Parse a .cue file to extract metadata and chapters"""
        metadata = {'author': '', 'title': '', 'year': '', 'narrator': ''}
        chapters = []
        
        if not os.path.exists(cue_path):
            return metadata, chapters
            
        try:
            # Use smart text reader for .cue files
            content = self._read_text_file(cue_path)
            
            if not content:
                return metadata, chapters
                
            current_track = None
            
            for line in content.splitlines():
                line = line.strip()
                if not line: continue
                
                # Global metadata
                if not current_track:
                    if line.startswith('PERFORMER '):
                        metadata['author'] = line[10:].strip('"')
                    elif line.startswith('TITLE '):
                        metadata['title'] = line[6:].strip('"')
                    elif line.startswith('REM DATE '):
                        metadata['year'] = line[9:].strip()
                
                # Tracks
                if line.startswith('TRACK '):
                    parts = line.split()
                    if len(parts) >= 2:
                        current_track = {
                            'index': parts[1],
                            'title': '',
                            'author': metadata['author'],
                            'start': 0.0
                        }
                        chapters.append(current_track)
                elif current_track:
                    if line.startswith('TITLE '):
                        current_track['title'] = line[6:].strip('"')
                    elif line.startswith('PERFORMER '):
                        current_track['author'] = line[10:].strip('"')
                    elif line.startswith('INDEX 01 '):
                        time_str = line[9:].strip()
                        # format MM:SS:FF (FF is 1/75th of a second)
                        time_parts = time_str.split(':')
                        if len(time_parts) == 3:
                            try:
                                mins = int(time_parts[0])
                                secs = int(time_parts[1])
                                frames = int(time_parts[2])
                                current_track['start'] = mins * 60 + secs + frames / 75.0
                            except ValueError:
                                pass
            
            # Calculate durations for chapters
            for i in range(len(chapters)):
                if i < len(chapters) - 1:
                    chapters[i]['duration'] = chapters[i+1]['start'] - chapters[i]['start']
                else:
                    chapters[i]['duration'] = 0 # To be filled later with file duration if needed
                    
        except Exception as e:
            print(f"Error parsing .cue file: {e}")
            
        return metadata, chapters

    def _extract_metadata(self, directory, files):
        """Extract metadata for the audiobook by checking .cue files or first few audio files"""
        metadata = {'author': '', 'title': '', 'narrator': '', 'year': ''}
        
        # 1. Try .cue files first
        cue_files = list(directory.glob('*.cue'))
        if cue_files:
            cue_meta, _ = self._parse_cue_file(cue_files[0])
            if cue_meta['author']: metadata['author'] = cue_meta['author']
            if cue_meta['title']: metadata['title'] = cue_meta['title']
            if cue_meta['year']: metadata['year'] = cue_meta['year']
            
            if all(metadata.values()):
                return metadata

        if not files:
            return metadata
            
        for f in files[:3]:
            tags = self._extract_file_tags(f)
            
            if not metadata['author']: metadata['author'] = tags['author']
            if not metadata['title']: metadata['title'] = tags['album'] or tags['title']
            if not metadata['narrator']: metadata['narrator'] = tags['narrator']
            if not metadata['year']: metadata['year'] = tags['year']
            
            # Exit if all metadata found
            if all(metadata.values()):
                break
                
        return metadata

    def _has_audio_files(self, directory):
        """Check if directory contains supported audio files"""
        try:
            for f in directory.iterdir():
                if f.is_file() and f.suffix.lower() in self.audio_extensions:
                    return True
            return False
        except PermissionError:
            return False

    def _find_playlist_files(self, folder: Path) -> list:
        """Find all .m3u/.m3u8 files in folder (not recursive)"""
        m3u_files = []
        for ext in ('*.m3u', '*.m3u8'):
            try:
                m3u_files.extend(folder.glob(ext))
            except Exception:
                pass
        return sorted(m3u_files)

    def _parse_m3u_file(self, m3u_path: Path) -> list:
        """
        Parse M3U/M3U8 playlist.
        Returns: [{'path': str, 'title': str, 'duration': float, 'is_url': bool}, ...]
        """
        entries = []
        content = None
        for encoding in ['utf-8', 'utf-8-sig', 'cp1251', 'latin-1']:
            try:
                content = m3u_path.read_text(encoding=encoding)
                break
            except Exception:
                continue
        if not content:
            return []

        lines = content.splitlines()
        current_title = ''
        current_duration = -1

        for line in lines:
            line = line.strip()
            if not line or (line.startswith('#') and not line.startswith('#EXTINF')):
                continue
            if line.startswith('#EXTINF'):
                match = re.match(r'#EXTINF:\s*(-?\d+)\s*,\s*(.*)', line)
                if match:
                    current_duration = float(match.group(1))
                    current_title = match.group(2).strip()
                continue

            file_path = line
            is_url = file_path.startswith(('http://', 'https://'))

            if is_url:
                entries.append({
                    'path': file_path,
                    'title': current_title or Path(file_path).name,
                    'duration': current_duration if current_duration > 0 else 0.0,
                    'is_url': True
                })
            else:
                if '://' in file_path:
                    current_title = ''
                    current_duration = -1
                    continue
                p_obj = Path(file_path)
                if not p_obj.is_absolute():
                    resolved = (m3u_path.parent / p_obj).resolve()
                else:
                    resolved = p_obj
                
                if resolved.exists() and resolved.suffix.lower() in self.audio_extensions:
                    entries.append({
                        'path': str(resolved),
                        'title': current_title or resolved.name,
                        'duration': current_duration if current_duration > 0 else 0.0,
                        'is_url': False
                    })
            current_title = ''
            current_duration = -1

        return entries

    def _get_url_duration_fast(self, url: str) -> dict:
        """
        Quickly estimate duration of URL file using a single HTTP GET request with Range.
        Returns: {'duration': float, 'size': int, 'bitrate': int, 'codec': str}
        """
        import urllib.request
        import io
        from urllib.parse import urlparse

        res = {
            'duration': 0.0,
            'size': 0,
            'bitrate': 0,
            'codec': 'Unknown'
        }

        try:
            req = urllib.request.Request(url)
            # Fetch 256KB to be safe with larger ID3 headers
            req.add_header('Range', 'bytes=0-262143')
            req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

            with urllib.request.urlopen(req, timeout=10) as resp:
                status = getattr(resp, 'status', 200)
                headers = resp.headers
                if status == 200:
                    chunk = resp.read(262144)
                else:
                    chunk = resp.read()

            content_range = headers.get('Content-Range', '')
            content_length = int(headers.get('Content-Length', 0))
            total_size = 0

            if status == 206 and content_range:
                match = re.search(r'/(\d+)', content_range)
                if match:
                    total_size = int(match.group(1))
            else:
                total_size = content_length

            res['size'] = total_size

            if not chunk or total_size == 0:
                return res

            buf = io.BytesIO(chunk)
            
            parsed = urlparse(url)
            suffix = Path(parsed.path).suffix.lower()

            # Try parser based on suffix first, fallback to try-all
            parsers_to_try = []
            if suffix == '.mp3':
                parsers_to_try = ['mp3', 'mp4']
            elif suffix in ('.m4a', '.m4b', '.mp4', '.aac'):
                parsers_to_try = ['mp4', 'mp3']
            elif suffix == '.flac':
                parsers_to_try = ['flac', 'mp3']
            elif suffix == '.ogg':
                parsers_to_try = ['ogg', 'mp3']
            else:
                parsers_to_try = ['mp3', 'mp4']

            parsed_ok = False
            for ptype in parsers_to_try:
                try:
                    if ptype == 'mp3':
                        from mutagen.mp3 import MP3
                        buf.seek(0)
                        audio = MP3(buf)
                        res['codec'] = 'MP3'
                        if audio.info.bitrate > 0:
                            res['bitrate'] = int(audio.info.bitrate)
                        
                        # Calculate duration
                        if audio.info.length > 0:
                            est_duration = total_size / (audio.info.bitrate / 8) if audio.info.bitrate > 0 else 0
                            if audio.info.length > est_duration * 0.9:
                                res['duration'] = audio.info.length
                            elif est_duration > 0:
                                # Subtract 4KB ID3 tag average
                                res['duration'] = max(0.0, (total_size - 4096) / (audio.info.bitrate / 8))
                        parsed_ok = True
                        break

                    elif ptype == 'mp4':
                        from mutagen.mp4 import MP4
                        buf.seek(0)
                        audio = MP4(buf)
                        res['codec'] = 'MP4/M4A'
                        if audio.info.bitrate > 0:
                            res['bitrate'] = int(audio.info.bitrate)
                        if audio.info.length > 0:
                            res['duration'] = audio.info.length
                        parsed_ok = True
                        break

                    elif ptype == 'flac':
                        from mutagen.flac import FLAC
                        buf.seek(0)
                        audio = FLAC(buf)
                        res['codec'] = 'FLAC'
                        if audio.info.bitrate > 0:
                            res['bitrate'] = int(audio.info.bitrate)
                        if audio.info.length > 0:
                            res['duration'] = audio.info.length
                        parsed_ok = True
                        break

                    elif ptype == 'ogg':
                        from mutagen.oggvorbis import OggVorbis
                        buf.seek(0)
                        audio = OggVorbis(buf)
                        res['codec'] = 'OGG'
                        if audio.info.bitrate > 0:
                            res['bitrate'] = int(audio.info.bitrate)
                        if audio.info.length > 0:
                            res['duration'] = audio.info.length
                        parsed_ok = True
                        break

                except Exception:
                    pass

            if not parsed_ok:
                # Last resort: check if starts with ID3
                if chunk.startswith(b'ID3') and len(chunk) >= 10:
                    res['codec'] = 'MP3'
                    res['bitrate'] = 128000
                    res['duration'] = (total_size - 4096) / 16000.0

        except Exception:
            pass

        return res

    def _save_playlist_as_book(self, m3u_path, book_path, parent_path, name, root, conn, verbose=False):
        """Save playlist as audiobook in the database"""
        c = conn.cursor()
        self._log("")
        self._log_info(self.tr("scanner.m3u_parsing", name=name), indent=2)
        entries = self._parse_m3u_file(m3u_path)
        if not entries:
            return

        self._log_info(self.tr("scanner.m3u_files_loaded", count=len(entries)), indent=2)
        rel_m3u = str(m3u_path.relative_to(root))

        f_author, f_title, f_narrator = self._parse_audiobook_name(name)

        # Detect language from folder/playlist name
        language = self._detect_language(name)

        # Parse writing year and recording year from playlist name (no tag access)
        year_written, year_recorded = self._parse_years(name, None, None)

        folder_of_m3u = m3u_path.parent
        parent_cover_file = None
        try:
            if parent_path != '':
                parent_folder = folder_of_m3u.parent
                if parent_folder != folder_of_m3u:
                    parent_cover_file = self._find_cover_file_only(parent_folder)
        except Exception:
            pass

        try:
            stat = m3u_path.stat()
            state_info = [f"M3U|{rel_m3u}|{stat.st_size}|{stat.st_mtime}", f"LANG|{language}"]
            
            cover_files = []
            if parent_cover_file:
                cover_files.append(parent_cover_file)
            
            root_covers = self._find_all_root_cover_files(folder_of_m3u)
            for rc in root_covers:
                if rc not in cover_files:
                    cover_files.append(rc)
                    
            for c_file in cover_files:
                try:
                    cover_path = Path(c_file)
                    if cover_path.exists():
                        c_stat = cover_path.stat()
                        state_info.append(f"COVER|{cover_path.name}|{c_stat.st_size}|{c_stat.st_mtime}")
                except Exception:
                    pass
                    
            state_str = "\n".join(sorted(state_info))
            current_state_hash = hashlib.md5(state_str.encode()).hexdigest()
        except Exception:
            current_state_hash = ''

        c.execute("SELECT id, state_hash FROM audiobooks WHERE path = ?", (book_path,))
        existing = c.fetchone()
        if existing and existing[1] == current_state_hash:
            c.execute("UPDATE audiobooks SET is_available = 1 WHERE id = ?", (existing[0],))
            return

        from collections import Counter
        sizes = []
        bitrates = []
        modes = []
        codecs = []

        for e in entries:
            # We already updated durations of local and URLs. Let's gather whatever size/bitrate/codec info we have.
            # Local entries analyzed:
            # Wait, local_paths info was merged into entries in local_entries loop above. Let's fetch from mutagen analysis if available.
            pass

        # Wait, since the local_entries loop above does not store size, bitrate, and codec back into the entries list, let's make sure it does!
        # Let's rewrite the analysis loop to store info in entries:
        local_entries = [(i, e) for i, e in enumerate(entries) if not e['is_url']]
        if local_entries:
            local_paths = [Path(e['path']) for _, e in local_entries]
            analyses = self._analyze_files_parallel(local_paths, conn=conn, max_workers=4)
            for (orig_idx, entry), info in zip(local_entries, analyses):
                if info:
                    if info.get('duration', 0) > 0:
                        entry['duration'] = info['duration']
                    entry['size'] = info.get('file_size', 0)
                    entry['bitrate'] = info.get('bitrate', 0)
                    entry['codec'] = info.get('codec', '').upper()
                    entry['mode'] = 'VBR' if info.get('is_vbr') else 'CBR'

        # Now url_entries_to_probe
        url_entries_to_probe = [e for e in entries if e['is_url'] and e['duration'] == 0]
        if url_entries_to_probe:
            total_urls = len(url_entries_to_probe)
            from concurrent.futures import as_completed

            workers = min(8, total_urls)
            futures = {}

            with ThreadPoolExecutor(max_workers=workers) as executor:
                for idx, entry in enumerate(url_entries_to_probe, 1):
                    future = executor.submit(self._get_url_duration_fast, entry['path'])
                    futures[future] = (idx, entry)

                for future in as_completed(futures):
                    idx, entry = futures[future]
                    try:
                        info = future.result()
                    except Exception:
                        info = {
                            'duration': 0.0,
                            'size': 0,
                            'bitrate': 0,
                            'codec': 'Unknown'
                        }

                    entry['duration'] = info['duration']
                    entry['size'] = info['size']
                    entry['bitrate'] = info['bitrate']
                    entry['codec'] = info['codec'].upper()
                    entry['mode'] = 'CBR'

                    # Format size
                    size_bytes = info['size']
                    if size_bytes >= 1024 * 1024:
                        size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
                    elif size_bytes > 0:
                        size_str = f"{size_bytes / 1024:.1f} KB"
                    else:
                        size_str = "Unknown"

                    # Format duration
                    dur_secs = info['duration']
                    h = int(dur_secs // 3600)
                    m = int((dur_secs % 3600) // 60)
                    s = int(dur_secs % 60)
                    if h > 0:
                        dur_str = f"{h}:{m:02d}:{s:02d}"
                    else:
                        dur_str = f"{m}:{s:02d}"

                    bitrate_val = f"{info['bitrate'] // 1000}" if info['bitrate'] > 0 else "Unknown"

                    self._log_info(
                        self.tr("scanner.probing_network_url", current=idx, total=total_urls, url=entry['path']),
                        indent=3
                    )
                    self._log_info(
                        self.tr(
                            "scanner.probing_url_details",
                            codec=info['codec'],
                            bitrate=bitrate_val,
                            duration=dur_str,
                            size=size_str
                        ),
                        indent=3
                    )

        # Aggregate tech info
        for entry in entries:
            if 'size' in entry and entry['size'] > 0:
                sizes.append(entry['size'])
            if 'bitrate' in entry and entry['bitrate'] > 0:
                bitrates.append(entry['bitrate'])
            if 'mode' in entry and entry['mode']:
                modes.append(entry['mode'])
            if 'codec' in entry and entry['codec'] and entry['codec'] != 'UNKNOWN':
                codecs.append(entry['codec'])

        common_codec = Counter(codecs).most_common(1)[0][0] if codecs else 'M3U'
        bitrate_min = (min(bitrates) // 1000) if bitrates else 0
        bitrate_max = (max(bitrates) // 1000) if bitrates else 0
        bitrate_mode = Counter(modes).most_common(1)[0][0] if modes else None
        container_val = 'M3U'
        total_size_val = sum(sizes)

        total_duration = sum(e['duration'] for e in entries)
        file_count = len(entries)

        cover, cover_cached = self._find_cover(folder_of_m3u, book_path, parent_cover_file)

        if existing:
            book_id = existing[0]
            c.execute("""
                UPDATE audiobooks
                SET parent_path=?, name=?, author=?, title=?, narrator=?,
                    language=COALESCE(language, ?), year_written=?, year_recorded=?,
                    file_count=?, duration=?, is_folder=0,
                    is_playlist=1, playlist_path=?,
                    cover_path=?, cached_cover_path=?,
                    state_hash=?, is_available=1,
                    codec=?, bitrate_min=?, bitrate_max=?, bitrate_mode=?, container=?,
                    total_size=?
                WHERE path=?
            """, (parent_path, name, f_author, f_title, f_narrator,
                  language, year_written, year_recorded,
                  file_count, total_duration, rel_m3u,
                  cover, cover_cached, current_state_hash,
                  common_codec, bitrate_min, bitrate_max, bitrate_mode, container_val,
                  total_size_val, book_path))
        else:
            c.execute("""
                INSERT INTO audiobooks
                (path, parent_path, name, author, title, narrator,
                 language, year_written, year_recorded,
                 file_count, duration, is_folder, is_playlist, playlist_path,
                 cover_path, cached_cover_path, state_hash,
                 listened_duration, progress_percent, current_file_index,
                 current_position, playback_speed, is_started, is_completed,
                 is_available, codec, bitrate_min, bitrate_max, bitrate_mode, container,
                 total_size, time_added)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,0,1,?,?,?,?,0,0,0,0,1.0,0,0,1,?,?,?,?,?,?,CURRENT_TIMESTAMP)
            """, (book_path, parent_path, name, f_author, f_title, f_narrator,
                  language, year_written, year_recorded,
                  file_count, total_duration, rel_m3u,
                  cover, cover_cached, current_state_hash,
                  common_codec, bitrate_min, bitrate_max, bitrate_mode, container_val,
                  total_size_val))
            c.execute("SELECT id FROM audiobooks WHERE path = ?", (book_path,))
            book_id = c.fetchone()[0]

        self._scan_and_save_all_covers(conn, folder_of_m3u, book_path, book_id, cover_cached, parent_cover_file)

        c.execute("DELETE FROM audiobook_files WHERE audiobook_id = ?", (book_id,))
        files_batch = []
        for idx, entry in enumerate(entries, 1):
            files_batch.append((
                book_id,
                entry['path'] if entry['is_url'] else str(Path(entry['path']).relative_to(root)),
                Path(entry['path']).name if not entry['is_url'] else entry['title'],
                idx,
                entry['duration'],
                0.0,
                entry['title'],
                '', '', '', '',
                1 if entry['is_url'] else 0
            ))

        c.executemany("""
            INSERT INTO audiobook_files
            (audiobook_id, file_path, file_name, track_number, duration,
             start_offset, tag_title, tag_artist, tag_album, tag_genre, tag_comment, is_url)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, files_batch)

        # Log summary
        self._log_book_summary(
            title=f_title or name,
            author=f_author,
            narrator=f_narrator,
            duration=total_duration,
            file_count=file_count,
            codec=common_codec,
            bitrate=bitrate_max,
            bitrate_mode=bitrate_mode or '',
            cover=cover_cached,
            cue_count=0,
            problems=sum(1 for e in entries if e['duration'] == 0),
            language=language,
            year_written=year_written,
            year_recorded=year_recorded
        )

    def _process_playlist_in_folder(self, folder, root, m3u_files, conn, save_folder_callback, verbose=False):
        """Process playlist files in a folder"""
        rel_folder = folder.relative_to(root)

        save_as_folder = False
        if len(m3u_files) == 1:
            m3u_file = m3u_files[0]
            is_generic = m3u_file.stem.lower() in ('playlist', 'book', 'index') or m3u_file.stem == folder.name
            
            # Check for subdirectories
            has_subdirs = False
            try:
                for item in folder.iterdir():
                    if item.is_dir():
                        has_subdirs = True
                        break
            except Exception:
                pass
                
            has_audio = self._has_audio_files(folder)
            if is_generic and has_audio and not has_subdirs:
                save_as_folder = True

        if save_as_folder:
            m3u_file = m3u_files[0]
            parent = str(rel_folder.parent) if str(rel_folder.parent) != '.' else ''
            self._save_playlist_as_book(
                m3u_path=m3u_file,
                book_path=str(rel_folder),
                parent_path=parent,
                name=folder.name,
                root=root,
                conn=conn,
                verbose=verbose
            )
            if parent:
                save_folder_callback(parent)
        else:
            for m3u_file in m3u_files:
                rel_m3u = m3u_file.relative_to(root)
                self._save_playlist_as_book(
                    m3u_path=m3u_file,
                    book_path=str(rel_m3u),
                    parent_path=str(rel_folder),
                    name=m3u_file.stem,
                    root=root,
                    conn=conn,
                    verbose=verbose
                )
            save_folder_callback(str(rel_folder))

    def _get_cached_analysis(self, file_path: Path, conn) -> dict | None:
        """Check cache and return metadata if file hasn't changed"""
        try:
            stat = file_path.stat()
            # Use relative path if possible, otherwise absolute
            rel_path = str(file_path)
            
            c = conn.cursor()
            c.execute("""
                SELECT duration, bitrate, codec, is_vbr, file_size, mtime
                FROM file_metadata_cache
                WHERE file_path = ?
            """, (rel_path,))
            
            row = c.fetchone()
            if row:
                cached_size, cached_mtime = row[4], row[5]
                # Check if file has changed (allowing small float precision difference for mtime)
                if stat.st_size == cached_size and abs(stat.st_mtime - cached_mtime) < 0.01:
                    return {
                        'duration': row[0],
                        'bitrate': row[1],
                        'codec': row[2],
                        'is_vbr': bool(row[3]),
                        'needs_ffprobe': False
                    }
        except Exception:
            pass
        return None

    def _save_to_cache(self, file_path: Path, info: dict, conn):
        """Save analysis result to cache"""
        try:
            stat = file_path.stat()
            rel_path = str(file_path)
            
            c = conn.cursor()
            c.execute("""
                INSERT OR REPLACE INTO file_metadata_cache
                (file_path, file_size, mtime, duration, bitrate, codec, is_vbr, cached_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                rel_path,
                stat.st_size,
                stat.st_mtime,
                info['duration'],
                info['bitrate'],
                info['codec'],
                1 if info.get('is_vbr') else 0
            ))
        except Exception:
            pass

    def _analyze_file_fast(self, path, verbose=False):
        """
        Fast analysis of audio file using only mutagen.
        Returns: {'duration': float, 'bitrate': int, 'codec': str, 'is_vbr': bool, 'needs_ffprobe': bool}
        """
        info = {
            'duration': 0.0,
            'bitrate': 0,
            'codec': '',
            'is_vbr': False,
            'needs_ffprobe': False
        }
        
        try:
            from mutagen.mp3 import MP3, BitrateMode
            from mutagen.mp4 import MP4
            from mutagen.flac import FLAC
            from mutagen.oggvorbis import OggVorbis
            from mutagen.wave import WAVE
            
            suffix = path.suffix.lower()
            audio = None
            
            if suffix == '.mp3':
                audio = MP3(path)
                info['codec'] = 'mp3'
                if hasattr(audio.info, 'bitrate_mode'):
                    info['is_vbr'] = (audio.info.bitrate_mode == BitrateMode.VBR)
            elif suffix in ('.m4a', '.m4b', '.mp4', '.aac'):
                audio = MP4(path)
                info['codec'] = 'aac'
            elif suffix == '.flac':
                audio = FLAC(path)
                info['codec'] = 'flac'
            elif suffix == '.ogg':
                audio = OggVorbis(path)
                info['codec'] = 'vorbis'
            elif suffix == '.wav':
                audio = WAVE(path)
                info['codec'] = 'pcm'
            elif suffix == '.ape':
                try:
                    from mutagen.monkeysaudio import MonkeysAudio
                    audio = MonkeysAudio(path)
                    info['codec'] = 'ape'
                except: pass
            
            if audio and audio.info:
                if hasattr(audio.info, 'length'):
                    info['duration'] = audio.info.length
                if hasattr(audio.info, 'bitrate') and audio.info.bitrate:
                    info['bitrate'] = int(audio.info.bitrate)
        except Exception:
            info['needs_ffprobe'] = True
            
        if info['duration'] == 0 or not info['codec']:
             info['needs_ffprobe'] = True
             
        return info

    def _analyze_file_with_ffprobe(self, path, info, verbose=False):
        """Supplementary analysis using ffprobe only if needed"""
        if not self.has_ffprobe:
            return info
            
        try:
            import subprocess
            startupinfo = None
            if hasattr(subprocess, 'STARTUPINFO'):
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            cmd = [
                str(self.ffprobe_path),
                '-v', 'error',
                '-select_streams', 'a:0',
                '-show_entries', 'stream=codec_name:format=duration,bit_rate',
                '-of', 'json',
                str(path)
            ]
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                encoding='utf-8', 
                timeout=10, 
                startupinfo=startupinfo
            )
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                if info['duration'] == 0 and 'format' in data and 'duration' in data['format']:
                    try: info['duration'] = float(data['format']['duration'])
                    except: pass
                if info['bitrate'] == 0 and 'format' in data and 'bit_rate' in data['format']:
                    try: info['bitrate'] = int(data['format']['bit_rate'])
                    except: pass
                if not info['codec'] and 'streams' in data and data['streams']:
                    info['codec'] = data['streams'][0].get('codec_name', '')
        except Exception:
            pass
            
        return info

    def _analyze_file(self, path, verbose=False):
        """Combined analysis: fast path with mutagen, fallback to ffprobe"""
        info = self._analyze_file_fast(path, verbose)
        if info.pop('needs_ffprobe', False):
            info = self._analyze_file_with_ffprobe(path, info, verbose)
        return info

    def _analyze_files_parallel(self, files, conn=None, max_workers=4, verbose=False):
        """Analyze a list of files concurrently with caching"""
        if not files:
            return []
            
        results = [None] * len(files)
        files_to_analyze = []
        file_indices = []
        
        # 1. Check cache first
        if conn:
            for i, f in enumerate(files):
                cached = self._get_cached_analysis(f, conn)
                if cached:
                    results[i] = cached
                else:
                    files_to_analyze.append(f)
                    file_indices.append(i)
        else:
            files_to_analyze = files
            file_indices = list(range(len(files)))
            
        # 2. Analyze only non-cached files
        if files_to_analyze:
            workers = min(max_workers, len(files_to_analyze))
            with ThreadPoolExecutor(max_workers=workers) as executor:
                fast_results = list(executor.map(lambda f: self._analyze_file_fast(f, verbose), files_to_analyze))
                
            for idx, (f, info) in zip(file_indices, zip(files_to_analyze, fast_results)):
                if info.pop('needs_ffprobe', False):
                    info = self._analyze_file_with_ffprobe(f, info, verbose)
                
                # Save to cache
                if conn and info['duration'] > 0:
                    self._save_to_cache(f, info, conn)
                    
                results[idx] = info
            
        return results

    def _extract_cover_from_file(self, f, key):
        """Extract embedded cover from a specific file"""
        try:
            from mutagen.id3 import ID3, APIC
            from mutagen.mp4 import MP4
            from mutagen.flac import FLAC
            
            # Use MD5 hash of the key (path) to ensure stable cover filename
            safe_name = hashlib.md5(key.encode()).hexdigest()
            cover_path = self.covers_dir / f"{safe_name}.jpg"
            
            # Check directly if file exists
            if cover_path.exists():
                 return str(cover_path)

            img_data = None
            
            if f.suffix.lower() == '.mp3':
                tags = ID3(f)
                for tag in tags.values():
                    if isinstance(tag, APIC):
                        img_data = tag.data
                        break
            
            elif f.suffix.lower() in ('.m4a', '.m4b', '.mp4'):
                audio = MP4(f)
                if 'covr' in audio:
                    img_data = audio['covr'][0]
            
            elif f.suffix.lower() == '.flac':
                audio = FLAC(f)
                if audio.pictures:
                    img_data = audio.pictures[0].data
            elif f.suffix.lower() == '.ape':
                from mutagen.monkeysaudio import MonkeysAudio
                audio = MonkeysAudio(f)
                if 'Cover Art (Front)' in audio:
                    img_data = audio['Cover Art (Front)'].value
            
            if img_data:
                # Resize and save
                image = QImage.fromData(img_data)
                if not image.isNull():
                     scaled = image.scaled(300, 300, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                     scaled.save(str(cover_path), "JPG")
                     return str(cover_path)

        except Exception:
            pass
        
        return None

    def _extract_embedded_cover(self, directory, key):
        """Extract embedded cover image from audio files"""
        try:
            audio_files = sorted(
                f for f in directory.iterdir()
                if f.is_file() and f.suffix.lower() in self.audio_extensions
            )
            
            for f in audio_files[:3]:
                result = self._extract_cover_from_file(f, key)
                if result:
                    return result
        except Exception:
            pass
        return None
    
    def _find_cover(self, directory, key, parent_cover_file=None):
        """Find cover image (file or embedded) for the audiobook. Returns (original_path, cached_path)"""
        
        path_obj = Path(directory)
        
        # Case 0: Standalone file
        if path_obj.is_file():
             # Try embedded only
             embedded = self._extract_cover_from_file(path_obj, key)
             return None, embedded

        # Helper to cache a file
        def cache_file(src_path):
            try:
                src_path_obj = Path(src_path)
                if not src_path_obj.exists():
                    return None
                    
                ext = src_path_obj.suffix.lower()
                safe_name = hashlib.md5(key.encode()).hexdigest()
                dest_path = self.covers_dir / f"{safe_name}{ext}"
                
                # Check directly if file exists to avoid unnecessary copy
                if not dest_path.exists():
                    # Try to resize and save
                    image = QImage(str(src_path))
                    if not image.isNull():
                         scaled = image.scaled(300, 300, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                         scaled.save(str(dest_path))
                    else:
                         # Fallback to direct copy
                         shutil.copy2(src_path, dest_path)
                         
                return str(dest_path)
            except Exception as e:
                self._log_error(f"Error caching cover: {e}")
                try:
                    # Fallback to direct copy on error
                    ext = Path(src_path).suffix.lower()
                    safe_name = hashlib.md5(key.encode()).hexdigest()
                    dest_path = self.covers_dir / f"{safe_name}{ext}"
                    if not dest_path.exists():
                        shutil.copy2(src_path, dest_path)
                    return str(dest_path)
                except:
                    return None

        # 1. Search in current directory (priority names)
        for name in self.cover_names:
            p = directory / name
            try:
                if p.is_file():
                    cached = cache_file(str(p))
                    return str(p), cached
            except (PermissionError, OSError):
                continue
        
        # 2. Search in current directory (any image)
        try:
            for f in directory.iterdir():
                if f.is_file() and f.suffix.lower() in {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}:
                     cached = cache_file(str(f))
                     return str(f), cached
        except (PermissionError, OSError):
            pass
        
        # 2.5. Inherit cover from parent directory if provided
        if parent_cover_file:
            try:
                p_path = Path(parent_cover_file)
                if p_path.is_file():
                    cached = cache_file(str(p_path))
                    return str(p_path), cached
            except Exception:
                pass
        
        # 3. Recursive search in subdirectories (priority names)
        for name in self.cover_names:
            try:
                for p in directory.rglob(name):
                    if p.is_file():
                        cached = cache_file(str(p))
                        return str(p), cached
            except (PermissionError, OSError):
                continue
        
        # 4. Recursive search in subdirectories (any image)
        for ext in ('.jpg', '.jpeg', '.png', '.bmp', '.webp'):
            try:
                for p in directory.rglob(f"*{ext}"):
                    if p.is_file():
                        cached = cache_file(str(p))
                        return str(p), cached
            except (PermissionError, OSError):
                continue
        
        # 5. Fallback to embedded cover
        # Embedded cover extraction already handles caching/extraction to covers_dir
        embedded_path = self._extract_embedded_cover(directory, key)
        if embedded_path:
             # For embedded covers, we don't have an "original" file path, so return None for original
             return None, embedded_path
             
        return None, None

    def _get_embedded_image_data(self, f):
        """Extract raw embedded cover image data from a file"""
        try:
            from mutagen.id3 import ID3, APIC
            from mutagen.mp4 import MP4
            from mutagen.flac import FLAC
            
            suffix = f.suffix.lower()
            if suffix == '.mp3':
                tags = ID3(f)
                for tag in tags.values():
                    if isinstance(tag, APIC):
                        return tag.data
            elif suffix in ('.m4a', '.m4b', '.mp4'):
                audio = MP4(f)
                if 'covr' in audio:
                    return audio['covr'][0]
            elif suffix == '.flac':
                audio = FLAC(f)
                if audio.pictures:
                    return audio.pictures[0].data
            elif suffix == '.ape':
                from mutagen.monkeysaudio import MonkeysAudio
                audio = MonkeysAudio(f)
                if 'Cover Art (Front)' in audio:
                    return audio['Cover Art (Front)'].value
        except Exception:
            pass
        return None

    def _scan_and_save_all_covers(self, conn, directory, key, audiobook_id, selected_cover_cached_path, parent_cover_file=None):
        """
        Scan for all available covers, cache them, and save to audiobook_covers table.
        """
        c = conn.cursor()
        
        # Get existing covers to match them and preserve details before deleting
        selected_orig_path = None
        selected_source_type = None
        selected_cached_path = None
        
        try:
            c.execute("""
                SELECT original_path, cached_path, source_type, is_selected 
                FROM audiobook_covers 
                WHERE audiobook_id = ?
            """, (audiobook_id,))
            existing_covers = c.fetchall()
            
            for orig_p, cached_p, src_type, is_sel in existing_covers:
                if is_sel:
                    selected_orig_path = orig_p
                    selected_cached_path = cached_p
                    selected_source_type = src_type
                    break
                    
            if not selected_cached_path and selected_cover_cached_path:
                for orig_p, cached_p, src_type, is_sel in existing_covers:
                    if cached_p == selected_cover_cached_path:
                        selected_orig_path = orig_p
                        selected_cached_path = cached_p
                        selected_source_type = src_type
                        break
        except Exception as e:
            self._log_error(f"Error querying existing covers: {e}")
            existing_covers = []
            
        # 1. Clear existing covers for this audiobook to avoid duplicate entries
        c.execute("DELETE FROM audiobook_covers WHERE audiobook_id = ?", (audiobook_id,))
        
        path_obj = Path(directory)
        safe_name = hashlib.md5(key.encode()).hexdigest()
        
        # Let's keep track of cached paths to prevent duplicate entries
        seen_cached_paths = set()
        
        # 2. Gather all image files
        file_covers = []
        if not path_obj.is_file():
            try:
                for ext in ('.jpg', '.jpeg', '.png', '.bmp', '.webp'):
                    for p in path_obj.rglob(f"*{ext}"):
                        if p.is_file():
                            file_covers.append(p)
            except Exception:
                pass
                
            # If no covers found in the folder itself, but we have a parent cover file, include it!
            if not file_covers and parent_cover_file:
                try:
                    p_path = Path(parent_cover_file)
                    if p_path.is_file():
                        file_covers.append(p_path)
                except Exception:
                    pass
                
            # Deduplicate original paths
            unique_paths = []
            seen_original_paths = set()
            for p in file_covers:
                try:
                    resolved = p.resolve()
                    if resolved not in seen_original_paths:
                        seen_original_paths.add(resolved)
                        unique_paths.append(p)
                except Exception:
                    pass
            file_covers = unique_paths
            
            # Sort by priority using the same logic
            def get_path_priority(p):
                try:
                    rel_p = p.relative_to(path_obj)
                    is_root = (len(rel_p.parts) == 1)
                except ValueError:
                    is_root = False
                    
                name = p.name.lower()
                is_priority_name = name in [cn.lower() for cn in self.cover_names]
                
                if is_root and is_priority_name:
                    return (0, name) # Top priority
                elif is_root:
                    return (1, name)
                elif is_priority_name:
                    return (2, name)
                else:
                    return (3, name)
            
            file_covers.sort(key=lambda p: (get_path_priority(p), str(p)))

        # Define a helper function to scale and cache file-based images
        def cache_original_file(src_path, dest_path):
            try:
                dest_path_obj = Path(dest_path)
                if not dest_path_obj.exists():
                    image = QImage(str(src_path))
                    if not image.isNull():
                        scaled = image.scaled(300, 300, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                        scaled.save(str(dest_path))
                    else:
                        shutil.copy2(src_path, dest_path)
                return True
            except Exception as e:
                self._log_error(f"Error caching all-cover file {src_path}: {e}")
                try:
                    dest_path_obj = Path(dest_path)
                    if not dest_path_obj.exists():
                        shutil.copy2(src_path, dest_path)
                    return True
                except:
                    return False

        # Define a helper to scale and cache embedded covers
        def cache_embedded_data(img_data, dest_path):
            try:
                dest_path_obj = Path(dest_path)
                if not dest_path_obj.exists():
                    image = QImage.fromData(img_data)
                    if not image.isNull():
                        scaled = image.scaled(300, 300, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                        scaled.save(str(dest_path), "JPG")
                        return True
                else:
                    return True
            except Exception as e:
                self._log_error(f"Error caching embedded cover: {e}")
            return False

        # 3. Process the file covers
        inserted_covers = []
        
        # Determine if any of the files is the selected one
        selected_file_idx = -1
        has_selected_cover = False
        selected_filename = None
        if selected_cover_cached_path and Path(selected_cover_cached_path).exists():
            has_selected_cover = True
            selected_filename = Path(selected_cover_cached_path).name.lower()
            
            # Try to match by original path first if we have the existing covers info and the type matches
            if selected_orig_path and selected_source_type == 'file':
                for idx, p in enumerate(file_covers):
                    if str(p) == selected_orig_path:
                        selected_file_idx = idx
                        break
            
            # Fallback to name/hash matching only if not matched by original path AND old cover was not embedded
            if selected_file_idx == -1 and selected_source_type != 'embedded':
                for idx, p in enumerate(file_covers):
                    ext = p.suffix.lower()
                    image_hash = hashlib.md5(str(p).encode()).hexdigest()[:8]
                    filename_hashed = f"{safe_name}_{image_hash}{ext}".lower()
                    filename_default = f"{safe_name}{ext}".lower()
                    if selected_filename in (filename_hashed, filename_default):
                        selected_file_idx = idx
                        break
        
        # If there is no pre-selected cover at all (fresh scan), default to idx 0 of file covers (if any)
        if not has_selected_cover and file_covers:
            selected_file_idx = 0
            
        for idx, p in enumerate(file_covers):
            ext = p.suffix.lower()
            original_path_str = str(p)
            
            is_selected = 1 if idx == selected_file_idx else 0
            
            if is_selected:
                if selected_cover_cached_path and Path(selected_cover_cached_path).exists():
                    cached_path_str = selected_cover_cached_path
                else:
                    dest_path = self.covers_dir / f"{safe_name}{ext}"
                    success = cache_original_file(p, dest_path)
                    if success:
                        cached_path_str = str(dest_path)
                    else:
                        continue
            else:
                image_hash = hashlib.md5(original_path_str.encode()).hexdigest()[:8]
                dest_path = self.covers_dir / f"{safe_name}_{image_hash}{ext}"
                
                # Cache the file
                success = cache_original_file(p, dest_path)
                if success:
                    cached_path_str = str(dest_path)
                else:
                    continue
            
            # Prevent duplicates in database
            if cached_path_str not in seen_cached_paths:
                seen_cached_paths.add(cached_path_str)
                inserted_covers.append((
                    audiobook_id,
                    original_path_str,
                    cached_path_str,
                    is_selected,
                    'file'
                ))

        # 4. Process embedded covers (scan all audio files up to 10 files)
        if len(inserted_covers) < 10:
            audio_files = []
            if path_obj.is_file():
                audio_files = [path_obj]
            else:
                try:
                    audio_files = sorted(
                        [f for f in path_obj.iterdir()
                        if f.is_file() and f.suffix.lower() in self.audio_extensions]
                    )
                except Exception:
                    pass
            
            seen_embedded_hashes = set()
            for f in audio_files[:10]:
                img_data = self._get_embedded_image_data(f)
                if img_data:
                    data_hash = hashlib.md5(img_data).hexdigest()
                    if data_hash not in seen_embedded_hashes:
                        seen_embedded_hashes.add(data_hash)
                        
                        # Cache embedded file
                        short_hash = data_hash[:8]
                        filename_hashed = f"{safe_name}_emb_{short_hash}.jpg".lower()
                        filename_default = f"{safe_name}.jpg".lower()
                        
                        is_selected = 0
                        if has_selected_cover:
                            cand_hashed = str(self.covers_dir / f"{safe_name}_emb_{short_hash}.jpg")
                            cand_default = str(self.covers_dir / f"{safe_name}.jpg")
                            
                            # If we have existing cover records, prefer matching by source type and cached path
                            if selected_source_type == 'embedded' and selected_cached_path:
                                if selected_cached_path in (cand_hashed, cand_default):
                                    is_selected = 1
                            elif selected_source_type != 'file':
                                # Fallback to filename matching only if the old cover was not a file cover
                                if selected_filename in (filename_hashed, filename_default):
                                    is_selected = 1
                        elif not inserted_covers:
                            is_selected = 1
                            
                        if is_selected:
                            if selected_cover_cached_path and Path(selected_cover_cached_path).exists():
                                cached_path_str = selected_cover_cached_path
                            else:
                                cached_path_str = str(self.covers_dir / f"{safe_name}.jpg")
                        else:
                            cached_path_str = str(self.covers_dir / f"{safe_name}_emb_{short_hash}.jpg")
                            
                        success = cache_embedded_data(img_data, cached_path_str)
                        if success:
                            if cached_path_str not in seen_cached_paths:
                                seen_cached_paths.add(cached_path_str)
                                inserted_covers.append((
                                    audiobook_id,
                                    None, # No original file path for embedded covers
                                    cached_path_str,
                                    is_selected,
                                    'embedded'
                                ))
                                
        # 5. Insert all found covers into the database
        if inserted_covers:
            c.executemany("""
                INSERT INTO audiobook_covers (audiobook_id, original_path, cached_path, is_selected, source_type)
                VALUES (?, ?, ?, ?, ?)
            """, inserted_covers)

        # 6. Update the main audiobooks table to be in sync with the selected cover in audiobook_covers
        selected_row = None
        for item in inserted_covers:
            if item[3] == 1: # is_selected
                selected_row = (item[1], item[2]) # (original_path, cached_path)
                break
                
        try:
            if selected_row:
                orig_path, cached_path = selected_row
                c.execute("""
                    UPDATE audiobooks 
                    SET cover_path = ?, cached_cover_path = ? 
                    WHERE id = ?
                """, (orig_path, cached_path, audiobook_id))
            else:
                c.execute("""
                    UPDATE audiobooks 
                    SET cover_path = NULL, cached_cover_path = NULL 
                    WHERE id = ?
                """, (audiobook_id,))
        except sqlite3.OperationalError:
            # Table 'audiobooks' might not exist in some unit test mocks
            pass

    def _calculate_state_hash(self, files, cover_file=None, description_file=None, language=None):
        """Calculate hash based on audio files, cover image(s), description file, and language
        
        Args:
            files: List of audio file paths
            cover_file: Path or list/tuple of paths to cover image files (optional)
            description_file: Path to description text file (optional)
            language: Detected language code, e.g. 'ru' (optional)
        
        Returns:
            MD5 hash string
        """
        state_info = []
        
        # Audio files
        for f in files:
            try:
                stat = f.stat()
                state_info.append(f"AUDIO|{f.name}|{stat.st_size}|{stat.st_mtime}")
            except Exception:
                continue
        
        # Cover files (can be a single path, a list/tuple of paths, or None)
        if cover_file:
            if isinstance(cover_file, (list, tuple, set)):
                cover_files = cover_file
            else:
                cover_files = [cover_file]
                
            for c_file in cover_files:
                try:
                    cover_path = Path(c_file)
                    if cover_path.exists():
                        stat = cover_path.stat()
                        state_info.append(f"COVER|{cover_path.name}|{stat.st_size}|{stat.st_mtime}")
                except Exception:
                    pass
        
        # Description file
        if description_file:
            try:
                desc_path = Path(description_file)
                if desc_path.exists():
                    stat = desc_path.stat()
                    state_info.append(f"DESC|{desc_path.name}|{stat.st_size}|{stat.st_mtime}")
            except Exception:
                pass
        
        # Language tag
        if language:
            state_info.append(f"LANG|{language}")

        # Sort for consistency
        state_str = "\n".join(sorted(state_info))
        return hashlib.md5(state_str.encode('utf-8')).hexdigest()

    def _find_cover_file_only(self, directory):
        """Find cover image file in the specified directory only (no recursion or embedding)"""
        path_obj = Path(directory)
        if not path_obj.exists() or path_obj.is_file():
            return None
            
        # 1. Search in directory (priority names)
        for name in self.cover_names:
            p = path_obj / name
            try:
                if p.is_file():
                    return str(p)
            except (PermissionError, OSError):
                continue
                
        # 2. Search in directory (any image)
        try:
            for f in sorted(path_obj.iterdir()):
                if f.is_file() and f.suffix.lower() in {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}:
                    return str(f)
        except (PermissionError, OSError):
            pass
            
        return None

    def _find_all_root_cover_files(self, directory):
        """Find all cover image files in the root directory only (no rglob)
        
        Args:
            directory: Path to the audiobook directory
            
        Returns:
            List of string paths to cover files
        """
        path_obj = Path(directory)
        if path_obj.is_file():
            return []
            
        covers = []
        try:
            for f in path_obj.iterdir():
                if f.is_file() and f.suffix.lower() in {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}:
                    covers.append(str(f))
        except (PermissionError, OSError):
            pass
        return sorted(covers)

    def _find_cover_file(self, directory):
        """Find original cover image file (without caching)
        
        Searches for cover images in the following order:
        1. Priority names in current directory (cover.jpg, folder.png, etc.)
        2. Any image file in current directory
        3. Priority names in subdirectories (recursive)
        4. Any image file in subdirectories (recursive)
        
        Args:
            directory: Path to the audiobook directory
        
        Returns:
            String path to cover file, or None if not found
        """
        path_obj = Path(directory)
        
        # Case 0: Standalone file - no cover file
        if path_obj.is_file():
            return None
        
        # 1. Search in current directory (priority names)
        for name in self.cover_names:
            p = directory / name
            try:
                if p.is_file():
                    return str(p)
            except (PermissionError, OSError):
                continue
        
        # 2. Search in current directory (any image)
        try:
            for f in directory.iterdir():
                if f.is_file() and f.suffix.lower() in {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}:
                    return str(f)
        except (PermissionError, OSError):
            pass
        
        # 3. Recursive search in subdirectories (priority names)
        for name in self.cover_names:
            try:
                for p in directory.rglob(name):
                    if p.is_file():
                        return str(p)
            except (PermissionError, OSError):
                continue
        
        # 4. Recursive search in subdirectories (any image)
        for ext in ('.jpg', '.jpeg', '.png', '.bmp', '.webp'):
            try:
                for p in directory.rglob(f"*{ext}"):
                    if p.is_file():
                        return str(p)
            except (PermissionError, OSError):
                continue
        
        return None

    def _find_description_file(self, directory):
        """Find description text file
        
        Searches for text files in the following priority:
        1. description.txt
        2. info.txt
        3. about.txt
        4. {folder_name}.txt
        5. First .txt file found
        
        Args:
            directory: Path to the audiobook directory
        
        Returns:
            String path to description file, or None if not found
        """
        path_obj = Path(directory)
        
        # Standalone file - no description
        if path_obj.is_file():
            return None
        
        potential_desc_files = sorted([f for f in directory.glob("*.txt")])
        if not potential_desc_files:
            return None
        
        # Prioritize: 'description.txt', 'info.txt', 'about.txt', '{folder_name}.txt'
        priority_names = ['description', 'info', 'about', directory.name.lower()]
        
        for p_name in priority_names:
            for f in potential_desc_files:
                if f.stem.lower() == p_name:
                    return str(f)
        
        # Fallback to first text file
        return str(potential_desc_files[0])

    def _read_text_file(self, file_path):
        """Read text file with smart encoding detection and mojibake prevention"""
        if not file_path or not os.path.exists(file_path):
            return ""
            
        # Try encodings in priority order. 
        # Strict/BOM-based ones first, then common 8-bit ones (CP1251 is high priority for Russian).
        # Greedy UTF-16LE is placed after 8-bit encodings to avoid false positives.
        encodings = ['utf-8-sig', 'utf-8', 'utf-16', 'cp1251', 'cp1252', 'utf-16-le', 'latin-1']
        
        for enc in encodings:
            try:
                with open(file_path, 'r', encoding=enc, errors='strict') as f:
                    content = f.read().strip()
                
                if content:
                    # Heuristic to detect UTF-16 interpretation of 8-bit text:
                    # If we got a lot of Chinese characters (CJK Ideographs) in a non-Chinese context, 
                    # it's likely a false positive for an 8-bit encoding like CP1251.
                    if enc == 'utf-16-le':
                        # Count characters in CJK Unified Ideographs and Extension A blocks
                        cjk_count = sum(1 for c in content if 0x4E00 <= ord(c) <= 0x9FFF or 0x3400 <= ord(c) <= 0x4DBF)
                        if cjk_count > len(content) * 0.2: # More than 20% CJK characters
                            continue
                            
                    return content
            except (UnicodeDecodeError, UnicodeError):
                continue
            except Exception:
                break
                
        # Last resort fallback with replacement characters
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                return f.read().strip()
        except Exception:
            return ""

    def _log_book_summary(self, title, author, narrator, duration, file_count, codec, bitrate, bitrate_mode, cover, cue_count, problems, language=None, year_written=None, year_recorded=None):
        """Print a consolidated summary of the book"""
        self._log("") # Empty line before book
        
        # Line 1: Title (with [+] marker)
        self._log(f"[+] {title}")
        
        # Line 2: Author & Narrator
        author_str = author if author else self.tr('scanner.unknown_author')
        if narrator:
            self._log(f"    {author_str} ({narrator})")
        else:
             self._log(f"    {author_str}")
        
        # Line 3: Tech Stats
        # Format: 10h 52m | 7 files | MP3 VBR 62kbps
        hours = int(duration // 3600)
        minutes = int((duration % 3600) // 60)
        time_str = f"{hours}h {minutes}m"
        
        files_str = f"{file_count} files"
        if file_count == 1:
             files_str = "1 file"
             
        bitrate_str = f"{bitrate}kbps"
        if bitrate_mode:
            bitrate_str = f"{bitrate_mode} {bitrate_str}"
            
        tech_line = f"    {time_str} | {files_str} | {codec.upper()} {bitrate_str}"
        self._log(tech_line)
        
        # Line 4: Metadata (Language, Written, Recorded)
        meta_parts = []
        if language:
            meta_parts.append(f"Language: {language}")
        if year_written:
            meta_parts.append(f"Written: {year_written}")
        if year_recorded:
            meta_parts.append(f"Recorded: {year_recorded}")
        if meta_parts:
            self._log(f"    {' | '.join(meta_parts)}")

        # Line 5: Extras (Cover, CUE, Problems)
        extras = []
        if cover:
            extras.append("[Cover: OK]")
        if cue_count > 0:
            extras.append(f"[CUE: {cue_count}]")
            
        if problems > 0:
            extras.append(f"[WARNING: {problems} failed files]")
            
        if extras:
            self._log(f"    {' '.join(extras)}")

    def scan_directory(self, root_path, subfolder_path=None, verbose=False):
        """Perform recursive directory scanning for audiobooks"""
        start_time = time.time()
        self._log_header(self.tr("scanner.scan_start"))
        
        root = Path(root_path)
        self._log_item("Root", str(root))
        
        if not root.exists():
            self._log_error(self.tr("scanner.error_not_exists"))
            return 0
        
        subfolder = None
        if subfolder_path:
            subfolder = Path(subfolder_path)
            if not subfolder.is_absolute():
                subfolder = root / subfolder
            self._log_item("Subfolder", str(subfolder))
        
        with sqlite3.connect(self.db_file) as conn:
            c = conn.cursor()
            # Performance optimizations for SQLite
            c.execute("PRAGMA foreign_keys = ON")
            c.execute("PRAGMA synchronous = NORMAL")
            c.execute("PRAGMA journal_mode = WAL")
            c.execute("PRAGMA cache_size = 10000")
            
            # Save current progress state to temp table
            # Save current progress state to temp table
            self._log_section(self.tr("scanner.saving_state"))
            
            c.execute("""
                CREATE TEMP TABLE temp_state AS
                SELECT
                    path,
                    listened_duration,
                    progress_percent,
                    current_file_index,
                    current_position,
                    playback_speed,
                    is_started,
                    is_completed,
                    is_merged
                FROM audiobooks
                WHERE is_folder = 0 -- Keep progress for actual books (including merged ones)
            """)
            
            # Fetch locally merged paths to handle virtual merging
            # Fetch locally merged paths to handle virtual merging
            self._log_section(self.tr("scanner.checking_merged_folders"))
            c.execute("SELECT path FROM audiobooks WHERE is_merged = 1")
            merged_paths_set = {row[0] for row in c.fetchall()}
            if merged_paths_set:
                 self._log_info(self.tr("scanner.merged_folders_found", count=len(merged_paths_set)))
                 for mp in merged_paths_set:
                     self._log(f"    [MERGED] {mp}")
            
            # Reset availability for all books before scanning
            if subfolder:
                subfolder_rel = str(subfolder.relative_to(root))
                c.execute("""
                    UPDATE audiobooks 
                    SET is_available = 0 
                    WHERE path = ? OR path LIKE ?
                """, (subfolder_rel, subfolder_rel + os.sep + '%'))
            else:
                c.execute("UPDATE audiobooks SET is_available = 0")
            
            c.execute("SELECT COUNT(*) FROM temp_state")
            saved_count = c.fetchone()[0]
            self._log_info(self.tr("scanner.saved_progress_count", count=saved_count))
            
            # Searching for folders
            # Searching for folders
            self._log_section(self.tr("scanner.searching_books"))
            
            folders = []
            walk_target = subfolder if subfolder else root
            for dirpath, dirnames, filenames in os.walk(walk_target):
                d = Path(dirpath)
                try:
                    rel_path_str = str(d.relative_to(root))
                except ValueError: continue
                
                if rel_path_str == '.': continue
                
                # Check for merged parent
                is_child_of_merged = False
                for mp in merged_paths_set:
                    if rel_path_str.startswith(mp + os.sep):
                        is_child_of_merged = True
                        break
                
                if is_child_of_merged:
                    dirnames.clear() # Skip subdirectories
                    continue
                
                # Check for audio files or playlist files in current filenames list (fast)
                has_audio = any(Path(fn).suffix.lower() in self.audio_extensions for fn in filenames)
                has_playlist = any(Path(fn).suffix.lower() in ('.m3u', '.m3u8') for fn in filenames)
                
                if has_audio or has_playlist or (rel_path_str in merged_paths_set):
                    folders.append(d)
            
            self._log_info(self.tr("scanner.found_folders", count=len(folders)))
            
            # Find standalone files and M3U playlists in root early to get total count
            standalone_files = []
            standalone_m3u = []
            if not subfolder:
                try:
                    for f in root.iterdir():
                        if f.is_file() and f.suffix.lower() in self.audio_extensions:
                            standalone_files.append(f)
                except PermissionError:
                    pass

                try:
                    for f in root.iterdir():
                        if f.is_file() and f.suffix.lower() in ('.m3u', '.m3u8'):
                            standalone_m3u.append(f)
                except PermissionError:
                    pass
            
            total_items = len(folders) + len(standalone_files) + len(standalone_m3u)
            
            # Cleanup old cache entries (older than 30 days)
            c.execute("DELETE FROM file_metadata_cache WHERE cached_at < datetime('now', '-30 days')")
            
            # Processing each folder
            # Processing each folder
            self._log_section(self.tr("scanner.processing_books"))
            
            saved_folders = set()
            
            def save_folder(path_str):
                """Recursively save parent folders in database"""
                if path_str in saved_folders or path_str == '':
                    return
                saved_folders.add(path_str)
                
                path_obj = Path(path_str)
                parent_path_str = str(path_obj.parent) if str(path_obj.parent) != '.' else ''
                
                if parent_path_str:
                    save_folder(parent_path_str)
                
                # Check for folder existence as audiobook (file_count=0)
                c.execute(
                    "SELECT id FROM audiobooks WHERE path = ? AND is_folder = 0",
                    (path_str,)
                )
                if c.fetchone():
                    return
                
                c.execute("""
                    INSERT OR IGNORE INTO audiobooks
                    (path, parent_path, name, author, title, narrator, cover_path, cached_cover_path,
                     file_count, duration, listened_duration, progress_percent, is_folder,
                     current_file_index, current_position, is_started, is_completed, is_available,
                     time_added)
                    VALUES (?, ?, ?, '', '', '', NULL, NULL, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, CURRENT_TIMESTAMP)
                """, (path_str, parent_path_str, path_obj.name))
                
                # Mark existing folder as available and ensure time_added is set
                c.execute("""
                    UPDATE audiobooks 
                    SET is_available = 1,
                        time_added = COALESCE(time_added, CURRENT_TIMESTAMP)
                    WHERE path = ? AND is_folder = 1
                """, (path_str,))
            
            for idx, folder in enumerate(folders, 1):
                rel = folder.relative_to(root)
                parent = rel.parent if str(rel.parent) != '.' else ''
                
                # Log progress
                percent = int(idx * 100 / total_items) if total_items > 0 else 0
                progress_text = self.tr("scanner.processing_item", current=idx, total=total_items, name=folder.name)
                self._log(f"\r{percent}% | {progress_text}", end="")
                
                m3u_files = self._find_playlist_files(folder)
                if m3u_files:
                    self._process_playlist_in_folder(folder, root, m3u_files, conn, save_folder, verbose)
                    continue
                
                # Get file list
                # Check if this is a merged folder
                is_merged = str(rel) in merged_paths_set
                
                # Get file list
                if is_merged:
                    # Recursive scan for merged folders
                    # We look for all audio files in this directory AND subdirectories
                    files = sorted(
                        f for f in folder.rglob('*')
                        if f.is_file() and f.suffix.lower() in self.audio_extensions
                    )
                else:
                    # Standard flat scan
                    files = sorted(
                        f for f in folder.iterdir()
                        if f.is_file() and f.suffix.lower() in self.audio_extensions
                    )
                
                # Query database for existing record
                c.execute("SELECT id, state_hash, codec, total_size, cover_path FROM audiobooks WHERE path = ?", (str(rel),))
                existing_row_data = c.fetchone()
                
                # Fast determination of cover files and description file to use in state hash (no rglob)
                cover_files = []
                if existing_row_data and existing_row_data[4]:
                    db_cover = existing_row_data[4]
                    cover_p = Path(db_cover)
                    if not cover_p.is_absolute():
                        cover_p = root / cover_p
                    try:
                        if cover_p.is_file():
                            cover_files.append(str(cover_p))
                    except Exception:
                        pass
                
                # Also include all root covers to detect new covers added to root
                root_covers = self._find_all_root_cover_files(folder)
                for rc in root_covers:
                    if rc not in cover_files:
                        cover_files.append(rc)
                
                description_file_path = self._find_description_file(folder)
                
                # Verbose logging (using primary cover file if found)
                if verbose:
                    primary_cover = cover_files[0] if cover_files else None
                    if primary_cover:
                        self._log_info(f"Cover: {Path(primary_cover).name}", indent=2)
                    if description_file_path:
                        self._log_info(f"Description: {Path(description_file_path).name}", indent=2)
                
                # Detect language from folder name (fast, needed for hash)
                language = self._detect_language(folder.name)

                # Calculate current state hash (extremely fast!)
                current_state_hash = self._calculate_state_hash(files, cover_files, description_file_path, language=language)
                
                # Skip if valid existing record found and codec is populated
                if existing_row_data:
                    db_id = existing_row_data[0]
                    db_hash = existing_row_data[1]
                    db_codec = existing_row_data[2]
                    db_total_size = existing_row_data[3]
                    
                    if db_hash == current_state_hash and db_codec is not None:
                        if not db_total_size:
                            try:
                                total_size = sum(f.stat().st_size for f in files)
                            except Exception:
                                total_size = 0
                            c.execute("UPDATE audiobooks SET is_available = 1, total_size = ? WHERE id = ?", (total_size, db_id))
                        else:
                            c.execute("UPDATE audiobooks SET is_available = 1 WHERE id = ?", (db_id,))
                        if verbose:
                            self._log_info(self.tr('scanner.skip_existing', path=rel), indent=2)
                        continue
                
                # Extract metadata from tags
                metadata = self._extract_metadata(folder, files)
                t_author = metadata.get('author', '')
                t_title = metadata.get('title', '')
                t_narrator = metadata.get('narrator', '')
                t_year = metadata.get('year', '')
                
                # Parse folder name
                f_author, f_title, f_narrator = self._parse_audiobook_name(folder.name)
                
                # Prioritize folder name info (usually more reliable for display)
                author = f_author or t_author
                title = f_title or t_title
                narrator = f_narrator or t_narrator

                # t_year already extracted by _extract_metadata — reuse as rec_tag (no double read)
                # Only fetch orig_year (TDOR/©opd/original_date) which _extract_metadata doesn't provide
                orig_year = self._extract_orig_year(files[0]) if files else None

                # Parse writing year and recording year
                # Sources: t_year (tag), orig_year (tag), folder.name (regex scan)
                year_written, year_recorded = self._parse_years(folder.name, t_year or None, orig_year)
                
                # Analyze files in parallel
                file_count = len(files)
                duration = 0
                failed_count = 0
                
                file_analyses = []
                bitrates = []
                codecs = []
                
                # VBR detection stats
                vbr_detected = False
                cbr_detected = False
                
                # Analyze files in parallel with cache lookup
                file_analyses = self._analyze_files_parallel(files, conn=conn, max_workers=4, verbose=verbose)
                
                for info in file_analyses:
                    file_duration = info['duration']
                    duration += file_duration
                    
                    if file_duration == 0:
                        failed_count += 1
                        
                    if info['bitrate'] > 0:
                        bitrates.append(info['bitrate'])
                        
                    if info['codec']:
                        codecs.append(info['codec'])
                        
                    if info['is_vbr']:
                        vbr_detected = True
                    elif info['bitrate'] > 0:
                        cbr_detected = True
                
                # Calculate total aggregate file size
                total_size = 0
                for f in files:
                    try:
                        total_size += f.stat().st_size
                    except Exception:
                        pass

                # Calculate aggregated stats
                listened = 0 # Default if new
                
                bitrate_min = (min(bitrates) // 1000) if bitrates else 0
                bitrate_max = (max(bitrates) // 1000) if bitrates else 0
                
                # Bitrate mode logic
                if vbr_detected and cbr_detected:
                    bitrate_mode = 'VBR/CBR'
                elif vbr_detected:
                    bitrate_mode = 'VBR'
                elif cbr_detected:
                   # Check if strict CBR (all bitrates same) or if it varies significantly
                   # Common logic: if min != max it's likely VBR even if headers say CBR or we missed the VBR header
                   # But user logic request: "if min != max -> VBR" (implied by previous context, but strictly user said "Logic: ...")
                   # Actually user said: "if some files CBr and some VBR -> VBR/CBR"
                   # If all are detected as CBR (not is_vbr):
                   bitrate_mode = 'CBR'
                else:
                    bitrate_mode = ''
                
                # Common codec
                from collections import Counter
                common_codec = Counter(codecs).most_common(1)[0][0] if codecs else ''
                
                # Container (extension) - use first file or most common
                extensions = [f.suffix.lstrip('.').lower() for f in files]
                container = Counter(extensions).most_common(1)[0][0] if extensions else ''
                
                parent_cover_file = None
                try:
                    if str(parent) != '':
                        parent_folder = root / parent
                        if parent_folder != folder:
                            parent_cover_file = self._find_cover_file_only(parent_folder)
                except Exception:
                    pass

                # Search for cover image
                cover, cover_cached = self._find_cover(folder, str(rel), parent_cover_file)

                # Check for .cue files in this folder
                cue_files = list(folder.glob('*.cue'))
                cue_data_chapters = []
                if cue_files:
                    _, cue_data_chapters = self._parse_cue_file(cue_files[0])

                # Read description content (file path already found earlier)
                description = self._read_text_file(description_file_path) if description_file_path else ""

                # Log unified book summary
                # Use max bitrate for display if no range, or just average/max? 
                # Display usually shows typically bitrate. Let's show average or max.
                # Previous logic used range. Let's just use average if range is small, 
                # or simplified "128kbps" if it's CBR.
                
                disp_bitrate = 0
                if bitrates:
                     avg_bitrate = sum(bitrates) // len(bitrates)
                     disp_bitrate = avg_bitrate // 1000
                
                self._log_book_summary(
                    title=title or folder.name, 
                    author=author, 
                    narrator=narrator, 
                    duration=duration, 
                    file_count=file_count, 
                    codec=common_codec, 
                    bitrate=disp_bitrate, 
                    bitrate_mode=bitrate_mode,
                    cover=cover_cached, 
                    cue_count=len(cue_data_chapters) if cue_data_chapters else 0,
                    problems=failed_count,
                    language=language,
                    year_written=year_written,
                    year_recorded=year_recorded
                )
                
                # Restore state from temp table if possible
                c.execute("""
                    SELECT
                        listened_duration,
                        progress_percent,
                        current_file_index,
                        current_position,
                        playback_speed,
                        is_started,
                        is_completed,
                        is_merged
                    FROM temp_state
                    WHERE path = ?
                """, (str(rel),))
                
                state = c.fetchone()
                if state:
                    listened, prog_pct, cur_idx, cur_pos, playback_speed, is_started, is_completed, saved_is_merged = state
                    # Ensure we respect the saved merged state preference if it matches
                    # logic: The is_merged flag comes from the MAIN table (via temp_state select), so we preserve it.
                    # But actually, we already determined 'is_merged' from 'merged_paths_set' which covers this.
                    if prog_pct > 0:
                        self._log_info(self.tr("scanner.progress_restored", percent=prog_pct), indent=2)
                else:
                    listened = 0
                    prog_pct = 0
                    cur_idx = 0
                    cur_pos = 0
                    playback_speed = 1.0
                    is_started = 0
                    is_completed = 0
                
                # Check if record already exists
                c.execute("SELECT id, cover_path, cached_cover_path FROM audiobooks WHERE path = ?", (str(rel),))
                existing_row = c.fetchone()
                
                if existing_row:
                    book_id, existing_cover_path, existing_cached_cover_path = existing_row
                    
                    # If there was a previously selected cover and it still exists/is valid, preserve it
                    if existing_cached_cover_path and Path(existing_cached_cover_path).exists():
                        if not existing_cover_path or Path(existing_cover_path).exists():
                            cover = existing_cover_path
                            cover_cached = existing_cached_cover_path
                            
                    # Update metadata only, preserve progress and status
                    c.execute("""
                        UPDATE audiobooks
                        SET parent_path = ?,
                            name = ?,
                            author = ?,
                            title = ?,
                            narrator = ?,
                            tag_author = ?,
                            tag_title = ?,
                            tag_narrator = ?,
                            tag_year = ?,
                            language = COALESCE(language, ?),
                            year_written = ?,
                            year_recorded = ?,
                            cover_path = ?,
                            cached_cover_path = ?,
                            file_count = ?,
                            duration = ?,
                            state_hash = ?,
                            codec = ?,
                            bitrate_min = ?,
                            bitrate_max = ?,
                            bitrate_mode = ?,
                            container = ?,
                            time_added = COALESCE(time_added, CURRENT_TIMESTAMP),
                            is_available = 1,
                            is_merged = ?,
                            description = ?,
                            total_size = ?,
                            is_folder = 0
                        WHERE path = ?
                    """, (
                        str(parent),
                        folder.name,
                        author,
                        title,
                        narrator,
                        t_author,
                        t_title,
                        t_narrator,
                        t_year,
                        language,
                        year_written,
                        year_recorded,
                        cover,
                        cover_cached,
                        file_count,
                        duration,
                        current_state_hash,
                        common_codec,
                        bitrate_min,
                        bitrate_max,
                        bitrate_mode,
                        container,
                        1 if is_merged else 0,
                        description,
                        total_size,
                        str(rel)
                    ))
                    book_id = existing_row[0]
                else:
                    # Insert new record with restored status if present
                    c.execute("""
                        INSERT INTO audiobooks
                        (
                            path, parent_path, name,
                            author, title, narrator,
                            tag_author, tag_title, tag_narrator, tag_year,
                            language, year_written, year_recorded,
                            cover_path, cached_cover_path,
                            file_count, duration,
                            listened_duration,
                            progress_percent,
                            is_folder,
                            current_file_index,
                            current_position,
                            playback_speed,
                            is_started,
                            is_completed,
                            is_available,
                            state_hash,
                            codec, bitrate_min, bitrate_max, bitrate_mode, container,
                            time_added, is_merged, description, total_size
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?)
                    """, (
                        str(rel),
                        str(parent),
                        folder.name,
                        author,
                        title,
                        narrator,
                        t_author,
                        t_title,
                        t_narrator,
                        t_year,
                        language,
                        year_written,
                        year_recorded,
                        cover,
                        cover_cached,
                        file_count,
                        duration,
                        listened,
                        prog_pct,
                        cur_idx,
                        cur_pos,
                        playback_speed,
                        is_started,
                        is_completed,
                        current_state_hash,
                        common_codec,
                        bitrate_min,
                        bitrate_max,
                        bitrate_mode,
                        container,
                        1 if is_merged else 0,
                        description,
                        total_size
                    ))
                    c.execute("SELECT id FROM audiobooks WHERE path = ?", (str(rel),))
                    book_id = c.fetchone()[0]

                # Scan and cache all available covers, and save to audiobook_covers table
                self._scan_and_save_all_covers(conn, folder, str(rel), book_id, cover_cached, parent_cover_file)

                # Update files list: remove old and insert current files
                c.execute("DELETE FROM audiobook_files WHERE audiobook_id = ?", (book_id,))
                
                virtual_file_index = 1
                files_batch = []
                
                for i, (f, info) in enumerate(zip(files, file_analyses), 1):
                    f_tags = self._extract_file_tags(f)
                    file_duration = info['duration']
                    
                    # Check for chapters
                    chapters = []
                    if f.suffix.lower() in ('.m4b', '.mp4', '.m4a'):
                        chapters = self._extract_chapters(f)
                    
                    if not chapters and cue_data_chapters and len(files) == 1:
                        chapters = cue_data_chapters
                        if chapters and chapters[-1].get('duration') == 0:
                            chapters[-1]['duration'] = max(0, file_duration - chapters[-1]['start'])
                    
                    if chapters:
                        for chap in chapters:
                            files_batch.append((
                                book_id,
                                str(f.relative_to(root)),
                                f.name,
                                virtual_file_index,
                                chap['duration'],
                                chap['start'],
                                chap['title'] or f.name,
                                f_tags['author'],
                                f_tags['album'],
                                f_tags['genre'],
                                f_tags['comment']
                            ))
                            virtual_file_index += 1
                    else:
                        if is_merged:
                             track_no = virtual_file_index
                        else:
                             track_no = f_tags['track'] if f_tags['track'] is not None else virtual_file_index
                             
                        files_batch.append((
                            book_id,
                            str(f.relative_to(root)),
                            f.name,
                            track_no,
                            file_duration,
                            0.0,
                            f_tags['title'],
                            f_tags['author'],
                            f_tags['album'],
                            f_tags['genre'],
                            f_tags['comment']
                        ))
                        if not is_merged and f_tags['track'] is not None:
                            virtual_file_index = max(virtual_file_index, f_tags['track'] + 1)
                        else:
                            virtual_file_index += 1
                
                
                if files_batch:
                    c.executemany("""
                        INSERT INTO audiobook_files
                        (audiobook_id, file_path, file_name, track_number, duration,
                         start_offset, tag_title, tag_artist, tag_album, tag_genre, tag_comment)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, files_batch)

                # Update the file_count in audiobooks table
                c.execute("UPDATE audiobooks SET file_count = ? WHERE id = ?", (len(files_batch), book_id))
            
            # Recreate intermediate folder structure
            self._log_section(self.tr("scanner.creating_structure"))
            
            for folder in folders:
                rel = folder.relative_to(root)
                parent = rel.parent
                if str(parent) != '.':
                    save_folder(str(parent))
            
            self._log_info(self.tr("scanner.created_folders", count=len(saved_folders)))

            # --- Process Standalone Files in Root ---
            self._log_section(self.tr("scanner.processing_standalone"))
            
            if standalone_files:
                self._log_info(self.tr("scanner.standalone_found", count=len(standalone_files)))
                for s_idx, f in enumerate(standalone_files, 1):
                    # Progress logging for standalone files
                    global_idx = len(folders) + s_idx
                    percent = int(global_idx * 100 / total_items) if total_items > 0 else 0
                    progress_text = self.tr("scanner.processing_item", current=global_idx, total=total_items, name=f.name)
                    self._log(f"\r{percent}% | {progress_text}", end="")
                    
                    self._process_standalone_file(f, root, conn, verbose=verbose)
            else:
                self._log_info(self.tr("scanner.standalone_found", count=0))

            # --- Process Standalone M3U Playlists in Root ---
            if standalone_m3u:
                for m_idx, m3u_file in enumerate(standalone_m3u, 1):
                    # Progress logging for standalone m3u playlists
                    global_idx = len(folders) + len(standalone_files) + m_idx
                    percent = int(global_idx * 100 / total_items) if total_items > 0 else 0
                    progress_text = self.tr("scanner.processing_item", current=global_idx, total=total_items, name=m3u_file.name)
                    self._log(f"\r{percent}% | {progress_text}", end="")
                    
                    rel_m3u = m3u_file.relative_to(root)
                    self._save_playlist_as_book(
                        m3u_path=m3u_file,
                        book_path=str(rel_m3u),
                        parent_path='',
                        name=m3u_file.stem,
                        root=root,
                        conn=conn,
                        verbose=verbose
                    )

            # Get total processed count from db
            c.execute("SELECT COUNT(*) FROM audiobooks WHERE is_folder = 0 AND is_available = 1")
            total_processed = c.fetchone()[0]

            # Finalize: cleanup temp table and commit
            c.execute("DROP TABLE temp_state")
            conn.commit()
        
        try:
            conn.close()
        except Exception:
            pass
        
        # Result statistics
        elapsed_time = time.time() - start_time
        elapsed_minutes = int(elapsed_time // 60)
        elapsed_seconds = int(elapsed_time % 60)
        
        self._log_header(self.tr("scanner.scan_complete"))
        self._log_info(self.tr("scanner.processed_count", count=total_processed))
        self._log_info(self.tr("scanner.elapsed_time", minutes=elapsed_minutes, seconds=elapsed_seconds))
        self._log_info(self.tr("scanner.db_file", path=self.db_file))
        self._log("")
        
        return total_processed

    def _process_standalone_file(self, file_path: Path, root: Path, conn, verbose=False):
        """Process a single audio file as a book"""
        c = conn.cursor()
        
        rel = file_path.relative_to(root)
        parent = '' # Root files have no parent path in our relative structure logic (or '.')
        
        # Find cover and description files (for standalone files, these are None)
        cover_file_path = None  # Standalone files don't have separate cover files
        description_file_path = None  # Standalone files don't have description files
        
        # Calculate current state hash
        current_state_hash = self._calculate_state_hash([file_path], cover_file_path, description_file_path)
        
        # Check for existing
        c.execute("SELECT id, state_hash, codec, cover_path, cached_cover_path, total_size FROM audiobooks WHERE path = ?", (str(rel),))
        existing_row_data = c.fetchone()
        
        if existing_row_data:
            db_id = existing_row_data[0]
            db_hash = existing_row_data[1]
            db_codec = existing_row_data[2]
            db_total_size = existing_row_data[5]
            if db_hash == current_state_hash and db_codec is not None:
                if not db_total_size:
                    try:
                        total_size = file_path.stat().st_size
                    except Exception:
                        total_size = 0
                    c.execute("UPDATE audiobooks SET is_available = 1, total_size = ? WHERE id = ?", (total_size, db_id))
                else:
                    c.execute("UPDATE audiobooks SET is_available = 1 WHERE id = ?", (db_id,))
                if verbose:
                    self._log_info(self.tr('scanner.skip_existing', path=rel), indent=2)
                return

        # Extract metadata
        # For single file, treat it as the "folder" for metadata extraction purposes
        # But we need a list of files
        files = [file_path]
        
        # Use file tags primarily
        tags = self._extract_file_tags(file_path)
        t_author = tags.get('author', '')
        t_title = tags.get('album', '') or tags.get('title', '')
        t_narrator = tags.get('narrator', '')
        t_year = tags.get('year', '')
        
        # Parse filename 
        f_author, f_title, f_narrator = self._parse_audiobook_name(file_path.stem)
        
        # Prioritize filename info but fallback to tags
        author = f_author or t_author
        title = f_title or t_title or file_path.stem
        narrator = f_narrator or t_narrator
        
        # Detect language from file name
        language = self._detect_language(file_path.name)

        # Extract original year from tags
        orig_year = self._extract_orig_year(file_path)

        # Parse years
        year_written, year_recorded = self._parse_years(file_path.name, t_year or None, orig_year)
        
        # Analyze file
        info = self._analyze_file(file_path, verbose)
        file_duration = info['duration']
        # If cached
        if info['duration'] > 0:
             self._save_to_cache(file_path, info, conn)
             
        common_codec = info['codec']
        bitrate = info['bitrate']
        bitrate_mode = 'VBR' if info['is_vbr'] else 'CBR'
        container = file_path.suffix.lstrip('.').lower()
        
        # Cover
        cover, cover_cached = self._find_cover(file_path, str(rel))
        
        if existing_row_data:
            _, _, _, existing_cover_path, existing_cached_cover_path = existing_row_data
            if existing_cached_cover_path and Path(existing_cached_cover_path).exists():
                if not existing_cover_path or Path(existing_cover_path).exists():
                    cover = existing_cover_path
                    cover_cached = existing_cached_cover_path
        
        # Check matching chapters
        chapters = []
        if file_path.suffix.lower() in ('.m4b', '.mp4', '.m4a'):
             chapters = self._extract_chapters(file_path)

        # Restore state
        c.execute("""
            SELECT
                listened_duration,
                progress_percent,
                current_file_index,
                current_position,
                playback_speed,
                is_started,
                is_completed
            FROM temp_state
            WHERE path = ?
        """, (str(rel),))
        state = c.fetchone()
        
        if state:
            listened, prog_pct, cur_idx, cur_pos, playback_speed, is_started, is_completed = state
            if prog_pct > 0:
                 self._log_info(self.tr("scanner.progress_restored", percent=prog_pct), indent=2)
        else:
            listened = 0
            prog_pct = 0
            cur_idx = 0
            cur_pos = 0
            playback_speed = 1.0
            is_started = 0
            is_completed = 0

        # Get standalone file size
        total_size = 0
        try:
            total_size = file_path.stat().st_size
        except Exception:
            pass

        # Check if record already exists (again, to get ID)
        if existing_row_data:
             c.execute("""
                UPDATE audiobooks
                SET parent_path = ?,
                    name = ?,
                    author = ?,
                    title = ?,
                    narrator = ?,
                    tag_author = ?,
                    tag_title = ?,
                    tag_narrator = ?,
                    tag_year = ?,
                    cover_path = ?,
                    cached_cover_path = ?,
                    file_count = ?,
                    duration = ?,
                    state_hash = ?,
                    codec = ?,
                    bitrate_min = ?,
                    bitrate_max = ?,
                    bitrate_mode = ?,
                    container = ?,
                    time_added = COALESCE(time_added, CURRENT_TIMESTAMP),
                    is_available = 1,
                    is_merged = 0,
                    description = ?,
                    total_size = ?,
                    is_folder = 0,
                    language = ?,
                    year_written = ?,
                    year_recorded = ?
                WHERE path = ?
            """, (
                str(parent),
                file_path.name,
                author,
                title,
                narrator,
                t_author,
                t_title,
                t_narrator,
                t_year,
                cover,
                cover_cached,
                1, # Will update later if chapters
                file_duration,
                current_state_hash,
                common_codec,
                bitrate,
                bitrate,
                bitrate_mode,
                container,
                tags.get('comment', ''),
                total_size,
                language,
                year_written,
                year_recorded,
                str(rel)
            ))
             book_id = existing_row_data[0]
        else:
             c.execute("""
                INSERT INTO audiobooks
                (
                    path, parent_path, name,
                    author, title, narrator,
                    tag_author, tag_title, tag_narrator, tag_year,
                    cover_path, cached_cover_path,
                    file_count, duration,
                    listened_duration,
                    progress_percent,
                    is_folder,
                    current_file_index,
                    current_position,
                    playback_speed,
                    is_started,
                    is_completed,
                    is_available,
                    state_hash,
                    codec, bitrate_min, bitrate_max, bitrate_mode, container,
                    time_added, is_merged, description, total_size,
                    language, year_written, year_recorded
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 0, ?, ?, ?, ?, ?)
            """, (
                str(rel),
                str(parent),
                file_path.name,
                author,
                title,
                narrator,
                t_author,
                t_title,
                t_narrator,
                t_year,
                cover,
                cover_cached,
                1,
                file_duration,
                listened,
                prog_pct,
                cur_idx,
                cur_pos,
                playback_speed,
                is_started,
                is_completed,
                current_state_hash,
                common_codec,
                bitrate,
                bitrate,
                bitrate_mode,
                container,
                tags.get('comment', ''),
                total_size,
                language,
                year_written,
                year_recorded
            ))
             c.execute("SELECT id FROM audiobooks WHERE path = ?", (str(rel),))
             book_id = c.fetchone()[0]

        # Scan and cache all available covers, and save to audiobook_covers table
        self._scan_and_save_all_covers(conn, file_path, str(rel), book_id, cover_cached)

        # Files (Chapters)
        c.execute("DELETE FROM audiobook_files WHERE audiobook_id = ?", (book_id,))
        
        files_batch = []
        virtual_file_index = 1
        
        if chapters:
            for chap in chapters:
                files_batch.append((
                    book_id,
                    str(file_path.relative_to(root)),
                    file_path.name,
                    virtual_file_index,
                    chap['duration'],
                    chap['start'],
                    chap['title'] or f"Chapter {virtual_file_index}",
                    t_author,
                    tags.get('album', ''),
                    tags.get('genre', ''),
                    tags.get('comment', '')
                ))
                virtual_file_index += 1
        else:
             files_batch.append((
                book_id,
                str(rel),
                file_path.name,
                1,
                file_duration,
                0.0,
                t_title or title,
                t_author,
                tags.get('album', ''),
                tags.get('genre', ''),
                tags.get('comment', '')
            ))

        if files_batch:
            c.executemany("""
                INSERT INTO audiobook_files
                (audiobook_id, file_path, file_name, track_number, duration,
                    start_offset, tag_title, tag_artist, tag_album, tag_genre, tag_comment)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, files_batch)

        # Update file_count
        c.execute("UPDATE audiobooks SET file_count = ? WHERE id = ?", (len(files_batch), book_id))
        
        # Log Summary
        self._log_book_summary(
            title=title, 
            author=author, 
            narrator=narrator, 
            duration=file_duration, 
            file_count=len(files_batch), 
            codec=common_codec, 
            bitrate=bitrate // 1000 if bitrate else 0, 
            bitrate_mode=bitrate_mode,
            cover=cover_cached, 
            cue_count=0,
            problems=1 if file_duration == 0 else 0,
            language=language,
            year_written=year_written,
            year_recorded=year_recorded
        )


def main():
    """Command-line entry point for scanning library"""
    scanner = AudiobookScanner()
    
    config = configparser.ConfigParser()
    config.read(scanner.config_file, encoding='utf-8')
    default_path = config.get(
        'Paths',
        'default_path',
        fallback=r'E:\MY\аудиокниги'
    )
    
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else default_path
    
    scanner._log_header(scanner.tr("scanner.cli_start"))
    scanner._log_item("Path", path)
    
    count = scanner.scan_directory(path, verbose=True)
    
    scanner._log_header(scanner.tr("scanner.cli_done", count=count))
    scanner._log("")


if __name__ == '__main__':
    main()
