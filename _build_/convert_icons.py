import os
import sys

try:
    from PIL import Image
except ImportError:
    print("Pillow library is not installed. Please install it using 'pip install Pillow'")
    sys.exit(1)

def convert_png_to_ico(directory):
    if not os.path.exists(directory):
        print(f"Directory not found: {directory}")
        return

    # Get all png files in the directory
    png_files = [f for f in os.listdir(directory) if f.lower().endswith('.png')]
    
    if not png_files:
        print(f"No PNG files found in {directory}")
        return

    print(f"Found {len(png_files)} PNG files in {directory}. Starting conversion...")

    for filename in png_files:
        png_path = os.path.join(directory, filename)
        ico_filename = os.path.splitext(filename)[0] + '.ico'
        ico_path = os.path.join(directory, ico_filename)

        try:
            img = Image.open(png_path)
            # Save as ICO with multiple sizes
            img.save(ico_path, format='ICO', sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32)])
            print(f"Converted: {filename} -> {ico_filename}")
        except Exception as e:
            print(f"Failed to convert {filename}: {e}")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Convert PNG icons to ICO format.")
    parser.add_argument("directory", nargs='?', help="Directory containing PNG files")
    
    args = parser.parse_args()

    if args.directory:
        target_dir = args.directory
    else:
        # Default to relative path if no argument provided (backward compatibility or ease of use)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        target_dir = os.path.join(project_root, 'icons')
    
    convert_png_to_ico(target_dir)
