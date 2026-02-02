
import os
import sys
import shutil
import configparser
from bass_player import BassPlayer, bass

def test_playback(file_path):
    print(f"Testing file: {file_path}")
    
    # Check config
    config_path = os.path.join(os.path.dirname(__file__), "resources", "settings.ini")
    print(f"Reading config: {config_path}")
    
    config = configparser.ConfigParser()
    config.read(config_path, encoding='utf-8')
    configured_ffmpeg = config['Paths'].get('ffmpeg_path', 'NOT SET')
    print(f"Configured ffmpeg_path: {configured_ffmpeg}")
    
    # Resolve expected path
    expected_ffmpeg = os.path.abspath(os.path.join(os.path.dirname(__file__), configured_ffmpeg))
    print(f"Expected ffmpeg path absolute: {expected_ffmpeg}")
    
    if not os.path.exists(expected_ffmpeg):
        print("ERROR: Configured ffmpeg path does not exist!")
    else:
        print("Configured ffmpeg path exists.")

    if not os.path.exists(file_path):
        print("File not found!")
        return
        
    player = BassPlayer()
    if not player.initialized:
        print("BASS not initialized")
        return

    # Trigger fallback which uses ffmpeg
    if player.load(file_path):
        print("Load successful!")
        if player.temp_file:
             print("FFmpeg fallback was triggered successfully.")
        player.free()
    else:
        error_code = bass.BASS_ErrorGetCode()
        print(f"Load failed. Error code: {error_code}")
        print("Check if ffmpeg path resolution in bass_player.py matches expectations.")

if __name__ == "__main__":
    test_file = r"C:\Users\user\Desktop\python\SPAudiobookPlayer\tests\Распад атома.m4b"
    test_playback(test_file)
