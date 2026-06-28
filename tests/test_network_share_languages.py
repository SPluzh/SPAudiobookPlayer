import os
import sys
from pathlib import Path
import pytest

# Ensure standard output can print Unicode characters
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

# Helper to print Unicode safely
def safe_print(text):
    try:
        print(text)
    except UnicodeEncodeError:
        try:
            sys.stdout.buffer.write((text + "\n").encode('utf-8'))
            sys.stdout.flush()
        except Exception:
            # Fallback to ascii representation
            print(text.encode('ascii', 'replace').decode('ascii'))

# Add project root to path if not already there
project_root = str(Path(__file__).parent.parent / "src")
if project_root not in sys.path:
    sys.path.append(project_root)


from lang_detector import detect_detailed, detect, _fix_encoding

SHARE_PATH = r"\\vmware-host\Shared Folders\аудиокниги"

def get_audio_files(directory):
    """Find audio files in a directory (non-recursive)."""
    extensions = {'.mp3', '.m4a', '.m4b', '.mp4', '.flac', '.ape'}
    audio_files = []
    try:
        for entry in os.scandir(directory):
            if entry.is_file() and Path(entry.name).suffix.lower() in extensions:
                audio_files.append(entry.path)
    except Exception:
        pass
    return sorted(audio_files)

def get_language_from_tags(audio_path):
    """Extract language and metadata tags from an audio file using mutagen."""
    try:
        from mutagen import File
        audio = File(audio_path)
        if not audio:
            return None, {}
            
        tags = {}
        suffix = Path(audio_path).suffix.lower()
        explicit_lang = None
        
        if suffix == '.mp3':
            id3 = audio.tags
            if id3:
                tags['title'] = _fix_encoding(str(id3.get('TIT2', ''))).strip()
                tags['author'] = _fix_encoding(str(id3.get('TPE1', ''))).strip()
                tags['album'] = _fix_encoding(str(id3.get('TALB', ''))).strip()
                # TLAN is standard ID3v2 tag for language
                tlan = id3.get('TLAN')
                if tlan:
                    explicit_lang = str(tlan).strip()
        elif suffix in ('.m4a', '.m4b', '.mp4'):
            t_title = audio.get('\xa9nam')
            if t_title: tags['title'] = _fix_encoding(str(t_title[0])).strip()
            t_author = audio.get('\xa9ART') or audio.get('\xa9alb')
            if t_author: tags['author'] = _fix_encoding(str(t_author[0])).strip()
            t_album = audio.get('\xa9alb')
            if t_album: tags['album'] = _fix_encoding(str(t_album[0])).strip()
            # @lan or language in mp4
            t_lang = audio.get('\xa9lan') or audio.get('language')
            if t_lang:
                explicit_lang = str(t_lang[0]).strip()
        elif suffix == '.flac':
            tags['title'] = _fix_encoding(str(audio.get('title', [''])[0])).strip()
            tags['author'] = _fix_encoding(str(audio.get('artist', [''])[0])).strip()
            tags['album'] = _fix_encoding(str(audio.get('album', [''])[0])).strip()
            t_lang = audio.get('language')
            if t_lang:
                explicit_lang = str(t_lang[0]).strip()
        elif suffix == '.ape':
            tags['title'] = _fix_encoding(str(audio.get('Title', [''])[0])).strip()
            tags['author'] = _fix_encoding(str(audio.get('Artist', [''])[0])).strip()
            tags['album'] = _fix_encoding(str(audio.get('Album', [''])[0])).strip()
            t_lang = audio.get('Language') or audio.get('language')
            if t_lang:
                explicit_lang = str(t_lang[0]).strip()
                
        # Clean up empty strings or none-like values
        for k in list(tags.keys()):
            if tags[k].lower() in ('none', '[none]', 'unknown', ''):
                tags[k] = ''
                
        return explicit_lang, tags
    except Exception as e:
        return None, {'error': str(e)}

@pytest.mark.skipif(not os.path.exists(SHARE_PATH), reason=f"Network path {SHARE_PATH} is not accessible")
def test_network_share_audiobooks_language():
    """Scan audiobooks on the network share, read metadata, and detect their language."""
    safe_print(f"\nScanning network share: {SHARE_PATH}\n")
    
    assert os.path.exists(SHARE_PATH), f"Network share path '{SHARE_PATH}' does not exist!"
    
    subdirs = []
    for entry in os.scandir(SHARE_PATH):
        if entry.is_dir():
            subdirs.append(entry)
            
    subdirs = sorted(subdirs, key=lambda e: e.name)
    assert len(subdirs) > 0, "No directories found on the network share!"
    
    results = []
    
    for subdir in subdirs:
        folder_name = subdir.name
        folder_path = subdir.path
        
        # Detect from folder name
        det_folder = detect_detailed(folder_name)
        
        # Look for audio files in the folder
        audio_files = get_audio_files(folder_path)
        
        explicit_lang = None
        metadata = {}
        det_metadata = "unknown"
        
        if audio_files:
            first_file = audio_files[0]
            explicit_lang, metadata = get_language_from_tags(first_file)
            
            # Try to detect from metadata text
            meta_texts = []
            if metadata.get('title'):
                meta_texts.append(metadata['title'])
            if metadata.get('author'):
                meta_texts.append(metadata['author'])
            if metadata.get('album'):
                meta_texts.append(metadata['album'])
                
            if meta_texts:
                combined_meta_text = " - ".join(meta_texts)
                det_metadata = detect(combined_meta_text)
        
        results.append({
            'folder': folder_name,
            'audio_count': len(audio_files),
            'det_folder': det_folder.lang,
            'rule': det_folder.rule,
            'explicit_lang': explicit_lang,
            'metadata': metadata,
            'det_metadata': det_metadata
        })
        
    # Print results summary
    safe_print(f"\n{'Folder Name':<60} | {'Files':<5} | {'Det Fold':<8} | {'Rule':<12} | {'Exp Lang':<8} | {'Det Meta':<8}")
    safe_print("-" * 115)
    for r in results:
        folder_trunc = r['folder'][:57] + '...' if len(r['folder']) > 60 else r['folder']
        safe_print(f"{folder_trunc:<60} | {r['audio_count']:<5} | {r['det_folder']:<8} | {r['rule']:<12} | {str(r['explicit_lang']):<8} | {r['det_metadata']:<8}")
        
    safe_print(f"\nTotal scanned: {len(results)} folders.")
    
    # Report generation to markdown file disabled.

