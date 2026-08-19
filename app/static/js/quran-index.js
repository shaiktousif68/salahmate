/**
 * Quran selection page (Surah/Para list) — lightweight script.
 *
 * The full quran.js audio engine is NOT needed on this page because there
 * are no ayah items, audio buttons, or the reader player here. This tiny
 * script only loads the selection list and the user's reading progress.
 *
 * Kept small so the Quran list appears instantly (no 60KB+ audio engine
 * parse/execute cost on this page).
 */
(function() {
    // Nothing functional is needed for the static surah/para cards.
    // The page is fully server-rendered — the cards link directly to the
    // reader pages which load the full quran.js audio engine.

    // If a "last read" card exists, it's already rendered by the server.
    // No extra JS actions are required for the selection page.
})();