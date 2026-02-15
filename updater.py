"""
Auto-updater module for SP Audiobook Player.
Checks GitHub releases for new versions, downloads and applies updates.
Works both in development mode and PyInstaller-built exe.
"""
import sys
import os
import json
import time
import shutil
import zipfile
import tempfile
import threading
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor


# GitHub repository info
GITHUB_REPO = "SPluzh/SPAudiobookPlayer"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

# Files/folders to preserve during update (never overwrite)
PRESERVE_PATHS = {
    "data",
    "settings.ini",
    "_internal\\data",
}

# User-Agent for GitHub API requests
USER_AGENT = "SPAudiobookPlayer-Updater/1.0"


def get_app_root() -> Path:
    """Get the application root directory (works in both dev and frozen modes)"""
    if getattr(sys, 'frozen', False):
        # PyInstaller one-dir mode: exe is at root level
        return Path(sys.executable).parent
    # Dev mode
    return Path(__file__).parent


def get_current_version() -> str:
    """Read current version from resources/version.txt"""
    if getattr(sys, 'frozen', False):
        # In frozen mode, resources are in _internal/resources/
        version_file = Path(sys.executable).parent / "_internal" / "resources" / "version.txt"
    else:
        version_file = Path(__file__).parent / "resources" / "version.txt"
    
    try:
        if version_file.exists():
            return version_file.read_text("utf-8").strip()
    except Exception:
        pass
    return "0.0.0"


def parse_version(version_str: str) -> tuple:
    """Parse version string like '1.4.1' into tuple (1, 4, 1) for comparison"""
    version_str = version_str.lstrip("vV").strip()
    try:
        parts = [int(x) for x in version_str.split(".")]
        # Pad to 3 elements
        while len(parts) < 3:
            parts.append(0)
        return tuple(parts)
    except (ValueError, AttributeError):
        return (0, 0, 0)


def is_newer_version(remote: str, local: str) -> bool:
    """Check if remote version is newer than local version"""
    return parse_version(remote) > parse_version(local)


class UpdateCheckResult:
    """Result of checking for updates"""
    def __init__(self):
        self.update_available = False
        self.remote_version = ""
        self.download_url = ""
        self.download_size = 0
        self.release_notes = ""
        self.error = None


def check_for_update() -> UpdateCheckResult:
    """
    Check GitHub releases for a newer version.
    Returns UpdateCheckResult with all relevant info.
    """
    result = UpdateCheckResult()
    
    try:
        req = urllib.request.Request(GITHUB_API_URL, headers={
            'User-Agent': USER_AGENT,
            'Accept': 'application/vnd.github.v3+json'
        })
        
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
        
        remote_version = data.get("tag_name", "").lstrip("vV")
        local_version = get_current_version()
        
        result.remote_version = remote_version
        result.release_notes = data.get("body", "")
        
        # Find the zip asset
        for asset in data.get("assets", []):
            if asset["name"].endswith(".zip"):
                result.download_url = asset["browser_download_url"]
                result.download_size = asset.get("size", 0)
                break
        
        if remote_version and result.download_url:
            result.update_available = is_newer_version(remote_version, local_version)
    
    except urllib.error.URLError as e:
        result.error = f"Network error: {e.reason}"
    except Exception as e:
        result.error = str(e)
    
    return result


class UpdateDownloader:
    """Downloads update zip with progress reporting via callback"""
    
    def __init__(self, url: str, target_path: Path, progress_callback=None, num_threads=4):
        self.url = url
        self.target_path = target_path
        self.progress_callback = progress_callback
        self.num_threads = num_threads
        self.total_size = 0
        self.downloaded = 0
        self.lock = threading.Lock()
        self.start_time = 0
        self.cancelled = False
        self.headers = {
            'User-Agent': USER_AGENT
        }
    
    def cancel(self):
        """Cancel the download"""
        self.cancelled = True
    
    def _download_chunk(self, start, end):
        """Download a specific byte range"""
        if self.cancelled:
            return
        
        req = urllib.request.Request(self.url, headers=self.headers)
        req.add_header('Range', f'bytes={start}-{end}')
        
        with urllib.request.urlopen(req) as response:
            with open(self.target_path, 'r+b') as f:
                f.seek(start)
                chunk_size = 256 * 1024  # 256KB
                while not self.cancelled:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    with self.lock:
                        self.downloaded += len(chunk)
                        self._report_progress()
    
    def _report_progress(self):
        """Report download progress via callback"""
        if not self.progress_callback or self.total_size <= 0:
            return
        
        elapsed = time.time() - self.start_time
        if elapsed > 0:
            speed = self.downloaded / elapsed
            percent = (self.downloaded / self.total_size) * 100
            remaining = (self.total_size - self.downloaded) / speed if speed > 0 else 0
            
            self.progress_callback(
                percent=percent,
                downloaded=self.downloaded,
                total=self.total_size,
                speed=speed,
                eta=remaining
            )
    
    def download(self) -> bool:
        """Execute the download. Returns True on success."""
        try:
            # Get file size
            req = urllib.request.Request(self.url, headers=self.headers, method='HEAD')
            with urllib.request.urlopen(req) as response:
                self.total_size = int(response.info().get('Content-Length', 0))
                accept_ranges = response.info().get('Accept-Ranges') == 'bytes'
            
            # Create empty file
            with open(self.target_path, 'wb') as f:
                f.truncate(self.total_size)
            
            self.start_time = time.time()
            
            if accept_ranges and self.total_size > 0 and self.num_threads > 1:
                # Multi-threaded download
                chunk_size = self.total_size // self.num_threads
                with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
                    futures = []
                    for i in range(self.num_threads):
                        start = i * chunk_size
                        end = self.total_size - 1 if i == self.num_threads - 1 else (i + 1) * chunk_size - 1
                        futures.append(executor.submit(self._download_chunk, start, end))
                    for future in futures:
                        future.result()
            else:
                # Single-thread fallback
                self._download_chunk(0, self.total_size - 1 if self.total_size > 0 else '')
            
            return not self.cancelled
        
        except Exception as e:
            print(f"Download error: {e}")
            return False


def extract_update(zip_path: Path, extract_dir: Path) -> bool:
    """Extract the downloaded zip to a temporary directory"""
    try:
        if extract_dir.exists():
            shutil.rmtree(extract_dir)
        extract_dir.mkdir(parents=True, exist_ok=True)
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(extract_dir)
        
        return True
    except Exception as e:
        print(f"Extract error: {e}")
        return False


def generate_update_script(app_root: Path, update_source: Path, exe_name: str) -> Path:
    """
    Generate a bat script that:
    1. Waits for the app to close
    2. Copies new files over old ones (preserving data/ and settings.ini)
    3. Cleans up temp files
    4. Restarts the app
    
    Returns the path to the generated script.
    """
    script_path = app_root / "_apply_update.bat"
    
    # Build exclusion list for xcopy
    # We use robocopy instead of xcopy for better control
    exclude_dirs = "data"
    exclude_files = "settings.ini"
    
    # Find the actual content directory inside the extracted zip
    # The zip might contain a top-level folder like "SP Audiobook Player/"
    # or the files might be at the root level
    content_check = f'''
@echo off
chcp 65001 >nul 2>&1
setlocal ENABLEDELAYEDEXPANSION

echo ============================================
echo   SP Audiobook Player - Applying Update
echo ============================================
echo.

set "APP_ROOT={app_root}"
set "UPDATE_SOURCE={update_source}"
set "EXE_NAME={exe_name}"
set "PID_FILE=%APP_ROOT%\\_update_pid.txt"

REM --- Wait for the application to close ---
echo Waiting for application to close...

if exist "!PID_FILE!" (
    set /p APP_PID=<"!PID_FILE!"
    echo   Waiting for PID: !APP_PID!
    :wait_loop
    tasklist /FI "PID eq !APP_PID!" 2>nul | find /i "!APP_PID!" >nul
    if not errorlevel 1 (
        timeout /t 1 /nobreak >nul
        goto wait_loop
    )
    del /f /q "!PID_FILE!" >nul 2>&1
) else (
    REM Fallback: wait by exe name
    :wait_name_loop
    tasklist /FI "IMAGENAME eq !EXE_NAME!" 2>nul | find /i "!EXE_NAME!" >nul
    if not errorlevel 1 (
        timeout /t 1 /nobreak >nul
        goto wait_name_loop
    )
)

echo Application closed. Applying update...
timeout /t 1 /nobreak >nul

REM --- Find the content directory ---
REM The zip might have a single top-level folder or files at root
set "CONTENT_DIR=!UPDATE_SOURCE!"

REM Check if there's a single subfolder (common with GitHub releases)
set "SUBFOLDER_COUNT=0"
set "LAST_SUBFOLDER="
for /d %%D in ("!UPDATE_SOURCE!\\*") do (
    set /a SUBFOLDER_COUNT+=1
    set "LAST_SUBFOLDER=%%D"
)

REM If exactly one subfolder and no files at root, use it as content
set "FILE_COUNT=0"
for %%F in ("!UPDATE_SOURCE!\\*.*") do set /a FILE_COUNT+=1

if !SUBFOLDER_COUNT! EQU 1 if !FILE_COUNT! EQU 0 (
    set "CONTENT_DIR=!LAST_SUBFOLDER!"
    echo   Using subfolder: !CONTENT_DIR!
)

echo   Source: !CONTENT_DIR!
echo   Target: !APP_ROOT!

REM --- Copy files using robocopy ---
REM /E = recursive, /IS = include same files, /IT = include tweaked
REM /XD = exclude directories, /XF = exclude files
REM /NFL /NDL /NJH /NJS = minimal logging
echo.
echo Copying files...

robocopy "!CONTENT_DIR!" "!APP_ROOT!" /E /IS /IT /XD data /XF settings.ini /NFL /NDL /NJH /NJS /R:3 /W:1

REM Robocopy exit codes: 0-7 are success, 8+ are errors
if !ERRORLEVEL! GEQ 8 (
    echo.
    echo [ERROR] Failed to copy files! Error code: !ERRORLEVEL!
    echo The application may need to be reinstalled.
    pause
    exit /b 1
)

echo Files copied successfully!

REM --- Cleanup ---
echo Cleaning up temporary files...
rmdir /s /q "!UPDATE_SOURCE!" >nul 2>&1

REM Remove the downloaded zip if still present
if exist "!APP_ROOT!\\_update_download.zip" del /f /q "!APP_ROOT!\\_update_download.zip" >nul 2>&1

echo.
echo ============================================
echo   Update applied successfully!
echo ============================================
echo.

REM --- Restart the application ---
echo Restarting application...
start "" "!APP_ROOT!\\!EXE_NAME!"

REM --- Self-delete this script ---
(goto) 2>nul & del "%~f0"
'''
    
    script_path.write_text(content_check, encoding='utf-8')
    return script_path


def apply_update(zip_path: Path, progress_callback=None) -> bool:
    """
    Apply a downloaded update:
    1. Extract zip to temp dir
    2. Generate update bat script
    3. Write PID file for the script to wait on
    4. Launch bat script
    5. Signal the app to close
    
    Returns True if the update process was started successfully.
    """
    app_root = get_app_root()
    update_dir = app_root / "_update_temp"
    
    if progress_callback:
        progress_callback(status="extracting")
    
    # Extract
    if not extract_update(zip_path, update_dir):
        return False
    
    if progress_callback:
        progress_callback(status="preparing")
    
    # Determine exe name
    if getattr(sys, 'frozen', False):
        exe_name = Path(sys.executable).name
    else:
        exe_name = "SP Audiobook Player.exe"
    
    # Write PID file so the update script knows what to wait for
    pid_file = app_root / "_update_pid.txt"
    pid_file.write_text(str(os.getpid()), encoding='utf-8')
    
    # Generate and launch update script
    script_path = generate_update_script(app_root, update_dir, exe_name)
    
    if progress_callback:
        progress_callback(status="launching")
    
    # Launch the update script in a new visible window
    subprocess.Popen(
        ['cmd', '/c', str(script_path)],
        creationflags=subprocess.CREATE_NEW_CONSOLE,
        cwd=str(app_root)
    )
    
    return True


def format_size(size_bytes: int) -> str:
    """Format bytes into human readable string"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
