import os
import ctypes
from ctypes import c_float, c_int, c_void_p, c_bool

# BASS constants
BASS_STREAM_DECODE = 0x200000
BASS_STREAM_PRESCAN = 0x20000
BASS_UNICODE = 0x80000000
BASS_FX_FREESOURCE = 0x10000
BASS_ATTRIB_VOL = 2
BASS_ATTRIB_TEMPO = 0x10000
BASS_POS_BYTE = 0
BASS_ACTIVE_PLAYING = 1

def load_library(name):
    """Load BASS shared library from resources or system path"""
    try:
        local_path = os.path.join(os.path.dirname(__file__), name)
        if os.path.exists(local_path):
            return ctypes.CDLL(local_path)
        return ctypes.CDLL(name)
    except OSError:
        return None

# Load libraries
bass = load_library("resources/bin/bass.dll")
bass_fx = load_library("resources/bin/bass_fx.dll")

# Define BASS functions if library is loaded
if bass:
    bass.BASS_Init.argtypes = [c_int, c_int, c_int, c_void_p, c_void_p]
    bass.BASS_Init.restype = c_bool
    bass.BASS_StreamCreateFile.argtypes = [c_bool, c_void_p, c_int, c_int, c_int]
    bass.BASS_StreamCreateFile.restype = c_int
    bass.BASS_ChannelPlay.argtypes = [c_int, c_bool]
    bass.BASS_ChannelPlay.restype = c_bool
    bass.BASS_ChannelPause.argtypes = [c_int]
    bass.BASS_ChannelPause.restype = c_bool
    bass.BASS_ChannelStop.argtypes = [c_int]
    bass.BASS_ChannelStop.restype = c_bool
    bass.BASS_ChannelIsActive.argtypes = [c_int]
    bass.BASS_ChannelIsActive.restype = c_int
    bass.BASS_ChannelSetAttribute.argtypes = [c_int, c_int, c_float]
    bass.BASS_ChannelSetAttribute.restype = c_bool
    bass.BASS_ChannelGetPosition.argtypes = [c_int, c_int]
    bass.BASS_ChannelGetPosition.restype = ctypes.c_uint64
    bass.BASS_ChannelSetPosition.argtypes = [c_int, ctypes.c_uint64, c_int]
    bass.BASS_ChannelSetPosition.restype = c_bool
    bass.BASS_ChannelGetLength.argtypes = [c_int, c_int]
    bass.BASS_ChannelGetLength.restype = ctypes.c_uint64
    bass.BASS_ChannelBytes2Seconds.argtypes = [c_int, ctypes.c_uint64]
    bass.BASS_ChannelBytes2Seconds.restype = ctypes.c_double
    bass.BASS_ChannelSeconds2Bytes.argtypes = [c_int, ctypes.c_double]
    bass.BASS_ChannelSeconds2Bytes.restype = ctypes.c_uint64
    bass.BASS_Free.argtypes = []
    bass.BASS_Free.restype = c_bool
    bass.BASS_StreamFree.argtypes = [c_int]
    bass.BASS_StreamFree.restype = c_bool

if bass_fx:
    bass_fx.BASS_FX_TempoCreate.argtypes = [c_int, c_int]
    bass_fx.BASS_FX_TempoCreate.restype = c_int

class BassPlayer:
    """Audio player using BASS library with tempo control support"""
    
    def __init__(self):
        """Initialize BASS audio engine"""
        self.chan = 0
        self.chan0 = 0
        self.vol_pos = 100
        self.speed_pos = 10
        self.initialized = False
        self.has_fx = bass_fx is not None
        self.current_file = ""

        if bass and bass.BASS_Init(-1, 44100, 0, 0, None):
            self.initialized = True

    def load(self, filepath: str) -> bool:
        """Load an audio file into the player"""
        if not self.initialized or not os.path.exists(filepath):
            return False

        if self.chan != 0:
            bass.BASS_StreamFree(self.chan)
            self.chan = 0
            self.chan0 = 0

        # Encode path for BASS (UTF-16LE with null terminator)
        path_bytes = filepath.encode('utf-16le') + b'\x00\x00'
        flags0 = BASS_STREAM_DECODE | BASS_UNICODE
        self.chan0 = bass.BASS_StreamCreateFile(False, path_bytes, 0, 0, flags0)

        if self.chan0 == 0:
            return False

        if self.has_fx:
            flags_fx = BASS_STREAM_PRESCAN | BASS_FX_FREESOURCE
            self.chan = bass_fx.BASS_FX_TempoCreate(self.chan0, flags_fx)

        if self.chan == 0:
            bass.BASS_StreamFree(self.chan0)
            self.chan = bass.BASS_StreamCreateFile(False, path_bytes, 0, 0, BASS_UNICODE)
            self.has_fx = False

        if self.chan != 0:
            self.current_file = filepath
            self.apply_attributes()
            return True
        return False

    def play(self):
        """Resume or start playback"""
        if self.chan != 0:
            self.apply_attributes()
            bass.BASS_ChannelPlay(self.chan, False)

    def pause(self):
        """Pause playback"""
        if self.chan != 0:
            bass.BASS_ChannelPause(self.chan)

    def stop(self):
        """Stop playback"""
        if self.chan != 0:
            bass.BASS_ChannelStop(self.chan)

    def is_playing(self) -> bool:
        """Check if currently playing"""
        return self.chan != 0 and bass.BASS_ChannelIsActive(self.chan) == BASS_ACTIVE_PLAYING

    def get_position(self) -> float:
        """Get current playback position in seconds"""
        if self.chan != 0:
            pos_bytes = bass.BASS_ChannelGetPosition(self.chan, BASS_POS_BYTE)
            return bass.BASS_ChannelBytes2Seconds(self.chan, pos_bytes)
        return 0.0

    def set_position(self, seconds: float):
        """Set playback position in seconds"""
        if self.chan != 0:
            pos_bytes = bass.BASS_ChannelSeconds2Bytes(self.chan, max(0, seconds))
            bass.BASS_ChannelSetPosition(self.chan, pos_bytes, BASS_POS_BYTE)

    def get_duration(self) -> float:
        """Get total duration of loaded file in seconds"""
        if self.chan != 0:
            len_bytes = bass.BASS_ChannelGetLength(self.chan, BASS_POS_BYTE)
            return bass.BASS_ChannelBytes2Seconds(self.chan, len_bytes)
        return 0.0

    def set_volume(self, value: int):
        """Set volume (0-100)"""
        self.vol_pos = max(0, min(100, value))
        self.apply_attributes()

    def set_speed(self, value: int):
        """Set playback speed (5-20 where 10 is 1.0x)"""
        self.speed_pos = max(5, min(20, value))
        self.apply_attributes()

    def apply_attributes(self):
        """Apply volume and tempo attributes to the channel"""
        if self.chan == 0:
            return
        bass.BASS_ChannelSetAttribute(self.chan, BASS_ATTRIB_VOL, c_float(self.vol_pos / 100.0))
        if self.has_fx:
            tempo_percent = (self.speed_pos * 10) - 100.0
            bass.BASS_ChannelSetAttribute(self.chan, BASS_ATTRIB_TEMPO, c_float(tempo_percent))

    def rewind(self, seconds: float):
        """Rewind or fast forward by specified seconds"""
        if self.chan != 0:
            new_pos = max(0, min(self.get_duration(), self.get_position() + seconds))
            self.set_position(new_pos)

    def free(self):
        """Free BASS resources"""
        if self.chan != 0:
            bass.BASS_StreamFree(self.chan)
        if self.initialized:
            bass.BASS_Free()
