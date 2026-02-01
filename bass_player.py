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
BASS_FX_BFX_PEAKEQ = 0x10004
BASS_FX_BFX_COMPRESSOR2 = 0x10011
BASS_BFX_CHANALL = -1

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

class BASS_BFX_PEAKEQ(ctypes.Structure):
    _fields_ = [
        ("lBand", c_int),
        ("fBandwidth", c_float),
        ("fQ", c_float),
        ("fCenter", c_float),
        ("fGain", c_float),
        ("lChannel", c_int),
    ]

class BASS_BFX_COMPRESSOR2(ctypes.Structure):
    _fields_ = [
        ("fGain", c_float),
        ("fThreshold", c_float),
        ("fRatio", c_float),
        ("fAttack", c_float),
        ("fRelease", c_float),
        ("lChannel", c_int),
    ]

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
    bass.BASS_ChannelSetFX.argtypes = [c_int, c_int, c_int]
    bass.BASS_ChannelSetFX.restype = c_int
    bass.BASS_ChannelRemoveFX.argtypes = [c_int, c_int]
    bass.BASS_ChannelRemoveFX.restype = c_bool
    bass.BASS_FXSetParameters.argtypes = [c_int, c_void_p]
    bass.BASS_FXSetParameters.restype = c_bool

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
        self.deesser_handle = 0
        self.deesser_enabled = False
        self.compressor_handle = 0
        self.compressor_enabled = False

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
            self.deesser_handle = 0
            self.compressor_handle = 0

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

    def set_deesser(self, enabled: bool):
        """Toggle DeEsser (parametric EQ filter at 6kHz)"""
        self.deesser_enabled = enabled
        self.apply_deesser()

    def apply_deesser(self):
        """Apply or remove the DeEsser effect on the current channel"""
        if self.chan == 0 or not self.initialized:
            return

        # Remove existing effect if any
        if self.deesser_handle != 0:
            bass.BASS_ChannelRemoveFX(self.chan, self.deesser_handle)
            self.deesser_handle = 0

        if self.deesser_enabled:
            # Set BASS_FX Peaking EQ at 6000Hz, -6dB, 4.5 bandwidth (Softer)
            # Using BASS_FX_BFX_PEAKEQ instead of DX8 to avoid constant conflicts
            self.deesser_handle = bass.BASS_ChannelSetFX(self.chan, BASS_FX_BFX_PEAKEQ, 0)
            if self.deesser_handle != 0:
                # lBand=0, fBandwidth=4.5, fQ=0, fCenter=6000.0, fGain=-6.0, lChannel=BASS_BFX_CHANALL
                params = BASS_BFX_PEAKEQ(0, 4.5, 0.0, 6000.0, -6.0, BASS_BFX_CHANALL)
                bass.BASS_FXSetParameters(self.deesser_handle, ctypes.byref(params))

    def set_compressor(self, enabled: bool):
        """Toggle Compressor (DX8 Compressor filter)"""
        self.compressor_enabled = enabled
        self.apply_compressor()

    def apply_compressor(self):
        """Apply or remove the Compressor effect on the current channel"""
        if self.chan == 0 or not self.initialized:
            return

        # Remove existing effect if any
        if self.compressor_handle != 0:
            bass.BASS_ChannelRemoveFX(self.chan, self.compressor_handle)
            self.compressor_handle = 0

        if self.compressor_enabled:
            # Set BASS_FX Compressor 2 (Hard Preset)
            # Using BASS_FX_BFX_COMPRESSOR2 ($10011) to avoid echo issue ($10001 is ECHO)
            # Parameters: fGain(5.0), fThreshold(-20.0), fRatio(4.0), fAttack(10.0), fRelease(300.0), lChannel(CHANALL)
            self.compressor_handle = bass.BASS_ChannelSetFX(self.chan, BASS_FX_BFX_COMPRESSOR2, 0)
            if self.compressor_handle != 0:
                params = BASS_BFX_COMPRESSOR2(5.0, -20.0, 4.0, 10.0, 300.0, BASS_BFX_CHANALL)
                bass.BASS_FXSetParameters(self.compressor_handle, ctypes.byref(params))

    def apply_attributes(self):
        """Apply volume and tempo attributes to the channel"""
        if self.chan == 0:
            return
        bass.BASS_ChannelSetAttribute(self.chan, BASS_ATTRIB_VOL, c_float(self.vol_pos / 100.0))
        if self.has_fx:
            tempo_percent = (self.speed_pos * 10) - 100.0
            bass.BASS_ChannelSetAttribute(self.chan, BASS_ATTRIB_TEMPO, c_float(tempo_percent))
        
        # Always reapply DeEsser and Compressor when attributes are reapplied (e.g. on new track)
        self.apply_deesser()
        self.apply_compressor()

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
