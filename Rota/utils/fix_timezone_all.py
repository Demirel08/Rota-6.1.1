"""
Tüm view dosyalarında datetime.now() → now_turkey() dönüşümü
Bir kerelik çalıştırılacak yardımcı script
"""

import os
import re

# İşlem yapılacak dosyalar
VIEW_FILES = [
    'views/production_view.py',
    'views/planning_view.py',
    'views/stock_view.py',
    'views/decision_view.py',
    'views/shipping_view.py',
    'views/daily_summary_dialog.py',
    'views/weekly_schedule_dialog.py',
    'views/report_view.py',
    'views/dashboard_view.py',
    'core/logger.py',
    'core/db_manager.py',
    'core/smart_planner.py',
    'core/pdf_engine.py',
    'core/security.py',
]

# Import eklenecek kod bloğu
IMPORT_BLOCK = """
try:
    from utils.timezone_helper import now_turkey, get_current_date_turkey
except ImportError:
    # Fallback: timezone_helper bulunamazsa normal datetime kullan
    from datetime import datetime as _dt
    now_turkey = lambda: _dt.now()
    get_current_date_turkey = lambda: _dt.now().date()
"""


def fix_file(filepath):
    """Bir dosyayı düzelt"""
    if not os.path.exists(filepath):
        print(f"[X] Dosya bulunamadi: {filepath}")
        return False

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Zaten düzeltilmiş mi kontrol et
    if 'from utils.timezone_helper import' in content:
        print(f"[OK] Zaten duzeltilmis: {filepath}")
        return True

    # datetime import'unu bul
    datetime_import_pattern = r'from datetime import.*\n'
    match = re.search(datetime_import_pattern, content)

    if not match:
        print(f"[!] datetime import bulunamadi: {filepath}")
        return False

    # Import bloğunu ekle
    insert_pos = match.end()
    new_content = content[:insert_pos] + IMPORT_BLOCK + content[insert_pos:]

    # datetime.now() → now_turkey() değiştir
    # Dikkat: isinstance(x, datetime) gibi type check'leri değiştirme
    new_content = re.sub(
        r'datetime\.now\(\)',
        'now_turkey()',
        new_content
    )

    # Dosyayı kaydet
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"[OK] Duzeltildi: {filepath}")
    return True


def main():
    """Tüm dosyaları düzelt"""
    print("Turkiye saati duzeltmesi baslatiliyor...\n")

    success_count = 0
    for filepath in VIEW_FILES:
        if fix_file(filepath):
            success_count += 1
        print()

    print(f"\nToplam {success_count}/{len(VIEW_FILES)} dosya duzeltildi.")


if __name__ == '__main__':
    main()
