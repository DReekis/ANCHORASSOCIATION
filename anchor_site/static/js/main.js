(function () {
    const nav = document.querySelector('.nav-glass');
    if (!nav) {
        return;
    }

    const navToggle = nav.querySelector('[data-nav-toggle]');
    const navLinks = nav.querySelector('.nav-glass__links');
    const dropdownTriggers = nav.querySelectorAll('[data-dropdown-trigger]');
    const dropdownItems = nav.querySelectorAll('.dropdown-item');

    const closeDropdowns = () => {
        nav.querySelectorAll('.nav-glass__dropdown-wrapper').forEach((wrapper) => {
            wrapper.classList.remove('is-open');
            const trigger = wrapper.querySelector('[data-dropdown-trigger]');
            if (trigger) {
                trigger.setAttribute('aria-expanded', 'false');
            }
        });
    };

    const setNavExpanded = (expanded) => {
        nav.classList.toggle('is-expanded', expanded);
        navLinks?.classList.toggle('active', expanded);
        navToggle?.setAttribute('aria-expanded', String(expanded));

        if (!expanded) {
            closeDropdowns();
        }
    };

    navToggle?.addEventListener('click', () => {
        const expanded = navToggle.getAttribute('aria-expanded') === 'true';
        setNavExpanded(!expanded);
    });

    dropdownTriggers.forEach((trigger) => {
        trigger.addEventListener('click', () => {
            const wrapper = trigger.closest('.nav-glass__dropdown-wrapper');
            if (!wrapper) {
                return;
            }

            const isOpen = wrapper.classList.contains('is-open');
            closeDropdowns();

            if (!isOpen) {
                wrapper.classList.add('is-open');
                trigger.setAttribute('aria-expanded', 'true');
            }
        });
    });

    dropdownItems.forEach((item) => {
        item.addEventListener('click', () => {
            setNavExpanded(false);
        });
    });

    document.addEventListener('click', (event) => {
        if (!nav.contains(event.target)) {
            setNavExpanded(false);
        }
    });

    window.addEventListener('resize', () => {
        closeDropdowns();
        if (window.innerWidth > 1080) {
            setNavExpanded(false);
        }
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            setNavExpanded(false);
        }
    });
})();

(function () {
    const stack = document.getElementById('mobileNavStack');
    const mobileNav = document.getElementById('mobileNav');
    const accreditationBar = document.getElementById('accreditationBar');
    const spacer = document.getElementById('mobileNavStackSpacer');
    const floatingDonate = document.querySelector('.floating-donate');

    if (!stack || !mobileNav || !accreditationBar || !spacer) {
        return;
    }

    const mobileBreakpoint = window.matchMedia('(max-width: 1080px)');
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    const shortcutLinks = Array.from(mobileNav.querySelectorAll('.expandable-icon'));
    const pressables = Array.from(
        mobileNav.querySelectorAll('.mobile-nav__hamburger, .expandable-icon, .mobile-nav__donate')
    );

    const metrics = {
        accreditationTravel: 0,
        collapseDistance: 1,
        hideDistance: 1,
        totalDistance: 2,
        stackHeight: 0,
        shellLift: 0,
        shellHideOffset: 0,
    };

    const controller = {
        state: 'expanded',
        ticking: false,
    };

    const easePremium = createCubicBezier(0.16, 1, 0.3, 1);

    function clamp(value, min, max) {
        return Math.min(max, Math.max(min, value));
    }

    function createCubicBezier(mX1, mY1, mX2, mY2) {
        const NEWTON_ITERATIONS = 4;
        const NEWTON_MIN_SLOPE = 0.001;
        const SUBDIVISION_PRECISION = 0.0000001;
        const SUBDIVISION_MAX_ITERATIONS = 10;
        const SPLINE_TABLE_SIZE = 11;
        const SAMPLE_STEP_SIZE = 1.0 / (SPLINE_TABLE_SIZE - 1.0);

        const sampleValues = new Float32Array(SPLINE_TABLE_SIZE);

        function calcBezier(t, a1, a2) {
            return (((1.0 - 3.0 * a2 + 3.0 * a1) * t + (3.0 * a2 - 6.0 * a1)) * t + (3.0 * a1)) * t;
        }

        function getSlope(t, a1, a2) {
            return 3.0 * (1.0 - 3.0 * a2 + 3.0 * a1) * t * t + 2.0 * (3.0 * a2 - 6.0 * a1) * t + (3.0 * a1);
        }

        function binarySubdivide(x, a, b) {
            let currentX;
            let currentT;
            let i = 0;

            do {
                currentT = a + (b - a) / 2.0;
                currentX = calcBezier(currentT, mX1, mX2) - x;
                if (currentX > 0.0) {
                    b = currentT;
                } else {
                    a = currentT;
                }
                i += 1;
            } while (Math.abs(currentX) > SUBDIVISION_PRECISION && i < SUBDIVISION_MAX_ITERATIONS);

            return currentT;
        }

        function newtonRaphsonIterate(x, guessT) {
            let t = guessT;

            for (let i = 0; i < NEWTON_ITERATIONS; i += 1) {
                const currentSlope = getSlope(t, mX1, mX2);
                if (currentSlope === 0.0) {
                    return t;
                }
                const currentX = calcBezier(t, mX1, mX2) - x;
                t -= currentX / currentSlope;
            }

            return t;
        }

        for (let i = 0; i < SPLINE_TABLE_SIZE; i += 1) {
            sampleValues[i] = calcBezier(i * SAMPLE_STEP_SIZE, mX1, mX2);
        }

        function getTForX(x) {
            let intervalStart = 0.0;
            let currentSample = 1;
            const lastSample = SPLINE_TABLE_SIZE - 1;

            while (currentSample !== lastSample && sampleValues[currentSample] <= x) {
                intervalStart += SAMPLE_STEP_SIZE;
                currentSample += 1;
            }
            currentSample -= 1;

            const dist = (x - sampleValues[currentSample]) /
                (sampleValues[currentSample + 1] - sampleValues[currentSample]);
            const guessForT = intervalStart + dist * SAMPLE_STEP_SIZE;
            const initialSlope = getSlope(guessForT, mX1, mX2);

            if (initialSlope >= NEWTON_MIN_SLOPE) {
                return newtonRaphsonIterate(x, guessForT);
            }

            if (initialSlope === 0.0) {
                return guessForT;
            }

            return binarySubdivide(x, intervalStart, intervalStart + SAMPLE_STEP_SIZE);
        }

        return (x) => {
            if (x <= 0) {
                return 0;
            }
            if (x >= 1) {
                return 1;
            }
            return calcBezier(getTForX(x), mY1, mY2);
        };
    }

    function mapProgress(value) {
        return reducedMotion.matches ? value : easePremium(value);
    }

    function setStackState(nextState) {
        if (controller.state === nextState) {
            return;
        }

        controller.state = nextState;
        stack.dataset.navState = nextState;
    }

    function resetStackStyles() {
        setStackState('expanded');

        stack.style.setProperty('--nav-stack-offset', '0px');
        stack.style.setProperty('--nav-collapse-progress', '0');
        stack.style.setProperty('--nav-hide-progress', '0');
        stack.style.setProperty('--nav-shell-shift', '0px');
        stack.style.setProperty('--nav-shell-scale', '1');
        stack.style.setProperty('--nav-accredit-shift', '0px');
        stack.style.setProperty('--nav-accredit-scale', '1');
        stack.style.setProperty('--nav-accredit-opacity', '1');
        stack.style.setProperty('--nav-logo-opacity', '1');
        stack.style.setProperty('--nav-logo-shift', '0px');
        stack.style.setProperty('--nav-logo-scale', '1');
        stack.style.setProperty('--nav-brand-shift', '0px');
        stack.style.setProperty('--nav-brand-opacity', '1');
        stack.style.setProperty('--nav-subtitle-shift', '0px');
        stack.style.setProperty('--nav-subtitle-opacity', '1');
        stack.style.setProperty('--nav-details-shift', '0px');
        stack.style.setProperty('--nav-details-opacity', '1');
        stack.style.setProperty('--nav-frost-opacity', '0.22');
        stack.style.setProperty('--nav-highlight-opacity', '0.48');
        stack.style.setProperty('--nav-merge-opacity', '0.86');
        stack.style.setProperty('--nav-halo-opacity', '0.28');
    }

    function updateShortcutStates() {
        const pathName = window.location.pathname;

        shortcutLinks.forEach((link) => {
            const href = link.getAttribute('href');
            if (!href) {
                return;
            }

            const linkUrl = new URL(href, window.location.origin);
            const isActive = linkUrl.pathname !== '/' && pathName.startsWith(linkUrl.pathname);
            link.classList.toggle('active', isActive);
        });
    }

    function updateMetrics() {
        if (!mobileBreakpoint.matches) {
            spacer.style.removeProperty('height');
            return;
        }

        const accreditationMarginTop = parseFloat(window.getComputedStyle(accreditationBar).marginTop) || 0;
        const navHeight = mobileNav.offsetHeight;
        const accreditationHeight = accreditationBar.offsetHeight;

        metrics.stackHeight = Math.max(
            navHeight,
            navHeight + accreditationHeight + accreditationMarginTop
        );
        metrics.accreditationTravel = Math.max(accreditationHeight + accreditationMarginTop - 6, 28);
        metrics.collapseDistance = Math.max(accreditationHeight * 0.96, 88);
        metrics.hideDistance = Math.max(navHeight * 1.08, 72);
        metrics.totalDistance = metrics.collapseDistance + metrics.hideDistance;
        metrics.shellLift = Math.max(navHeight * 0.05, 2);
        metrics.shellHideOffset = Math.max(navHeight + 20, 74);

        spacer.style.height = `${metrics.stackHeight}px`;
        stack.style.setProperty('--mobile-nav-stack-height', `${metrics.stackHeight}px`);
    }

    function render() {
        const currentScrollY = Math.max(window.scrollY || 0, 0);

        if (floatingDonate) {
            floatingDonate.classList.toggle('is-visible', currentScrollY > Math.max(170, metrics.collapseDistance + 40));
        }

        if (!mobileBreakpoint.matches) {
            resetStackStyles();
            return;
        }

        const travel = clamp(currentScrollY, 0, metrics.totalDistance);
        const collapseRaw = clamp(travel / metrics.collapseDistance, 0, 1);
        const hideRaw = clamp((travel - metrics.collapseDistance) / metrics.hideDistance, 0, 1);
        const totalRaw = clamp(travel / metrics.totalDistance, 0, 1);

        const collapseProgress = mapProgress(collapseRaw);
        const hideProgress = mapProgress(hideRaw);
        const totalProgress = mapProgress(totalRaw);
        const accreditationOpacity = clamp(1 - collapseProgress * 1.08, 0, 1);
        const subtitleOpacity = clamp(1 - collapseProgress * 1.28, 0, 1);
        const detailsOpacity = clamp(1 - collapseProgress * 0.94, 0, 1);
        const haloOpacity = clamp(0.24 + totalProgress * 0.16 - hideProgress * 0.08, 0.18, 0.38);
        const frostOpacity = clamp(0.22 + collapseProgress * 0.28, 0.22, 0.52);
        const highlightOpacity = clamp(0.48 + collapseProgress * 0.18, 0.48, 0.68);
        const mergeOpacity = clamp(0.86 - collapseProgress * 1.1, 0, 0.86);

        stack.style.setProperty('--nav-stack-offset', `${(-hideProgress * metrics.shellHideOffset).toFixed(2)}px`);
        stack.style.setProperty('--nav-collapse-progress', collapseProgress.toFixed(4));
        stack.style.setProperty('--nav-hide-progress', hideProgress.toFixed(4));
        stack.style.setProperty('--nav-shell-shift', `${(-collapseProgress * metrics.shellLift).toFixed(2)}px`);
        stack.style.setProperty('--nav-shell-scale', `${(1 - hideProgress * 0.024).toFixed(4)}`);
        stack.style.setProperty('--nav-accredit-shift', `${(-collapseProgress * metrics.accreditationTravel).toFixed(2)}px`);
        stack.style.setProperty('--nav-accredit-scale', `${(1 - collapseProgress * 0.1).toFixed(4)}`);
        stack.style.setProperty('--nav-accredit-opacity', accreditationOpacity.toFixed(4));
        stack.style.setProperty('--nav-logo-opacity', `${(1 - collapseProgress * 0.16).toFixed(4)}`);
        stack.style.setProperty('--nav-logo-shift', `${(-collapseProgress * 2.5).toFixed(2)}px`);
        stack.style.setProperty('--nav-logo-scale', `${(1 - collapseProgress * 0.045).toFixed(4)}`);
        stack.style.setProperty('--nav-brand-shift', `${(-collapseProgress * 10).toFixed(2)}px`);
        stack.style.setProperty('--nav-brand-opacity', `${(1 - collapseProgress * 0.14).toFixed(4)}`);
        stack.style.setProperty('--nav-subtitle-shift', `${(-collapseProgress * 8).toFixed(2)}px`);
        stack.style.setProperty('--nav-subtitle-opacity', subtitleOpacity.toFixed(4));
        stack.style.setProperty('--nav-details-shift', `${(-collapseProgress * 6).toFixed(2)}px`);
        stack.style.setProperty('--nav-details-opacity', detailsOpacity.toFixed(4));
        stack.style.setProperty('--nav-frost-opacity', frostOpacity.toFixed(4));
        stack.style.setProperty('--nav-highlight-opacity', highlightOpacity.toFixed(4));
        stack.style.setProperty('--nav-merge-opacity', mergeOpacity.toFixed(4));
        stack.style.setProperty('--nav-halo-opacity', haloOpacity.toFixed(4));

        if (hideRaw >= 0.995) {
            setStackState('hidden');
        } else if (collapseRaw >= 0.995) {
            setStackState('collapsed');
        } else if (collapseRaw > 0.001) {
            setStackState('collapsing');
        } else {
            setStackState('expanded');
        }
    }

    function scheduleRender(forceImmediate = false) {
        if (forceImmediate) {
            controller.ticking = false;
            render();
            return;
        }

        if (controller.ticking) {
            return;
        }

        controller.ticking = true;
        window.requestAnimationFrame(() => {
            controller.ticking = false;
            render();
        });
    }

    function queueDonateSpring(button) {
        if (reducedMotion.matches || !button.classList.contains('mobile-nav__donate')) {
            return;
        }

        button.classList.remove('is-springing');
        window.requestAnimationFrame(() => {
            button.classList.add('is-springing');
        });
    }

    function attachPressInteractions() {
        pressables.forEach((element) => {
            const clearPressedState = () => {
                element.classList.remove('is-pressed');
            };

            element.addEventListener('pointerdown', () => {
                element.classList.add('is-pressed');
            });

            element.addEventListener('pointerup', () => {
                clearPressedState();
                queueDonateSpring(element);
            });

            element.addEventListener('pointerleave', clearPressedState);
            element.addEventListener('pointercancel', clearPressedState);
            element.addEventListener('blur', clearPressedState);
            element.addEventListener('animationend', () => {
                element.classList.remove('is-springing');
            });
        });
    }

    function handleViewportChange() {
        updateMetrics();
        scheduleRender(true);
    }

    function bindMediaChange(mediaQueryList, handler) {
        if (typeof mediaQueryList.addEventListener === 'function') {
            mediaQueryList.addEventListener('change', handler);
            return;
        }

        if (typeof mediaQueryList.addListener === 'function') {
            mediaQueryList.addListener(handler);
        }
    }

    updateShortcutStates();
    attachPressInteractions();
    updateMetrics();
    scheduleRender(true);

    window.addEventListener('scroll', () => {
        scheduleRender();
    }, { passive: true });

    window.addEventListener('resize', handleViewportChange);
    bindMediaChange(mobileBreakpoint, handleViewportChange);
    bindMediaChange(reducedMotion, () => scheduleRender(true));

    if (typeof ResizeObserver === 'function') {
        const resizeObserver = new ResizeObserver(() => {
            updateMetrics();
            scheduleRender(true);
        });

        resizeObserver.observe(mobileNav);
        resizeObserver.observe(accreditationBar);
    }
})();

// ---- Gallery Slideshow (Home Page) ----
(function () {
    const slideshow = document.getElementById('gallerySlideshow');
    if (!slideshow) {
        return;
    }

    const slides = slideshow.querySelectorAll('.gallery-slide');
    if (slides.length <= 1) {
        return;
    }

    let current = 0;

    window.setInterval(() => {
        slides[current].classList.remove('active');
        current = (current + 1) % slides.length;
        slides[current].classList.add('active');
    }, 3000);
})();
