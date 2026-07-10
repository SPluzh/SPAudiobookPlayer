"""
Auto-updater module for SP Audiobook Player.
Checks GitHub releases for new versions, downloads and applies updates.
Works both in development mode and PyInstaller-built exe.
"""
import sys
import os
import ssl
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

# Fallback: check raw version file (public branch)
GITHUB_RAW_VERSION_URL = (
    f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/resources/version.txt"
)

# Files/folders to preserve during update (never overwrite)
PRESERVE_PATHS = {
    "data",
    "settings.ini",
    "_internal\\data",
}

# User-Agent for GitHub API requests
USER_AGENT = "SPAudiobookPlayer-Updater/1.0"

# Network settings
_TIMEOUT = 12          # seconds per attempt
_MAX_RETRIES = 2       # how many times to retry on transient errors
_RETRY_DELAY = 1.5     # seconds between retries

# Token file name (placed next to exe or src/, never committed)
_TOKEN_FILE = ".github_token"


def _get_github_token() -> str:
    """
    Load a GitHub Personal Access Token for authenticated API requests.
    Priority:
      1. Environment variable GITHUB_TOKEN
      2. File .github_token next to the exe / src directory
    Returns empty string if not found.
    """
    # 1. Env var
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        return token
    # 2. Token file
    if getattr(sys, 'frozen', False):
        token_path = Path(sys.executable).parent / _TOKEN_FILE
    else:
        token_path = Path(__file__).parent / _TOKEN_FILE
    if token_path.exists():
        try:
            token = token_path.read_text("utf-8").strip()
        except Exception:
            pass
    return token


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


def _make_ssl_context(verify: bool = True) -> ssl.SSLContext:
    """Create an SSL context, optionally with verification disabled."""
    if verify:
        ctx = ssl.create_default_context()
    else:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _urlopen_with_retry(req: urllib.request.Request, timeout: int = _TIMEOUT) -> bytes:
    """
    Open a URL with retry logic and SSL fallback.
    Returns response bytes. Raises on final failure.
    """
    last_error = None
    # First pass: normal SSL; second pass: relaxed SSL
    ssl_contexts = [_make_ssl_context(verify=True), _make_ssl_context(verify=False)]

    for ctx in ssl_contexts:
        for attempt in range(_MAX_RETRIES + 1):
            try:
                with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                    return resp.read()
            except urllib.error.HTTPError as e:
                # HTTP errors (4xx/5xx) are final — no point retrying
                raise
            except urllib.error.URLError as e:
                last_error = e
                reason = str(e.reason) if e.reason else str(e)
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_DELAY)
            except OSError as e:
                last_error = e
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_DELAY)
        # If we survived the retry loop without success, try next SSL context

    raise last_error or Exception("Unknown network error")


def _describe_url_error(e: urllib.error.URLError) -> str:
    """Turn a URLError into a user-friendly Russian/English message."""
    reason = str(e.reason) if e.reason else str(e)
    reason_lower = reason.lower()
    if "ssl" in reason_lower or "certificate" in reason_lower:
        return f"SSL error: {reason}"
    if "timed out" in reason_lower or "timeout" in reason_lower:
        return f"Connection timed out (server did not respond in {_TIMEOUT}s)"
    if "name or service not known" in reason_lower or "getaddrinfo" in reason_lower:
        return "DNS lookup failed — check your internet connection"
    if "connection refused" in reason_lower:
        return "Connection refused by server"
    return f"Network error: {reason}"


def _check_via_releases_api() -> "UpdateCheckResult":
    """Primary method: fetch the latest release from GitHub API."""
    result = UpdateCheckResult()
    headers = {
        'User-Agent': USER_AGENT,
        'Accept': 'application/vnd.github.v3+json'
    }
    token = _get_github_token()
    if token:
        headers['Authorization'] = f'Bearer {token}'
    req = urllib.request.Request(GITHUB_API_URL, headers=headers)
    try:
        raw = _urlopen_with_retry(req)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            result.error = "Repository or releases not found on GitHub (404)"
        elif e.code == 403:
            result.error = "GitHub API rate limit exceeded — try again later (403)"
        else:
            result.error = f"GitHub API error: HTTP {e.code}"
        return result
    except urllib.error.URLError as e:
        result.error = _describe_url_error(e)
        return result
    except Exception as e:
        result.error = str(e)
        return result

    try:
        data = json.loads(raw.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        result.error = f"Invalid API response: {e}"
        return result

    remote_version = data.get("tag_name", "").lstrip("vV")
    local_version = get_current_version()
    result.remote_version = remote_version
    result.release_notes = data.get("body", "")

    for asset in data.get("assets", []):
        if asset["name"].endswith(".zip"):
            result.download_url = asset["browser_download_url"]
            result.download_size = asset.get("size", 0)
            break

    if remote_version and result.download_url:
        result.update_available = is_newer_version(remote_version, local_version)
    elif remote_version and not result.download_url:
        # Release exists but has no zip asset yet
        result.error = f"Release v{remote_version} found but has no downloadable asset"

    return result


def _check_via_raw_version() -> "UpdateCheckResult":
    """
    Fallback method: read version.txt from GitHub raw content.
    Only tells us whether a newer version exists — no download URL.
    """
    result = UpdateCheckResult()
    headers = {'User-Agent': USER_AGENT}
    token = _get_github_token()
    if token:
        headers['Authorization'] = f'Bearer {token}'
    req = urllib.request.Request(GITHUB_RAW_VERSION_URL, headers=headers)
    try:
        raw = _urlopen_with_retry(req)
        remote_version = raw.decode('utf-8').strip().lstrip("vV")
        local_version = get_current_version()
        result.remote_version = remote_version
        if remote_version:
            result.update_available = is_newer_version(remote_version, local_version)
    except urllib.error.HTTPError as e:
        result.error = f"Raw version check failed: HTTP {e.code}"
    except urllib.error.URLError as e:
        result.error = _describe_url_error(e)
    except Exception as e:
        result.error = str(e)
    return result


def check_for_update() -> UpdateCheckResult:
    """
    Check GitHub releases for a newer version.
    Tries the Releases API first; falls back to raw version.txt if the API
    fails with a network error (not an HTTP error like 404/403).
    Returns UpdateCheckResult with all relevant info.
    """
    result = _check_via_releases_api()

    # If the API failed with a non-HTTP network error, try the simpler fallback
    if result.error and not result.remote_version:
        raw_result = _check_via_raw_version()
        if not raw_result.error:
            # Fallback worked: report availability but no download URL
            raw_result.release_notes = "[Detailed release info unavailable — update via GitHub Releases page]"
            return raw_result
        # Both failed — return the original API error (more informative)
        result.error = f"{result.error}; fallback also failed: {raw_result.error}"

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
    REM pause removed for invisible mode
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
    
    # Launch the update script invisibly (no console window)
    # 0x08000000 is CREATE_NO_WINDOW
    subprocess.Popen(
        ['cmd', '/c', str(script_path)],
        creationflags=0x08000000,
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
