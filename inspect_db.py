"""Inspect the database to identify users and their related records."""
import sqlite3
import sys

DB_PATH = 'instance/salahmate.db'

def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # List all users
    cur.execute('SELECT id, username, email, full_name FROM users ORDER BY id')
    print('=== USERS ===')
    for r in cur.fetchall():
        print(f'  ID={r[0]}  username={r[1]}  email={r[2]}  name={r[3]}')

    # Count records per user per table
    tables = ['prayers', 'quran_readings', 'bookmarks', 'alarms', 'attendance', 'quran_reading', 'bookmark', 'dhikr']
    print('\n=== RECORD COUNTS PER USER ===')
    for t in tables:
        cur.execute(f'SELECT user_id, COUNT(*) FROM {t} GROUP BY user_id ORDER BY user_id')
        rows = cur.fetchall()
        if rows:
            print(f'  {t}: {dict(rows)}')
        else:
            print(f'  {t}: (empty)')

    # Check for orphaned records (user_id not in users table)
    print('\n=== ORPHANED RECORDS ===')
    for t in tables:
        cur.execute(f'SELECT COUNT(*) FROM {t} WHERE user_id NOT IN (SELECT id FROM users)')
        count = cur.fetchone()[0]
        if count > 0:
            print(f'  {t}: {count} orphaned records!')
        else:
            print(f'  {t}: 0 orphaned')

    conn.close()
    return 0

if __name__ == '__main__':
    sys.exit(main())