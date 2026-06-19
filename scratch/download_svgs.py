import urllib.request
import json
from pathlib import Path

ICONS_DIR = Path(__file__).parent.parent / "resources" / "icons"
ICONS_DIR.mkdir(parents=True, exist_ok=True)

MAPPING = {
    "add": "plus",
    "arrow-down-wide-narrow": "arrow-down-wide-narrow",
    "arrow-up-narrow-wide": "arrow-up-narrow-wide",
    "author": "user",
    "check": "check",
    "chevron-down": "chevron-down",
    "collapse": "list-chevrons-down-up",
    "context_edit_metadata": "pencil",
    "context_favorite_off": "heart",
    "context_favorite_on": "heart",
    "context_mark_read": "check",
    "context_mark_unread": "plus",
    "context_open_folder": "folder-open",
    "context_play": "play",
    "context_tags": "tag",
    "delete": "trash-2",
    "download": "download",
    "edit": "pencil",
    "expand": "list-chevrons-up-down",
    "fail": "circle-alert",
    "favorites": "heart",
    "filter_all": "infinity",
    "filter_completed": "check",
    "filter_in_progress": "play",
    "filter_not_started": "plus",
    "folder_cover": "folder",
    "forward_10": "chevron-right",
    "forward_60": "chevrons-right",
    "github": "cloud-download",
    "info_bitrate": "disc-3",
    "info_duration": "clock",
    "info_file_count": "music",
    "info_size": "save",
    "languages": "languages",
    "locate": "locate",
    "menu_about": "info",
    "menu_reload": "rotate-cw",
    "menu_scan": "search",
    "menu_settings": "settings",
    "merge": "squares-unite",
    "narrator": "mic",
    "next": "chevron-last",
    "opus": "music",
    "palette": "palette",
    "pause": "pause",
    "play": "play",
    "prev": "chevron-first",
    "rewind_10": "chevron-left",
    "rewind_60": "chevrons-left",
    "save": "save",
    "scan": "search",
    "square-check": "square-check",
    "statistics": "chart-pie",
    "update": "refresh-cw"
}

def download_svg(lucide_name: str) -> str:
    url = f"https://raw.githubusercontent.com/lucide-icons/lucide/main/icons/{lucide_name}.svg"
    try:
        with urllib.request.urlopen(url) as response:
            return response.read().decode('utf-8')
    except Exception as e:
        print(f"Error downloading {lucide_name}: {e}")
        return ""

def main():
    print("Starting SVG download...")
    for local_name, lucide_name in MAPPING.items():
        print(f"Downloading {local_name} (Lucide: {lucide_name})...")
        svg_content = download_svg(lucide_name)
        if svg_content:
            # Special case: context_favorite_on should be filled heart
            if local_name == "context_favorite_on":
                # replace fill="none" with fill="currentColor" so it renders filled
                svg_content = svg_content.replace('fill="none"', 'fill="currentColor"')
            
            dest_path = ICONS_DIR / f"{local_name}.svg"
            dest_path.write_text(svg_content, encoding="utf-8")
            print(f"Saved {dest_path}")
        else:
            print(f"Failed to download {local_name}")

if __name__ == "__main__":
    main()
