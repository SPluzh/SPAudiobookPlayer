
import sys

def check_header(file_path):
    try:
        with open(file_path, 'rb') as f:
            header = f.read(16)
            print(f"Header (hex): {header.hex()}")
            print(f"Header (bytes): {header}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_header(r"C:\Users\user\Desktop\python\SPAudiobookPlayer\tests\Распад атома.m4b")
