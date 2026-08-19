"""Safely remove test users (IDs 3-19) and all their related data."""
import shutil, sqlite3, sys, time

DB_PATH = 'instance/salahmate.db'
PROTECTED_IDS = {1, 2}
CHILD_TABLES = ['prayers', 'quran_readings', 'bookmarks', 'alarms',
                'attendance', 'quran_reading', 'bookmark', 'dhikr']

def main():
    backup = f'instance/salahmate_backup_{time.strftime("%Y%m%d_%H%M%S")}.db'
    shutil.copy2(DB_PATH, backup)
    print(f'Backup: {backup}')

    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute('PRAGMA busy_timeout = 10000')
    cur = conn.cursor()

    cur.execute('SELECT id, username FROM users ORDER BY id')
    all_users = cur.fetchall()
    test_ids = [uid for uid, _ in all_users if uid not in PROTECTED_IDS]
    if not test_ids:
        print('No test users found.')
        conn.close()
        return 0

    print(f'Removing {len(test_ids)} test users: {[u for uid, u in all_users if uid in test_ids]}')
    ph = ','.join('?' * len(test_ids))

    total = 0
    for t in CHILD_TABLES:
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

    # Verify protected users
    for uid in sorted(PROTECTED_IDS):
        cur.execute('SELECT username FROM users WHERE id=?', (uid,))
        r = cur.fetchone()
        assert r, f'User {uid} MISSING!'
        print(f'  User {uid} ({r[0]}) preserved')

    # Verify no orphans
    for t in CHILD_TABLES:
        cur.execute(f'SELECT COUNT(*) FROM {t} WHERE user_id NOT IN (SELECT id FROM users)')
        n = cur.fetchone()[0]
        assert n == 0, f'{t} has {n} orphans!'
    print('  No orphaned records')

    cur.execute('SELECT id, username FROM users ORDER BY id')
    print(f'  Remaining users: {cur.fetchall()}')
    conn.close()
    print(f'Removed {total} records total. Backup: {backup}')
    return 0

if __name__ == '__main__':
    sys.exit(main())