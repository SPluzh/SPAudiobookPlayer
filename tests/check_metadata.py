
import mutagen
from mutagen.mp4 import MP4

def check_metadata(file_path):
    try:
        audio = MP4(file_path)
        print("Metadata:")
        print(audio.pprint())
        print("-" * 20)
        print(f"Info: {audio.info}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_metadata(r"C:\Users\user\Desktop\python\SPAudiobookPlayer\tests\Распад атома.m4b")
