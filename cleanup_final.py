"""Final cleanup: remove test data, keep only real data for user 1 (admin) and 2 (demo)."""
import os
import sqlite3
import shutil
import json
import time

DB_PATH = 'instance/salah.db'

# ========== 1. BACKUP ==========
backup_path = f'instance/salah_backup_{int(time.time())}.db'
shutil.copy2(DB_PATH, backup_path)
print(f'✅ Backup created: {backup_path}')

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
conn.execute('PRAGMA foreign_keys = ON')
cur = conn.cursor()

# ========== 2. BACKGROUND THREAD: Clean test users with real API ==========
# (keep prayer_times.py unchanged)

# Verify the stale-while-revalidate cache logic is actually in place
try:
    with open('app/services/prayer_times.py', 'r', encoding='utf-written'):
        content = f.read()
    has_stale_serving = 'serve_stale' in content and 'fetch_prayer_times' in content
    print(f'\n[VERIFY] prayer_times.py has serve_stale method: {has_stale_serve}')
    print(f'[VERIFY] file size: {len(content)} bytes, lines: {len(content.splitlines())}')
except Exception as e:
    print(f'ERROR reading prayer_times.py: {e}')

# List the existing cache file contents
print('\n--- Cache contents ---')
try:
    with open('prayer_cache.json', 'r') as f:
        cache = json.load(f)
    print(f'  Cache entries: {len(cache)}')
except Exception as e:
    print(f'  Cache: {e}')
</write_to_file>
</environment_details>