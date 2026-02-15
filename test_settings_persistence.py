import configparser
import os
from pathlib import Path

# Mocking the constants and types
DARK_STYLE = ""
DARK_QSS_PATH = ""

class MockPlayer:
    def __init__(self):
        self.vol_pos = 100
        self.speed_pos = 10
    def set_deesser_preset(self, p): pass
    def set_deesser(self, e): pass
    def set_compressor_preset(self, p): pass
    def set_compressor(self, e): pass
    def set_vad_threshold(self, t): pass
    def set_vad_grace_period(self, g): pass
    def set_retroactive_grace(self, r): pass
    def set_noise_suppression(self, n): pass
    def set_pitch(self, v): pass
    def set_pitch_enabled(self, e): pass

class MockApp:
    def __init__(self, config_file):
        self.config_file = Path(config_file)
        self.script_dir = Path(".")
        self.player = MockPlayer()
        self.default_path = "C:/Library"
        self.default_cover_file = "default.png"
        self.folder_cover_file = "folder.png"
        self.saved_geometry_hex = None
        self.current_theme = "dark"
        self.audiobook_icon_size = 100
        self.audiobook_row_height = 120
        self.folder_icon_size = 35
        self.folder_row_height = 45
        self.auto_rewind = True
        self.auto_check_updates = False # Changed for test
        self.show_id3 = True
        self.deesser_enabled = False
        self.compressor_enabled = False
        self.noise_suppression_enabled = False
        self.vad_threshold = 90
        self.vad_grace_period = 0
        self.vad_retroactive_grace = 0
        self.deesser_preset = 1
        self.compressor_preset = 1
        self.pitch_enabled = False
        self.pitch_value = 0.0
        self.show_folders = False
        self.show_filter_labels = True

    def geometry(self):
        class Rect:
            def x(self): return 100
            def y(self): return 100
            def width(self): return 800
            def height(self): return 600
        return Rect()

    def saveGeometry(self):
        class Geo:
            def toHex(self):
                class Hex:
                    def data(self):
                        class Data:
                            def decode(self): return "ABCD"
                        return Data()
                return Hex()
        return Geo()

    def save_settings(self):
        config = configparser.ConfigParser()
        if self.config_file.exists():
            config.read(self.config_file, encoding='utf-8')
        
        rect = self.geometry()
        if 'Display' not in config: config['Display'] = {}
        config['Display']['window_x'] = str(rect.x())
        config['Display']['window_y'] = str(rect.y())
        config['Display']['window_width'] = str(rect.width())
        config['Display']['window_height'] = str(rect.height())
        config['Display']['window_geometry'] = self.saveGeometry().toHex().data().decode()
        config['Display']['theme'] = self.current_theme
        
        if 'Paths' not in config: config['Paths'] = {}
        config['Paths']['default_path'] = self.default_path
        config['Paths']['default_cover_file'] = self.default_cover_file
        config['Paths']['folder_cover_file'] = self.folder_cover_file
        
        # Player and Audio Functional Preferences
        if 'Player' not in config: config['Player'] = {}
        config['Player']['show_id3'] = str(self.show_id3)
        config['Player']['auto_rewind'] = str(self.auto_rewind)
        config['Player']['auto_check_updates'] = str(self.auto_check_updates)
        
        if 'Audio' not in config: config['Audio'] = {}
        config['Audio']['volume'] = str(self.player.vol_pos)
        config['Audio']['speed'] = str(self.player.speed_pos)
        config['Audio']['deesser'] = str(self.deesser_enabled)
        config['Audio']['compressor'] = str(self.compressor_enabled)
        config['Audio']['noise_suppression'] = str(self.noise_suppression_enabled)
        config['Audio']['vad_threshold'] = str(self.vad_threshold)
        config['Audio']['vad_grace_period'] = str(self.vad_grace_period)
        config['Audio']['vad_retroactive_grace'] = str(self.vad_retroactive_grace)
        config['Audio']['deesser_preset'] = str(self.deesser_preset)
        config['Audio']['compressor_preset'] = str(self.compressor_preset)
        config['Audio']['pitch_enabled'] = str(self.pitch_enabled)
        config['Audio']['pitch_value'] = str(self.pitch_value)

        if 'Library' not in config: config['Library'] = {}
        config['Library']['show_folders'] = str(self.show_folders)
        config['Library']['show_filter_labels'] = str(self.show_filter_labels)
        
        if 'Audiobook_Style' not in config: config['Audiobook_Style'] = {}
        config['Audiobook_Style']['icon_size'] = str(self.audiobook_icon_size)
        config['Audiobook_Style']['row_height'] = str(self.audiobook_row_height)
        
        if 'Folder_Style' not in config: config['Folder_Style'] = {}
        config['Folder_Style']['icon_size'] = str(self.folder_icon_size)
        config['Folder_Style']['row_height'] = str(self.folder_row_height)
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            config.write(f)

    def load_settings(self):
        config = configparser.ConfigParser()
        config.read(self.config_file, encoding='utf-8')
        
        self.show_id3 = config.getboolean('Player', 'show_id3', fallback=False)
        self.auto_rewind = config.getboolean('Player', 'auto_rewind', fallback=False)
        self.auto_check_updates = config.getboolean('Player', 'auto_check_updates', fallback=True)
        
        print(f"Loaded auto_check_updates: {self.auto_check_updates}")
        print(f"Loaded auto_rewind: {self.auto_rewind}")
        print(f"Loaded show_id3: {self.show_id3}")

def test():
    config_file = "test_settings.ini"
    if os.path.exists(config_file): os.remove(config_file)
    
    app = MockApp(config_file)
    print("Saving settings with auto_check_updates=False...")
    app.save_settings()
    
    # Check the file content
    with open(config_file, 'r') as f:
        content = f.read()
        print("Config File Content:")
        print(content)
        
    print("Loading settings...")
    app2 = MockApp(config_file)
    app2.load_settings()
    
    assert app2.auto_check_updates == False
    assert app2.auto_rewind == True
    assert app2.show_id3 == True
    print("Test passed!")
    
    if os.path.exists(config_file): os.remove(config_file)

if __name__ == "__main__":
    test()
