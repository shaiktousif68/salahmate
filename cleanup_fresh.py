"""Clean up test users using a fresh copy of the database."""
import shutil, sqlite3, sys, os

ORIGINAL = 'instance/salahmate.db'
BACKUP = 'instance/salahmate_backup_20260818_165039.db'
WORKING = 'instance/salahmate_working.db'
TABLES = ['prayers', 'quran_readings', 'bookmarks', 'alarms',
          'attendance', 'quran_reading', 'bookmark', 'dhikr']

def main():
    shutil.copy2(BACKUP, WORKING)
    print(f'Working copy from {BACKUP}')

    conn = sqlite3.connect(WORKING, timeout=10)
    conn.execute('PRAGMA busy_timeout = 10000')
    cur = conn.cursor()

    cur.execute('SELECT id, username FROM users ORDER BY id')
    all_users = cur.fetchall()
    test_ids = [uid for uid, _ in all_users if uid not in {1, 2}]
    if not test_ids:
        print('No test users found.')
        conn.close()
        return 0

    print(f'Removing {len(test_ids)} test users')
    ph = ','.join('?' * len(test_ids))
    total = 0

    for t in TABLES:
        cur.execute(f'SELECT COUNT(*) FROM {t} WHERE user_id IN ({ph})', test_ids)
        n = cur.fetchone()[0]
        if n:
            cur.execute(f'DELETE FROM {t} WHERE user_id IN ({ph})', test_ids)
            print(f'  Deleted {n} from {t}')
            total += n

    cur.execute(f'DELETE FROM users WHERE id IN ({ph})', test_ids)
    print(f'  Deleted {cur.rowcount} test users')
    total += cur.rowcount
    conn.commit()

    for uid in sorted({1, 2}):
        cur.execute('SELECT username FROM users WHERE id=?', (uid,))
        r = cur.fetchone()
        assert r, f'User {uid} MISSING!'
        print(f'  User {uid} ({r[0]}) preserved')

    for t in TABLES:
        cur.execute(f'SELECT COUNT(*) FROM {t} WHERE user_id NOT IN (SELECT id FROM users)')
        n = cur.fetchone()[0]
        assert n == 0, f'{t} has {n} orphans!'
    print('  No orphaned records')

    cur.execute('SELECT id, username FROM users ORDER BY id')
    print(f'  Remaining: {cur.fetchall()}')
    conn.close()

    shutil.copy2(WORKING, ORIGINAL)
    os.remove(WORKING)
    print(f'Cleaned DB written. Removed {total} records.')
    return 0

if __name__ == '__main__':
    sys.exit(main())