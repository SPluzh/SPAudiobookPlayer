import os
import sys
import urllib.request
import zipfile
import shutil
import time
import argparse
import threading
import json
import configparser
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

def load_translations():
    """Load translation strings for the updater based on app settings"""
    script_dir = Path(__file__).parent
    config_file = script_dir / 'resources' / 'settings.ini'
    lang = 'en'
    
    if config_file.exists():
        try:
            config = configparser.ConfigParser()
            config.read(config_file, encoding='utf-8')
            lang = config.get('Display', 'language', fallback='en')
        except:
            pass
            
    trans_file = script_dir / 'resources' / 'translations' / f'{lang}.json'
    translations = {}
    if trans_file.exists():
        try:
            with open(trans_file, 'r', encoding='utf-8') as f:
                translations = json.load(f)
        except:
            pass
    return translations

_translations = None

def tr(key, **kwargs):
    """Local translation function for the standalone updater script"""
    global _translations
    if _translations is None:
        _translations = load_translations()
        
    parts = key.split('.')
    data = _translations
    for p in parts:
        if isinstance(data, dict) and p in data:
            data = data[p]
        else:
            return key
            
    if isinstance(data, str):
        try:
            return data.format(**kwargs)
        except:
            return data
    return key

def format_size(size_bytes):
    """Format bytes into human readable MB string"""
    return f"{size_bytes / (1024 * 1024):.1f} MB"

def safe_unlink(path, retries=5, delay=0.5):
    """Safely delete a file with retries for Windows permission issues"""
    for i in range(retries):
        try:
            if path.exists():
                path.unlink()
            return True
        except PermissionError:
            if i < retries - 1:
                time.sleep(delay)
            else:
                print(tr('ffmpeg_updater.warning_delete', path=path))
                return False
        except Exception as e:
            print(tr('ffmpeg_updater.error_delete', path=path, error=e))
            return False
    return False

class Downloader:
    """Multi-threaded file downloader with progress reporting"""
    
    def __init__(self, url, target_path, num_threads=8):
        """Initialize downloader with URL and target path"""
        self.url = url
        self.target_path = target_path
        self.num_threads = num_threads
        self.total_size = 0
        self.read_so_far = 0
        self.start_time = 0
        self.lock = threading.Lock()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

    def _download_chunk(self, start, end):
        """Download a specific byte range of the file"""
        req = urllib.request.Request(self.url, headers=self.headers)
        req.add_header('Range', f'bytes={start}-{end}')
        
        with urllib.request.urlopen(req) as response:
            with open(self.target_path, 'r+b') as f:
                f.seek(start)
                chunk_size = 1024 * 256 # 256KB inner buffer
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    with self.lock:
                        self.read_so_far += len(chunk)
                        self._report_progress()

    def _report_progress(self):
        """Calculate and print download progress, speed, and ETA"""
        elapsed_time = time.time() - self.start_time
        if elapsed_time > 0:
            speed_val = self.read_so_far / elapsed_time
            speed_str = f"{speed_val / (1024 * 1024):.1f} MB/s"
            
            if self.total_size > 0:
                percent = self.read_so_far * 100 / self.total_size
                remaining_bytes = self.total_size - self.read_so_far
                eta_secs = remaining_bytes / speed_val if speed_val > 0 else 0
                eta_str = f"{int(eta_secs // 60)}m {int(eta_secs % 60)}s"
                
                s = tr('ffmpeg_updater.progress', 
                       current=format_size(self.read_so_far), 
                       total=format_size(self.total_size), 
                       percent=percent,
                       speed=speed_str,
                       eta=eta_str)
            else:
                s = tr('ffmpeg_updater.progress_unknown', 
                       current=format_size(self.read_so_far),
                       speed=speed_str)
            
            sys.stdout.write(s)
            sys.stdout.flush()

    def download(self):
        """Execute the multi-threaded download process"""
        # Initial request to get file size and check range support
        req = urllib.request.Request(self.url, headers=self.headers, method='HEAD')
        with urllib.request.urlopen(req) as response:
            self.total_size = int(response.info().get('Content-Length', 0))
            accept_ranges = response.info().get('Accept-Ranges') == 'bytes'

        # Create empty file of target size
        with open(self.target_path, 'wb') as f:
            f.truncate(self.total_size)

        self.start_time = time.time()
        
        if accept_ranges and self.total_size > 0:
            chunk_size = self.total_size // self.num_threads
            futures = []
            with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
                for i in range(self.num_threads):
                    start = i * chunk_size
                    end = self.total_size - 1 if i == self.num_threads - 1 else (i + 1) * chunk_size - 1
                    futures.append(executor.submit(self._download_chunk, start, end))
                for future in futures:
                    future.result() # Wait for completion and raise errors if any
        else:
            # Fallback to single thread if ranges not supported
            self._download_chunk(0, self.total_size - 1 if self.total_size > 0 else '')

        return time.time() - self.start_time

def download_ffmpeg(force=False):
    """Orchestrate downloading, extracting, and installing FFmpeg/ffprobe"""
    # URL for FFmpeg release essentials (Windows builds by gyan.dev)
    url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    script_dir = Path(__file__).parent
    bin_dir = script_dir / "resources" / "bin"
    zip_path = script_dir / "resources" / "ffmpeg.zip"
    
    print("=" * 60)
    print(f"      {tr('ffmpeg_updater.title')}      ")
    print("=" * 60)
    
    # Check existing files
    print(f"\n{tr('ffmpeg_updater.check_dir')}")
    if not bin_dir.exists():
        print(tr('ffmpeg_updater.creating', path=bin_dir))
        bin_dir.mkdir(exist_ok=True)
    
    ffmpeg_exe = bin_dir / "ffmpeg.exe"
    ffprobe_exe = bin_dir / "ffprobe.exe"
    
    if ffmpeg_exe.exists() and ffprobe_exe.exists() and not force:
        print(tr('ffmpeg_updater.already_exist', path=bin_dir))
        print(f"    • ffmpeg.exe: {format_size(ffmpeg_exe.stat().st_size)}")
        print(f"    • ffprobe.exe: {format_size(ffprobe_exe.stat().st_size)}")
        print(tr('ffmpeg_updater.skip_hint'))
        return True

    if force:
        print(tr('ffmpeg_updater.force_requested'))

    print(f"\n{tr('ffmpeg_updater.downloading')}")
    print(tr('ffmpeg_updater.source', url=url))
    
    try:
        downloader = Downloader(url, zip_path)
        duration = downloader.download()
        print(tr('ffmpeg_updater.download_success', time=duration))
        
        print(f"\n{tr('ffmpeg_updater.extracting')}")
        ffmpeg_found = False
        ffprobe_found = False
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for file_info in zip_ref.infolist():
                filename = os.path.basename(file_info.filename)
                if filename in ["ffmpeg.exe", "ffprobe.exe"]:
                    target_path = bin_dir / filename
                    print(tr('ffmpeg_updater.extract_msg', exe=filename, path=target_path))
                    with zip_ref.open(file_info) as source, open(target_path, "wb") as target:
                        shutil.copyfileobj(source, target)
                    
                    if filename == "ffmpeg.exe": ffmpeg_found = True
                    if filename == "ffprobe.exe": ffprobe_found = True
        
        print(f"\n{tr('ffmpeg_updater.finishing')}")
        if ffmpeg_found and ffprobe_found:
            print("-" * 40)
            print(tr('ffmpeg_updater.success'))
            print(tr('ffmpeg_updater.location', path=bin_dir))
            print(f"  ffmpeg.exe: {format_size(ffmpeg_exe.stat().st_size)}")
            print(f"  ffprobe.exe: {format_size(ffprobe_exe.stat().st_size)}")
            print("-" * 40)
            return True
        else:
            print(tr('ffmpeg_updater.warning_not_found'))
            return False
            
    except Exception as e:
        print(tr('ffmpeg_updater.error', error=e))
        return False
    finally:
        if zip_path.exists():
            print(tr('ffmpeg_updater.cleanup'))
            safe_unlink(zip_path)

if __name__ == "__main__":
    # Ensure stdout uses utf-8
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except:
            pass

    parser = argparse.ArgumentParser(description=tr('ffmpeg_updater.arg_desc'))
    parser.add_argument("-u", "--update", "-f", "--force", action="store_true", 
                        help=tr('ffmpeg_updater.arg_force'))
    args = parser.parse_args()

    try:
        download_ffmpeg(force=args.update)
    except KeyboardInterrupt:
        print(tr('ffmpeg_updater.interrupted'))
    
    print("\n" + "=" * 60)
    input(tr('ffmpeg_updater.press_enter'))
