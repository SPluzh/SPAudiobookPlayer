import sys
import os
from pathlib import Path

# Add current directory to path
sys.path.append(os.getcwd())

from PyQt6.QtWidgets import QApplication
from translations import tr, trf, set_language
from about_dialog import AboutDialog

def main():
    app = QApplication(sys.argv)
    
    # Test translations
    print("Testing translations...")
    set_language('ru')
    
    try:
        ver = trf('about.version', version='1.0.0')
        print(f"Version string: {ver}")
    except Exception as e:
        print(f"Translation error: {e}")
        return

    print("Creating AboutDialog...")
    try:
        dlg = AboutDialog(None)
        print("AboutDialog created successfully.")
        # We won't exec() simply because we can't interact, but we can trigger showEvent manually if we want,
        # or just assume if init passes, it's likely fine.
        # But crash says "starts", so maybe showEvent.
        
        # dlg.show() 
        # But we can't see it.
    except Exception as e:
        print(f"AboutDialog creation error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
