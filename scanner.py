import sqlite3
import re
from pathlib import Path
import configparser
import json
import sys
import hashlib

from database import init_database

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
        
        print("\n" + "=" * 70)
        print(self.tr("scanner.init_title"))
        print("=" * 70)
        
        # ffprobe path
        path_str = self.config.get('Paths', 'ffprobe_path', fallback=str(self.script_dir / 'resources' / 'bin' / 'ffprobe.exe'))
        self.ffprobe_path = Path(path_str)
        if not self.ffprobe_path.is_absolute():
            self.ffprobe_path = self.script_dir / self.ffprobe_path
        self.has_ffprobe = self.ffprobe_path.exists()
        
        print(f"\n{self.tr('scanner.working_paths')}")
        print(self.tr("scanner.path_script", path=self.script_dir))
        print(self.tr("scanner.path_config", path=self.config_file))
        print(self.tr("scanner.path_db", path=self.db_file))
        print(self.tr("scanner.path_covers", path=self.covers_dir))
        
        if self.has_ffprobe:
            print(self.tr("scanner.ffprobe_found", path=self.ffprobe_path))
        else:
            print(self.tr("scanner.ffprobe_not_found"))
        
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
            fallback='.mp3,.m4a,.m4b,.ogg,.flac,.wav,.aac,.wma,.opus'
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
        print("\n" + "-" * 70)
        print(self.tr("scanner.loading_settings"))
        print("-" * 70)
        
        print("\n" + self.tr("scanner.audio_formats", count=len(self.audio_extensions)))
        print(f"  {', '.join(sorted(self.audio_extensions))}")
        
        print("\n" + self.tr("scanner.cover_names", count=len(self.cover_names)))
        for name in self.cover_names:
            print(f"  - {name}")


    def _init_database(self):
        """Initialize database schema"""
        print("\n" + "-" * 70)
        print(self.tr("scanner.db_init"))
        print("-" * 70)
        
        init_database(self.db_file)
        
        print("\n" + self.tr("scanner.db_tables_ready"))
        print(self.tr("scanner.db_indexes_ready"))
        print(self.tr("scanner.db_cascade_on"))


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
                            
            elif suffix in ('.m4a', '.m4b'):
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

        except Exception:
            pass
            
        # Cleanup values
        for key in tags:
            if isinstance(tags[key], str) and tags[key].lower() in ('none', '[none]', 'unknown', ''):
                tags[key] = ''
                
        return tags

    def _extract_metadata(self, directory, files):
        """Extract metadata for the audiobook by checking first few files"""
        metadata = {'author': '', 'title': '', 'narrator': '', 'year': ''}
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
    
    def _get_audio_duration(self, path, verbose=False):
        """Get audio duration using Mutagen or ffprobe"""
        # Method 1: Mutagen
        try:
            from mutagen.mp3 import MP3
            from mutagen.mp4 import MP4
            from mutagen.flac import FLAC
            from mutagen.oggvorbis import OggVorbis
            from mutagen.wave import WAVE
            
            suffix = path.suffix.lower()
            audio = None
            
            if suffix == '.mp3':
                audio = MP3(path)
            elif suffix in ('.m4a', '.m4b', '.aac'):
                audio = MP4(path)
            elif suffix == '.flac':
                audio = FLAC(path)
            elif suffix == '.ogg':
                audio = OggVorbis(path)
            elif suffix == '.wav':
                audio = WAVE(path)
            
            if audio and audio.info and hasattr(audio.info, 'length'):
                duration = audio.info.length
                if duration > 0:
                    return duration
        except Exception as e:
            if verbose:
                print(self.tr("scanner.log_mutagen_error", error=type(e).__name__))
        
        # Method 2: ffprobe
        if self.has_ffprobe:
            try:
                import subprocess
                
                # Hide console window on Windows
                startupinfo = None
                if hasattr(subprocess, 'STARTUPINFO'):
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                
                result = subprocess.run(
                    [
                        str(self.ffprobe_path),
                        '-v', 'error',
                        '-show_entries', 'format=duration',
                        '-of', 'default=noprint_wrappers=1:nokey=1',
                        str(path)
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    startupinfo=startupinfo
                )
                
                if result.returncode == 0 and result.stdout.strip():
                    duration = float(result.stdout.strip())
                    if duration > 0:
                        if verbose:
                            print(self.tr("scanner.log_ffprobe_duration", duration=duration))
                        return duration
            except Exception as e:
                if verbose:
                    print(self.tr("scanner.log_ffprobe_error", error=type(e).__name__))
        
        if verbose:
            print(self.tr("scanner.log_duration_failed"))
        return 0


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
                
                if f.suffix.lower() == '.mp3':
                    tags = ID3(f)
                    for tag in tags.values():
                        if isinstance(tag, APIC):
                            cover_path.write_bytes(tag.data)
                            return str(cover_path)
                
                elif f.suffix.lower() in ('.m4a', '.m4b'):
                    audio = MP4(f)
                    if 'covr' in audio:
                        cover_path.write_bytes(audio['covr'][0])
                        return str(cover_path)
                
                elif f.suffix.lower() == '.flac':
                    audio = FLAC(f)
                    if audio.pictures:
                        cover_path.write_bytes(audio.pictures[0].data)
                        return str(cover_path)
            except Exception:
                continue
        
        return None
    
    def _find_cover(self, directory, key):
        """Find cover image (file or embedded) for the audiobook"""
        for name in self.cover_names:
            p = directory / name
            if p.exists():
                return str(p)
        
        for f in directory.iterdir():
            if f.is_file() and f.suffix.lower() in {'.jpg', '.jpeg', '.png', '.bmp'}:
                return str(f)
        
        return self._extract_embedded_cover(directory, key)

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


    def scan_directory(self, root_path, verbose=False):
        """Perform recursive directory scanning for audiobooks"""
        print("\n" + "=" * 70)
        print(self.tr("scanner.scan_start"))
        print("=" * 70)
        
        root = Path(root_path)
        print("\n" + self.tr("scanner.root_dir", path=root))
        
        if not root.exists():
            print("\n" + self.tr("scanner.error_not_exists"))
            return 0
        
        with sqlite3.connect(self.db_file) as conn:
            c = conn.cursor()
            c.execute("PRAGMA foreign_keys = ON")
            
            # Save current progress state to temp table
            print("\n" + "-" * 70)
            print(self.tr("scanner.saving_state"))
            print("-" * 70)
            
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
                    is_completed
                FROM audiobooks
                WHERE is_folder = 0
            """)
            
            # Reset availability for all books before scanning
            c.execute("UPDATE audiobooks SET is_available = 0")
            
            c.execute("SELECT COUNT(*) FROM temp_state")
            saved_count = c.fetchone()[0]
            print(self.tr("scanner.saved_progress_count", count=saved_count))
            
            # Searching for folders
            print("\n" + "-" * 70)
            print(self.tr("scanner.searching_books"))
            print("-" * 70)
            
            folders = [
                d for d in root.rglob('*')
                if d.is_dir() and self._has_audio_files(d)
            ]
            
            print("\n" + self.tr("scanner.found_folders", count=len(folders)))
            
            # Processing each folder
            print("\n" + "-" * 70)
            print(self.tr("scanner.processing_books"))
            print("-" * 70)
            
            for idx, folder in enumerate(folders, 1):
                rel = folder.relative_to(root)
                parent = rel.parent if str(rel.parent) != '.' else ''
                
                # Get file list
                files = sorted(
                    f for f in folder.iterdir()
                    if f.is_file() and f.suffix.lower() in self.audio_extensions
                )
                
                # Calculate current state hash
                current_state_hash = self._calculate_state_hash(files)
                
                # Check for existing record and state hash
                c.execute("SELECT id, state_hash FROM audiobooks WHERE path = ?", (str(rel),))
                existing_row_data = c.fetchone()
                
                if existing_row_data and existing_row_data[1] == current_state_hash:
                    # Hash matches - skip deep scan and update availability
                    c.execute("UPDATE audiobooks SET is_available = 1 WHERE id = ?", (existing_row_data[0],))
                    if verbose:
                        print(f"  {self.tr('scanner.skip_existing', path=rel)}")
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
                
                if author or title or narrator:
                    print(f"  {self.tr('scanner.author', author=author or self.tr('scanner.not_specified'))}")
                    print(f"  {self.tr('scanner.title', title=title or self.tr('scanner.not_specified'))}")
                    if narrator:
                        print(f"  {self.tr('scanner.narrator', narrator=narrator)}")
                
                if t_author or t_title:
                    print(f"  Tags: Author='{t_author}', Title='{t_title}', Narrator='{t_narrator}'")
                
                # Count files and calculate total duration
                file_count = len(files)
                duration = 0
                failed_count = 0
                
                for f in files:
                    file_duration = self._get_audio_duration(f, verbose=verbose)
                    duration += file_duration
                    if file_duration == 0:
                        failed_count += 1
                
                hours = int(duration // 3600)
                minutes = int((duration % 3600) // 60)
                
                if failed_count > 0:
                    print(self.tr("scanner.files_stats_problem", count=file_count, failed=failed_count, hours=hours, minutes=minutes))
                    print(self.tr("scanner.duration_warn", count=failed_count))
                else:
                    print(self.tr("scanner.files_stats", count=file_count, hours=hours, minutes=minutes))
                
                # Search for cover image
                cover = self._find_cover(folder, str(rel))
                if cover:
                    cover_name = Path(cover).name
                    print(self.tr("scanner.cover_found", name=cover_name))
                
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
                    listened, prog_pct, cur_idx, cur_pos, playback_speed, is_started, is_completed = state
                    if prog_pct > 0:
                        print(self.tr("scanner.progress_restored", percent=prog_pct))
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
                            file_count = ?,
                            duration = ?,
                            state_hash = ?,
                            is_available = 1
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
                        file_count,
                        duration,
                        current_state_hash,
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
                            cover_path,
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
                            state_hash
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, 1, ?)
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
                        file_count,
                        duration,
                        listened,
                        prog_pct,
                        cur_idx,
                        cur_pos,
                        playback_speed,
                        is_started,
                        is_completed,
                        current_state_hash
                    ))
                    c.execute("SELECT id FROM audiobooks WHERE path = ?", (str(rel),))
                    book_id = c.fetchone()[0]

                # Update files list: remove old and insert current files
                c.execute("DELETE FROM audiobook_files WHERE audiobook_id = ?", (book_id,))
                
                for i, f in enumerate(files, 1):
                    f_tags = self._extract_file_tags(f)
                    # Use track number from tag if available, otherwise sequential index
                    track_no = f_tags['track'] if f_tags['track'] is not None else i
                    file_duration = self._get_audio_duration(f)
                    
                    c.execute("""
                        INSERT INTO audiobook_files
                        (
                            audiobook_id, file_path, file_name, track_number, duration,
                            tag_title, tag_artist, tag_album, tag_genre, tag_comment
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        book_id,
                        str(f.relative_to(root)),
                        f.name,
                        track_no,
                        file_duration,
                        f_tags['title'],
                        f_tags['author'],
                        f_tags['album'],
                        f_tags['genre'],
                        f_tags['comment']
                    ))
            
            # Recreate intermediate folder structure
            print("\n" + "-" * 70)
            print(self.tr("scanner.creating_structure"))
            print("-" * 70)
            
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
                    (path, parent_path, name, author, title, narrator, cover_path,
                     file_count, duration, listened_duration, progress_percent, is_folder,
                     current_file_index, current_position, is_started, is_completed, is_available)
                    VALUES (?, ?, ?, '', '', '', NULL, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1)
                """, (path_str, parent, path_obj.name))
                
                # Mark existing folder as available
                c.execute(
                    "UPDATE audiobooks SET is_available = 1 WHERE path = ? AND is_folder = 1",
                    (path_str,)
                )
            
            for folder in folders:
                rel = folder.relative_to(root)
                parent = rel.parent
                if str(parent) != '.':
                    save_folder(str(parent))
            
            print(self.tr("scanner.created_folders", count=len(saved_folders)))
            
            # Finalize: cleanup temp table and commit
            c.execute("DROP TABLE temp_state")
            conn.commit()
        
        # Result statistics
        print("\n" + "=" * 70)
        print(self.tr("scanner.scan_complete"))
        print("=" * 70)
        print("\n" + self.tr("scanner.processed_count", count=len(folders)))
        print(self.tr("scanner.db_file", path=self.db_file))
        print()
        
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
    
    print("\n" + "=" * 70)
    print(scanner.tr("scanner.cli_start"))
    print("=" * 70)
    print("\n" + scanner.tr("scanner.cli_path", path=path))
    
    count = scanner.scan_directory(path, verbose=True)
    
    print("=" * 70)
    print(scanner.tr("scanner.cli_done", count=count))
    print("=" * 70 + "\n")


if __name__ == '__main__':
    main()
