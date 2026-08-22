/**
 * Daily Dhikr Challenge — Tasbeeh counter
 *
 * UI logic for the 3D circular counter.
 *
 * Persistence model:
 * - The DATABASE is the single source of truth for the saved count.
 * - Taps update the UI optimistically and schedule a DEBOUNCED save that
 *   sends the ABSOLUTE count (not a per-tap increment).
 * - The backend stores max(current, absolute_count), so an older client
 *   value can NEVER overwrite a newer database value.
 * - A `pagehide` handler flushes the latest count via `navigator.sendBeacon`
 *   so logout / navigation / tab-close never loses the last taps.
 * - There is NO maximum count — the counter can grow without limit.
 */

(function () {
    // Current selected Dhikr
    let currentDhikr = null;
    let currentCount = 0;

    // Debounce timer for the absolute-count save
    let saveTimer = null;
    const SAVE_DEBOUNCE_MS = 400;

    // DOM elements
    const selector = document.querySelector('.dhikr-selector');
    const options = document.querySelectorAll('.dhikr-option');
    const countNumber = document.getElementById('dhikr-count-number');
    const countTarget = document.getElementById('dhikr-count-target');
    const tapHint = document.getElementById('dhikr-tap-hint');
    const counterBtn = document.getElementById('dhikr-counter-btn');
    const counterArabic = document.getElementById('dhikr-counter-arabic');
    const counterName = document.getElementById('dhikr-counter-name');
    const progressRing = document.getElementById('dhikr-progress-ring');
    const completionEl = document.getElementById('dhikr-completion');
    const resetBtn = document.getElementById('dhikr-reset-btn');

    // Skip if the section isn't on this page
    if (!selector || options.length === 0) return;

    /**
     * Update the main counter UI for the current Dhikr.
     */
    function updateCounterUI() {
        if (!countNumber) return;

        const count = currentCount;

        countNumber.textContent = String(count);

        if (countTarget) {
            countTarget.textContent = '';
        }

        // Update matching option card
        options.forEach(opt => {
            if (opt.dataset.dhikr === currentDhikr) {
                const countSpan =
                    opt.querySelector('.dhikr-option-count');

                if (countSpan) {
                    countSpan.textContent = String(count);
                }
            }
        });
    }

    /**
     * Save the CURRENT absolute count for the current Dhikr.
     *
     * Sends the absolute count so the backend can store
     * max(current, count) — it can never decrease the stored value.
     */
    async function saveCurrentCount() {
        if (!currentDhikr) return;

        const dhikrToSave = currentDhikr;
        const countToSave = currentCount;

        try {
            const response = await fetch(
                '/prayers/dhikr/increment',
                {
                    method: 'POST',
                    headers: {
                        'Content-Type':
                            'application/json'
                    },
                    body: JSON.stringify({
                        dhikr: dhikrToSave,
                        count: countToSave
                    })
                }
            );

            const data = await response.json();

            if (data.success) {
                /*
                 * Only reconcile the UI from the server when the
                 * user hasn't tapped again since this save started.
                 * The server never returns a LOWER count than what
                 * we sent, so this is safe.
                 */
                if (dhikrToSave === currentDhikr) {
                    currentCount = Number(data.count) || currentCount;
                    updateCounterUI();
                }
            } else {
                showDhikrToast(
                    'Failed to save Dhikr count',
                    'danger'
                );
            }
        } catch (error) {
            showDhikrToast(
                'Network error — count not saved',
                'danger'
            );
        }
    }

    /**
     * Schedule a debounced save of the current absolute count.
     */
    function scheduleSave() {
        if (saveTimer) {
            clearTimeout(saveTimer);
        }
        saveTimer = setTimeout(function () {
            saveTimer = null;
            saveCurrentCount();
        }, SAVE_DEBOUNCE_MS);
    }

    /**
     * Flush the latest count immediately (used on page hide / logout).
     *
     * Uses navigator.sendBeacon so the request survives page unload.
     */
    function flushSave() {
        if (saveTimer) {
            clearTimeout(saveTimer);
            saveTimer = null;
        }

        if (!currentDhikr || currentCount <= 0) return;

        const payload = JSON.stringify({
            dhikr: currentDhikr,
            count: currentCount
        });

        if (navigator.sendBeacon) {
            const blob = new Blob(
                [payload],
                { type: 'application/json' }
            );
            navigator.sendBeacon(
                '/prayers/dhikr/increment',
                blob
            );
        } else {
            // Fallback: fire-and-forget fetch (best effort).
            fetch('/prayers/dhikr/increment', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: payload,
                keepalive: true
            }).catch(function () {});
        }
    }

    // Flush on page hide (logout, navigation, tab close, refresh).
    window.addEventListener('pagehide', flushSave);

    /**
     * Select a Dhikr and switch the main counter.
     */
    function selectDhikr(dhikrKey) {
        // Flush any pending save for the previous Dhikr first.
        flushSave();

        currentDhikr = dhikrKey;

        options.forEach(opt => {
            const isActive = opt.dataset.dhikr === dhikrKey;

            opt.classList.toggle('active', isActive);

            opt.setAttribute(
                'aria-pressed',
                isActive ? 'true' : 'false'
            );

            if (
                isActive &&
                opt.dataset.name &&
                opt.dataset.arabic
            ) {
                if (counterArabic) {
                    counterArabic.textContent =
                        opt.dataset.arabic;
                }

                if (counterName) {
                    counterName.textContent =
                        opt.dataset.name;
                }

                if (counterBtn) {
                    counterBtn.setAttribute(
                        'aria-label',
                        'Tap to count ' + opt.dataset.name
                    );
                }
            }
        });

        // Get current count from selected option
        const activeOpt =
            document.querySelector('.dhikr-option.active');

        if (activeOpt) {
            const countSpan =
                activeOpt.querySelector('.dhikr-option-count');

            const text = countSpan
                ? countSpan.textContent
                : '0';

            const parsed =
                parseInt(text.trim(), 10);

            currentCount =
                Number.isNaN(parsed) ? 0 : parsed;
        } else {
            currentCount = 0;
        }

        updateCounterUI();
    }

    // --- Event: Select Dhikr option ---
    options.forEach(opt => {
        opt.addEventListener('click', function () {
            selectDhikr(this.dataset.dhikr);
        });
    });

    // --- Event: Tap the circular counter to +1 ---
    if (counterBtn) {
        counterBtn.addEventListener(
            'click',
            function () {
                if (!currentDhikr) return;

                /*
                 * Increase the UI immediately (optimistic).
                 * No upper limit — the count can grow without bound.
                 */
                currentCount += 1;

                // Immediate number update
                if (countNumber) {
                    countNumber.textContent =
                        String(currentCount);

                    // Restart bump animation
                    countNumber.classList.remove('bump');

                    void countNumber.offsetWidth;

                    countNumber.classList.add('bump');
                }

                // Button tap animation
                counterBtn.classList.remove('tapped');

                void counterBtn.offsetWidth;

                counterBtn.classList.add('tapped');

                // Update progress/card
                updateCounterUI();

                /*
                 * Schedule a debounced save of the absolute count.
                 */
                scheduleSave();
            }
        );
    }

    // --- Event: Reset with confirmation ---
    if (resetBtn) {
        resetBtn.addEventListener(
            'click',
            async function () {
                if (!currentDhikr) return;

                if (currentCount === 0) return;

                if (!confirm('Reset this Dhikr count?')) {
                    return;
                }

                // Cancel any pending debounced save.
                if (saveTimer) {
                    clearTimeout(saveTimer);
                    saveTimer = null;
                }

                const dhikrToReset = currentDhikr;

                currentCount = 0;

                updateCounterUI();

                try {
                    const response = await fetch(
                        '/prayers/dhikr/reset',
                        {
                            method: 'POST',
                            headers: {
                                'Content-Type':
                                    'application/json'
                            },
                            body: JSON.stringify({
                                dhikr: dhikrToReset
                            })
                        }
                    );

                    const data = await response.json();

                    if (!data.success) {
                        if (
                            data.count !== undefined &&
                            dhikrToReset === currentDhikr
                        ) {
                            currentCount =
                                Number(data.count) || 0;

                            updateCounterUI();
                        }

                        showDhikrToast(
                            'Failed to reset Dhikr count',
                            'danger'
                        );
                    } else {
                        showDhikrToast(
                            'Dhikr reset',
                            'success'
                        );
                    }
                } catch (error) {
                    showDhikrToast(
                        'Network error — reset not saved',
                        'danger'
                    );
                }
            }
        );
    }

    // --- Small toast helper ---
    function showDhikrToast(message, type) {
        const container =
            document.querySelector(
                '.toast-container-salahmate'
            );

        if (!container) return;

        const toast =
            document.createElement('div');

        toast.className =
            'toast-salahmate toast-' +
            (type || 'info');

        toast.textContent = message;

        container.appendChild(toast);

        setTimeout(() => {
            toast.remove();
        }, 3000);
    }

    // --- Initialize: select the first Dhikr ---
    if (options.length > 0) {
        selectDhikr(
            options[0].dataset.dhikr
        );
    }
})();