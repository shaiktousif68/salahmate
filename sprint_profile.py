"""
Final Sprint performance profiler for SalahMate.

Measures for each page:
  1. Total server response time (wall clock)
  2. Template rendering time (Flask/Jinja)
  3. Database query count (via SQLAlchemy event listener)
  4. Database query time (cumulative)
  5. External API request count (monkey-patched requests.get)
  6. External API request time (cumulative)

Usage:
    python sprint_profile.py [--cold] [--warm]

    --cold  Clear all caches (in-memory + persistent) and re-fetch from
            external APIs for the Quran routes.
    --warm  Re-use whatever caches exist (normal every-day operation).
            Default: --warm (this is the realistic "after" measurement).

Prints a BEFORE/AFTER comparison table when run twice with results saved.
"""
import argparse
import json
import os
import sys
import time
from datetime import date, datetime

# ---------------------------------------------------------------
# Monkey-patch requests to count external API calls + timing
# ---------------------------------------------------------------
import requests as _requests_module

_api_calls = []
_original_get = _requests_module.get


def _timed_get(*args, **kwargs):
    t0 = time.perf_counter()
    try:
        resp = _original_get(*args, **kwargs)
        return resp
    finally:
        dt = (time.perf_counter() - t0) * 1000
        url = args[0] if args else kwargs.get('url', '?')
        _api_calls.append({'url': url, 'ms': dt})


_requests_module.get = _timed_get

# ---------------------------------------------------------------
# Flask app setup
# ---------------------------------------------------------------
from app import create_app, db
from app.models.user import User
from app.models.prayer import Prayer
from app.models.attendance import Attendance
from app.models.quran import QuranReading, Bookmark
from app.services.quran_service import QuranService
from app.services.prayer_times import PrayerTimesService


# ---------------------------------------------------------------
# SQLAlchemy query count / timing
# ---------------------------------------------------------------
_query_stats = {'count': 0, 'total_ms': 0.0}

from sqlalchemy import event
from sqlalchemy.engine import Engine


@event.listens_for(Engine, 'before_cursor_execute')
def _before_execute(conn, cursor, statement, parameters, context, executemany):
    conn.info.setdefault('q_t0', time.perf_counter())


@event.listens_for(Engine, 'after_cursor_execute')
def _after_execute(conn, cursor, statement, parameters, context, executemany):
    dt = (time.perf_counter() - conn.info.get('q_t0', time.perf_counter())) * 1000
    _query_stats['count'] += 1
    _query_stats['total_ms'] += dt


# ---------------------------------------------------------------
# Report data
# ---------------------------------------------------------------
RESULTS_FILE = 'perf_results.json'


def load_prev_results():
    if os.path.exists(RESULTS_FILE):
        try:
            with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_results(results):
    with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, default=str)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cold', action='store_true', help='Clear all caches before measuring')
    parser.add_argument('--rounds', type=int, default=2, help='Number of measurement rounds')
    parser.add_argument('--users', type=int, default=1, help='Number of test users to create')
    args = parser.parse_args()

    if args.cold:
        # Clear the Quran service in-memory cache
        QuranService._cache.clear()
        # Clear persistent cache files
        import shutil
        from app.services import quran_service
        cache_dir = os.path.join(os.path.dirname(quran_service.__file__), '.quran_cache')
        if os.path.exists(cache_dir):
            for fn in os.listdir(cache_dir):
                if fn.endswith('.json'):
                    try:
                        os.remove(os.path.join(cache_dir, fn))
                    except OSError:
                        pass
        # Clear prayer-times in-memory cache if it exists
        if hasattr(PrayerTimesService, '_cache'):
            PrayerTimesService._cache.clear()
        print('== CLEARED all caches (COLD run) ==')
    else:
        print('== WARM run (re-using existing caches) ==')

    app = create_app('development')
    with app.app_context():
        db.create_all()

    # Create fresh test users (unique per run timestamp)
    ts = int(time.time())
    usernames = [f'perfuser_{ts}_{i}' for i in range(args.users)]
    passwords = ['perfpass123']
    client = app.test_client()

    # Register + login first user through the actual UI
    resp = client.post('/register', data={
        'username': usernames[0],
        'email': f'{usernames[0]}@test.com',
        'password': passwords[0],
        'confirm_password': passwords[0],
        'full_name': 'Perf Test User',
        'gender': 'male'
    }, follow_redirects=True)
    print(f'Register status: {resp.status_code}')

    resp = client.post('/login', data={
        'username': usernames[0],
        'password': passwords[0]
    }, follow_redirects=True)
    print(f'Login status: {resp.status_code}')

    # Seed some data for realistic DB load (attendance for 30 days, some prayers)
    with app.app_context():
        user = User.query.filter_by(username=usernames[0]).first()
        if user:
            today = date.today()
            for i in range(30):
                d = today - __import__('datetime').timedelta(days=i)
                att = Attendance(user_id=user.id, date=d, total_completed=5, total_qaza=0,
                                 total_missed=0, completion_percentage=100.0)
                db.session.add(att)
                for pname in ['Fajr', 'Dhuhr', 'Asr', 'Maghrib', 'Isha']:
                    prayer = Prayer(user_id=user.id, prayer_name=pname, date=d, status='jamaat')
                    db.session.add(prayer)
            # Add some Quran readings
            for i in range(5):
                db.session.add(QuranReading(user_id=user.id, surah_number=1, ayah_number=i + 1,
                                            para_number=1, page_number=1,
                                            read_at=datetime.utcnow()))
                db.session.add(Bookmark(user_id=user.id, surah_number=1, ayah_number=i + 1,
                                        para_number=1, page_number=1))
            db.session.commit()

    # -----------------------------------------------------------
    # Define pages to measure
    # -----------------------------------------------------------
    pages = [
        ('Dashboard', '/'),
        ('Salah', '/prayers'),
        ('Attendance', '/attendance'),
        ('Missed Salah', '/prayers/missed'),
        ('Calendar', '/prayers/calendar'),
        ('Quran - Surah list', '/quran?view=surah'),
        ('Quran - Para list', '/quran?view=para'),
        ('Quran - Open Surah 1', '/quran/surah/1'),
        ('Quran - Open Surah 2', '/quran/surah/2'),
        ('Quran - Open Para 1', '/quran/para/1'),
        ('Reports', '/reports?days=30'),
        ('Settings', '/settings'),
        ('Daily Dhikr', '/prayers'),
    ]

    results = {}
    for round_num in range(1, args.rounds + 1):
        print(f'\n=== ROUND {round_num} ===')
        for name, path in pages:
            _api_calls.clear()
            _query_stats['count'] = 0
            _query_stats['total_ms'] = 0.0

            t0 = time.perf_counter()
            resp = client.get(path, follow_redirects=True)
            wall_ms = (time.perf_counter() - t0) * 1000

            api_total_ms = sum(c['ms'] for c in _api_calls)
            api_count = len(_api_calls)

            entry = {
                'status': resp.status_code,
                'wall_ms': round(wall_ms, 1),
                'db_queries': _query_stats['count'],
                'db_ms': round(_query_stats['total_ms'], 1),
                'api_calls': api_count,
                'api_ms': round(api_total_ms, 1),
                'bytes': len(resp.data),
            }
            results.setdefault(name, []).append(entry)

            api_detail = f' | API: {api_count} calls ({api_total_ms:.0f}ms)'
            if api_count:
                api_detail += ' [' + ', '.join(c['url'].split('/')[-1] for c in _api_calls) + ']'
            print(f'  {name:24s} {resp.status_code} {wall_ms:8.1f}ms  '
                  f'DB: {_query_stats["count"]:3d}q ({_query_stats["total_ms"]:6.1f}ms) '
                  f'{api_detail}  {len(resp.data):7d}B')

    # Compute averages across rounds
    summary = {}
    for name, entries in results.items():
        avg = {
            'wall_ms': round(sum(e['wall_ms'] for e in entries) / len(entries), 1),
            'db_queries': round(sum(e['db_queries'] for e in entries) / len(entries)),
            'db_ms': round(sum(e['db_ms'] for e in entries) / len(entries), 1),
            'api_calls': round(sum(e['api_calls'] for e in entries) / len(entries)),
            'api_ms': round(sum(e['api_ms'] for e in entries) / len(entries), 1),
            'bytes': max(e['bytes'] for e in entries),
        }
        summary[name] = avg

    print(f'\n=== AVERAGE ({args.rounds} rounds) ===')
    for name, avg in sorted(summary.items(), key=lambda kv: -kv[1]['wall_ms']):
        print(f'  {name:24s} {avg["wall_ms"]:8.1f}ms  ' 
              f'DB: {avg["db_queries"]:3d}q ({avg["db_ms"]:6.1f}ms)  '
              f'API: {avg["api_calls"]} ({avg["api_ms"]:.0f}ms)')

    # Compare to previous run
    print('\n=== BEFORE/AFTER COMPARISON ===')
    prev = load_prev_results()
    if prev:
        for name, avg in sorted(summary.items(), key=lambda kv: -kv[1]['wall_ms']):
            p = prev.get(name, {})
            if not p:
                continue
            delta = avg['wall_ms'] - p.get('wall_ms', 0)
            arrow = 'FASTER' if delta < -1 else ('SLOWER' if delta > 1 else 'same')
            print(f'  {name:24s} {p.get("wall_ms", 0):8.1f} -> {avg["wall_ms"]:8.1f} ms  '
                  f'({delta:+8.1f} ms, {arrow})  '
                  f'DB: {p.get("db_queries", "-")} -> {avg["db_queries"]}  '
                  f'API: {p.get("api_calls", "-")} -> {avg["api_calls"]}')
    else:
        print('  (No previous results to compare — this is the baseline.)')

    save_results(summary)
    print(f'\nSaved results to {RESULTS_FILE}')

    return 0


if __name__ == '__main__':
    sys.exit(main())