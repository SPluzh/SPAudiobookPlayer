import os
import sys
import re
from pathlib import Path
from mutagen import File

# Ensure standard output can print Unicode characters
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

share_path = r"\\vmware-host\Shared Folders\аудиокниги"

def get_audio_files(directory):
    extensions = {'.mp3', '.m4a', '.m4b', '.mp4', '.flac', '.ape'}
    audio_files = []
    try:
        for entry in os.scandir(directory):
            if entry.is_file() and Path(entry.name).suffix.lower() in extensions:
                audio_files.append(entry.path)
    except Exception:
        pass
    return sorted(audio_files)

def inspect_year_tags(audio_path):
    try:
        audio = File(audio_path)
        if not audio:
            return None, None
            
        suffix = Path(audio_path).suffix.lower()
        rec_year = None
        orig_year = None
        
        if suffix == '.mp3':
            id3 = audio.tags
            if id3:
                rec_year = id3.get('TDRC') or id3.get('TYER')
                orig_year = id3.get('TDOR') or id3.get('TORY')
        elif suffix in ('.m4a', '.m4b', '.mp4'):
            rec_year = audio.get('©day')
            orig_year = audio.get('©opd') or audio.get('original_release_date') or audio.get('original-release-date')
        elif suffix == '.flac':
            rec_year = audio.get('date') or audio.get('DATE') or audio.get('year') or audio.get('YEAR')
            orig_year = audio.get('original_release_date') or audio.get('original_date') or audio.get('original_year') or audio.get('ORIGINAL_RELEASE_DATE') or audio.get('ORIGINAL_DATE') or audio.get('ORIGINAL_YEAR')
        elif suffix == '.ape':
            rec_year = audio.get('Year') or audio.get('year') or audio.get('Date') or audio.get('date')
            orig_year = audio.get('Original Year') or audio.get('original year')
            
        if rec_year: rec_year = str(rec_year[0] if isinstance(rec_year, list) else rec_year).strip()
        if orig_year: orig_year = str(orig_year[0] if isinstance(orig_year, list) else orig_year).strip()
        
        return rec_year, orig_year
    except Exception:
        pass
    return None, None

def parse_years(folder_name, rec_tag, orig_tag):
    tag_years = set()
    if rec_tag:
        for y in re.findall(r'\b\d{4}\b', rec_tag):
            if 1800 <= int(y) <= 2026:
                tag_years.add(int(y))
    if orig_tag:
        for y in re.findall(r'\b\d{4}\b', orig_tag):
            if 1800 <= int(y) <= 2026:
                tag_years.add(int(y))
                
    # 2. Gather all unique years from folder name (anywhere in the name)
    folder_years = []
    for match in re.finditer(r'\b\d{4}\b', folder_name):
        y_val = int(match.group(0))
        if 1800 <= y_val <= 2026:
            pos = match.start()
            # Check 30 chars before and after for narration keywords
            context = folder_name[max(0, pos-30):min(len(folder_name), pos+30)]
            is_audio = any(kw in context.lower() for kw in ['чит', 'гол', 'кня', 'клю', 'кир', 'ав', 'ауди', 'изд', 'kbps', 'mp3', 'm4b', 'flac', 'мелод'])
            folder_years.append((y_val, is_audio))
            
    # Combine all found years
    all_years = list(tag_years)
    for y, is_aud in folder_years:
        if y not in all_years:
            all_years.append(y)
            
    all_years = sorted(all_years)
    
    book_year = None
    audio_year = None
    
    if len(all_years) >= 2:
        # The smaller one is the book publication year, the larger is the audiobook recording year.
        book_year = all_years[0]
        audio_year = all_years[-1]
    elif len(all_years) == 1:
        single_year = all_years[0]
        # Check if the folder year had audio context
        is_aud = False
        for y, is_a in folder_years:
            if y == single_year:
                is_aud = is_a
                break
                
        if is_aud or single_year >= 2000:
            audio_year = single_year
        else:
            book_year = single_year
            
    # Normalize values
    b_year_str = str(book_year) if book_year else "Неизвестно"
    a_year_str = str(audio_year) if audio_year else "Неизвестно"
    
    return b_year_str, a_year_str

def run_inspection():
    subdirs = []
    for entry in os.scandir(share_path):
        if entry.is_dir():
            subdirs.append(entry)
            
    subdirs = sorted(subdirs, key=lambda e: e.name)
    
    report_lines = []
    report_lines.append("# Отчет по годам аудиокниг: год написания и год записи")
    report_lines.append("")
    report_lines.append("| Папка / Книга | Год написания (книги) | Год записи (аудиокниги) |")
    report_lines.append("|:---|:---|:---|")
    
    stats_both = 0
    stats_only_book = 0
    stats_only_audio = 0
    stats_none = 0
    
    print(f"{'Название книги (Папка)':<75} | {'Год книги':<12} | {'Год записи':<10}")
    print("-" * 105)
    
    for subdir in subdirs:
        audio_files = get_audio_files(subdir.path)
        rec_tag, orig_tag = None, None
        if audio_files:
            rec_tag, orig_tag = inspect_year_tags(audio_files[0])
            
        book_year, audio_year = parse_years(subdir.name, rec_tag, orig_tag)
        
        # Track statistics
        if book_year != "Неизвестно" and audio_year != "Неизвестно":
            stats_both += 1
        elif book_year != "Неизвестно":
            stats_only_book += 1
        elif audio_year != "Неизвестно":
            stats_only_audio += 1
        else:
            stats_none += 1
            
        folder_trunc = subdir.name[:72] + '...' if len(subdir.name) > 75 else subdir.name
        print(f"{folder_trunc:<75} | {book_year:<12} | {audio_year:<10}")
        report_lines.append(f"| {subdir.name} | {book_year} | {audio_year} |")
        
    summary = []
    summary.append("## Статистика")
    summary.append(f"- Всего отсканировано аудиокниг: **{len(subdirs)}**")
    summary.append(f"- Найдены оба года (написания и записи): **{stats_both}**")
    summary.append(f"- Найден только год написания книги: **{stats_only_book}**")
    summary.append(f"- Найден только год записи аудиокниги: **{stats_only_audio}**")
    summary.append(f"- Года не определены: **{stats_none}**")
    
    # Prepend summary to report
    report_lines.insert(2, "\n".join(summary))
    report_lines.insert(3, "")
    
    # Save report
    report_path = os.path.join(os.path.dirname(__file__), "years_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
        
    print("\n" + "=" * 40)
    print(f"Отчет сохранен в: {report_path}")
    print(f"Статистика:")
    for line in summary:
        print("  " + line)
    print("=" * 40)

if __name__ == "__main__":
    run_inspection()
