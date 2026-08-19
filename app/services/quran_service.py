import json
import os
import time
from concurrent.futures import ThreadPoolExecutor

import requests
from flask import current_app


class QuranService:
    """Service for fetching Quran data from the AlQuran Cloud API.

    Data sources:
    - Arabic text: quran-uthmani (Trusted Uthmani script)
    - Translations: Sahih International (English), Jalandhry (Urdu), Zekr (Telugu)
    - Audio: alafasy, abdulbasitmurattal, husary, and more from the API
    """

    # In-memory cache for immutable Quran API responses.
    # The Quran text, translations, and audio metadata are static and never change,
    # so caching them is completely safe. Key: API endpoint, Value: (timestamp, data)
    _cache = {}
    _CACHE_TTL = 31536000  # 1 year (immutable data never changes)

    # Persistent file cache directory (relative to this module file).
    # Populated once at class definition time; survives process restarts.
    _cache_dir = os.path.join(os.path.dirname(__file__), '.quran_cache')
    # Ensure the cache directory exists when the class is defined.
    os.makedirs(_cache_dir, exist_ok=True)

    # Cache lookup order: memory cache → persistent file cache → external API
    @classmethod
    def _load_from_persistent(cls, endpoint):
        """Load data from the persistent file cache if available and not expired.

        Returns (timestamp, data) tuple or None if not found/expired/corrupt.
        """
        try:
            safe_endpoint = endpoint.replace('/', '_').replace(':', '_'); cache_file = os.path.join(cls._cache_dir, f'{safe_endpoint}.json')
            if not os.path.exists(cache_file):
                return None
            with open(cache_file, 'r', encoding='utf-8') as f:
                entry = json.load(f)
            # entry should be [timestamp, data]
            if not isinstance(entry, list) or len(entry) < 2:
                return None
            timestamp, data = entry[0], entry[1]
            now = time.time()
            if now - timestamp < cls._CACHE_TTL:
                # Populate in-memory cache so future hits are fast
                cls._cache[endpoint] = (timestamp, data)
                return timestamp, data
            # Expired — remove stale file
            try:
                os.remove(cache_file)
            except OSError:
                pass
            return None
        except (json.JSONDecodeError, OSError, KeyError, TypeError):
            # Corrupt cache file — remove and fall through to API
            try:
                os.remove(os.path.join(cls._cache_dir, f'{endpoint}.json'))
            except OSError:
                pass
            return None

    @classmethod
    def _save_to_persistent(cls, endpoint, timestamp, data):
        """Save data to the persistent file cache using atomic write.

        Writes to a temp file first, then os.replace() so a partial write
        never leaves a corrupt file in place.
        """
        try:
            safe_endpoint = endpoint.replace('/', '_').replace(':', '_'); cache_file = os.path.join(cls._cache_dir, f'{safe_endpoint}.json')
            tmp_file = cache_file + '.tmp'
            with open(tmp_file, 'w', encoding='utf-8') as f:
                json.dump([timestamp, data], f, ensure_ascii=False, indent=2)
            os.replace(tmp_file, cache_file)
        except (OSError, json.JSONEncodeError):
            # Best-effort; non-fatal if we can't persist
            pass

    # Definition of available translations
    TRANSLATIONS = [
        {"identifier": "en.sahih", "name": "English (Sahih International)"},
        {"identifier": "ur.jalandhry", "name": "Urdu (Jalandhry)"},
        {"identifier": "te.zekr", "name": "Telugu (Zekr)"},
    ]

    # Default Arabic edition
    ARABIC_EDITION = "quran-uthmani"

    # Popular reciters available via the API
    DEFAULT_RECITERS = [
        {"identifier": "ar.alafasy", "name": "Mishary Rashid Alafasy"},
        {"identifier": "ar.abdulbasitmurattal", "name": "Abdul Basit Abdul Samad (Murattal)"},
        {"identifier": "ar.husary", "name": "Mahmoud Khalil Al-Husary"},
        {"identifier": "ar.ahmedajamy", "name": "Ahmed Al-Ajamy"},
        {"identifier": "ar.hudhaify", "name": "Ali Al-Hudhaify"},
        {"identifier": "ar.saoodshuraym", "name": "Saud Al-Shuraim"},
        {"identifier": "ar.sudais", "name": "Abdul Rahman Al-Sudais"},
    ]

    PARA_NAMES = [
        {"number": 1, "name": "Alif Lam Meem", "arabic": "الم"},
        {"number": 2, "name": "Sayaqul", "arabic": "سَيَقُولُ"},
        {"number": 3, "name": "Tilka Rusul", "arabic": "تِلْكَ الرُّسُلُ"},
        {"number": 4, "name": "Lan Tanalu", "arabic": "لَنْ تَنَالُوا"},
        {"number": 5, "name": "Wal Muhsanat", "arabic": "وَالْمُحْصَنَاتُ"},
        {"number": 6, "name": "La Yuhibbullah", "arabic": "لَا يُحِبُّ اللَّهُ"},
        {"number": 7, "name": "Wa Iza Samiu", "arabic": "وَإِذَا سَمِعُوا"},
        {"number": 8, "name": "Wa Lau Annana", "arabic": "وَلَوْ أَنَّنَا"},
        {"number": 9, "name": "Qalal Mala'", "arabic": "قَالَ الْمَلَأُ"},
        {"number": 10, "name": "Wa'lamu", "arabic": "وَاعْلَمُوا"},
        {"number": 11, "name": "Y'atazirun", "arabic": "يَعْتَذِرُونَ"},
        {"number": 12, "name": "Wa Ma Min Dabbah", "arabic": "وَمَا مِنْ دَابَّةٍ"},
        {"number": 13, "name": "Wa Ma Ubarri'u", "arabic": "وَمَا أُبَرِّئُ"},
        {"number": 14, "name": "Rubama", "arabic": "رُبَمَا"},
        {"number": 15, "name": "Subhanallazi", "arabic": "سُبْحَانَ الَّذِي"},
        {"number": 16, "name": "Qala Alam", "arabic": "قَالَ أَلَمْ"},
        {"number": 17, "name": "Iqtaraba", "arabic": "اقْتَرَبَ"},
        {"number": 18, "name": "Qad Aflaha", "arabic": "قَدْ أَفْلَحَ"},
        {"number": 19, "name": "Wa Qalallazina", "arabic": "وَقَالَ الَّذِينَ"},
        {"number": 20, "name": "Amman Khalaq", "arabic": "أَمَّنْ خَلَقَ"},
        {"number": 21, "name": "Utlu Ma Uhiya", "arabic": "اتْلُ مَا أُوحِيَ"},
        {"number": 22, "name": "Wa Man Yaqnut", "arabic": "وَمَنْ يَقْنُتْ"},
        {"number": 23, "name": "Wa Mali", "arabic": "وَمَا لِيَ"},
        {"number": 24, "name": "Faman Azlam", "arabic": "فَمَنْ أَظْلَمُ"},
        {"number": 25, "name": "Ilayhi Yuraddu", "arabic": "إِلَيْهِ يُرَدُّ"},
        {"number": 26, "name": "Ha Meem", "arabic": "حم"},
        {"number": 27, "name": "Qala Fama Khatbukum", "arabic": "قَالَ فَمَا خَطْبُكُمْ"},
        {"number": 28, "name": "Qad Sami' Allah", "arabic": "قَدْ سَمِعَ اللَّهُ"},
        {"number": 29, "name": "Tabarakallazi", "arabic": "تَبَارَكَ الَّذِي"},
        {"number": 30, "name": "Amma", "arabic": "عَمَّ"},
    ]

    @classmethod
    def _get(cls, endpoint, base_url=None):
        """Make a GET request to the Quran API with an in-memory cache.

        The Quran text and translations are immutable, so caching responses
        is safe and eliminates repeated slow external API calls when the same
        Para/Surah/ayah is requested again.

        ``base_url`` is optional. When using ``_get_many``, the caller
        captures ``current_app.config['QURAN_API_URL']`` on the calling
        thread (which holds the application context) and passes it in
        explicitly so worker threads never touch ``current_app``.
        """
        now = time.time()
        cached = cls._cache.get(endpoint)
        if cached and now - cached[0] < cls._CACHE_TTL:
            return cached[1]

        # Persistent cache: immutable Quran data survives Flask restarts,
        # so the slow external API request is only made once per endpoint.
        persistent = cls._load_from_persistent(endpoint)
        if persistent is not None:
            ts, data = persistent
            cls._cache[endpoint] = (ts, data)
            return data

        if base_url is None:
            base_url = current_app.config['QURAN_API_URL']
        url = f"{base_url}/{endpoint}"
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            data = response.json()
            if data.get('code') == 200:
                cached_data = data.get('data')
                cls._cache[endpoint] = (now, cached_data)
                cls._save_to_persistent(endpoint, now, cached_data)
                return cached_data
        except (requests.RequestException, ValueError):
            pass
        return None

    @classmethod
    def _get_many(cls, endpoints):
        """Fetch multiple API endpoints concurrently.

        Used to fetch Arabic text and a translation in parallel on the first
        (uncached) request, reducing the first-load latency roughly in half.
        """
        # Capture the API base URL on the calling thread (which has the Flask
        # application context) so the worker threads never access current_app.
        base_url = current_app.config['QURAN_API_URL']
        with ThreadPoolExecutor(max_workers=len(endpoints)) as executor:
            results = list(executor.map(lambda ep: cls._get(ep, base_url), endpoints))
        return results

    @classmethod
    def get_surah_list(cls):
        """Get the list of all 114 surahs."""
        data = cls._get('surah')
        if not data:
            return []
        if isinstance(data, list):
            return data
        return data.get('surahs', [])

    @classmethod
    def get_para_list(cls):
        """Get the list of all 30 paras with names."""
        return cls.PARA_NAMES

    @classmethod
    def get_reciters(cls):
        """Get the list of available reciters.

        The AlQuran Cloud API provides audio through editions like:
        ar.alafasy, ar.abdulbasitmurattal, ar.husary, etc.
        These are the trusted reciters supported by the API.
        """
        return cls.DEFAULT_RECITERS

    @classmethod
    def get_translations(cls):
        """Get the list of available translations."""
        return cls.TRANSLATIONS

    @classmethod
    def get_surah(cls, surah_number):
        """Get a specific surah with all its ayahs (Arabic text)."""
        return cls._get(f'surah/{surah_number}/{cls.ARABIC_EDITION}')

    @classmethod
    def get_surah_with_translation(cls, surah_number, translation_identifier='en.sahih'):
        """Get a surah with both Arabic text and a translation."""
        arabic_endpoint = f'surah/{surah_number}/{cls.ARABIC_EDITION}'
        translation_endpoint = f'surah/{surah_number}/{translation_identifier}'

        # Fetch Arabic and translation concurrently on first load.
        # On subsequent loads the cache returns both instantly.
        data, translation_data = cls._get_many([arabic_endpoint, translation_endpoint])

        if not data:
            return None

        result = dict(data)
        result['translation'] = None
        result['translation_identifier'] = translation_identifier

        if translation_data and isinstance(translation_data, dict):
            result['translation'] = translation_data

        return result

    @classmethod
    def get_ayah(cls, surah_number, ayah_number):
        """Get a specific ayah in Arabic."""
        return cls._get(f'ayah/{surah_number}:{ayah_number}/{cls.ARABIC_EDITION}')

    @classmethod
    def get_ayah_with_translation(cls, surah_number, ayah_number, translation_identifier='en.sahih'):
        """Get a specific ayah in Arabic and translation."""
        ayah_data, translation_data = cls._get_many([
            f'ayah/{surah_number}:{ayah_number}/{cls.ARABIC_EDITION}',
            f'ayah/{surah_number}:{ayah_number}/{translation_identifier}'
        ])

        if not ayah_data:
            return None

        result = dict(ayah_data)
        result['translation'] = translation_data.get('text') if translation_data else None
        result['translation_identifier'] = translation_identifier

        return result

    @classmethod
    def get_para(cls, para_number):
        """Get all surahs/ayahs in a specific para (juz)."""
        return cls._get(f'juz/{para_number}/{cls.ARABIC_EDITION}')

    @classmethod
    def get_para_with_translation(cls, para_number, translation_identifier='en.sahih'):
        """Get a para with both Arabic text and translations."""
        arabic_endpoint = f'juz/{para_number}/{cls.ARABIC_EDITION}'
        translation_endpoint = f'juz/{para_number}/{translation_identifier}'

        # Fetch Arabic and translation concurrently on first load.
        # On subsequent loads the cache returns both instantly.
        para_data, translation_data = cls._get_many([arabic_endpoint, translation_endpoint])

        if not para_data:
            return None

        result = dict(para_data)
        result['translation_identifier'] = translation_identifier

        # Build a map of translation text by surah:ayah
        translation_map = {}
        if translation_data and isinstance(translation_data, dict):
            ayahs = translation_data.get('ayahs', [])
            if isinstance(ayahs, list):
                for t_ayah in ayahs:
                    if isinstance(t_ayah, dict):
                        surah_num = None
                        surah_info = t_ayah.get('surah')
                        if isinstance(surah_info, dict):
                            surah_num = surah_info.get('number')
                        ayah_num = t_ayah.get('numberInSurah')
                        if surah_num is not None and ayah_num is not None:
                            translation_map[f'{surah_num}:{ayah_num}'] = t_ayah.get('text')

        result['translation_map'] = translation_map

        return result

    @classmethod
    def get_edition(cls, edition='quran-uthmani'):
        """Get Quran in a specific edition/translation."""
        return cls._get(f'edition/{edition}')

    @classmethod
    def search_quran(cls, query):
        """Search the Quran for a specific text."""
        return cls._get(f'search/{query}')

    @classmethod
    def get_ayah_audio(cls, surah_number, ayah_number, edition='ar.alafasy'):
        """Get audio data for a specific ayah.

        Returns the audio URL from the AlQuran Cloud API.
        """
        data = cls._get(f'ayah/{surah_number}:{ayah_number}/{edition}')
        if data:
            return data.get('audio')
        return None

    @classmethod
    def get_surah_audio(cls, surah_number, edition='ar.alafasy'):
        """Get audio URLs for all ayahs in a surah."""
        data = cls._get(f'surah/{surah_number}/{edition}')
        if not data or not isinstance(data, dict):
            return None

        ayahs = data.get('ayahs', [])
        audio_urls = []
        for ayah in ayahs:
            audio_urls.append(ayah.get('audio'))

        return audio_urls

    @classmethod
    def get_surah_meta(cls, surah_number):
        """Get metadata for a surah."""
        data = cls._get(f'surah/{surah_number}')
        if not data:
            return None
        return {
            'number': data.get('number'),
            'name': data.get('name'),
            'english_name': data.get('englishName'),
            'english_name_translation': data.get('englishNameTranslation'),
            'revelation_type': data.get('revelationType'),
            'number_of_ayahs': data.get('numberOfAyahs'),
            'ayahs': data.get('ayahs', [])
        }
