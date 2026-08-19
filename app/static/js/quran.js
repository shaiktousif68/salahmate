/**
 * Quran reader functionality
 *
 * Audio player state uses ``var`` instead of ``let`` so that the script
 * can be re-executed safely by the SPA navigation code (``navigation.js``
 * creates a new ``<script>`` element and inserts it into the DOM, which
 * runs it in the global scope).  ``let`` would throw a ``SyntaxError`` on
 * re-declaration.
 *
 * Audio URLs are proxied through the Flask backend (``/quran/audio/proxy/``)
 * because the ``cdn.islamic.network`` CDN does not send CORS headers,
 * and the browser blocks ``new Audio(crossOriginUrl)`` for seek/playback.
 */
// Audio player state
var audioQueue = window.audioQueue || [];
var currentAudioIndex = window.currentAudioIndex || 0;
var currentAudio = window.currentAudio || null;
// Preloaded audio for the NEXT ayah (played instantly when current ends).
// nextAudioIndex is the queue index the preloaded audio corresponds to.
var nextAudio = window.nextAudio || null;
var nextAudioIndex = window.nextAudioIndex !== undefined ? window.nextAudioIndex : -1;
// Tracks whether the preloaded nextAudio has finished buffering enough to
// play immediately (readyState >= 3, i.e. HAVE_FUTURE_DATA). Set true when
// the canplay event fires; reset false when a new preload starts.
var nextAudioReady = window.nextAudioReady || false;
// Increments on every preload request; stale in-flight fetches are discarded.
var preloadToken = window.preloadToken || 0;
// Key of the ayah currently being preloaded, or null when idle. Prevents
// duplicate /quran/audio/ayah/... requests for the same next ayah when
// preloadNextAyah is called repeatedly (e.g. SPA re-execution or play events).
var preloadingKey = window.preloadingKey || null;
// Cache of resolved proxied audio URLs, keyed by "surah:ayah:edition".
// Avoids repeated Flask + external API round-trips for the same ayah.
var audioUrlCache = window.audioUrlCache || {};
// Increments every time the user selects a different ayah; guards stale
// in-flight direct-play fetches so they can't override newer clicks.
var playToken = window.playToken || 0;
// Tracks which surah+edition combinations have been batch-loaded into
// audioUrlCache. Key: "surah:edition". Prevents duplicate batch fetches.
var batchLoadedSurahs = window.batchLoadedSurahs || {};

// Guard: if audioQueue is already initialized (e.g. SPA re-execution),
// don't wipe the queue of a potentially playing audio session.
if (!window.__quranAudioInitialized) {
    window.__quranAudioInitialized = true;
    window.audioQueue = audioQueue;
    window.currentAudioIndex = currentAudioIndex;
    window.currentAudio = currentAudio;
    window.nextAudio = nextAudio;
    window.nextAudioIndex = nextAudioIndex;
    window.nextAudioReady = nextAudioReady;
    window.preloadToken = preloadToken;
    window.preloadingKey = preloadingKey;
    window.audioUrlCache = audioUrlCache;
    window.playToken = playToken;
    window.batchLoadedSurahs = batchLoadedSurahs;
} else {
    // Restore state from the window references so the SPA re-execution
    // doesn't reset the audio player mid-playback.
    audioQueue = window.audioQueue;
    currentAudioIndex = window.currentAudioIndex;
    currentAudio = window.currentAudio;
    nextAudio = window.nextAudio;
    nextAudioIndex = window.nextAudioIndex;
    nextAudioReady = window.nextAudioReady || false;
    preloadToken = window.preloadToken;
    preloadingKey = window.preloadingKey || null;
    audioUrlCache = window.audioUrlCache;
    playToken = window.playToken;
    batchLoadedSurahs = window.batchLoadedSurahs || {};
}

function initQuranReader() {
    // Ensure we only attach listeners once per page instance
    const readerPage = document.querySelector('.quran-reader-page');
    if (readerPage && readerPage.dataset.quranInitialized === 'true') {
        return;
    }
    if (readerPage) {
        readerPage.dataset.quranInitialized = 'true';
    }

    // This is a FRESH reader page (direct navigation, or SPA swap to a new
    // Para/Surah — e.g. Para list → Para 1 → back → Para 1 again).
    // Clear any audio/session state persisted on window from the PREVIOUS
    // reader so stale state (old playing audio, old queue, stale preloads,
    // old play token) NEVER leaks into the reopened page. Each Para/Surah
    // open is therefore a clean reader. Continue Reading is unaffected:
    // the deep-link target is read independently in scrollToTargetAyah()
    // AFTER the fresh init below.
    stopAudio();

    const fontSizeControls = document.querySelectorAll('.quran-font-size');
    fontSizeControls.forEach(control => {
        control.addEventListener('click', function() {
            const direction = this.dataset.direction;
            changeFontSize(direction);
        });
    });

    // Initialize reading mode toggle
    const modeToggle = document.getElementById('reading-mode-toggle');
    if (modeToggle) {
        modeToggle.addEventListener('click', toggleReadingMode);
    }

    // Initialize bookmark buttons
    document.querySelectorAll('.bookmark-btn').forEach(button => {
        button.addEventListener('click', function() {
            const surahNumber = this.dataset.surah;
            const ayahNumber = this.dataset.ayah;
            const paraNumber = this.dataset.para;
            const pageNumber = this.dataset.page;
            toggleBookmark(surahNumber, ayahNumber, paraNumber, pageNumber, this);
        });
    });

    // Initialize audio buttons
    document.querySelectorAll('.audio-btn').forEach(button => {
        button.addEventListener('click', function() {
            const surahNumber = this.dataset.surah;
            const ayahNumber = this.dataset.ayah;
            const edition = document.getElementById('reciter-select')?.value || 'ar.alafasy';
            playAyahAudio(surahNumber, ayahNumber, edition);
        });
    });

    // Initialize reciter select
    const reciterSelect = document.getElementById('reciter-select');
    if (reciterSelect) {
        reciterSelect.addEventListener('change', function() {
            stopAudio();
            localStorage.setItem('quranReciter', this.value);
        });

        // Restore saved preference
        const savedReciter = localStorage.getItem('quranReciter');
        if (savedReciter) {
            reciterSelect.value = savedReciter;
        }
    }

    // Initialize translation select
    const translationSelect = document.getElementById('translation-select');
    if (translationSelect) {
        translationSelect.addEventListener('change', function() {
            // Reload page with selected translation
            const url = new URL(window.location.href);
            url.searchParams.set('translation', this.value);
            window.location.href = url.toString();
        });

        // Save preference
        localStorage.setItem('quranTranslation', translationSelect.value);
    }

    // Initialize 3-dot menu buttons
    document.querySelectorAll('.ayah-menu-btn').forEach(button => {
        button.addEventListener('click', function(e) {
            e.stopPropagation();
            const dropdown = this.closest('.ayah-menu-wrap').querySelector('.ayah-dropdown');
            const isOpen = dropdown.classList.contains('open');

            // Close all dropdowns
            document.querySelectorAll('.ayah-dropdown.open').forEach(d => d.classList.remove('open'));

            if (!isOpen) {
                dropdown.classList.add('open');
            }
        });
    });

    // Close dropdowns on outside click — attach ONCE globally (SPA-safe).
    // Without this guard, every SPA navigation re-runs initQuranReader and
    // stacks duplicate document listeners.
    if (!window.__quranDocListenersAttached) {
        window.__quranDocListenersAttached = true;
        document.addEventListener('click', function() {
            document.querySelectorAll('.ayah-dropdown.open').forEach(d => d.classList.remove('open'));
        });
    }

    // Initialize ayah menu items
    document.querySelectorAll('.ayah-menu-item').forEach(item => {
        item.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            const action = this.dataset.action;
            const surahNumber = this.dataset.surah;
            const ayahNumber = this.dataset.ayah;
            const paraNumber = this.dataset.para;
            const pageNumber = this.dataset.page;

            // Close dropdown
            const dropdown = this.closest('.ayah-dropdown');
            if (dropdown) dropdown.classList.remove('open');

            switch (action) {
                case 'translation':
                    showTranslationModal(surahNumber, ayahNumber);
                    break;
                case 'audio':
                    const edition = document.getElementById('reciter-select')?.value || 'ar.alafasy';
                    playAyahAudio(surahNumber, ayahNumber, edition);
                    break;
                case 'bookmark':
                    const btn = this.closest('.ayah-item').querySelector('.bookmark-btn');
                    toggleBookmark(surahNumber, ayahNumber, paraNumber, pageNumber, btn);
                    break;
                case 'share':
                    shareAyah(surahNumber, ayahNumber);
                    break;
                case 'copy':
                    copyAyah(surahNumber, ayahNumber);
                    break;
            }
        });
    });

    // Initialize audio player controls
    initializeAudioPlayer();

    // Track reading position on scroll
    trackReadingPosition();

    // Visual polish (UI only — no audio/caching/preload/API changes)
    initAyahReveal();
    animateReadingProgress();
    initAudioPlayer3DTilt();

    // Deep-link support: scroll to the target ayah (e.g. Continue Reading)
    scrollToTargetAyah();

    // Warm up the first ayah's audio URL so the very first play skips the
    // slow external API round-trip and starts almost instantly.
    warmUpFirstAudio();
}

// Run the initializer. This works for both initial page load (assuming the script is at the end of the body)
// and for the SPA navigation, which re-executes this script.
initQuranReader();
/**
 * Change the Quran font size
 * @param {string} direction - 'increase' or 'decrease'
 */
function changeFontSize(direction) {
    const ayahTexts = document.querySelectorAll('.ayah-text');
    if (!ayahTexts.length) return;

    const currentSize = parseFloat(getComputedStyle(ayahTexts[0]).fontSize);
    const newSize = direction === 'increase'
        ? Math.min(currentSize + 2, 32)
        : Math.max(currentSize - 2, 14);

    ayahTexts.forEach(text => {
        text.style.fontSize = newSize + 'px';
    });

    // Save preference
    localStorage.setItem('quranFontSize', newSize);
}

/**
 * Toggle between dark and light reading mode
 */
function toggleReadingMode() {
    const body = document.body;
    const isLight = body.classList.contains('reading-mode-light');
    const button = document.getElementById('reading-mode-toggle');

    if (isLight) {
        body.classList.remove('reading-mode-light');
        if (button) button.innerHTML = '<i class="fas fa-sun"></i> Light';
    } else {
        body.classList.add('reading-mode-light');
        if (button) button.innerHTML = '<i class="fas fa-moon"></i> Dark';
    }

    localStorage.setItem('quranReadingMode', isLight ? 'dark' : 'light');
}

/**
 * Toggle a bookmark for an ayah
 */
function toggleBookmark(surahNumber, ayahNumber, paraNumber, pageNumber, button) {
    fetch('/quran/bookmark', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            surah_number: surahNumber,
            ayah_number: ayahNumber,
            para_number: paraNumber,
            page_number: pageNumber
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            button.classList.toggle('active');
            const isActive = button.classList.contains('active');
            showToast(isActive ? 'Bookmark added' : 'Bookmark updated', 'success');

            // Visual pop animation — no backend/API change
            button.classList.remove('pop');
            void button.offsetWidth; // restart the animation
            button.classList.add('pop');
            const icon = button.querySelector('.fas');
            if (icon) {
                icon.classList.remove('bookmark-bounce');
                void icon.offsetWidth;
                icon.classList.add('bookmark-bounce');
            }
        } else {
            showToast(data.error || 'Failed to bookmark', 'danger');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showToast('Failed to bookmark. Please try again.', 'danger');
    });
}

/**
 * Show translation modal for an ayah
 */
async function showTranslationModal(surahNumber, ayahNumber) {
    try {
        const response = await fetch(`/quran/ayah/${surahNumber}/${ayahNumber}`);
        const data = await response.json();

        if (data.success) {
            document.getElementById('modal-arabic').textContent = data.arabic;
            document.getElementById('modal-translation').textContent = data.translation || '';
            document.getElementById('modal-ayah-label').textContent =
                `Surah ${data.surah_name || surahNumber} : Ayah ${ayahNumber}`;
            document.getElementById('translation-modal').classList.add('open');
        } else {
            showToast(data.error || 'Unable to load ayah', 'danger');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('Failed to load ayah data.', 'danger');
    }
}

/**
 * Close the translation modal
 */
function closeModal() {
    document.getElementById('translation-modal').classList.remove('open');
}

/**
 * Share an ayah
 */
async function shareAyah(surahNumber, ayahNumber) {
    try {
        const response = await fetch(`/quran/ayah/${surahNumber}/${ayahNumber}`);
        const data = await response.json();

        if (data.success) {
            const text = `${data.arabic}\n\nSurah ${data.surah_name || surahNumber}:${ayahNumber}`;
            if (navigator.share) {
                await navigator.share({ text: text });
            } else {
                await navigator.clipboard.writeText(text);
                showToast('Ayah copied to clipboard', 'success');
            }
        }
    } catch (error) {
        console.error('Share failed:', error);
    }
}

/**
 * Copy an ayah to clipboard
 */
async function copyAyah(surahNumber, ayahNumber) {
    try {
        const response = await fetch(`/quran/ayah/${surahNumber}/${ayahNumber}`);
        const data = await response.json();

        if (data.success && data.arabic) {
            await navigator.clipboard.writeText(data.arabic);
            showToast('Ayah copied to clipboard', 'success');
        } else {
            showToast(data.error || 'Failed to get ayah for copying.', 'danger');
        }
    } catch (error) {
        console.error('Copy failed:', error);
    }
}

/**
 * Stop any playing audio
 */
function stopAudio() {
    // Invalidate any in-flight play/preload fetch so stale responses cannot
    // recreate audio after the user stops playback.
    playToken = (playToken || 0) + 1;
    window.playToken = playToken;

    if (currentAudio) {
        currentAudio.pause();
        currentAudio = null;
    }
    audioQueue = [];
    currentAudioIndex = 0;
    clearPreloadedAudio();

    // Sync state to window so SPA re-execution preserves it
    window.audioQueue = audioQueue;
    window.currentAudioIndex = currentAudioIndex;
    window.currentAudio = currentAudio;

    const player = document.getElementById('audio-player');
    if (player) {
        player.style.display = 'none';
        player.classList.remove('is-playing');
    }

    const icon = document.getElementById('audio-player-icon');
    if (icon) {
        icon.className = 'fas fa-play';
        icon.innerHTML = '';
    }

    // Reset the custom progress bar
    const progressFill = document.getElementById('audio-progress-fill');
    const progressThumb = document.getElementById('audio-progress-thumb');
    if (progressFill) progressFill.style.width = '0%';
    if (progressThumb) progressThumb.style.left = '0%';

    const playPauseBtn = document.getElementById('audio-play-pause');
    if (playPauseBtn) playPauseBtn.innerHTML = '<i class="fas fa-play"></i>';

    document.querySelectorAll('.audio-btn').forEach(btn => {
        btn.innerHTML = '<i class="fas fa-play"></i>';
        btn.classList.remove('loading');
    });

    // Remove the playing highlight from all ayahs (visual only)
    clearActiveAyah();
}

/**
 * Play audio for a specific ayah
 */
function playAyahAudio(surahNumber, ayahNumber, edition) {
    // Stop anything currently playing immediately. The user clicked another
    // ayah, so the old audio must not keep playing (and competing for
    // bandwidth) while the new ayah's URL is fetched.
    if (currentAudio) {
        currentAudio.pause();
        currentAudio = null;
        window.currentAudio = null;
    }

    // Invalidate any stale in-flight play fetch from an earlier click so it
    // cannot replace the audio the user just selected.
    playToken = (playToken || 0) + 1;
    window.playToken = playToken;

    // Update the audio queue
    const audioItems = Array.from(document.querySelectorAll('.ayah-item'));
    const currentIndex = audioItems.findIndex(item =>
        item.dataset.surah == surahNumber && item.dataset.ayah == ayahNumber
    );

    if (currentIndex >= 0) {
        audioQueue = audioItems.map(item => ({
            surah: item.dataset.surah,
            ayah: item.dataset.ayah,
            para: item.dataset.para || 1
        }));
        currentAudioIndex = currentIndex;
    } else {
        audioQueue = [{ surah: surahNumber, ayah: ayahNumber, para: 1 }];
        currentAudioIndex = 0;
    }

    // Sync state to window so SPA re-execution preserves it
    window.audioQueue = audioQueue;
    window.currentAudioIndex = currentAudioIndex;

    // The queue changed (new ayah selected) — discard any stale preload
    clearPreloadedAudio();

    // Kick off a background batch fetch of ALL audio URLs for this surah.
    // This single external API request populates audioUrlCache so every
    // consecutive transition uses an instant cache hit — no per-ayah
    // /quran/audio/ayah/... 4-15s requests.
    loadBatchSurahAudio(surahNumber, edition).catch(() => {});

    playCurrentAyah(edition);
}

/**
 * Discard any preloaded next-ayah audio.
 */
function clearPreloadedAudio() {
    if (nextAudio) {
        nextAudio.pause();
        nextAudio.src = '';
        nextAudio = null;
    }
    nextAudioIndex = -1;
    nextAudioReady = false;
    // Release the preload-in-flight guard so a future preload for the
    // same ayah can start (queue/ayah/reciter changed or playback stopped).
    preloadingKey = null;
    window.preloadingKey = null;
    window.nextAudio = null;
    window.nextAudioIndex = -1;
    window.nextAudioReady = false;
}

/**
 * Fetch audio URLs for ALL ayahs of a surah in ONE batch request.
 *
 * Uses the new /quran/audio/surah/<n>/all endpoint (backed by
 * QuranService.get_surah_audio()) which makes a single external API call,
 * eliminating the per-ayah 4-15 second /quran/audio/ayah/... requests.
 *
 * Populates audioUrlCache with every ayah's proxied URL so playCurrentAyah
 * and preloadNextAyah resolve URLs instantly from cache.
 *
 * @param {number|string} surahNumber  Surah number (1-114)
 * @param {string}         edition   Reciter edition, e.g. 'ar.alafasy'
 */
async function loadBatchSurahAudio(surahNumber, edition) {
    const batchKey = `${surahNumber}:${edition}`;
    // Skip if this surah+edition is already batch-loaded (or in flight).
    if (batchLoadedSurahs[batchKey]) return;

    // Mark as in-flight so concurrent calls for the same surah+edition
    // (e.g. SPA re-execution or two audio-btn clicks) don't duplicate.
    batchLoadedSurahs[batchKey] = 'loading';
    window.batchLoadedSurahs = batchLoadedSurahs;

    try {
        const response = await fetch(`/quran/audio/surah/${surahNumber}/all?edition=${edition}`);
        const data = await response.json();
        if (data.success && data.audio_urls && typeof data.audio_urls === 'object') {
            const urls = data.audio_urls; // { "1": "/quran/audio/proxy/...", "2": ... }
            for (const [ayahNum, audioUrl] of Object.entries(urls)) {
                if (audioUrl) {
                    const cacheKey = `${surahNumber}:${ayahNum}:${edition}`;
                    audioUrlCache[cacheKey] = audioUrl;
                }
            }
            window.audioUrlCache = audioUrlCache;
        }
        // Mark as loaded (even on failure so we don't retry endlessly).
        batchLoadedSurahs[batchKey] = true;
        window.batchLoadedSurahs = batchLoadedSurahs;
    } catch (e) {
        // Non-fatal: per-ayah /quran/audio/ayah/... fallback still works.
        batchLoadedSurahs[batchKey] = true;
        window.batchLoadedSurahs = batchLoadedSurahs;
    }
}

/**
 * Preload the Audio for the ayah AFTER the current one while the current
 * ayah is still playing. When the current ayah ends, the preloaded audio
 * is swapped in immediately — no re-fetch + new Audio() + buffering delay.
 *
 * Only the ayah after the current one is preloaded (never the whole queue).
 * A token guards against stale fetches: if the user changes ayah, reciter,
 * or stops playback while the fetch is in flight, the result is discarded.
 */
async function preloadNextAyah(edition) {
    // No next ayah (last ayah of surah/para) → nothing to preload
    if (currentAudioIndex + 1 >= audioQueue.length) {
        clearPreloadedAudio();
        return;
    }

    const nextIndex = currentAudioIndex + 1;
    const item = audioQueue[nextIndex];
    const cacheKey = `${item.surah}:${item.ayah}:${edition}`;

    // Deduplicate: if this exact next ayah+edition was already created as
    // a preload Audio object, do NOT create it again. Note: having the URL
    // in audioUrlCache is NOT a reason to skip preloading — the cache holds
    // the URL, not the MP3 bytes. We must always create+buffer the Audio
    // object for the next ayah (this is exactly what eliminates the 4-6s
    // transition delay).
    if (preloadingKey === cacheKey) return;
    if (nextAudio && nextAudioIndex === nextIndex) return;

    preloadingKey = cacheKey;
    window.preloadingKey = cacheKey;

    const token = ++preloadToken;
    window.preloadToken = preloadToken;

    try {
        // Use the cached audio URL when available.
        let audioUrl = audioUrlCache[cacheKey];
        if (!audioUrl) {
            // URL cache miss — kick off ONE batch request for the whole
            // surah (single external API call) and retry the preload. On the
            // next call the URL will be available immediately.
            loadBatchSurahAudio(item.surah, edition).catch(() => {});
            preloadingKey = null;
            window.preloadingKey = null;
            return;
        }

        // Discard stale results (user changed ayah/reciter/stopped meanwhile)
        if (token !== preloadToken) return;
        if (currentAudioIndex + 1 !== nextIndex) return;

        const audio = new Audio(audioUrl);
        audio.preload = 'auto';
        audio.load(); // Explicitly kick off MP3 buffering NOW, not on play().
        const speedLabel = document.getElementById('audio-speed-label');
        audio.playbackRate = parseFloat(speedLabel?.textContent?.replace('x', '') || '1');

        // Mark ready once the browser has enough data to start playback
        // immediately (HAVE_FUTURE_DATA = readyState 3).
        nextAudioReady = false;
        const markReady = () => {
            if (nextAudio === audio && token === preloadToken) {
                nextAudioReady = true;
                window.nextAudioReady = true;
            }
        };
        audio.addEventListener('canplay', markReady);
        audio.addEventListener('canplaythrough', markReady);
        // If already buffered (from HTTP cache), mark ready synchronously.
        if (audio.readyState >= 3) {
            markReady();
        }

        // Replace any existing preload (avoid duplicate downloads)
        if (nextAudio && nextAudio !== audio) {
            nextAudio.pause();
            nextAudio.src = '';
        }
        nextAudio = audio;
        nextAudioIndex = nextIndex;
        window.nextAudio = nextAudio;
        window.nextAudioIndex = nextAudioIndex;
    } catch (e) {
        // Preload failures are non-fatal — the normal fetch path will retry
        preloadingKey = null;
        window.preloadingKey = null;
    }
}

/**
 * Play the current ayah in the queue
 */
async function playCurrentAyah(edition) {
    if (!audioQueue.length) return;

    const item = audioQueue[currentAudioIndex];
    const surahNumber = item.surah;
    const ayahNumber = item.ayah;

    // Capture the current play token. If the user clicks another ayah while
    // this function awaits its URL fetch, the response must be discarded.
    const token = playToken;

    // Stop any existing audio IMMEDIATELY. Don't let the old ayah keep playing
    // (and competing for bandwidth) while the new ayah URL is fetched.
    if (currentAudio) {
        currentAudio.pause();
        currentAudio = null;
        window.currentAudio = null;
    }

    try {
        // Update UI to show loading state while the audio URL is fetched.
        // All buttons reset to Play; the clicked one shows an animated spinner.
        document.querySelectorAll('.audio-btn').forEach(btn => {
            btn.innerHTML = '<i class="fas fa-play"></i>';
            btn.classList.remove('loading');
        });
        const activeBtn = document.querySelector(`.audio-btn[data-surah="${surahNumber}"][data-ayah="${ayahNumber}"]`);
        if (activeBtn) {
            activeBtn.classList.add('loading');
            activeBtn.innerHTML = '<i class="fas fa-circle-notch"></i>';
        }

        // Highlight the currently playing ayah (visual only — audio logic untouched)
        setActiveAyah(surahNumber, ayahNumber);

        const player = document.getElementById('audio-player');
        if (player) {
            player.style.display = 'flex';
            player.classList.add('is-playing');
            // Show the surah NAME when available (e.g. "Surah Al-Baqarah 2:8")
            // instead of just "Surah 2:8". The name comes from the ayah item's
            // data-surah-name attribute (present on both Surah and Para pages).
            const activeItem = document.querySelector(
                `.ayah-item[data-surah="${surahNumber}"][data-ayah="${ayahNumber}"]`
            );
            const surahName = activeItem?.dataset.surahName;
            document.getElementById('audio-player-title').textContent =
                surahName ? `Surah ${surahName} ${ayahNumber}` : `Surah ${surahNumber}:${ayahNumber}`;

            // The 3D player icon shows Pause while playing; the separate
            // waveform + pulse rings handle the animation (visual only).
            const playerIcon = document.getElementById('audio-player-icon');
            if (playerIcon) {
                playerIcon.className = 'fas fa-pause';
                playerIcon.innerHTML = '';
            }
        }

        // Use a preloaded Audio object if it matches this exact queue index
        // (preloaded while the previous ayah was playing). This avoids the
        // fetch + new Audio() + buffering delay between consecutive ayahs.
        let audioToPlay = null;
        if (nextAudio && nextAudioIndex === currentAudioIndex) {
            audioToPlay = nextAudio;
            nextAudio = null;
            nextAudioIndex = -1;
            preloadingKey = null;
            window.preloadingKey = null;
            window.nextAudio = null;
            window.nextAudioIndex = -1;
        } else {
            // Stale preload (e.g. user pressed Previous) — discard it
            if (nextAudio) {
                nextAudio.pause();
                nextAudio.src = '';
                nextAudio = null;
                nextAudioIndex = -1;
                preloadingKey = null;
                window.preloadingKey = null;
                window.nextAudio = null;
                window.nextAudioIndex = -1;
            }

            // Reuse a cached audio URL to skip the Flask request and the
            // external API lookup entirely when the same ayah/reciter is
            // played again.
            const cacheKey = `${surahNumber}:${ayahNumber}:${edition}`;
            let audioUrl = audioUrlCache[cacheKey];
            if (!audioUrl) {
                // Cache miss — AWAIT the single batch fetch of the whole
                // surah (one external API call via QuranService.get_surah_audio)
                // BEFORE falling back to a per-ayah request. This prevents the
                // first-ayah 4-15 second /quran/audio/ayah/... request that the
                // previous fire-and-forget pattern triggered.
                await loadBatchSurahAudio(surahNumber, edition);
                // If the user selected another ayah while the batch fetch was
                // in flight, discard this stale request (same token guard the
                // fallback below uses).
                if (token !== playToken) return;

                // The batch successfully populated the cache with every ayah's
                // URL, including the one we're about to play — use it directly.
                audioUrl = audioUrlCache[cacheKey];
                if (!audioUrl) {
                    // Batch failed or didn't include this ayah — fall back
                    // to the original per-ayah endpoint so playback still works.
                    const response = await fetch(`/quran/audio/ayah/${surahNumber}/${ayahNumber}?edition=${edition}`);
                    // If the user already selected another token while this
                    // request was in flight, the newer selection supersedes it —
                    // discard this stale response.
                    if (token !== playToken) return;

                    const data = await response.json();

                    if (!data.success || !data.audio_url) {
                        // Reset the loading state back to the Play icon
                        // (visual only — audio logic untouched).
                        if (activeBtn) {
                            activeBtn.classList.remove('loading');
                            activeBtn.innerHTML = '<i class="fas fa-play"></i>';
                        }
                        showToast('Audio not available', 'warning');
                        return;
                    }

                    audioUrl = data.audio_url;
                    audioUrlCache[cacheKey] = audioUrl;
                    window.audioUrlCache = audioUrlCache;
                }
            }

            audioToPlay = new Audio(audioUrl);
        }

        currentAudio = audioToPlay;
        // If the user selected yet another ayah while this audio was being
        // prepared, don't start playing the stale one.
        if (token !== playToken) {
            audioToPlay.pause();
            audioToPlay.src = '';
            return;
        }
        // Sync to window so SPA re-execution preserves the playing audio
        window.currentAudio = currentAudio;
        const speedLabel = document.getElementById('audio-speed-label');
        currentAudio.playbackRate = parseFloat(speedLabel?.textContent?.replace('x', '') || '1');

        // Loading state finished — the active ayah button becomes Pause,
        // and the sticky player's controls reflect the playing state too.
        if (activeBtn) {
            activeBtn.classList.remove('loading');
            activeBtn.innerHTML = '<i class="fas fa-pause"></i>';
        }

        const playPauseBtn = document.getElementById('audio-play-pause');
        if (playPauseBtn) {
            playPauseBtn.innerHTML = '<i class="fas fa-pause"></i>';
        }

        currentAudio.play().catch(error => {
            console.error('Audio playback failed:', error);
            showToast('Unable to play audio. Please try again.', 'warning');
        });

        // Smoothly scroll the newly-active ayah into view when audio
        // auto-advances (not when the user manually clicks an ayah).
        if (window.__autoAdvancing) {
            window.__autoAdvancing = false;
            const activeItem = document.querySelector(
                `.ayah-item[data-surah="${surahNumber}"][data-ayah="${ayahNumber}"]`
            );
            if (activeItem) {
                activeItem.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }

        currentAudio.addEventListener('ended', function() { // Use regular function for `this`
            // If this audio object that just ended is no longer the "current" one
            // (e.g., user clicked another ayah), do nothing. This prevents race conditions.
            if (this !== currentAudio) {
                return;
            }

            const repeatLabel = document.getElementById('audio-repeat-label');
            const repeatText = repeatLabel?.textContent?.toLowerCase() || 'off';
            const repeatMode = repeatText === 'ayah' || repeatText === 'surah' ? repeatText : 'off';

            if (repeatMode === 'ayah' && currentAudio) {
                // Repeat current ayah
                currentAudio.currentTime = 0;
                currentAudio.play();
            } else {
                // Move to next ayah
                currentAudioIndex++;
                if (currentAudioIndex < audioQueue.length) {
                    // Flag so playCurrentAyah knows to smooth-scroll to the
                    // newly active ayah (auto-advance, not a manual click).
                    window.__autoAdvancing = true;
                    playCurrentAyah(edition);
                } else if (repeatMode === 'surah') {
                    currentAudioIndex = 0;
                    window.__autoAdvancing = true;
                    playCurrentAyah(edition);
                } else {
                    stopAudio();
                }
            }
        });

        // Update time display + custom progress bar
        const updateTime = () => {
            const timeDisplay = document.getElementById('audio-player-time');
            if (timeDisplay && currentAudio) {
                const format = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
                timeDisplay.textContent = `${format(currentAudio.currentTime)} / ${format(currentAudio.duration || 0)}`;
            }
            const progressFill = document.getElementById('audio-progress-fill');
            const progressThumb = document.getElementById('audio-progress-thumb');
            if (currentAudio && progressFill && progressThumb) {
                const pct = (currentAudio.currentTime / (currentAudio.duration || 1)) * 100;
                progressFill.style.width = pct + '%';
                progressThumb.style.left = pct + '%';
            }
        };

        currentAudio.addEventListener('timeupdate', updateTime);

        // Preload the NEXT ayah while this one plays, so the transition
        // to the next ayah is instant (no fetch + buffering delay).
        preloadNextAyah(edition);
    } catch (error) {
        console.error('Error playing audio:', error);
        showToast('Failed to play audio. Please try again.', 'danger');
    }
}

/**
 * Initialize audio player controls (custom SalahMate UI)
 */
function initializeAudioPlayer() {
    const playPauseBtn = document.getElementById('audio-play-pause');
    const prevBtn = document.getElementById('audio-prev');
    const nextBtn = document.getElementById('audio-next');
    const progressBar = document.getElementById('audio-progress');
    const progressFill = document.getElementById('audio-progress-fill');
    const progressThumb = document.getElementById('audio-progress-thumb');
    const speedBtn = document.getElementById('audio-speed-btn');
    const speedLabel = document.getElementById('audio-speed-label');
    const speedDropdown = document.getElementById('audio-speed-dropdown');
    const repeatBtn = document.getElementById('audio-repeat-btn');
    const repeatLabel = document.getElementById('audio-repeat-label');
    const repeatDropdown = document.getElementById('audio-repeat-dropdown');

    // Play/Pause button
    if (playPauseBtn) {
        playPauseBtn.addEventListener('click', () => {
            if (!currentAudio) return;
            // Sync the active ayah-level button icon/state with the sticky
            // player control (visual only — audio logic is untouched).
            const activeBtn = document.querySelector(
                `.audio-btn[data-surah="${audioQueue[currentAudioIndex]?.surah}"][data-ayah="${audioQueue[currentAudioIndex]?.ayah}"]`
            );
            const coreIcon = document.getElementById('audio-player-icon');
            if (currentAudio.paused) {
                currentAudio.play();
                playPauseBtn.innerHTML = '<i class="fas fa-pause"></i>';
                if (coreIcon) {
                    coreIcon.className = 'fas fa-pause';
                    coreIcon.innerHTML = '';
                }
                if (activeBtn) {
                    activeBtn.classList.remove('loading');
                    activeBtn.innerHTML = '<i class="fas fa-pause"></i>';
                }
            } else {
                currentAudio.pause();
                playPauseBtn.innerHTML = '<i class="fas fa-play"></i>';
                if (coreIcon) {
                    coreIcon.className = 'fas fa-play';
                    coreIcon.innerHTML = '';
                }
                if (activeBtn) {
                    activeBtn.classList.remove('loading');
                    activeBtn.innerHTML = '<i class="fas fa-play"></i>';
                }
            }
        });
    }

    // Previous button
    if (prevBtn) {
        prevBtn.addEventListener('click', () => {
            if (currentAudioIndex > 0) {
                // Stop the current audio immediately, just like a manual click.
                if (currentAudio) {
                    currentAudio.pause();
                    currentAudio = null;
                    window.currentAudio = null;
                }
                playToken = (playToken || 0) + 1;
                window.playToken = playToken;
                currentAudioIndex--;
                const edition = document.getElementById('reciter-select')?.value || 'ar.alafasy';
                playCurrentAyah(edition);
            }
        });
    }

    // Next button
    if (nextBtn) {
        nextBtn.addEventListener('click', () => {
            if (currentAudioIndex < audioQueue.length - 1) {
                // Stop the current audio immediately, so the next ayah can start ASAP.
                if (currentAudio) {
                    currentAudio.pause();
                    currentAudio = null;
                    window.currentAudio = null;
                }
                playToken = (playToken || 0) + 1;
                window.playToken = playToken;
                currentAudioIndex++;
                const edition = document.getElementById('reciter-select')?.value || 'ar.alafasy';
                playCurrentAyah(edition);
            }
        });
    }

    // Custom progress bar — click to seek
    if (progressBar && progressFill && progressThumb) {
        const seekFromEvent = (e) => {
            if (!currentAudio || !currentAudio.duration) return;
            const rect = progressBar.getBoundingClientRect();
            const ratio = Math.min(Math.max((e.clientX - rect.left) / rect.width, 0), 1);
            currentAudio.currentTime = ratio * currentAudio.duration;
            progressFill.style.width = (ratio * 100) + '%';
            progressThumb.style.left = (ratio * 100) + '%';
        };
        progressBar.addEventListener('click', seekFromEvent);
        // Drag support
        let isDragging = false;
        progressThumb.addEventListener('mousedown', (e) => {
            e.preventDefault();
            isDragging = true;
        });
        document.addEventListener('mousemove', (e) => {
            if (isDragging) seekFromEvent(e);
        });
        document.addEventListener('mouseup', () => {
            isDragging = false;
        });
    }

    // Custom speed dropdown
    if (speedBtn && speedDropdown && speedLabel) {
        speedBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            speedDropdown.classList.toggle('open');
            if (repeatDropdown) repeatDropdown.classList.remove('open');
        });
        speedDropdown.querySelectorAll('.audio-select-option').forEach(option => {
            option.addEventListener('click', () => {
                const speed = option.dataset.speed;
                if (currentAudio) {
                    currentAudio.playbackRate = parseFloat(speed);
                }
                localStorage.setItem('quranAudioSpeed', speed);
                speedLabel.textContent = speed + 'x';
                speedDropdown.querySelectorAll('.audio-select-option').forEach(o => o.classList.remove('active'));
                option.classList.add('active');
                speedDropdown.classList.remove('open');
            });
        });
        // Restore saved speed
        const savedSpeed = localStorage.getItem('quranAudioSpeed');
        if (savedSpeed) {
            speedLabel.textContent = savedSpeed + 'x';
            speedDropdown.querySelectorAll('.audio-select-option').forEach(o => {
                o.classList.toggle('active', o.dataset.speed === savedSpeed);
            });
        }
    }

    // Custom repeat dropdown
    if (repeatBtn && repeatDropdown && repeatLabel) {
        repeatBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            repeatDropdown.classList.toggle('open');
            if (speedDropdown) speedDropdown.classList.remove('open');
        });
        repeatDropdown.querySelectorAll('.audio-select-option').forEach(option => {
            option.addEventListener('click', () => {
                const repeat = option.dataset.repeat;
                localStorage.setItem('quranAudioRepeat', repeat);
                repeatLabel.textContent = repeat === 'off' ? 'Off' : (repeat === 'ayah' ? 'Ayah' : 'Surah');
                repeatDropdown.querySelectorAll('.audio-select-option').forEach(o => o.classList.remove('active'));
                option.classList.add('active');
                repeatDropdown.classList.remove('open');
            });
        });
        // Restore saved repeat
        const savedRepeat = localStorage.getItem('quranAudioRepeat');
        if (savedRepeat) {
            repeatLabel.textContent = savedRepeat === 'off' ? 'Off' : (savedRepeat === 'ayah' ? 'Ayah' : 'Surah');
            repeatDropdown.querySelectorAll('.audio-select-option').forEach(o => {
                o.classList.toggle('active', o.dataset.repeat === savedRepeat);
            });
        }
    }

    // Close custom dropdowns on outside click — attach ONCE globally (SPA-safe).
    // Without this guard, every SPA navigation re-runs initializeAudioPlayer
    // and stacks duplicate document listeners.
    if (!window.__quranPlayerDocListenersAttached) {
        window.__quranPlayerDocListenersAttached = true;
        document.addEventListener('click', () => {
            document.querySelectorAll('.audio-select-dropdown.open').forEach(d => d.classList.remove('open'));
        });
    }
}

/**
 * Track reading position and save to server
 */
function trackReadingPosition() {
    const ayahItems = document.querySelectorAll('.ayah-item');
    if (!ayahItems.length) return;

    let lastTracked = null;

    // Use IntersectionObserver to detect which ayah is in view
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const item = entry.target;
                const surahNumber = item.dataset.surah;
                const ayahNumber = item.dataset.ayah;
                const paraNumber = item.dataset.para;
                const pageNumber = item.dataset.page;

                if (surahNumber && ayahNumber && lastTracked !== `${surahNumber}:${ayahNumber}`) {
                    lastTracked = `${surahNumber}:${ayahNumber}`;
                    saveReadingPosition(surahNumber, ayahNumber, paraNumber, pageNumber);
                }
            }
        });
    }, { threshold: 0.3 });

    ayahItems.forEach(item => observer.observe(item));
}

/**
 * Save reading position to server
 */
function saveReadingPosition(surahNumber, ayahNumber, paraNumber, pageNumber) {
    fetch('/quran/track-reading', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            surah_number: surahNumber,
            ayah_number: ayahNumber,
            para_number: paraNumber,
            page_number: pageNumber
        })
    })
    .then(response => response.json())
    .then(data => {
        if (!data.success) {
            console.error('Failed to track reading:', data.error);
        }
    })
    .catch(error => {
        console.error('Error tracking reading:', error);
    });
}

/* =========================================================
   VISUAL ANIMATION HELPERS
   (UI/UX only — no audio, caching, preload, or API logic)
   ========================================================= */

/**
 * Scroll-reveal ayahs with IntersectionObserver.
 * Each ayah is revealed ONCE (is-visible) — never re-animated on re-entry.
 */
function initAyahReveal() {
    const ayahItems = document.querySelectorAll('.ayah-item');
    if (!ayahItems.length) return;

    // Respect reduced motion OR missing IntersectionObserver support:
    // reveal everything instantly so content is never hidden.
    if (
        (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) ||
        !('IntersectionObserver' in window)
    ) {
        ayahItems.forEach(item => item.classList.add('is-visible'));
        return;
    }

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('is-visible');
                observer.unobserve(entry.target); // reveal once only
            }
        });
    }, { threshold: 0.05, rootMargin: '0px 0px -20px 0px' });

    ayahItems.forEach(item => observer.observe(item));
}

/**
 * Animate the reading progress fill from 0% → current on page load.
 * Does NOT change the actual progress calculation.
 */
function animateReadingProgress() {
    const fill = document.querySelector('.reader-progress .progress-fill');
    if (!fill) return;

    const target = parseFloat(fill.style.width) || 0;
    fill.style.width = '0%';
    // Force a reflow so the 0% state is painted before transitioning.
    void fill.offsetWidth;
    requestAnimationFrame(() => {
        fill.style.width = target + '%';
    });
}

/**
 * Highlight the currently playing ayah (visual only).
 * Adds .playing + a tiny equalizer indicator; removes them from any other ayah.
 */
function setActiveAyah(surahNumber, ayahNumber) {
    document.querySelectorAll('.ayah-item.playing').forEach(item => {
        item.classList.remove('playing');
        const eq = item.querySelector('.audio-equalizer');
        if (eq) eq.remove();
    });

    const activeItem = document.querySelector(
        `.ayah-item[data-surah="${surahNumber}"][data-ayah="${ayahNumber}"]`
    );
    if (!activeItem) return;

    activeItem.classList.add('playing');
    // Ensure the ayah is visible (in case it was below the fold).
    activeItem.classList.add('is-visible');

    // Tiny animated equalizer next to the actions.
    if (!activeItem.querySelector('.audio-equalizer')) {
        const eq = document.createElement('span');
        eq.className = 'audio-equalizer';
        eq.innerHTML = '<span></span><span></span><span></span>';
        const actions = activeItem.querySelector('.ayah-actions');
        if (actions) actions.appendChild(eq);
    }
}

/**
 * Remove the playing highlight from all ayahs (audio stopped).
 */
function clearActiveAyah() {
    document.querySelectorAll('.ayah-item.playing').forEach(item => {
        item.classList.remove('playing');
        const eq = item.querySelector('.audio-equalizer');
        if (eq) eq.remove();
    });
}

/**
 * Scroll the reader to the target ayah (Continue Reading deep-link).
 * Reads data-target-ayah (surah pages) and data-target-surah/ayah (para pages)
 * from the rendered page. Runs once per page load — never on scroll.
 */
function scrollToTargetAyah() {
    const readerPage = document.querySelector('.quran-reader-page');
    if (!readerPage) return;

    const targetSurah = readerPage.dataset.targetSurah;
    const targetAyah = readerPage.dataset.targetAyah;
    if (!targetAyah) return;

    // Surah pages: the ayah is unique within the page → match by ayah number.
    // Para pages (have data-target-surah): match surah+ayah — a para contains
    // ayahs from many surahs, so the ayah number alone would be ambiguous.
    let targetItem = null;
    if (targetSurah) {
        targetItem = document.querySelector(
            `.ayah-item[data-surah="${targetSurah}"][data-ayah="${targetAyah}"]`
        );
    } else {
        targetItem = document.querySelector(`.ayah-item[data-ayah="${targetAyah}"]`);
    }

    if (targetItem) {
        // Ensure the IntersectionObserver reveal already marked it visible,
        // then scroll it into the center of the viewport.
        targetItem.classList.add('is-visible');
        // Small delay lets the CSS entrance animations start before scrolling.
        setTimeout(() => {
            targetItem.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }, 150);
    }
}

/**
 * Warm up the first ayah's audio URL immediately so the first play skips the
 * slow external API round-trip. This only populates audioUrlCache — it never
 * downloads MP3 bytes and never interferes with preloadNextAyah/playback.
 */
function warmUpFirstAudio() {
    const firstAyah = document.querySelector('.ayah-item');
    if (!firstAyah) return;

    const surahNumber = firstAyah.dataset.surah;
    if (!surahNumber) return;

    const edition = document.getElementById('reciter-select')?.value || 'ar.alafasy';
    const batchKey = `${surahNumber}:${edition}`;

    // Only warm up if this surah+edition isn't already cached/loading.
    if (batchLoadedSurahs[batchKey]) return;

    // Fire-and-forget: fill the URL cache with every ayah's proxied URL.
    // The very first play then resolves instantly instead of waiting 2-5s
    // for the external alquran.cloud API on first click.
    loadBatchSurahAudio(surahNumber, edition).catch(() => {});
}

/**
 * Subtle mouse-following 3D tilt on the audio player card.
 * UI-only — does not touch the audio engine. Uses CSS transforms
 * with a rAF throttle so it stays cheap and never causes audio lag.
 */
function initAudioPlayer3DTilt() {
    const player = document.getElementById('audio-player');
    if (!player) return;

    // Respect reduced motion
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        return;
    }

    let rafId = null;
    let isHovering = false;

    player.addEventListener('mouseenter', () => {
        isHovering = true;
    });

    player.addEventListener('mouseleave', () => {
        isHovering = false;
        if (rafId) cancelAnimationFrame(rafId);
        player.style.transform = '';
    });

    player.addEventListener('mousemove', (e) => {
        if (!isHovering) return;
        if (rafId) cancelAnimationFrame(rafId);
        rafId = requestAnimationFrame(() => {
            const rect = player.getBoundingClientRect();
            const px = (e.clientX - rect.left) / rect.width - 0.5;
            const py = (e.clientY - rect.top) / rect.height - 0.5;
            // Subtle tilt — max ~4-6 degrees, never wild
            const rotateY = px * 6;
            const rotateX = -py * 4;
            player.style.transform = `perspective(1200px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateY(-2px)`;
        });
    });
}
