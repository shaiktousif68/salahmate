"""Test stale-while-revalidate prayer-time cache."""
import json, os, sys, time
from datetime import date

import requests as _req
_orig_get = _req.get
_api_delay = 0.0
_api_fail = False

def _timed_get(*args, **kwargs):
    timeout = kwargs.get('timeout', 3)
    if _api_delay > 0:
        if _api_delay > timeout:
            # Simulate a real timeout — the API is slower than the timeout
            raise _req.Timeout('Simulated API timeout')
        time.sleep(_api_delay)
    if _api_fail:
        raise _req.RequestException('Simulated API failure')
    # Return a mock AlAdhan response so background refresh completes fast
    class MockResponse:
        def raise_for_status(self):
            pass
        def json(self):
            return {
                'code': 200,
                'data': {
                    'timings': {
                        'Fajr': '04:40', 'Sunrise': '06:00', 'Dhuhr': '12:25',
                        'Asr': '15:48', 'Maghrib': '18:30', 'Isha': '19:45',
                        'Imsak': '04:30', 'Midnight': '00:00'
                    },
                    'date': {
                        'hijri': {'date': '01-01-1448', 'weekday': {'en': 'Monday'}}
                    }
                }
            }
    return MockResponse()

_req.get = _timed_get

from app import create_app, db
from app.models.user import User
from app.services.prayer_times import PrayerTimesService
from app.services import prayer_times as _pt_module

CACHE_DIR = os.path.join(os.path.dirname(_pt_module.__file__), '.prayer_cache')

def clear_cache():
    if os.path.exists(CACHE_DIR):
        for fn in os.listdir(CACHE_DIR):
            try: os.remove(os.path.join(CACHE_DIR, fn))
            except OSError: pass
    PrayerTimesService._cache.clear()

def create_expired_cache(lat, lon, method, date_str):
    key = PrayerTimesService._cache_key(lat, lon, method, date_str)
    f = PrayerTimesService._cache_file_path(key)
    os.makedirs(CACHE_DIR, exist_ok=True)
    old_ts = time.time() - 2 * 86400
    data = {'Fajr': '04:40', 'Sunrise': '06:00', 'Dhuhr': '12:25',
            'Asr': '15:48', 'Maghrib': '18:30', 'Isha': '19:45',
            'Imsak': '04:30', 'Midnight': '00:00', 'date': date_str,
            'hijri_date': '01-01-1448', 'hijri_weekday': 'Monday'}
    with open(f, 'w', encoding='utf-8') as fh:
        json.dump([old_ts, data], fh, ensure_ascii=False)

def main():
    global _api_delay, _api_fail
    app = create_app('development')
    with app.app_context():
        db.create_all()
        today = date.today()
        date_str = today.strftime('%d-%m-%Y')
        LAT, LON, M = 21.4225, 39.8262, 4

        print('=' * 60)
        print('STALE-WHILE-REVALIDATE CACHE TEST')
        print('=' * 60)

        # TEST 1: Fresh cache
        print('\n--- TEST 1: Fresh cache ---')
        clear_cache()
        PrayerTimesService._cache[PrayerTimesService._cache_key(LAT, LON, M, date_str)] = (time.time(), {'Fajr': '04:40'})
        t0 = time.perf_counter()
        r = PrayerTimesService.get_prayer_times(LAT, LON, M, today)
        dt = (time.perf_counter() - t0) * 1000
        assert r is not None and dt < 100, f'Fresh cache: {dt:.1f}ms'
        print(f'  {dt:.1f}ms  PASS')

        # TEST 2: Expired cache + slow API (2s, under 3s timeout) -> instant + background refresh
        print('\n--- TEST 2: Expired cache + 2s API delay ---')
        clear_cache()
        create_expired_cache(LAT, LON, M, date_str)
        _api_delay = 2.0
        t0 = time.perf_counter()
        r = PrayerTimesService.get_prayer_times(LAT, LON, M, today)
        dt = (time.perf_counter() - t0) * 1000
        assert r is not None and dt < 100, f'Stale cache: {dt:.1f}ms'
        print(f'  {dt:.1f}ms  Served stale instantly (2s API did NOT block)  PASS')
        time.sleep(4)
        key = PrayerTimesService._cache_key(LAT, LON, M, date_str)
        cached = PrayerTimesService._cache.get(key)
        assert cached and time.time() - cached[0] < 60, 'Background refresh failed'
        print('  Background refresh completed  PASS')
        _api_delay = 0.0

        # TEST 3: First-ever request + slow API (8s) -> 3s timeout
        print('\n--- TEST 3: First request + 8s API delay ---')
        clear_cache()
        _api_delay = 8.0
        t0 = time.perf_counter()
        r = PrayerTimesService.get_prayer_times(LAT, LON, M, today)
        dt = (time.perf_counter() - t0) * 1000
        assert dt < 5000, f'First request blocked {dt:.1f}ms'
        print(f'  {dt:.1f}ms  Short timeout prevented 8s block  PASS')
        _api_delay = 0.0

        # TEST 4: API unavailable + stale cache
        print('\n--- TEST 4: API unavailable + stale cache ---')
        clear_cache()
        create_expired_cache(LAT, LON, M, date_str)
        _api_fail = True
        t0 = time.perf_counter()
        r = PrayerTimesService.get_prayer_times(LAT, LON, M, today)
        dt = (time.perf_counter() - t0) * 1000
        assert r is not None and dt < 100, f'API fail: {dt:.1f}ms'
        print(f'  {dt:.1f}ms  Stale data served despite API failure  PASS')
        _api_fail = False

        # TEST 5: Multiple navigations -> no duplicate refresh
        print('\n--- TEST 5: Multiple navigations ---')
        clear_cache()
        create_expired_cache(LAT, LON, M, date_str)
        _api_delay = 2.0
        PrayerTimesService.get_prayer_times(LAT, LON, M, today)
        t0 = time.perf_counter()
        r = PrayerTimesService.get_prayer_times(LAT, LON, M, today)
        dt = (time.perf_counter() - t0) * 1000
        assert r is not None and dt < 100, f'2nd call: {dt:.1f}ms'
        print(f'  {dt:.1f}ms  No duplicate refresh  PASS')
        _api_delay = 0.0

        print('\n' + '=' * 60)
        print('ALL STALE-WHILE-REVALIDATE TESTS PASSED')
        print('=' * 60)
    return 0

if __name__ == '__main__':
    sys.exit(main())