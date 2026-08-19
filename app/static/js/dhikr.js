/**
 * Daily Dhikr Challenge — Tasbeeh counter
 * UI-only logic for the 3D circular counter. Persistence is done
 * asynchronously via the /prayers/dhikr/* API endpoints.
 */

(function() {
    const MAX_COUNT = 100;
    const DHIKR_MAX = window.dhikrMax || 100;

    // Current selected Dhikr
    let currentDhikr = null;
    let currentCount = 0;

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

        const count = Math.min(currentCount, MAX_COUNT);
        countNumber.textContent = String(count);
        if (countTarget) countTarget.textContent = ' / ' + MAX_COUNT;

        // Smooth progress ring update
        const percent = (count / MAX_COUNT) * 100;
        if (progressRing) {
            progressRing.style.setProperty('--progress', percent + '%');
        }

        // Completion state
        if (completionEl) {
            if (count >= MAX_COUNT) {
                completionEl.classList.add('visible');
                const text = completionEl.querySelector('span') || completionEl;
                text.textContent = '✨ Completed! Alhamdulillah';
            } else {
                completionEl.classList.remove('visible');
                const text = completionEl.querySelector('span') || completionEl;
                text.textContent = '✨ Complete your daily Dhikr';
            }
        }

        // Update the matching option card count
        options.forEach(opt => {
            if (opt.dataset.dhikr === currentDhikr) {
                const countSpan = opt.querySelector('.dhikr-option-count');
                if (countSpan) countSpan.textContent = count + ' / ' + MAX_COUNT;
                opt.classList.toggle('completed', count >= MAX_COUNT);
            }
        });
    }

    /**
     * Select a Dhikr and switch the main counter.
     */
    function selectDhikr(dhikrKey) {
        currentDhikr = dhikrKey;
        options.forEach(opt => {
            const isActive = opt.dataset.dhikr === dhikrKey;
            opt.classList.toggle('active', isActive);
            opt.setAttribute('aria-pressed', isActive ? 'true' : 'false');
            if (isActive && opt.dataset.name && opt.dataset.arabic) {
                if (counterArabic) counterArabic.textContent = opt.dataset.arabic;
                if (counterName) counterName.textContent = opt.dataset.name;
                if (counterBtn) counterBtn.setAttribute('aria-label', 'Tap to count ' + opt.dataset.name);
            }
        });

        // Set count from the option card's current text ("37 / 100")
        const activeOpt = document.querySelector('.dhikr-option.active');
        if (activeOpt) {
            const countSpan = activeOpt.querySelector('.dhikr-option-count');
            const text = countSpan ? countSpan.textContent : '0 / 100';
            const parsed = parseInt(text.split('/')[0].trim(), 10);
            currentCount = isNaN(parsed) ? 0 : parsed;
        } else {
            currentCount = 0;
        }

        updateCounterUI();
    }

    // --- Event: Select Dhikr option ---
    options.forEach(opt => {
        opt.addEventListener('click', function() {
            selectDhikr(this.dataset.dhikr);
        });
    });

    // --- Event: Tap the circular counter to +1 ---
    if (counterBtn) {
        counterBtn.addEventListener('click', function() {
            if (!currentDhikr) return;

            if (currentCount >= MAX_COUNT) {
                // Already completed — don't increase beyond 100
                return;
            }

            // Instant visual update (UI feels immediate)
            currentCount += 1;
            if (countNumber) {
                countNumber.textContent = String(currentCount);
                countNumber.classList.remove('bump');
                void countNumber.offsetWidth; // restart animation
                countNumber.classList.add('bump');
            }

            // Button tap animation
            counterBtn.classList.remove('tapped');
            void counterBtn.offsetWidth;
            counterBtn.classList.add('tapped');

            updateCounterUI();

            // Asynchronous save (graceful failure)
            fetch('/prayers/dhikr/increment', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ dhikr: currentDhikr })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    // Sync back the authoritative count from the server
                    currentCount = data.count;
                    updateCounterUI();
                } else {
                    // Revert optimistic update on failure
                    currentCount -= 1;
                    updateCounterUI();
                    showDhikrToast('Failed to save Dhikr count', 'danger');
                }
            })
            .catch(() => {
                // Revert optimistic update on network failure
                currentCount -= 1;
                updateCounterUI();
                showDhikrToast('Network error — count not saved', 'danger');
            });
        });
    }

    // --- Event: Reset with confirmation ---
    if (resetBtn) {
        resetBtn.addEventListener('click', function() {
            if (!currentDhikr) return;

            if (currentCount === 0) return;

            if (!confirm('Reset this Dhikr count?')) return;

            currentCount = 0;
            updateCounterUI();

            fetch('/prayers/dhikr/reset', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ dhikr: currentDhikr })
            })
            .then(r => r.json())
            .then(data => {
                if (!data.success) {
                    currentCount = data.count !== undefined ? data.count : currentCount;
                    updateCounterUI();
                    showDhikrToast('Failed to reset Dhikr count', 'danger');
                } else {
                    showDhikrToast('Dhikr reset', 'success');
                }
            })
            .catch(() => {
                showDhikrToast('Network error — reset not saved', 'danger');
            });
        });
    }

    // --- Small toast helper for feedback ---
    function showDhikrToast(message, type) {
        const container = document.querySelector('.toast-container-salahmate');
        const toast = document.createElement('div');
        toast.className = 'toast-salahmate toast-' + (type || 'info');
        toast.textContent = message;
        if (container) {
            container.appendChild(toast);
            setTimeout(() => toast.remove(), 3000);
        }
    }

    // --- Initialize: select the first Dhikr ---
    if (options.length > 0) {
        selectDhikr(options[0].dataset.dhikr);
    }
})();