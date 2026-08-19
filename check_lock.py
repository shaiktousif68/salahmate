"""Check database lock state."""
import os, glob, stat

print('=== DB FILES ===')
for f in glob.glob('instance/salahmate.db*'):
    print(f'  {f}: {os.path.getsize(f)} bytes')

mode = os.stat('instance/salahmate.db').st_mode
print(f'DB read-only: {bool(not (mode & stat.S_IWRITE))}')

print('\n=== WRITE TEST ===')
import sqlite3
try:
    conn = sqlite3.connect('instance/salahmate.db', timeout=3)
    conn.execute('PRAGMA busy_timeout = 3000')
    conn.execute('CREATE TABLE IF NOT EXISTS _lock_test (id INTEGER)')
    conn.execute('DROP TABLE _lock_test')
    conn.commit()
    print('Write OK')
    conn.close()
except Exception as e:
    print(f'Write FAILED: {e}')

print('\n=== READ TEST ===')
try:
    conn = sqlite3.connect('instance/salahmate.db', timeout=3)
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM users')
    print(f'Users: {cur.fetchone()[0]}')
    conn.close()
    print('Read OK')
except Exception as e:
    print(f'Read FAILED: {e}')