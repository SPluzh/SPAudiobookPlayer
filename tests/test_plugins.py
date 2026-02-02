
import os
import sys
import ctypes
from bass_player import BassPlayer, bass, BASS_UNICODE

# BASS constants
BASS_STREAM_DECODE = 0x200000

def load_with_plugins(file_path, plugins_to_load):
    print(f"\n--- Testing with plugins: {plugins_to_load} ---")
    
    # Initialize BASS manually to control plugins
    if not bass.BASS_Init(-1, 44100, 0, 0, None):
        print("BASS_Init failed")
        return

    loaded_plugins = []
    for p in plugins_to_load:
        plugin_path = os.path.join(os.path.dirname(__file__), "resources/bin", p)
        if os.path.exists(plugin_path):
            path_bytes = plugin_path.encode('utf-16le') + b'\x00\x00'
            hplugin = bass.BASS_PluginLoad(path_bytes, 0x80000000) # BASS_POS_BYTE ignored, just flags
            if hplugin:
                loaded_plugins.append(hplugin)
            else:
                print(f"Failed to load {p}")
        else:
            print(f"Plugin not found: {p}")

    print(f"Loaded: {[p for p in plugins_to_load]}")

    # Try to load file
    path_bytes = file_path.encode('utf-16le') + b'\x00\x00'
    chan = bass.BASS_StreamCreateFile(False, path_bytes, 0, 0, BASS_UNICODE)
    
    if chan:
        print("Success! Stream created.")
        bass.BASS_StreamFree(chan)
    else:
        print(f"Failed. Error code: {bass.BASS_ErrorGetCode()}")

    # Free plugins and BASS
    for h in loaded_plugins:
        bass.BASS_PluginFree(h)
    bass.BASS_Free()

if __name__ == "__main__":
    test_file = r"C:\Users\user\Desktop\python\SPAudiobookPlayer\tests\Распад атома.m4b"
    
    # 1. No plugins
    load_with_plugins(test_file, [])
    
    # 2. Only bassopus
    load_with_plugins(test_file, ["bassopus.dll"])
    
    # 3. Only bass_aac
    load_with_plugins(test_file, ["bass_aac.dll"])
    
    # 4. Both (Order 1)
    load_with_plugins(test_file, ["bassopus.dll", "bass_aac.dll"])

    # 5. Both (Order 2)
    load_with_plugins(test_file, ["bass_aac.dll", "bassopus.dll"])
