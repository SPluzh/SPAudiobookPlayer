
import os
import shutil
import ctypes
from bass_player import BassPlayer, bass

def test_rename(original_path, new_extension):
    new_path = original_path + new_extension
    print(f"\nTesting rename to: {new_extension}")
    
    try:
        shutil.copy(original_path, new_path)
    except Exception as e:
        print(f"Copy failed: {e}")
        return

    player = BassPlayer()
    # Ensure plugins are loaded
    
    if player.load(new_path):
        print(f"Success loading {new_path}")
        print(f"Duration: {player.get_duration()}")
        player.free()
    else:
        print(f"Failed loading {new_path}. Error: {bass.BASS_ErrorGetCode()}")
        player.free()
    
    try:
        os.remove(new_path)
    except:
        pass

if __name__ == "__main__":
    original = r"C:\Users\user\Desktop\python\SPAudiobookPlayer\tests\Распад атома.m4b"
    test_rename(original, ".opus")
    test_rename(original, ".ogg")
    test_rename(original, ".mp4")
