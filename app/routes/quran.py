from datetime import datetime
import requests
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, Response
from flask_login import login_required, current_user
from app import db
from app.models.quran import QuranReading, Bookmark
from app.services.quran_service import QuranService

quran_bp = Blueprint('quran', __name__)


@quran_bp.route('/quran')
@login_required
def index():
    """Quran main page with surah/para selection."""
    view = request.args.get('view', 'surah')
    query = request.args.get('q', '').lower().strip()
    surahs = []
    paras = []

    if view == 'surah':
        surah_list = QuranService.get_surah_list()
        if query:
            surahs = [s for s in surah_list if query in s['englishName'].lower() or query in s.get('name', '') or query in str(s.get('number', ''))]
        else:
            surahs = surah_list
    elif view == 'para':
        para_list = QuranService.get_para_list()
        if query:
            paras = [p for p in para_list if query in str(p['number'])]
        else:
            paras = para_list

    # Get user's recent readings (single query — the first record IS the last read)
    recent_readings = QuranReading.query.filter_by(user_id=current_user.id).order_by(
        QuranReading.read_at.desc()
    ).limit(5).all()

    # Last read is simply the most recent of the same query — no duplicate DB call
    last_read_ayah = recent_readings[0] if recent_readings else None

    # Get user's bookmarks
    bookmarks = Bookmark.query.filter_by(user_id=current_user.id).all()

    return render_template(
        'quran/index.html',
        last_read_ayah=last_read_ayah,
        view=view,
        surahs=surahs,
        paras=paras,
        bookmarks=bookmarks,
        recent_readings=recent_readings
    )


@quran_bp.route('/quran/para/<int:para_number>')
@login_required
def para(para_number):
    """View Quran by para (juz)."""
    if not 1 <= para_number <= 30:
        flash('Invalid para number. Must be between 1 and 30.', 'danger')
        return redirect(url_for('quran.index'))

    # Get selected translation (default Urdu — Jalandhry)
    translation_identifier = request.args.get('translation', 'ur.jalandhry')

    # Fetch Arabic + translation together (concurrently on first load, cached after).
    para_data = QuranService.get_para_with_translation(para_number, translation_identifier)
    # Add validation for the API response structure
    if not para_data or not isinstance(para_data, dict):
        flash('Unable to load para data or invalid format. Please try again.', 'danger')
        return redirect(url_for('quran.index'))

    # The API response for a Juz contains a flat list of all ayahs.
    # The old code incorrectly iterated over `para_data['surahs']` which is a dictionary of surah metadata, not a list of surah objects with ayahs.
    ayahs_from_api = para_data.get('ayahs', [])
    ayahs = []

    if not isinstance(ayahs_from_api, list):
        flash('Invalid para data structure from API.', 'danger')
        return redirect(url_for('quran.index'))

    for ayah in ayahs_from_api:
        # Gracefully handle potentially malformed ayah objects from the API
        if not isinstance(ayah, dict):
            continue

        surah_info = ayah.get('surah')
        if not isinstance(surah_info, dict):
            continue

        ayahs.append({
            'surah_number': surah_info.get('number'),
            'surah_name': surah_info.get('englishName'),
            'surah_arabic_name': surah_info.get('name'),
            'ayah_number': ayah.get('numberInSurah'),
            'text': ayah.get('text'),
            'page': ayah.get('page')
        })

    # Get user's bookmarks for this para (single query — previously executed TWICE)
    para_bookmarks = Bookmark.query.filter_by(
        user_id=current_user.id,
        para_number=para_number
    ).all()

    # Get user's last read position for this para
    last_read_ayah = QuranReading.query.filter_by(user_id=current_user.id, para_number=para_number).order_by(QuranReading.read_at.desc()).first()

    bookmarks = para_bookmarks  # Same data — reuse, avoids a duplicate query
    reciters = QuranService.get_reciters()
    translations = QuranService.get_translations()

    # Get para name from the service
    para_name = None
    para_arabic_name = None
    for p in QuranService.get_para_list():
        if p['number'] == para_number:
            para_name = p.get('name')
            para_arabic_name = p.get('arabic')
            break

    # Set of (surah_number, ayah_number) tuples for highlighting bookmark buttons.
    # A Para contains ayahs from many surahs, so we must track the exact
    # surah+ayah pair — same behavior as the Surah reader (which tracks
    # individual ayah numbers within its single surah).
    bookmarked_ayahs = set()
    for bookmark in para_bookmarks:
        bookmarked_ayahs.add((bookmark.surah_number, bookmark.ayah_number))

    # Optional target surah+ayah for deep-links / "Continue Reading"
    # (e.g. ?surah=2&ayah=254). The reader scrolls to this ayah on load.
    # Pure enhancement — no data change.
    target_surah = request.args.get('surah', type=int)
    target_ayah = request.args.get('ayah', type=int)

    # Create a translation map for the template
    translation_map = {}
    if para_data:
        translation_map = para_data.get('translation_map', {})

    return render_template(
        'quran/para.html',
        target_surah=target_surah,
        target_ayah=target_ayah,
        para_number=para_number,
        para_name=para_name,
        para_arabic_name=para_arabic_name,
        ayahs=ayahs,
        bookmarks=bookmarks,
        reciters=reciters,
        translations=translations,
        translation_identifier=translation_identifier,
        translation_map=translation_map,
        last_read_ayah=last_read_ayah,
        para_bookmarks=para_bookmarks, # Pass bookmarks specific to this para
        bookmarked_ayahs=bookmarked_ayahs
    )


@quran_bp.route('/quran/surah/<int:surah_number>')
@login_required
def surah(surah_number):
    """View a specific surah."""
    if not 1 <= surah_number <= 114:
        flash('Invalid surah number. Must be between 1 and 114.', 'danger')
        return redirect(url_for('quran.index'))

    # Get selected translation (default Urdu — Jalandhry)
    translation_identifier = request.args.get('translation', 'ur.jalandhry')

    # Fetch Arabic + translation together (concurrently on first load, cached after).
    surah_with_translation = QuranService.get_surah_with_translation(surah_number, translation_identifier)
    if not surah_with_translation:
        flash('Unable to load surah data. Please try again.', 'danger')
        return redirect(url_for('quran.index'))

    # The `surah_with_translation` result is a dict of the Arabic surah data
    # with ayahs plus the translation. Reuse it for the full surah to avoid
    # a second external API call for the same Arabic text.
    surah_full_data = surah_with_translation

    # Build the surah metadata dict from the same response (surah/{n}/edition
    # includes the surah metadata fields used by the template header).
    surah_data = {
        'number': surah_with_translation.get('number'),
        'name': surah_with_translation.get('name'),
        'english_name': surah_with_translation.get('englishName'),
        'english_name_translation': surah_with_translation.get('englishNameTranslation'),
        'revelation_type': surah_with_translation.get('revelationType'),
        'number_of_ayahs': surah_with_translation.get('numberOfAyahs'),
        'ayahs': surah_with_translation.get('ayahs', [])
    }

    # Optional target ayah for deep-links / "Continue Reading" (e.g. ?ayah=254).
    # The reader scrolls to this ayah on load. Pure enhancement — no data change.
    target_ayah = request.args.get('ayah', type=int)

    # Get user's bookmarks for this surah (all bookmarks for the surah)
    surah_bookmarks = Bookmark.query.filter_by(
        user_id=current_user.id,
        surah_number=surah_number
    ).all()

    # Get user's last read position for this surah
    last_read_ayah = QuranReading.query.filter_by(user_id=current_user.id, surah_number=surah_number).order_by(QuranReading.read_at.desc()).first()

    reciters = QuranService.get_reciters()
    translations = QuranService.get_translations()

    # Set of bookmarked ayah numbers for highlighting bookmark buttons
    bookmarked_ayahs = set()
    for bookmark in surah_bookmarks:
        bookmarked_ayahs.add(bookmark.ayah_number)

    # Create a translation map for the template
    translation_map = {}
    if surah_with_translation and surah_with_translation.get('translation'):
        translation_ayahs = surah_with_translation['translation'].get('ayahs', [])
        if isinstance(translation_ayahs, list):
            for t_ayah in translation_ayahs:
                if isinstance(t_ayah, dict):
                    ayah_num = t_ayah.get('numberInSurah')
                    if ayah_num is not None:
                        translation_map[str(ayah_num)] = t_ayah.get('text')

    return render_template(
        'quran/reader.html',
        surah=surah_full_data, # Pass the full surah data with ayahs
        surah_meta=surah_data, # Keep meta data for header if needed
        bookmarks=surah_bookmarks, # Pass bookmarks specific to this surah
        reciters=reciters,
        translations=translations,
        translation_identifier=translation_identifier,
        translation_map=translation_map,
        last_read_ayah=last_read_ayah,
        bookmarked_ayahs=bookmarked_ayahs,
        target_ayah=target_ayah
    )


@quran_bp.route('/quran/ayah/<int:surah_number>/<int:ayah_number>')
@login_required
def ayah_detail(surah_number, ayah_number):
    """Get a specific ayah with Arabic text and translation."""
    translation_identifier = request.args.get('translation', 'ur.jalandhry')
    ayah_data = QuranService.get_ayah_with_translation(surah_number, ayah_number, translation_identifier)

    if not ayah_data:
        return jsonify({'success': False, 'error': 'Ayah not found'}), 404

    surah_info = ayah_data.get('surah', {})
    return jsonify({
        'success': True,
        'surah_number': surah_number,
        'surah_name': surah_info.get('englishName') if isinstance(surah_info, dict) else None,
        'ayah_number': ayah_number,
        'arabic': ayah_data.get('text'),
        'translation': ayah_data.get('translation'),
        'translation_identifier': translation_identifier,
        'page': ayah_data.get('page'),
        'juz': ayah_data.get('juz')
    })


@quran_bp.route('/quran/audio/proxy/<path:audio_url>')
@login_required
def audio_proxy(audio_url):
    """Proxy audio files from the CDN to avoid CORS issues.

    The islamic.network CDN does not send CORS headers, so the browser
    blocks audio loaded directly via ``new Audio(cdn_url)``.  This route
    fetches the audio on the server side and streams it back same-origin,
    and also works around range requests which some browsers require for
    audio seek support.
    """
    # Reconstruct the full CDN URL from the path-encoded parameter
    # The path comes from url_for-style encoding, e.g. https:/cdn.islamic.network/...
    full_url = f"https://{audio_url}" if not audio_url.startswith('http') else audio_url

    try:
        # Forward the Range header if the client is seeking
        headers = {}
        range_header = request.headers.get('Range')
        if range_header:
            headers['Range'] = range_header

        resp = requests.get(full_url, headers=headers, stream=True, timeout=30)
        resp.raise_for_status()

        # The upstream CDN supports Range requests (verified: it returns
        # 206 + Content-Range). Browsers need Content-Length, Content-Range,
        # and Accept-Ranges on the proxied response to seek/stream MP3 audio
        # reliably. Only strip hop-by-hop headers that don't apply after we
        # re-serve the stream (e.g. Connection, Transfer-Encoding, and
        # Content-Encoding since we are not re-encoding the bytes).
        excluded_headers = {
            'connection', 'transfer-encoding', 'keep-alive',
            'proxy-authenticate', 'proxy-authorization', 'te', 'trailer',
            'upgrade', 'content-encoding'
        }
        response_headers = {
            k: v for k, v in resp.headers.items()
            if k.lower() not in excluded_headers
        }

        # Explicitly advertise range support for browsers even if a
        # particular upstream response omitted it (e.g. cached plain 200).
        response_headers.setdefault('Accept-Ranges', 'bytes')

        # Include CORS headers so the audio element can work
        response_headers['Access-Control-Allow-Origin'] = '*'

        # Quran audio is immutable — cache aggressively in the browser so the
        # next ayah's MP3 is served from the HTTP cache instead of re-fetching
        # through this proxy (and the CDN) on every playback.
        # Only cache full (200) responses, NOT partial (206) range responses,
        # so a seek never caches a truncated file as if it were the whole file.
        if resp.status_code == 200:
            response_headers['Cache-Control'] = 'public, max-age=31536000, immutable'
        else:
            response_headers['Cache-Control'] = 'no-store'

        return Response(
            resp.iter_content(chunk_size=8192),
            status=resp.status_code,
            content_type=resp.headers.get('Content-Type', 'audio/mpeg'),
            headers=response_headers,
            direct_passthrough=True
        )
    except requests.RequestException as e:
        return jsonify({'success': False, 'error': str(e)}), 502


@quran_bp.route('/quran/audio/surah/<int:surah_number>/all')
@login_required
def surah_audio_all(surah_number):
    """Get audio URLs for ALL ayahs of a surah in ONE batch request.

    Uses the existing QuranService.get_surah_audio() (one external API
    call) to eliminate the per-ayah 4-15 second /quran/audio/ayah/...
    requests that previously happened for every consecutive transition.
    """
    if not 1 <= surah_number <= 114:
        return jsonify({'success': False, 'error': 'Invalid surah number'}), 400

    edition = request.args.get('edition', 'ar.alafasy')
    audio_urls = QuranService.get_surah_audio(surah_number, edition=edition)
    if not audio_urls:
        return jsonify({'success': False, 'error': 'Audio not available'}), 404

    # Proxy each CDN URL through /quran/audio/proxy/ to avoid CORS issues.
    # The result is a dict: { ayah_number: proxied_url }.
    proxied = {}
    for idx, audio_url in enumerate(audio_urls, start=1):
        if audio_url:
            proxied[idx] = url_for(
                'quran.audio_proxy',
                audio_url=audio_url.replace('https://', ''),
                _external=True
            )

    return jsonify({'success': True, 'audio_urls': proxied})


@quran_bp.route('/quran/audio/surah/<int:surah_number>')
@login_required
def surah_audio(surah_number):
    """Get audio URL for the first ayah of a surah to start playback."""
    edition = request.args.get('edition', 'ar.alafasy')
    audio_url = QuranService.get_ayah_audio(surah_number, 1, edition=edition)
    if not audio_url:
        return jsonify({'success': False, 'error': 'Audio not available'}), 404
    # Return a proxied URL so the browser can play it without CORS issues
    proxied_url = url_for('quran.audio_proxy', audio_url=audio_url.replace('https://', ''), _external=True)
    return jsonify({'success': True, 'audio_url': proxied_url})


@quran_bp.route('/quran/audio/ayah/<int:surah_number>/<int:ayah_number>')
@login_required
def ayah_audio(surah_number, ayah_number):
    """Get audio URL for a specific ayah."""
    edition = request.args.get('edition', 'ar.alafasy')
    audio_url = QuranService.get_ayah_audio(surah_number, ayah_number, edition=edition)
    if not audio_url:
        return jsonify({'success': False, 'error': 'Audio not available'}), 404
    # Return a proxied URL so the browser can play it without CORS issues
    proxied_url = url_for('quran.audio_proxy', audio_url=audio_url.replace('https://', ''), _external=True)
    return jsonify({'success': True, 'audio_url': proxied_url})


@quran_bp.route('/quran/track-reading', methods=['POST'])
@login_required
def track_reading():
    """Track a Quran reading position."""
    data = request.get_json()
    surah_number = data.get('surah_number')
    ayah_number = data.get('ayah_number')
    para_number = data.get('para_number') # Expect para_number from frontend
    page_number = data.get('page_number')

    if not surah_number or not ayah_number:
        return jsonify({'success': False, 'error': 'Surah and ayah numbers are required'}), 400

    # Check if this reading position already exists
    reading = QuranReading.query.filter_by(
        user_id=current_user.id,
        surah_number=surah_number,
        ayah_number=ayah_number
    ).first()

    if reading: # Update existing reading
        reading.para_number = para_number
        reading.page_number = page_number
        reading.read_at = datetime.utcnow()
    else:
        reading = QuranReading(
            user_id=current_user.id,
            surah_number=surah_number,
            ayah_number=ayah_number,
            para_number=para_number,
            page_number=page_number,
            read_at=datetime.utcnow()
        )
        db.session.add(reading)

    try:
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@quran_bp.route('/quran/bookmark', methods=['POST'])
@login_required
def add_bookmark():
    """Add a bookmark for a reading position."""
    data = request.get_json()
    surah_number = data.get('surah_number')
    ayah_number = data.get('ayah_number')
    para_number = data.get('para_number') # Expect para_number from frontend
    page_number = data.get('page_number')
    label = data.get('label')

    if not surah_number or not ayah_number:
        return jsonify({'success': False, 'error': 'Surah and ayah numbers are required'}), 400

    # Check if bookmark already exists
    bookmark = Bookmark.query.filter_by(
        user_id=current_user.id,
        surah_number=surah_number,
        ayah_number=ayah_number
    ).first()

    if bookmark: # Update existing bookmark (e.g., label)
        bookmark.label = label
        bookmark.para_number = para_number
        bookmark.page_number = page_number
        bookmark.created_at = datetime.utcnow() # Update timestamp if re-bookmarked
    else:
        bookmark = Bookmark(
            user_id=current_user.id,
            surah_number=surah_number,
            ayah_number=ayah_number,
            para_number=para_number,
            page_number=page_number,
            label=label
        )
        db.session.add(bookmark)

    try:
        db.session.commit()
        return jsonify({'success': True, 'bookmark_id': bookmark.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@quran_bp.route('/quran/bookmark/<int:bookmark_id>/delete', methods=['POST'])
@login_required
def delete_bookmark(bookmark_id):
    """Delete a bookmark."""
    bookmark = Bookmark.query.filter_by(
        id=bookmark_id,
        user_id=current_user.id
    ).first()

    if not bookmark:
        return jsonify({'success': False, 'error': 'Bookmark not found'}), 404

    try:
        db.session.delete(bookmark)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@quran_bp.route('/quran/search')
@login_required
def search():
    """Search the Quran."""
    query = request.args.get('q', '').strip()
    results = None
    if query:
        results = QuranService.search_quran(query)

    # This route will render the quran index page with search results
    return render_template(
        'quran/index.html',
        search_query=query,
        search_results=results
    )


