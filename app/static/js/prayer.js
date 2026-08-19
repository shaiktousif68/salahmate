/**
 * Prayer tracking functionality
 */

// Prayer status click handling is registered at the TOP LEVEL (not inside
// DOMContentLoaded) so it is also registered when this script is re-executed
// dynamically by the SPA navigation (navigation.js) - which happens after
// DOMContentLoaded has already fired on the Dashboard. The guard prevents
// duplicate listeners if the script is executed multiple times.
if (!window.__prayerInitialized) {
    window.__prayerInitialized = true;
    // Event delegation for status buttons
    document.addEventListener('click', function(e) {
        const btn = e.target.closest('.btn-status');
        if (!btn) return;

        const prayerName = btn.dataset.prayer;
        const status = btn.dataset.status;
        const date = btn.dataset.date;

        if (prayerName && status && date) {
            updatePrayer(prayerName, status, date);
        }
    });
}

/**
 * Update a prayer's status via AJAX
 * @param {string} prayerName - The name of the prayer (Fajr, Dhuhr, etc.)
 * @param {string} status - The new status (jamaat, alone, qaza, missed, excused)
 * @param {string} date - The date in ISO format (YYYY-MM-DD)
 */
function updatePrayer(prayerName, status, date) {
    const prayerItem = document.querySelector(`.prayer-item[data-prayer="${prayerName}"]`);
    const allButtons = prayerItem ? prayerItem.querySelectorAll('.btn-status') : [];

    // Disable all buttons while saving
    allButtons.forEach(btn => btn.disabled = true);

    fetch('/attendance/update', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify({
            prayer_name: prayerName,
            status: status,
            date: date
        })
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(data => {
                throw new Error(data.error || 'Server error');
            });
        }
        return response.json();
    })
    .then(data => {
        if (!data.success) {
            throw new Error(data.error || 'Failed to update prayer');
        }

        // Update button styles - clear ALL status classes first
        allButtons.forEach(btn => {
            btn.classList.remove('status-jamaat', 'status-alone', 'status-qaza', 'status-missed', 'status-excused', 'active');
            btn.classList.add('btn-outline');
        });

        // Highlight the selected status button
        const activeBtn = prayerItem ? prayerItem.querySelector(`.btn-status[data-status="${status}"]`) : null;
        if (activeBtn) {
            activeBtn.classList.remove('btn-outline');
            activeBtn.classList.add(`status-${status}`, 'active');
        }

        // Update attendance display
        if (data.attendance) {
            const progressFill = document.getElementById('progress-fill');
            const progressText = document.getElementById('progress-text');

            if (progressFill) {
                progressFill.style.width = `${data.attendance.completion_percentage}%`;
            }
            if (progressText) {
                progressText.textContent = `${data.attendance.total_completed}/5 completed`;
            }
        }

        const statusLabels = {
            'jamaat': 'Jamaat',
            'alone': 'Alone',
            'qaza': 'Qaza',
            'missed': 'Missed',
            'excused': 'Excused',
            'not_recorded': 'Not Recorded'
        };
        showToast(`${prayerName} marked as ${statusLabels[status] || status}`, 'success');
    })
    .catch(error => {
        console.error('Error:', error);
        showToast(error.message || 'Failed to update prayer. Please try again.', 'danger');
    })
    .finally(() => {
        allButtons.forEach(btn => btn.disabled = false);
    });
}