import json
import os
import threading
import time

import requests
from datetime import datetime, date
from flask import current_app


class PrayerTimesService:
    """Service for fetching and calculating prayer times.

    Caching strategy: STALE-WHILE-REVALIDATE.

    The user must NEVER wait for the external AlAdhan API. If any cached
    prayer data exists (even expired), it is served immediately and the
    cache is refreshed in the background. Only the very first request for
    a given location+date (no cache at all) makes a synchronous API call,
    and that call uses a short 3-second timeout so it can never block the
    page for 10+ seconds.
    """

    PRAYER_NAMES = ['Fajr', 'Dhuhr', 'Asr', 'Maghrib', 'Isha']

    # In-memory cache: key = "lat:lon:method:date", value = (timestamp, data)
    _cache = {}
    # TTL: 23 hours. After this, the cached data is served as "stale" and
    # refreshed in the background — the user never waits.
    _CACHE_TTL = 23 * 3600
    # Short timeout for the FIRST-EVER request (no cache at all). Prevents
    # a slow/unavailable API from blocking the page for 10+ seconds.
    _API_TIMEOUT = 3
    # Longer timeout for BACKGROUND refreshes (runs in a daemon thread and
    # never blocks the page — it can afford to wait for the real API).
    _REFRESH_TIMEOUT = 15
    # Track in-flight background refreshes to avoid duplicate API calls.
    _refresh_locks = {}

    # Persistent file cache directory (same pattern as QuranService).
    _cache_dir = os.path.join(os.path.dirname(__file__), '.prayer_cache')
    os.makedirs(_cache_dir, exist_ok=True)

    @classmethod
    def _cache_key(cls, latitude, longitude, method, date_str):
        return f'{latitude}:{longitude}:{method}:{date_str}'

    @classmethod
    def _cache_file_path(cls, key):
        """Return the filesystem path for a cache key (Windows-safe)."""
        # Windows cannot have ':' in filenames — sanitize the key.
        safe_key = key.replace(':', '_')
        return os.path.join(cls._cache_dir, f'{safe_key}.json')

    @classmethod
    def _load_from_persistent(cls, key):
        """Load from the persistent file cache.

        Returns (timestamp, data) tuple if the file exists and is valid,
        even if the data is EXPIRED (stale). Returns None if no file exists
        or the file is corrupt. Expired data is NOT deleted — it is served
        as stale and refreshed in the background.
        """
        try:
            cache_file = cls._cache_file_path(key)
            if not os.path.exists(cache_file):
                return None
            with open(cache_file, 'r', encoding='utf-8') as f:
                entry = json.load(f)
            if not isinstance(entry, list) or len(entry) < 2:
                return None
            timestamp, data = entry[0], entry[1]
            # Populate in-memory cache (even if stale — it's still useful)
            cls._cache[key] = (timestamp, data)
            return timestamp, data
        except (json.JSONDecodeError, OSError, KeyError, TypeError):
            try:
                os.remove(cls._cache_file_path(key))
            except OSError:
                pass
            return None

    @classmethod
    def _save_to_persistent(cls, key, timestamp, data):
        """Save to the persistent file cache (atomic write)."""
        try:
            cache_file = cls._cache_file_path(key)
            tmp_file = cache_file + '.tmp'
            with open(tmp_file, 'w', encoding='utf-8') as f:
                json.dump([timestamp, data], f, ensure_ascii=False)
            os.replace(tmp_file, cache_file)
        except (OSError, TypeError, ValueError):
            pass

    @classmethod
    def _fetch_from_api(cls, latitude, longitude, method, date_str, api_url, timeout=None):
        """Fetch prayer times from the AlAdhan API.

        This is a pure function — it does NOT touch ``current_app`` so it
        can be safely called from a background thread. The caller must pass
        the API URL explicitly (captured on the calling thread).
        """
        if timeout is None:
            timeout = cls._API_TIMEOUT
        params = {
            'latitude': latitude,
            'longitude': longitude,
            'method': method,
            'date': date_str
        }
        try:
            response = requests.get(api_url, params=params, timeout=timeout)
            response.raise_for_status()
            data = response.json()

            if data.get('code') != 200:
                return None

            timings = data['data']['timings']
            return {
                'Fajr': timings.get('Fajr'),
                'Sunrise': timings.get('Sunrise'),
                'Dhuhr': timings.get('Dhuhr'),
                'Asr': timings.get('Asr'),
                'Maghrib': timings.get('Maghrib'),
                'Isha': timings.get('Isha'),
                'Imsak': timings.get('Imsak'),
                'Midnight': timings.get('Midnight'),
                'date': date_str,
                'hijri_date': data['data'].get('date', {}).get('hijri', {}).get('date'),
                'hijri_weekday': data['data'].get('date', {}).get('hijri', {}).get('weekday', {}).get('en')
            }
        except (requests.RequestException, KeyError, ValueError):
            return None

    @classmethod
    def _refresh_in_background(cls, key, latitude, longitude, method, date_str, api_url):
        """Refresh the cache in a background daemon thread.

        Uses a per-key lock to prevent duplicate concurrent refreshes.
        The API URL is captured on the calling thread (which has the Flask
        app context) and passed explicitly — the worker thread never
        touches ``current_app``.
        """
        # Prevent duplicate concurrent refreshes for the same key
        lock = cls._refresh_locks.setdefault(key, threading.Lock())
        if not lock.acquire(blocking=False):
            return  # Another refresh is already in flight

        def _do_refresh():
            try:
                result = cls._fetch_from_api(
                    latitude, longitude, method, date_str, api_url,
                    timeout=cls._REFRESH_TIMEOUT
                )
                if result is not None:
                    now = time.time()
                    cls._cache[key] = (now, result)
                    cls._save_to_persistent(key, now, result)
            finally:
                lock.release()

        t = threading.Thread(target=_do_refresh, daemon=True)
        t.start()

    @classmethod
    def get_prayer_times(cls, latitude, longitude, method=4, date_obj=None):
        """
        Fetch prayer times from the AlAdhan API (stale-while-revalidate).

        Lookup order:
          1. In-memory cache (fresh) → return immediately
          2. Persistent file cache (fresh) → return immediately
          3. Persistent file cache (STALE/expired) → return stale data
             immediately + trigger background refresh
          4. No cache at all → fetch with short 3s timeout (never blocks
             the page for 10+ seconds)

        Args:
            latitude (float): User's latitude
            longitude (float): User's longitude
            method (int): Calculation method (4 = Umm Al-Qura)
            date_obj (date, optional): Date to fetch times for. Defaults to today.

        Returns:
            dict: Prayer times dictionary or None on error
        """
        if date_obj is None:
            date_obj = date.today()

        date_str = date_obj.strftime('%d-%m-%Y')
        cache_key = cls._cache_key(latitude, longitude, method, date_str)
        now = time.time()

        # 1. In-memory cache (fresh)
        cached = cls._cache.get(cache_key)
        if cached and now - cached[0] < cls._CACHE_TTL:
            return cached[1]

        # 2 & 3. Persistent file cache (fresh OR stale)
        persistent = cls._load_from_persistent(cache_key)
        if persistent is not None:
            ts, data = persistent
            if now - ts < cls._CACHE_TTL:
                # Fresh — return immediately
                return data
            # STALE — serve immediately, refresh in background
            api_url = current_app.config['PRAYER_TIMES_API_URL']
            cls._refresh_in_background(
                cache_key, latitude, longitude, method, date_str, api_url
            )
            return data

        # 4. No cache at all — fetch with short timeout
        api_url = current_app.config['PRAYER_TIMES_API_URL']
        result = cls._fetch_from_api(
            latitude, longitude, method, date_str, api_url,
            timeout=cls._API_TIMEOUT
        )
        if result is not None:
            cls._cache[cache_key] = (now, result)
            cls._save_to_persistent(cache_key, now, result)
        return result

    @classmethod
    def get_todays_prayer_times(cls, user):
        """Get today's prayer times for a user."""
        return cls.get_prayer_times(
            latitude=user.latitude,
            longitude=user.longitude,
            method=user.calculation_method
        )

    @classmethod
    def get_next_prayer(cls, prayer_times):
        """
        Determine the next upcoming prayer.

        Args:
            prayer_times (dict): Prayer times dictionary

        Returns:
            tuple: (prayer_name, time_str) or (None, None)
        """
        if not prayer_times:
            return None, None

        now = datetime.now().time()
        upcoming = []

        for name in cls.PRAYER_NAMES:
            time_str = prayer_times.get(name)
            if not time_str:
                continue
            try:
                prayer_time = datetime.strptime(time_str, '%H:%M').time()
                if prayer_time > now:
                    upcoming.append((name, time_str))
            except ValueError:
                continue

        if upcoming:
            upcoming.sort(key=lambda x: x[1])
            return upcoming[0]

        # All prayers passed, next is Fajr tomorrow
        return 'Fajr', prayer_times.get('Fajr')

    @classmethod
    def format_time(cls, time_str):
        """Convert 24-hour time string to 12-hour format."""
        try:
            return datetime.strptime(time_str, '%H:%M').strftime('%I:%M %p')
        except (ValueError, TypeError):
            return time_str