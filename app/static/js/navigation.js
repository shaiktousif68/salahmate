/**
 * SalahMate SPA Navigation
 * Intercepts navigation to provide an instant, single-page application experience
 * with no loading indicators.
 */
(function() {
    // isNavigating is informational (spinner state); true navigation races
    // are resolved by aborting stale requests in navigate().
    let isNavigating = false;

    /**
     * Manually executes scripts from a given container. This is necessary because
     * scripts inserted via innerHTML are not run by the browser.
     * @param {HTMLElement} container The element containing the new scripts.
     */
    const executeScriptsInContainer = (container) => {
        if (!container) return;
        const scripts = Array.from(container.querySelectorAll('script'));
        scripts.forEach(oldScript => {
            const newScript = document.createElement('script');
            Array.from(oldScript.attributes).forEach(attr => {
                newScript.setAttribute(attr.name, attr.value);
            });
            if (oldScript.innerHTML) {
                newScript.innerHTML = oldScript.innerHTML;
            }
            oldScript.parentNode.replaceChild(newScript, oldScript);
        });
    };

    /**
     * Updates the 'active' state on sidebar and mobile navigation links
     * based on the current URL, mimicking the Flask template logic.
     * @param {string} href The new URL.
     */
    const updateActiveNavLinks = (href) => {
        const url = new URL(href, window.location.origin);
        const pathname = url.pathname;

        document.querySelectorAll('.sidebar .active, .mobile-nav .active').forEach(el => el.classList.remove('active'));

        document.querySelectorAll('.sidebar a, .mobile-nav a').forEach(link => {
            const linkUrl = new URL(link.href);
            if (linkUrl.pathname === pathname && linkUrl.search === url.search) {
                link.classList.add('active');
                // Handle parent menu items
                const parentSubmenu = link.closest('.submenu');
                if (parentSubmenu) {
                    parentSubmenu.previousElementSibling?.classList.add('active');
                }
            }
        });
    };

    /**
     * Shows a small inline spinner on the clicked link so the UI feels
     * responsive while the (possibly slow) external Quran API request runs.
     * The page itself is never frozen — only the clicked link shows progress.
     * @param {HTMLElement} link The anchor element that was clicked.
     */
    const showLinkLoading = (link) => {
        if (!link || link.hasAttribute('data-nav-loading')) return;
        const originalHTML = link.innerHTML;
        link.setAttribute('data-nav-loading', '1');
        link.setAttribute('data-nav-original-html', originalHTML);
        link.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        link.style.opacity = '0.75';
        link.style.pointerEvents = 'none';
    };

    /**
     * Restores the clicked link to its original state.
     * @param {HTMLElement} link The anchor element that had a spinner added.
     */
    const clearLinkLoading = (link) => {
        if (!link || !link.hasAttribute('data-nav-loading')) return;
        const originalHTML = link.getAttribute('data-nav-original-html');
        if (originalHTML !== null) {
            link.innerHTML = originalHTML;
        }
        link.removeAttribute('data-nav-loading');
        link.removeAttribute('data-nav-original-html');
        link.style.opacity = '';
        link.style.pointerEvents = '';
    };

    /**
     * Fetches a new page, parses its content, and updates the DOM without a full reload.
     * @param {string} href The URL to navigate to.
     * @param {boolean} pushState Whether to push a new state to the browser's history.
     * @param {HTMLElement} clickedLink Optional anchor element that triggered this navigation.
     */
    // Track the latest in-flight request so we can abort stale navigations.
    let activeController = null;

    const navigate = async (href, pushState = true, clickedLink = null) => {
        // If a navigation is already in flight, abort it — the LATEST click
        // always wins. Without aborting, the older (slower) response could
        // overwrite the page the user just selected, forcing a second click.
        if (activeController) {
            activeController.abort();
        }
        const controller = new AbortController();
        activeController = controller;
        isNavigating = true;

        showLinkLoading(clickedLink);

        try {
            const response = await fetch(href, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
                signal: controller.signal
            });

            if (response.redirected && new URL(response.url).pathname.includes('/login')) {
                window.location.href = href;
                return;
            }
            if (!response.ok) throw new Error(`Server responded with status ${response.status}`);

            const html = await response.text();
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');

            const newMain = doc.querySelector('main.main-content, main.auth-main');
            const currentMain = document.querySelector('main.main-content, main.auth-main');
            if (!newMain || !currentMain) throw new Error('Main content area not found.');

            // Swap content and page title
            currentMain.replaceWith(newMain);
            document.title = doc.title;

            // Swap and execute page-specific scripts.
            // Re-query the container AFTER replacing <main> so we never write
            // into a detached node (the container lives in base.html, outside
            // <main>). If one is missing on this particular page, scripts are
            // skipped gracefully instead of throwing.
            const newScriptContainer = doc.getElementById('script-container');
            const currentScriptContainer = document.getElementById('script-container');
            if (newScriptContainer && currentScriptContainer) {
                currentScriptContainer.innerHTML = newScriptContainer.innerHTML;
                executeScriptsInContainer(currentScriptContainer);
            }

            if (pushState) {
                history.pushState({ path: href }, '', href);
            }

            updateActiveNavLinks(href);
            newMain.scrollTo(0, 0);

        } catch (error) {
            // An aborted request is NOT an error — a newer click superseded it.
            // Fully ignore it so it never triggers the full-reload fallback
            // (which would interrupt the newer navigation and feel like a
            // "double-click" / dead first click).
            if (error && error.name === 'AbortError') {
                return;
            }
            console.error('SPA navigation failed, falling back to full page load:', error);
            window.location.href = href; // Fallback for safety
        } finally {
            clearLinkLoading(clickedLink);
            isNavigating = false;
            if (activeController === controller) {
                activeController = null;
            }
        }
    };

    // --- Event Listeners ---
    document.addEventListener('click', (event) => {
        const link = event.target.closest('a');
        const isIgnored = !link || link.origin !== window.location.origin || link.hasAttribute('data-no-spa') || link.hasAttribute('download') || link.target === '_blank' || event.ctrlKey || event.metaKey || !['http:', 'https:'].includes(link.protocol) || (link.pathname === window.location.pathname && link.hash) || link.pathname.includes('/logout');
        if (isIgnored) return;

        event.preventDefault();
        navigate(link.href, true, link);
    });

    window.addEventListener('popstate', (event) => {
        if (event.state && event.state.path) {
            navigate(event.state.path, false);
        }
    });

    // --- Initial Setup ---
    // Store the initial URL in the history state for back/forward navigation.
    history.replaceState({ path: window.location.href }, '', window.location.href);
    updateActiveNavLinks(window.location.href);

})();