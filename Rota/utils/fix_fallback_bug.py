"""
Fix the recursive fallback bug in all files
"""

import os
import re

# Files to fix
FILES = [
    'views/production_view.py',
    'views/planning_view.py',
    'views/stock_view.py',
    'views/decision_view.py',
    'views/shipping_view.py',
    'views/daily_summary_dialog.py',
    'views/weekly_schedule_dialog.py',
    'views/report_view.py',
    'views/dashboard_view.py',
    'core/db_manager.py',
    'core/smart_planner.py',
    'core/pdf_engine.py',
    'core/security.py',
]

OLD_FALLBACK = """    # Fallback: timezone_helper bulunamazsa normal datetime kullan
    now_turkey = lambda: now_turkey()
    get_current_date_turkey = lambda: now_turkey().date()"""

NEW_FALLBACK = """    # Fallback: timezone_helper bulunamazsa normal datetime kullan
    from datetime import datetime as _dt
    now_turkey = lambda: _dt.now()
    get_current_date_turkey = lambda: _dt.now().date()"""


def fix_file(filepath):
    """Fix the fallback bug in a file"""
    if not os.path.exists(filepath):
        print(f"[X] Dosya bulunamadi: {filepath}")
        return False

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    if OLD_FALLBACK not in content:
        print(f"[OK] Zaten duzgun: {filepath}")
        return True

    new_content = content.replace(OLD_FALLBACK, NEW_FALLBACK)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"[OK] Duzeltildi: {filepath}")
    return True


def main():
    print("Fallback bug duzeltmesi baslatiliyor...\n")

    success_count = 0
    for filepath in FILES:
        if fix_file(filepath):
            success_count += 1
        print()

    print(f"\nToplam {success_count}/{len(FILES)} dosya duzeltildi.")


if __name__ == '__main__':
    main()
