import os
import ctypes
import subprocess
import tempfile
from ctypes import c_float, c_int, c_void_p, c_bool

# BASS constants
BASS_STREAM_DECODE = 0x200000
BASS_STREAM_PRESCAN = 0x20000
BASS_UNICODE = 0x80000000
BASS_FX_FREESOURCE = 0x10000
BASS_ATTRIB_VOL = 2
BASS_ATTRIB_TEMPO = 0x10000
BASS_ATTRIB_TEMPO = 0x10000
BASS_ATTRIB_TEMPO_PITCH = 0x10001
BASS_POS_BYTE = 0
BASS_ACTIVE_PLAYING = 1
BASS_FX_BFX_PEAKEQ = 0x10004
BASS_FX_BFX_COMPRESSOR2 = 0x10011
BASS_BFX_CHANALL = -1
BASS_UNICODE = 0x80000000

# Plugin flags
BASS_PLUGIN_UNICODE = 0x80000000

# VST flags
BASS_VST_KEEP_CHANS = 1  # Keep original channel count

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
bass_vst = load_library("resources/bin/bass_vst.dll")

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
    bass.BASS_PluginLoad.argtypes = [c_void_p, c_int]
    bass.BASS_PluginLoad.restype = c_int
    bass.BASS_PluginFree.argtypes = [c_int]
    bass.BASS_PluginFree.restype = c_bool

if bass_fx:
    bass_fx.BASS_FX_TempoCreate.argtypes = [c_int, c_int]
    bass_fx.BASS_FX_TempoCreate.restype = c_int

if bass_vst:
    # BASS_VST_ChannelSetDSP(chan, dllFile, flags, priority) -> vstHandle
    bass_vst.BASS_VST_ChannelSetDSP.argtypes = [c_int, c_void_p, c_int, c_int]
    bass_vst.BASS_VST_ChannelSetDSP.restype = c_int
    # BASS_VST_ChannelRemoveDSP(chan, vstHandle) -> BOOL
    bass_vst.BASS_VST_ChannelRemoveDSP.argtypes = [c_int, c_int]
    bass_vst.BASS_VST_ChannelRemoveDSP.restype = c_bool
    # BASS_VST_SetParam(vstHandle, paramIndex, value) -> BOOL
    bass_vst.BASS_VST_SetParam.argtypes = [c_int, c_int, c_float]
    bass_vst.BASS_VST_SetParam.restype = c_bool

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
        self.temp_file = None
        
        # Noise suppression (VST) state
        self.noise_suppression_enabled = False
        self.noise_suppression_handle = 0
        self.vad_threshold = 0.90  # Default 90% (0.0-1.0)
        self.vad_grace_period = 0.0  # Param 1: Grace Period
        self.vad_retroactive_grace = 0.0  # Param 2: Retroactive Grace
        
        # Effect Presets (0=Light, 1=Medium, 2=Strong)
        self.deesser_preset = 1
        self.compressor_preset = 1
        self.has_vst = bass_vst is not None
        
        # Pitch state
        self.pitch_enabled = False
        self.pitch_pos = 0.0

        # Initialize BASS at 48kHz (required for RNNoise VST plugin)
        if bass and bass.BASS_Init(-1, 48000, 0, 0, None):
            self.initialized = True
            
            # Load plugins (OPUS, AAC/M4B, FLAC, APE)
            self.plugins = {}
            for plugin in ["bassopus.dll", "bass_aac.dll", "bassflac.dll", "bassape.dll"]:
                self._load_plugin(plugin)

    def _load_plugin(self, filename: str):
        """Helper to load a BASS plugin"""
        plugin_path = os.path.join(os.path.dirname(__file__), "resources/bin", filename)
        if os.path.exists(plugin_path):
            path_bytes = plugin_path.encode('utf-16le') + b'\x00\x00'
            hplugin = bass.BASS_PluginLoad(path_bytes, BASS_PLUGIN_UNICODE)
            if hplugin:
                self.plugins[filename] = hplugin

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
            self.noise_suppression_handle = 0

        # Cleanup previous temp file
        if self.temp_file and os.path.exists(self.temp_file):
            try:
                os.remove(self.temp_file)
            except:
                pass
            self.temp_file = None

        # Try to load file directly
        path_bytes = filepath.encode('utf-16le') + b'\x00\x00'
        flags0 = BASS_STREAM_DECODE | BASS_UNICODE
        self.chan0 = bass.BASS_StreamCreateFile(False, path_bytes, 0, 0, flags0)

        # If loading failed, check for BASS_ERROR_FILEFORM (41) and try FFmpeg fallback
        if self.chan0 == 0:
            error_code = bass.BASS_ErrorGetCode()
            if error_code == 41:  # BASS_ERROR_FILEFORM
                # Check for ffmpeg from config or default
                config_path = os.path.join(os.path.dirname(__file__), "resources", "settings.ini")
                ffmpeg_path = os.path.join(os.path.dirname(__file__), "resources/bin/ffmpeg.exe") # Default
                temp_dir = os.path.join(os.path.dirname(__file__), "data", "temp") # Default
                
                if os.path.exists(config_path):
                    import configparser
                    config = configparser.ConfigParser()
                    try:
                        config.read(config_path, encoding='utf-8')
                        if 'Paths' in config:
                            # Read temp_dir
                            if 'temp_dir' in config['Paths']:
                                configured_temp = config['Paths']['temp_dir']
                                if not os.path.isabs(configured_temp):
                                    temp_dir = os.path.join(os.path.dirname(__file__), configured_temp)
                                else:
                                    temp_dir = configured_temp
                            
                            # Read ffmpeg_path
                            if 'ffmpeg_path' in config['Paths']:
                                configured_ffmpeg = config['Paths']['ffmpeg_path']
                                if not os.path.isabs(configured_ffmpeg):
                                    ffmpeg_path = os.path.join(os.path.dirname(__file__), configured_ffmpeg)
                                else:
                                    ffmpeg_path = configured_ffmpeg
                    except:
                        pass

                if os.path.exists(ffmpeg_path):
                    try:
                        os.makedirs(temp_dir, exist_ok=True)
                        
                        # Create temp file path
                        fd, temp_path = tempfile.mkstemp(suffix=".opus", dir=temp_dir)
                        os.close(fd)
                        
                        # Run ffmpeg to transmux
                        subprocess.run([
                            ffmpeg_path,
                            '-y',
                            '-v', 'error',
                            '-i', filepath,
                            '-c:a', 'copy',
                            temp_path
                        ], check=True, startupinfo=self._get_startupinfo())
                        
                        if os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
                            self.temp_file = temp_path
                            # Try loading the converted file
                            temp_path_bytes = temp_path.encode('utf-16le') + b'\x00\x00'
                            self.chan0 = bass.BASS_StreamCreateFile(False, temp_path_bytes, 0, 0, flags0)
                    except Exception as e:
                        print(f"FFmpeg fallback failed: {e}")
                        pass

        if self.chan0 == 0:
            return False

        if self.has_fx:
            flags_fx = BASS_STREAM_PRESCAN | BASS_FX_FREESOURCE
            self.chan = bass_fx.BASS_FX_TempoCreate(self.chan0, flags_fx)

        if self.chan == 0:
            bass.BASS_StreamFree(self.chan0)
            # Retry with original file if fallback wasn't used, or explicitly with what we have
            target_bytes = path_bytes
            if self.temp_file:
                 target_bytes = self.temp_file.encode('utf-16le') + b'\x00\x00'
            
            self.chan = bass.BASS_StreamCreateFile(False, target_bytes, 0, 0, BASS_UNICODE)
            self.has_fx = False

        if self.chan != 0:
            self.current_file = filepath
            self.apply_attributes()
            return True
        return False

    def _get_startupinfo(self):
        """Get startupinfo to hide console window on Windows"""
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            return startupinfo
        return None

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

    def unload(self):
        """Stop playback and free the current stream and temporary files"""
        if self.chan != 0:
            # Remove VST before freeing stream
            if self.noise_suppression_handle != 0 and self.has_vst:
                bass_vst.BASS_VST_ChannelRemoveDSP(self.chan, self.noise_suppression_handle)
                self.noise_suppression_handle = 0
            
            bass.BASS_StreamFree(self.chan)
            self.chan = 0
            self.chan0 = 0
            self.current_file = ""
            self.deesser_handle = 0
            self.compressor_handle = 0

        if self.temp_file and os.path.exists(self.temp_file):
            try:
                os.remove(self.temp_file)
            except:
                pass
            self.temp_file = None


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

    def set_pitch(self, semitones: float):
        """Set pitch in semitones (e.g. -12 to +12)"""
        self.pitch_pos = semitones
        self.apply_attributes()

    def set_pitch_enabled(self, enabled: bool):
        """Enable/Disable pitch shifting"""
        self.pitch_enabled = enabled
        self.apply_attributes()

    def set_noise_suppression(self, enabled: bool):
        """Toggle noise suppression (RNNoise VST plugin)"""
        self.noise_suppression_enabled = enabled
        self.apply_noise_suppression()

    def set_vad_threshold(self, value: float):
        """Set VAD threshold (0.0-1.0) for noise suppression sensitivity"""
        self.vad_threshold = max(0.0, min(1.0, value))
        if self.noise_suppression_handle != 0 and self.has_vst:
            bass_vst.BASS_VST_SetParam(self.noise_suppression_handle, 0, self.vad_threshold)

    def set_vad_grace_period(self, value: float):
        """Set VAD Grace Period (0.0-1.0) - delay before silence"""
        self.vad_grace_period = max(0.0, min(1.0, value))
        if self.noise_suppression_handle != 0 and self.has_vst:
            bass_vst.BASS_VST_SetParam(self.noise_suppression_handle, 1, self.vad_grace_period)

    def set_retroactive_grace(self, value: float):
        """Set Retroactive Grace Period (0.0-1.0) - pre-recording buffer (latency!)"""
        self.vad_retroactive_grace = max(0.0, min(1.0, value))
        if self.noise_suppression_handle != 0 and self.has_vst:
            bass_vst.BASS_VST_SetParam(self.noise_suppression_handle, 2, self.vad_retroactive_grace)

    def apply_noise_suppression(self):
        """Apply or remove the noise suppression VST effect on the current channel"""
        if self.chan == 0 or not self.initialized or not self.has_vst:
            return

        # Remove existing VST if any
        if self.noise_suppression_handle != 0:
            bass_vst.BASS_VST_ChannelRemoveDSP(self.chan, self.noise_suppression_handle)
            self.noise_suppression_handle = 0

        if self.noise_suppression_enabled:
            vst_path = os.path.join(os.path.dirname(__file__), 
                                    "resources/bin/rnnoise_stereo.dll")
            if os.path.exists(vst_path):
                # Encode path as UTF-16LE for BASS_UNICODE
                path_bytes = vst_path.encode('utf-16le') + b'\x00\x00'
                # Priority -1 = process FIRST (before other effects)
                self.noise_suppression_handle = bass_vst.BASS_VST_ChannelSetDSP(
                    self.chan, path_bytes, BASS_UNICODE | BASS_VST_KEEP_CHANS, -1
                )
                
                if self.noise_suppression_handle != 0:
                    # Configure plugin parameters using stored threshold
                    bass_vst.BASS_VST_SetParam(self.noise_suppression_handle, 0, self.vad_threshold)
                    bass_vst.BASS_VST_SetParam(self.noise_suppression_handle, 1, self.vad_grace_period)
                    bass_vst.BASS_VST_SetParam(self.noise_suppression_handle, 2, self.vad_retroactive_grace)

    def set_deesser_preset(self, preset: int):
        """Set DeEsser Preset (0=Light, 1=Medium, 2=Strong)"""
        self.deesser_preset = max(0, min(2, preset))
        if self.deesser_enabled and self.deesser_handle:
            self.apply_deesser()

    def set_compressor_preset(self, preset: int):
        """Set Compressor Preset (0=Light, 1=Medium, 2=Strong)"""
        self.compressor_preset = max(0, min(2, preset))
        if self.compressor_enabled and self.compressor_handle:
            self.apply_compressor()

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
            # Set BASS_FX Peaking EQ at 6000Hz
            # Using BASS_FX_BFX_PEAKEQ instead of DX8 to avoid constant conflicts
            self.deesser_handle = bass.BASS_ChannelSetFX(self.chan, BASS_FX_BFX_PEAKEQ, 0)
            if self.deesser_handle != 0:
                # Presets: Light(0), Medium(1), Strong(2)
                defaults = {
                    0: (3.0, -3.0),   # Light: Bandwidth 3.0, Gain -3dB
                    1: (4.5, -6.0),   # Medium: Bandwidth 4.5, Gain -6dB
                    2: (6.0, -12.0)   # Strong: Bandwidth 6.0, Gain -12dB
                }
                bw, gain = defaults.get(self.deesser_preset, (4.5, -6.0))
                
                # lBand=0, fBandwidth=bw, fQ=0, fCenter=6000.0, fGain=gain, lChannel=BASS_BFX_CHANALL
                params = BASS_BFX_PEAKEQ(0, bw, 0.0, 6000.0, gain, BASS_BFX_CHANALL)
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
            # Using BASS_FX_BFX_COMPRESSOR2 ($10011) to avoid echo issue
            self.compressor_handle = bass.BASS_ChannelSetFX(self.chan, BASS_FX_BFX_COMPRESSOR2, 0)
            if self.compressor_handle != 0:
                # Presets: Light(0), Medium(1), Strong(2) (Ratio, Threshold, Gain)
                defaults = {
                    0: (2.0, -15.0, 4.0),  # Light
                    1: (4.0, -20.0, 7.0),  # Medium
                    2: (8.0, -28.0, 12.0)  # Strong
                }
                ratio, thresh, gain = defaults.get(self.compressor_preset, (4.0, -20.0, 7.0))
                
                # fGain, fThreshold, fRatio, fAttack=10.0, fRelease=300.0, lChannel=CHANALL
                params = BASS_BFX_COMPRESSOR2(gain, thresh, ratio, 10.0, 300.0, BASS_BFX_CHANALL)
                bass.BASS_FXSetParameters(self.compressor_handle, ctypes.byref(params))

    def apply_attributes(self):
        """Apply volume and tempo attributes to the channel"""
        if self.chan == 0:
            return
        bass.BASS_ChannelSetAttribute(self.chan, BASS_ATTRIB_VOL, c_float(self.vol_pos / 100.0))
        if self.has_fx:
            tempo_percent = (self.speed_pos * 10) - 100.0
            bass.BASS_ChannelSetAttribute(self.chan, BASS_ATTRIB_TEMPO, c_float(tempo_percent))
            
            pitch_val = self.pitch_pos if self.pitch_enabled else 0.0
            bass.BASS_ChannelSetAttribute(self.chan, BASS_ATTRIB_TEMPO_PITCH, c_float(pitch_val))
        # Always reapply effects when attributes are reapplied (e.g. on new track)
        self.apply_noise_suppression()  # First in chain (priority -1)
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
            self.chan = 0
            
        if self.initialized:
            # Free plugins
            if hasattr(self, 'plugins'):
                for hplugin in self.plugins.values():
                    bass.BASS_PluginFree(hplugin)
                self.plugins.clear()
            
            # Legacy cleanup
            if hasattr(self, 'opus_plugin') and self.opus_plugin:
                 bass.BASS_PluginFree(self.opus_plugin)
                 
            bass.BASS_Free()
            self.initialized = False

        # Cleanup temporary file if it exists
        if hasattr(self, 'temp_file') and self.temp_file and os.path.exists(self.temp_file):
            try:
                os.remove(self.temp_file)
            except:
                pass
            self.temp_file = None

