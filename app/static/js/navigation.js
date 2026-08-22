/**
 * SalahMate SPA Navigation
 * TEMP DEBUG VERSION
 *
 * This version temporarily disables SPA content swapping
 * and uses normal full-page navigation.
 */
(function() {
    // isNavigating is informational.
    let isNavigating = false;

    /**
     * Manually executes scripts from a given container.
     * Kept here for later when SPA navigation is restored.
     */
    const executeScriptsInContainer = (container) => {
        if (!container) return;

        const scripts = Array.from(
            container.querySelectorAll('script')
        );

        scripts.forEach(oldScript => {
            const newScript = document.createElement('script');

            Array.from(oldScript.attributes).forEach(attr => {
                newScript.setAttribute(
                    attr.name,
                    attr.value
                );
            });

            if (oldScript.innerHTML) {
                newScript.innerHTML = oldScript.innerHTML;
            }

            oldScript.parentNode.replaceChild(
                newScript,
                oldScript
            );
        });
    };

    /**
     * Updates active state on navigation links.
     */
    const updateActiveNavLinks = (href) => {
        const url = new URL(
            href,
            window.location.origin
        );

        const pathname = url.pathname;

        document
            .querySelectorAll(
                '.sidebar .active, .mobile-nav .active'
            )
            .forEach(el => {
                el.classList.remove('active');
            });

        document
            .querySelectorAll(
                '.sidebar a, .mobile-nav a'
            )
            .forEach(link => {
                const linkUrl = new URL(link.href);

                if (
                    linkUrl.pathname === pathname &&
                    linkUrl.search === url.search
                ) {
                    link.classList.add('active');

                    const parentSubmenu =
                        link.closest('.submenu');

                    if (parentSubmenu) {
                        const parent =
                            parentSubmenu.previousElementSibling;

                        if (parent) {
                            parent.classList.add('active');
                        }

                        const menuItem =
                            link.closest(
                                '.nav-item-with-submenu'
                            );

                        if (menuItem) {
                            menuItem.classList.add('open');
                        }
                    }
                }
            });
    };

    /**
     * Shows loading state on clicked link.
     */
    const showLinkLoading = (link) => {
        if (
            !link ||
            link.hasAttribute('data-nav-loading')
        ) {
            return;
        }

        const originalHTML = link.innerHTML;

        link.setAttribute(
            'data-nav-loading',
            '1'
        );

        link.setAttribute(
            'data-nav-original-html',
            originalHTML
        );

        link.innerHTML =
            '<i class="fas fa-spinner fa-spin"></i>';

        link.style.opacity = '0.75';
        link.style.pointerEvents = 'none';
    };

    /**
     * Restores clicked link.
     */
    const clearLinkLoading = (link) => {
        if (
            !link ||
            !link.hasAttribute('data-nav-loading')
        ) {
            return;
        }

        const originalHTML =
            link.getAttribute(
                'data-nav-original-html'
            );

        if (originalHTML !== null) {
            link.innerHTML = originalHTML;
        }

        link.removeAttribute(
            'data-nav-loading'
        );

        link.removeAttribute(
            'data-nav-original-html'
        );

        link.style.opacity = '';
        link.style.pointerEvents = '';
    };

    /**
     * TEMPORARY DEBUG NAVIGATION
     *
     * Instead of fetching HTML and replacing <main>,
     * perform a normal browser navigation.
     *
     * This guarantees that:
     * - base.html reloads
     * - quran.js loads normally
     * - reader.html loads normally
     * - all CSS loads normally
     * - service-worker/browser SPA swapping is bypassed
     *
     * If the new 3D player appears after this change,
     * the problem is confirmed to be SPA navigation.
     */
    let activeController = null;

    const navigate = async (
        href,
        pushState = true,
        clickedLink = null
    ) => {
        // Cancel any previous navigation.
        if (activeController) {
            activeController.abort();
        }

        const controller =
            new AbortController();

        activeController = controller;
        isNavigating = true;

        showLinkLoading(clickedLink);

        /*
         * =====================================================
         * TEMPORARY FULL-PAGE NAVIGATION
         * =====================================================
         *
         * Do NOT use fetch() + replaceWith() for this test.
         *
         * A normal navigation forces the browser to rebuild
         * the complete page and execute quran.js from scratch.
         */

        window.location.href = href;

        return;
    };

    // =========================================================
    // Mobile Sidebar Toggle
    // =========================================================

    document.addEventListener(
        'click',
        (event) => {

            const toggle =
                event.target.closest(
                    '.mobile-menu-toggle'
                );

            if (!toggle) return;

            const sidebar =
                document.querySelector(
                    '.sidebar'
                );

            if (!sidebar) return;

            const isOpen =
                sidebar.classList.toggle(
                    'open'
                );

            toggle.setAttribute(
                'aria-expanded',
                isOpen ? 'true' : 'false'
            );

            toggle.setAttribute(
                'aria-label',
                isOpen
                    ? 'Close menu'
                    : 'Open menu'
            );
        }
    );


    // =========================================================
    // Quran / Sidebar Submenu Toggle
    // =========================================================

    document.addEventListener(
        'click',
        (event) => {

            const parent =
                event.target.closest(
                    '.nav-link-parent'
                );

            if (!parent) return;

            const menuItem =
                parent.closest(
                    '.nav-item-with-submenu'
                );

            if (!menuItem) return;

            // Stop normal anchor navigation.
            event.preventDefault();
            event.stopPropagation();

            // Close other open submenus.
            document
                .querySelectorAll(
                    '.nav-item-with-submenu.open'
                )
                .forEach(item => {

                    if (item !== menuItem) {
                        item.classList.remove(
                            'open'
                        );
                    }
                });

            // Toggle clicked submenu.
            menuItem.classList.toggle(
                'open'
            );
        }
    );


    // =========================================================
    // Normal Navigation
    // =========================================================

    document.addEventListener(
        'click',
        (event) => {

            const link =
                event.target.closest('a');

            const isIgnored =
                !link ||
                link.origin !==
                    window.location.origin ||
                link.hasAttribute(
                    'data-no-spa'
                ) ||
                link.hasAttribute(
                    'download'
                ) ||
                link.target === '_blank' ||
                event.ctrlKey ||
                event.metaKey ||
                ![
                    'http:',
                    'https:'
                ].includes(
                    link.protocol
                ) ||
                (
                    link.pathname ===
                        window.location.pathname &&
                    link.hash
                ) ||
                link.pathname.includes(
                    '/logout'
                );

            if (isIgnored) return;

            event.preventDefault();

            /*
             * IMPORTANT:
             * This now performs a COMPLETE browser reload.
             */
            navigate(
                link.href,
                true,
                link
            );
        }
    );


    // =========================================================
    // Browser Back / Forward
    // =========================================================

    window.addEventListener(
        'popstate',
        (event) => {

            /*
             * For this debug version we let the browser
             * handle normal history navigation.
             *
             * No SPA fetch here.
             */
            return;
        }
    );


    // =========================================================
    // Initial Setup
    // =========================================================

    history.replaceState(
        {
            path: window.location.href
        },
        '',
        window.location.href
    );

    updateActiveNavLinks(
        window.location.href
    );

})();