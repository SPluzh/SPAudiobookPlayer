"""
Opus Converter Module
Converts audiobook files to Opus format for reduced file size with maintained quality.
Based on logic from https://github.com/kadykov/audiobook-opus-converter
"""

import subprocess
import json
import os
import shutil
from pathlib import Path
from typing import List, Tuple, Optional
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from PyQt6.QtCore import QThread, pyqtSignal


SUPPORTED_INPUT_FORMATS = {
    '.mp3', '.m4a', '.m4b', '.aac', '.flac', '.wav', '.ogg', '.wma', '.ape'
}


@dataclass
class ConversionResult:
    """Result of converting a single file"""
    success: bool
    old_path: str
    new_path: str
    message: str
    actual_bitrate: int = 0  # actual bitrate in kbps from ffprobe


@dataclass
class ConversionStats:
    """Statistics for the overall conversion process"""
    total_files: int = 0
    converted: int = 0
    skipped: int = 0
    failed: int = 0
    errors: List[str] = field(default_factory=list)


class OpusConversionThread(QThread):
    """Background thread for converting audio files to Opus format using parallel workers"""
    
    # Signals
    progress = pyqtSignal(int, int, str)          # current, total, filename
    file_converted = pyqtSignal(str, str, str)     # old_path, new_path, bitrate
    log_message = pyqtSignal(str)                  # log text
    conversion_finished = pyqtSignal(bool, str)    # success, summary message
    
    def __init__(self, library_path: str, bitrate: str = "48k",
                 stereo_strategy: str = "downmix",
                 ffmpeg_path: str = "ffmpeg",
                 ffprobe_path: str = "ffprobe",
                 max_workers: int = 0,
                 parent=None):
        super().__init__(parent)
        self.library_path = Path(library_path)
        self.bitrate = bitrate
        self.stereo_strategy = stereo_strategy
        self.ffmpeg_path = str(ffmpeg_path)
        self.ffprobe_path = str(ffprobe_path)
        # Default to CPU count (capped at 8 to avoid I/O saturation)
        self.max_workers = max_workers if max_workers > 0 else min(os.cpu_count() or 4, 8)
        self._cancelled = False
        self._lock = Lock()
        self.stats = ConversionStats()
    
    def cancel(self):
        """Request cancellation of the conversion process"""
        self._cancelled = True
    
    def run(self):
        """Main conversion process with parallel workers"""
        try:
            # Check ffmpeg availability
            if not self._check_ffmpeg():
                self.conversion_finished.emit(False, "FFmpeg not found or missing Opus support")
                return
            
            # Find all convertible files
            files = self._find_convertible_files()
            self.stats.total_files = len(files)
            
            if not files:
                self.log_message.emit("No files to convert - all files are already in Opus format")
                self.conversion_finished.emit(True, "No files to convert")
                return
            
            workers = min(self.max_workers, len(files))
            self.log_message.emit(f"Found {len(files)} files to convert (workers: {workers})")
            
            completed = 0
            
            with ThreadPoolExecutor(max_workers=workers) as executor:
                future_to_file = {
                    executor.submit(self._convert_file, f): f for f in files
                }
                
                for future in as_completed(future_to_file):
                    if self._cancelled:
                        executor.shutdown(wait=False, cancel_futures=True)
                        self.log_message.emit("Conversion cancelled by user")
                        summary = f"Cancelled. Converted: {self.stats.converted}, Failed: {self.stats.failed}"
                        self.conversion_finished.emit(False, summary)
                        return
                    
                    file_path = future_to_file[future]
                    completed += 1
                    
                    try:
                        result = future.result()
                    except Exception as exc:
                        with self._lock:
                            self.stats.failed += 1
                            self.stats.errors.append(str(exc))
                        self.log_message.emit(f"✗ {file_path.name}: {exc}")
                        self.progress.emit(completed, len(files), file_path.name)
                        continue
                    
                    self.progress.emit(completed, len(files), file_path.name)
                    
                    if result.success:
                        with self._lock:
                            self.stats.converted += 1
                        bitrate_str = f"{result.actual_bitrate}k" if result.actual_bitrate else self.bitrate
                        self.file_converted.emit(result.old_path, result.new_path, bitrate_str)
                        self.log_message.emit(f"✓ {file_path.name}")
                    else:
                        with self._lock:
                            self.stats.failed += 1
                            self.stats.errors.append(result.message)
                        self.log_message.emit(f"✗ {file_path.name}: {result.message}")
            
            # Final summary
            summary = f"Converted: {self.stats.converted}, Failed: {self.stats.failed}"
            success = self.stats.failed == 0
            self.conversion_finished.emit(success, summary)
            
        except Exception as e:
            self.log_message.emit(f"Critical error: {e}")
            self.conversion_finished.emit(False, str(e))
    
    def _check_ffmpeg(self) -> bool:
        """Check if ffmpeg is available and supports opus"""
        try:
            result = subprocess.run(
                [self.ffmpeg_path, "-codecs"],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            if "libopus" not in result.stdout:
                self.log_message.emit("FFmpeg does not have Opus codec support (libopus)")
                return False
            return True
        except FileNotFoundError:
            self.log_message.emit(f"FFmpeg not found at: {self.ffmpeg_path}")
            return False
        except Exception as e:
            self.log_message.emit(f"Error checking FFmpeg: {e}")
            return False
    
    def _find_convertible_files(self) -> List[Path]:
        """Find all audio files that can be converted to opus"""
        files = []
        for f in sorted(self.library_path.rglob("*")):
            if f.is_file() and f.suffix.lower() in SUPPORTED_INPUT_FORMATS:
                files.append(f)
        return files
    
    def _get_audio_duration(self, file_path: Path) -> Optional[float]:
        """Get audio file duration using ffprobe"""
        try:
            cmd = [
                self.ffprobe_path,
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "json",
                str(file_path)
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                return float(data.get("format", {}).get("duration", 0))
        except Exception:
            pass
        return None
    
    def _get_audio_channels(self, file_path: Path) -> int:
        """Get number of audio channels"""
        try:
            cmd = [
                self.ffprobe_path,
                "-v", "error",
                "-select_streams", "a:0",
                "-show_entries", "stream=channels",
                "-of", "json",
                str(file_path)
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                streams = data.get("streams", [])
                if streams:
                    return int(streams[0].get("channels", 2))
        except Exception:
            pass
        return 2
    
    def _get_audio_bitrate(self, file_path: Path) -> int:
        """Get actual audio bitrate in kbps using ffprobe"""
        try:
            cmd = [
                self.ffprobe_path,
                "-v", "error",
                "-select_streams", "a:0",
                "-show_entries", "stream=bit_rate",
                "-of", "json",
                str(file_path)
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                streams = data.get("streams", [])
                if streams:
                    bit_rate = streams[0].get("bit_rate")
                    if bit_rate:
                        return int(bit_rate) // 1000  # bps -> kbps
            # Fallback: try format-level bitrate
            cmd2 = [
                self.ffprobe_path,
                "-v", "error",
                "-show_entries", "format=bit_rate",
                "-of", "json",
                str(file_path)
            ]
            result2 = subprocess.run(
                cmd2, capture_output=True, text=True, timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            if result2.returncode == 0:
                data2 = json.loads(result2.stdout)
                fmt = data2.get("format", {})
                bit_rate = fmt.get("bit_rate")
                if bit_rate:
                    return int(bit_rate) // 1000
        except Exception:
            pass
        return 0
    
    def _convert_file(self, input_file: Path) -> ConversionResult:
        """Convert a single audio file to opus, replacing the original"""
        output_file = input_file.with_suffix('.opus')
        old_path = str(input_file)
        new_path = str(output_file)
        
        # If output already exists (e.g. from a previous partial run), skip
        if output_file.exists():
            return ConversionResult(
                success=False,
                old_path=old_path,
                new_path=new_path,
                message=f"Output file already exists: {output_file.name}"
            )
        
        # Early cancellation check
        if self._cancelled:
            return ConversionResult(False, old_path, new_path, "Cancelled")
        
        try:
            # Get original duration for verification
            original_duration = self._get_audio_duration(input_file)
            
            # Determine stereo handling
            channels = self._get_audio_channels(input_file)
            is_stereo = channels > 1
            
            target_bitrate = self.bitrate
            audio_filter = None
            
            if is_stereo and self.stereo_strategy == "downmix":
                audio_filter = "pan=mono|c0=0.5*c0+0.5*c1"
            
            # Build ffmpeg command
            cmd = [
                self.ffmpeg_path,
                "-y",
                "-v", "error",
                "-i", str(input_file),
                "-map", "0:a",           # Audio streams only
                "-map_metadata", "0",    # Copy all metadata
            ]
            
            # Add audio filter if needed
            if audio_filter:
                cmd.extend(["-af", audio_filter])
            
            cmd.extend([
                "-c:a", "libopus",
                "-b:a", target_bitrate,
                "-vbr", "on",
                "-compression_level", "10",
                "-application", "audio",  # 'audio' mode for music/audiobooks (better than 'voip' at 48k)
                str(output_file)
            ])
            
            # Run conversion with Popen for cancellation support
            creation_flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=creation_flags
            )
            
            # Poll with cancellation check
            import time
            while proc.poll() is None:
                if self._cancelled:
                    proc.kill()
                    proc.wait(timeout=5)
                    # Clean up partial output
                    if output_file.exists():
                        try:
                            output_file.unlink()
                        except Exception:
                            pass
                    return ConversionResult(False, old_path, new_path, "Cancelled")
                time.sleep(0.3)
            
            if proc.returncode != 0:
                # Clean up failed output
                if output_file.exists():
                    output_file.unlink()
                stderr = proc.stderr.read().decode('utf-8', errors='replace') if proc.stderr else ""
                error_msg = stderr.strip()[:200] if stderr else "Unknown error"
                return ConversionResult(False, old_path, new_path, f"FFmpeg error: {error_msg}")
            
            # Verify output exists
            if not output_file.exists():
                return ConversionResult(False, old_path, new_path, "Output file was not created")
            
            # Verify duration matches (within 2 seconds tolerance)
            if original_duration and original_duration > 0:
                new_duration = self._get_audio_duration(output_file)
                if new_duration and abs(original_duration - new_duration) > 2.0:
                    output_file.unlink()
                    return ConversionResult(
                        False, old_path, new_path,
                        f"Duration mismatch: {original_duration:.1f}s vs {new_duration:.1f}s"
                    )
            
            # Probe actual bitrate from the output file
            actual_bitrate = self._get_audio_bitrate(output_file)
            
            # Delete original file
            try:
                input_file.unlink()
            except Exception as e:
                # If we can't delete the original, the conversion still succeeded
                self.log_message.emit(f"  Warning: could not delete original {input_file.name}: {e}")
            
            return ConversionResult(True, old_path, new_path, "OK", actual_bitrate=actual_bitrate)
            
        except subprocess.TimeoutExpired:
            if output_file.exists():
                output_file.unlink()
            return ConversionResult(False, old_path, new_path, "Conversion timed out")
        except Exception as e:
            if output_file.exists():
                try:
                    output_file.unlink()
                except:
                    pass
            return ConversionResult(False, old_path, new_path, str(e))



def count_convertible_files(library_path: str) -> int:
    """Count the number of non-opus audio files in the library"""
    count = 0
    lib = Path(library_path)
    if not lib.exists():
        return 0
    for f in lib.rglob("*"):
        if f.is_file() and f.suffix.lower() in SUPPORTED_INPUT_FORMATS:
            count += 1
    return count
