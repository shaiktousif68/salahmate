import pathlib

p = pathlib.Path('app/static/js/prayer.js')
content = p.read_text(encoding='utf-8')

old = """document.addEventListener('DOMContentLoaded', function() {
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
});"""

new = """// Prayer status click handling is registered at the TOP LEVEL (not inside
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
}"""

if old not in content:
    print('ERROR: Original DOMContentLoaded block not found')
    raise SystemExit(1)

content = content.replace(old, new)
p.write_text(content, encoding='utf-8')
print('prayer.js SPA fix applied successfully')