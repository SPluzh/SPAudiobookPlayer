
import subprocess
import os
import sys

def convert_and_test():
    ffmpeg_path = os.path.abspath(r"resources\bin\ffmpeg.exe")
    input_file = os.path.abspath(r"tests\Распад атома.m4b")
    output_file = os.path.abspath(r"tests\temp_test.opus")

    print(f"FFmpeg: {ffmpeg_path}")
    print(f"Input: {input_file}")
    
    if not os.path.exists(input_file):
        print("Input file missing!")
        return

    # Create command
    cmd = [
        ffmpeg_path,
        '-y', # Overwrite
        '-v', 'error',
        '-i', input_file,
        '-c:a', 'copy', # Transmux
        output_file
    ]

    print("Running ffmpeg...")
    try:
        subprocess.run(cmd, check=True)
        print("Conversion successful!")
        
        if os.path.exists(output_file):
            print(f"Output size: {os.path.getsize(output_file)} bytes")
            # Now run playback test
            import test_playback
            test_playback.test_playback(output_file)
        else:
            print("Output file not found after success?!")

    except subprocess.CalledProcessError as e:
        print(f"FFmpeg failed: {e}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    convert_and_test()
