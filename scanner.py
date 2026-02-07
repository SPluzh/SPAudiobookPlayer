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
    
    def __init__(self, config_file='settings.ini'):
        """Initialize scanner and load configurations"""
        self.script_dir = Path(__file__).parent
        self.config_file = self.script_dir / 'resources' / config_file
        
        # Load settings
        self._load_settings()
        
        # Paths
        self.db_file = self.script_dir / 'data' / 'audiobooks.db'
        
        covers_dir_str = self.config.get('Paths', 'covers_dir', fallback='data/extracted_covers')
        self.covers_dir = Path(covers_dir_str)
        if not self.covers_dir.is_absolute():
            self.covers_dir = self.script_dir / self.covers_dir
        
        # Load translations
        self._load_translations()
        
    def _log(self, message: str, end: str = '\n'):
        """Helper to print formatted messages"""
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
        self.config_file = self.script_dir / 'resources' / config_file
        
        # Load settings
        self._load_settings()
        
        # Paths
        self.db_file = self.script_dir / 'data' / 'audiobooks.db'
        
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
            fallback='cover.jpg,cover.png,cover.jpeg,folder.jpg,folder.png'
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
                    return fixed
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
            
        return text

    @staticmethod
    def _parse_audiobook_name(folder_name):
        """Parse audiobook folder name into author, title, and narrator"""
        narrator = ''
        folder_name_clean = folder_name.strip()
        
        # Look for square or round brackets at the end
        m = re.search(r'[\[\(](.+?)[\]\)]$', folder_name_clean)
        if m:
            bracket_content = m.group(1).strip()
            folder_name_clean = folder_name_clean[:m.start()].strip()
            
            # Split by commas
            parts = [p.strip() for p in bracket_content.split(',')]
            
            if parts:
                first_part = parts[0]
                
                # Check if it's NOT technical info
                is_technical = (
                    re.match(r'^\d{4}$', first_part) or  # Year
                    any(kw in first_part.lower() for kw in ['kbps', 'mp3', 'm4b', 'flac', 'ogg', 'wav'])
                )
                
                if not is_technical:
                    # Remove "narrated by" or equivalent prefixes
                    narrator = re.sub(r'^(чит\.|читает)\s+', '', first_part, flags=re.IGNORECASE).strip()
                    
                    # Remove studio abbreviations in brackets if present
                    if re.search(r'\([А-ЯA-Z]{2,5}\)$', narrator):
                        narrator = re.sub(r'\s*\([А-ЯA-Z]{2,5}\)$', '', narrator).strip()
        
        # Split author and title by dash/hyphen
        m2 = re.split(r'\s*[–—-]\s*', folder_name_clean, maxsplit=1)
        if len(m2) == 2:
            author, title = m2
        else:
            author = ''
            title = folder_name_clean
        
        return author.strip(), title.strip(), narrator.strip()
    
    
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
            # Try different encodings
            content = None
            for enc in ['utf-8-sig', 'utf-8', 'cp1251', 'latin-1']:
                try:
                    with open(cue_path, 'r', encoding=enc) as f:
                        content = f.read()
                    break
                except UnicodeDecodeError:
                    continue
            
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

    def _analyze_files_parallel(self, files, max_workers=4, verbose=False):
        """Analyze a list of files concurrently"""
        if not files:
            return []
            
        # Strategy: Run fast mutagen analysis in parallel. 
        # Then run ffprobe sequentially for those that still need it 
        # (ffprobe is heavy, multicore ffprobe might be too much I/O).
        
        workers = min(max_workers, len(files))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            fast_results = list(executor.map(lambda f: self._analyze_file_fast(f, verbose), files))
            
        final_results = []
        for f, info in zip(files, fast_results):
            if info.pop('needs_ffprobe', False):
                info = self._analyze_file_with_ffprobe(f, info, verbose)
            final_results.append(info)
            
        return final_results


    def _extract_embedded_cover(self, directory, key):
        """Extract embedded cover image from audio files"""
        try:
            from mutagen.id3 import ID3, APIC
            from mutagen.mp4 import MP4
            from mutagen.flac import FLAC
        except Exception:
            return None
        
        audio_files = sorted(
            f for f in directory.iterdir()
            if f.is_file() and f.suffix.lower() in self.audio_extensions
        )
        
        for f in audio_files[:3]:
            try:
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
                    else:
                        # Fallback if image load fails 
                        pass

            except Exception:
                continue
        
        return None
    
    def _find_cover(self, directory, key):
        """Find cover image (file or embedded) for the audiobook. Returns (original_path, cached_path)"""
        
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
                if f.is_file() and f.suffix.lower() in {'.jpg', '.jpeg', '.png', '.bmp'}:
                     cached = cache_file(str(f))
                     return str(f), cached
        except (PermissionError, OSError):
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
        for ext in ('.jpg', '.jpeg', '.png', '.bmp'):
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

    def _calculate_state_hash(self, files):
        """Calculate a hash based on file names, sizes, and modification times"""
        state_info = []
        for f in files:
            try:
                stat = f.stat()
                state_info.append(f"{f.name}|{stat.st_size}|{stat.st_mtime}")
            except Exception:
                continue
        
        state_str = "\n".join(state_info)
        return hashlib.md5(state_str.encode('utf-8')).hexdigest()


    def _log_book_summary(self, title, author, narrator, duration, file_count, codec, bitrate, bitrate_mode, cover, cue_count, problems):
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
        
        # Line 4: Extras (Cover, CUE, Problems)
        extras = []
        if cover:
            extras.append("[Cover: OK]")
        if cue_count > 0:
            extras.append(f"[CUE: {cue_count}]")
            
        if problems > 0:
            extras.append(f"[WARNING: {problems} failed files]")
            
        if extras:
            self._log(f"    {' '.join(extras)}")

    def scan_directory(self, root_path, verbose=False):
        """Perform recursive directory scanning for audiobooks"""
        start_time = time.time()
        self._log_header(self.tr("scanner.scan_start"))
        
        root = Path(root_path)
        self._log_item("Root", str(root))
        
        if not root.exists():
            self._log_error(self.tr("scanner.error_not_exists"))
            return 0
        
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
            c.execute("UPDATE audiobooks SET is_available = 0")
            
            c.execute("SELECT COUNT(*) FROM temp_state")
            saved_count = c.fetchone()[0]
            self._log_info(self.tr("scanner.saved_progress_count", count=saved_count))
            
            # Searching for folders
            # Searching for folders
            self._log_section(self.tr("scanner.searching_books"))
            
            folders = []
            for dirpath, dirnames, filenames in os.walk(root):
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
                
                # Check for audio files in current filenames list (fast)
                has_audio = any(Path(fn).suffix.lower() in self.audio_extensions for fn in filenames)
                
                if has_audio or (rel_path_str in merged_paths_set):
                    folders.append(d)
            
            self._log_info(self.tr("scanner.found_folders", count=len(folders)))
            
            # Processing each folder
            # Processing each folder
            self._log_section(self.tr("scanner.processing_books"))
            
            for idx, folder in enumerate(folders, 1):
                rel = folder.relative_to(root)
                parent = rel.parent if str(rel.parent) != '.' else ''
                
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
                
                # Calculate current state hash
                current_state_hash = self._calculate_state_hash(files)
                
                # Check for existing record and state hash
                c.execute("SELECT id, state_hash, codec FROM audiobooks WHERE path = ?", (str(rel),))
                existing_row_data = c.fetchone()
                
                # Skip if valid existing record found and codec is populated
                if existing_row_data:
                    db_hash = existing_row_data[1]
                    db_codec = existing_row_data[2]
                    
                    if db_hash == current_state_hash and db_codec is not None:
                        c.execute("UPDATE audiobooks SET is_available = 1 WHERE id = ?", (existing_row_data[0],))
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
                
                # Analyze files
                file_count = len(files)
                duration = 0
                failed_count = 0
                
                file_analyses = []
                bitrates = []
                codecs = []
                
                # VBR detection stats
                vbr_detected = False
                cbr_detected = False
                
                # Analyze files in parallel
                file_analyses = self._analyze_files_parallel(files, max_workers=4, verbose=verbose)
                
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
                
                # Search for cover image
                cover, cover_cached = self._find_cover(folder, str(rel))

                # Check for .cue files in this folder
                cue_files = list(folder.glob('*.cue'))
                cue_data_chapters = []
                if cue_files:
                    _, cue_data_chapters = self._parse_cue_file(cue_files[0])

                # Check for description file
                description = ""
                potential_desc_files = sorted([f for f in folder.glob("*.txt")])
                # Prioritize: 'description.txt', 'info.txt', '{folder_name}.txt'
                priority_names = ['description', 'info', 'about', folder.name.lower()]
                selected_file = None
                
                # Check priority
                for p_name in priority_names:
                    for f in potential_desc_files:
                        if f.stem.lower() == p_name:
                            selected_file = f
                            break
                    if selected_file:
                        break
                
                # Fallback to first text file if any exist
                if not selected_file and potential_desc_files:
                    selected_file = potential_desc_files[0]
                
                if selected_file:
                    description = ""
                    # smart encoding detection
                    encodings = ['utf-8', 'cp1251', 'cp1252', 'latin-1']
                    for enc in encodings:
                        try:
                            with open(selected_file, 'r', encoding=enc, errors='strict') as df:
                                description = df.read().strip()
                            if description:
                                break
                        except UnicodeDecodeError:
                            continue
                        except Exception:
                            break
                    
                    # Fallback if all strict attempts fail
                    if not description:
                        try:
                            with open(selected_file, 'r', encoding='utf-8', errors='replace') as df:
                                description = df.read().strip()
                        except Exception:
                            pass

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
                    problems=failed_count
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
                        is_completed
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
                c.execute("SELECT id FROM audiobooks WHERE path = ?", (str(rel),))
                existing_row = c.fetchone()
                
                if existing_row:
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
                            time_added, is_merged, description
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?)
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
                        description
                    ))
                    c.execute("SELECT id FROM audiobooks WHERE path = ?", (str(rel),))
                    book_id = c.fetchone()[0]

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
            
            saved_folders = set()
            
            def save_folder(path_str):
                """Recursively save parent folders in database"""
                if path_str in saved_folders or path_str == '':
                    return
                saved_folders.add(path_str)
                
                path_obj = Path(path_str)
                parent = str(path_obj.parent) if str(path_obj.parent) != '.' else ''
                
                if parent:
                    save_folder(parent)
                
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
                """, (path_str, parent, path_obj.name))
                
                # Mark existing folder as available and ensure time_added is set
                c.execute("""
                    UPDATE audiobooks 
                    SET is_available = 1,
                        time_added = COALESCE(time_added, CURRENT_TIMESTAMP)
                    WHERE path = ? AND is_folder = 1
                """, (path_str,))
            
            for folder in folders:
                rel = folder.relative_to(root)
                parent = rel.parent
                if str(parent) != '.':
                    save_folder(str(parent))
            
            self._log_info(self.tr("scanner.created_folders", count=len(saved_folders)))
            
            # Finalize: cleanup temp table and commit
            c.execute("DROP TABLE temp_state")
            conn.commit()
        
        # Result statistics
        elapsed_time = time.time() - start_time
        elapsed_minutes = int(elapsed_time // 60)
        elapsed_seconds = int(elapsed_time % 60)
        
        self._log_header(self.tr("scanner.scan_complete"))
        self._log_info(self.tr("scanner.processed_count", count=len(folders)))
        self._log_info(self.tr("scanner.elapsed_time", minutes=elapsed_minutes, seconds=elapsed_seconds))
        self._log_info(self.tr("scanner.db_file", path=self.db_file))
        self._log("")
        
        return len(folders)


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
