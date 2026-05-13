(function () {
    const nav = document.querySelector('.nav-glass');
    if (!nav) {
        return;
    }

    const navToggle = nav.querySelector('[data-nav-toggle]');
    const navLinks = nav.querySelector('.nav-glass__links');
    const dropdownWrappers = Array.from(nav.querySelectorAll('.nav-glass__dropdown-wrapper'));
    const dropdownTriggers = dropdownWrappers
        .map((wrapper) => wrapper.querySelector('[data-dropdown-trigger]'))
        .filter(Boolean);
    const dropdownItems = nav.querySelectorAll('a.dropdown-item');
    const finePointerDesktop = window.matchMedia('(min-width: 1081px) and (hover: hover) and (pointer: fine)');
    const openTimers = new WeakMap();
    const closeTimers = new WeakMap();

    const clearScheduled = (wrapper) => {
        const openTimer = openTimers.get(wrapper);
        if (openTimer) {
            window.clearTimeout(openTimer);
            openTimers.delete(wrapper);
        }

        const closeTimer = closeTimers.get(wrapper);
        if (closeTimer) {
            window.clearTimeout(closeTimer);
            closeTimers.delete(wrapper);
        }
    };

    const getTrigger = (wrapper) => wrapper.querySelector('[data-dropdown-trigger]');

    const getLineage = (wrapper) => {
        const lineage = [];
        let current = wrapper;

        while (current && current.classList.contains('nav-glass__dropdown-wrapper')) {
            lineage.push(current);
            current = current.parentElement?.closest('.nav-glass__dropdown-wrapper') || null;
        }

        return lineage;
    };

    const closeDropdowns = () => {
        dropdownWrappers.forEach((wrapper) => {
            clearScheduled(wrapper);
            wrapper.classList.remove('is-open');
            const trigger = getTrigger(wrapper);
            if (trigger) {
                trigger.setAttribute('aria-expanded', 'false');
            }
        });
    };

    const closeWrapper = (wrapper) => {
        clearScheduled(wrapper);
        wrapper.classList.remove('is-open');

        const trigger = getTrigger(wrapper);
        if (trigger) {
            trigger.setAttribute('aria-expanded', 'false');
        }

        dropdownWrappers.forEach((candidate) => {
            if (candidate !== wrapper && wrapper.contains(candidate)) {
                clearScheduled(candidate);
                candidate.classList.remove('is-open');
                const nestedTrigger = getTrigger(candidate);
                if (nestedTrigger) {
                    nestedTrigger.setAttribute('aria-expanded', 'false');
                }
            }
        });
    };

    const openWrapper = (wrapper) => {
        const lineage = new Set(getLineage(wrapper));

        dropdownWrappers.forEach((candidate) => {
            if (!lineage.has(candidate)) {
                closeWrapper(candidate);
            }
        });

        getLineage(wrapper).reverse().forEach((candidate) => {
            clearScheduled(candidate);
            candidate.classList.add('is-open');
            const trigger = getTrigger(candidate);
            if (trigger) {
                trigger.setAttribute('aria-expanded', 'true');
            }
        });
    };

    const scheduleOpen = (wrapper, delay = 70) => {
        clearScheduled(wrapper);
        openTimers.set(wrapper, window.setTimeout(() => {
            openTimers.delete(wrapper);
            openWrapper(wrapper);
        }, delay));
    };

    const scheduleClose = (wrapper, delay = 140) => {
        clearScheduled(wrapper);
        closeTimers.set(wrapper, window.setTimeout(() => {
            closeTimers.delete(wrapper);
            closeWrapper(wrapper);
        }, delay));
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
        trigger.addEventListener('click', (event) => {
            event.preventDefault();
            event.stopPropagation();

            const wrapper = trigger.closest('.nav-glass__dropdown-wrapper');
            if (!wrapper) {
                return;
            }

            const isOpen = wrapper.classList.contains('is-open');
            if (!isOpen) {
                openWrapper(wrapper);
                return;
            }

            closeWrapper(wrapper);
        });

        const wrapper = trigger.closest('.nav-glass__dropdown-wrapper');
        if (!wrapper) {
            return;
        }

        wrapper.addEventListener('focusin', () => {
            openWrapper(wrapper);
        });

        wrapper.addEventListener('focusout', () => {
            window.setTimeout(() => {
                if (!wrapper.contains(document.activeElement)) {
                    closeWrapper(wrapper);
                }
            }, 0);
        });

        wrapper.addEventListener('pointerenter', () => {
            if (!finePointerDesktop.matches) {
                return;
            }

            scheduleOpen(wrapper, wrapper.classList.contains('nav-glass__dropdown-wrapper--nested') ? 85 : 60);
        });

        wrapper.addEventListener('pointerleave', () => {
            if (!finePointerDesktop.matches) {
                return;
            }

            scheduleClose(wrapper, wrapper.classList.contains('nav-glass__dropdown-wrapper--nested') ? 150 : 130);
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
    const headerSystem = document.getElementById('headerSystem');
    const headerMain = document.getElementById('headerMain');
    const headerAccreditation = document.getElementById('headerAccreditation');
    const mobileNav = document.getElementById('mobileNav');
    const spacer = document.getElementById('headerSystemSpacer');
    const floatingDonate = document.querySelector('.floating-donate');

    if (!headerSystem || !headerMain || !headerAccreditation || !spacer) {
        return;
    }

    const mobileBreakpoint = window.matchMedia('(max-width: 1080px)');
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    const shortcutLinks = mobileNav
        ? Array.from(mobileNav.querySelectorAll('.expandable-icon'))
        : [];
    const pressables = mobileNav
        ? Array.from(mobileNav.querySelectorAll('.mobile-nav__hamburger, .expandable-icon, .mobile-nav__donate'))
        : [];

    const metrics = {
        topInset: 20,
        accreditationHeight: 0,
        mainHeight: 0,
        containerWidth: 0,
        collapseDistance: 1,
        morphDistance: 1,
        hideDistance: 1,
        totalDistance: 3,
        collapseEnd: 0.33,
        morphEnd: 0.75,
    };

    const controller = {
        state: 'expanded',
        ticking: false,
    };

    function clamp(value, min, max) {
        return Math.min(max, Math.max(min, value));
    }

    function easeInOutCubic(value) {
        if (value < 0.5) {
            return 4 * value * value * value;
        }

        return 1 - Math.pow(-2 * value + 2, 3) / 2;
    }

    function mapProgress(value) {
        return reducedMotion.matches ? value : easeInOutCubic(value);
    }

    function getStageProgress(progress, start, end) {
        if (end <= start) {
            return progress >= end ? 1 : 0;
        }

        return mapProgress(clamp((progress - start) / (end - start), 0, 1));
    }

    function setHeaderState(nextState) {
        if (controller.state === nextState) {
            return;
        }

        controller.state = nextState;
        headerSystem.dataset.headerState = nextState;
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

    function measureExpandedHeader() {
        const previousProgress = {
            progress: headerSystem.style.getPropertyValue('--header-progress'),
            collapse: headerSystem.style.getPropertyValue('--header-collapse-progress'),
            morph: headerSystem.style.getPropertyValue('--header-morph-progress'),
            hide: headerSystem.style.getPropertyValue('--header-hide-progress'),
        };

        headerSystem.style.setProperty('--header-progress', '0');
        headerSystem.style.setProperty('--header-collapse-progress', '0');
        headerSystem.style.setProperty('--header-morph-progress', '0');
        headerSystem.style.setProperty('--header-hide-progress', '0');

        const measurements = {
            mainHeight: headerMain.offsetHeight,
            accreditationHeight: headerAccreditation.offsetHeight,
        };

        headerSystem.style.setProperty('--header-progress', previousProgress.progress || '0');
        headerSystem.style.setProperty('--header-collapse-progress', previousProgress.collapse || '0');
        headerSystem.style.setProperty('--header-morph-progress', previousProgress.morph || '0');
        headerSystem.style.setProperty('--header-hide-progress', previousProgress.hide || '0');

        return measurements;
    }

    function updateMetrics() {
        const headerStyles = window.getComputedStyle(headerSystem);
        const measurements = measureExpandedHeader();
        const isMobile = mobileBreakpoint.matches;
        const maxWidth = parseFloat(headerStyles.getPropertyValue('--header-max-width')) || (isMobile ? 440 : 1180);
        const sideInset = parseFloat(headerStyles.getPropertyValue('--header-side-inset')) || (isMobile ? 12 : 24);

        metrics.topInset = parseFloat(headerStyles.getPropertyValue('--header-inset-top')) || (isMobile ? 16 : 20);
        metrics.accreditationHeight = measurements.accreditationHeight;
        metrics.mainHeight = measurements.mainHeight;
        metrics.containerWidth = Math.min(window.innerWidth - (sideInset * 2), maxWidth);
        metrics.collapseDistance = Math.max(
            metrics.accreditationHeight * (isMobile ? 0.86 : 0.76),
            isMobile ? 88 : 112
        );
        metrics.morphDistance = Math.max(metrics.mainHeight * (isMobile ? 0.92 : 1.08), isMobile ? 84 : 128);
        metrics.hideDistance = Math.max(
            metrics.mainHeight + metrics.topInset + (isMobile ? 20 : 28),
            isMobile ? 74 : 96
        );
        metrics.totalDistance = metrics.collapseDistance + metrics.morphDistance + metrics.hideDistance;
        metrics.collapseEnd = metrics.collapseDistance / metrics.totalDistance;
        metrics.morphEnd = (metrics.collapseDistance + metrics.morphDistance) / metrics.totalDistance;

        const compactWidth = isMobile
            ? Math.min(Math.max(metrics.containerWidth - 48, 280), 356)
            : Math.min(Math.max(metrics.containerWidth * 0.76, 760), 920);
        const mainCompactHeight = Math.max(metrics.mainHeight - (isMobile ? 6 : 8), isMobile ? 56 : 64);
        const spacerHeight = Math.round(metrics.topInset + metrics.accreditationHeight + metrics.mainHeight);

        headerSystem.style.setProperty('--header-system-height', `${spacerHeight}px`);
        headerSystem.style.setProperty('--header-accredit-travel', `${Math.max(metrics.accreditationHeight * 0.9, isMobile ? 72 : 96)}px`);
        headerSystem.style.setProperty('--header-hide-travel', `${Math.max(metrics.mainHeight + metrics.topInset + 24, isMobile ? 76 : 98)}px`);
        headerSystem.style.setProperty('--header-width-start', `${metrics.containerWidth}px`);
        headerSystem.style.setProperty('--header-width-end', `${Math.min(metrics.containerWidth, compactWidth)}px`);
        headerSystem.style.setProperty('--header-main-height-start', `${metrics.mainHeight}px`);
        headerSystem.style.setProperty('--header-main-height-end', `${mainCompactHeight}px`);
        headerSystem.style.setProperty('--header-main-pad-x-start', `${isMobile ? 12 : 22}px`);
        headerSystem.style.setProperty('--header-main-pad-x-end', `${isMobile ? 10 : 16}px`);
        headerSystem.style.setProperty('--header-main-pad-y-start', `${isMobile ? 9 : 12}px`);
        headerSystem.style.setProperty('--header-main-pad-y-end', `${isMobile ? 7 : 9}px`);
        headerSystem.style.setProperty('--header-accreditation-height', `${metrics.accreditationHeight}px`);
        spacer.style.height = `${spacerHeight}px`;
    }

    function render() {
        const currentScrollY = Math.max(window.scrollY || 0, 0);
        const totalDistance = Math.max(metrics.totalDistance, 1);
        const progress = clamp(currentScrollY / totalDistance, 0, 1);
        const collapseProgress = getStageProgress(progress, 0, metrics.collapseEnd);
        const morphProgress = getStageProgress(progress, metrics.collapseEnd, metrics.morphEnd);
        const hideProgress = getStageProgress(progress, metrics.morphEnd, 1);

        if (floatingDonate) {
            floatingDonate.classList.toggle(
                'is-visible',
                currentScrollY > Math.max(170, metrics.collapseDistance + (metrics.morphDistance * 0.55))
            );
        }

        headerSystem.style.setProperty('--header-progress', progress.toFixed(4));
        headerSystem.style.setProperty('--header-collapse-progress', collapseProgress.toFixed(4));
        headerSystem.style.setProperty('--header-morph-progress', morphProgress.toFixed(4));
        headerSystem.style.setProperty('--header-hide-progress', hideProgress.toFixed(4));

        if (hideProgress >= 0.995) {
            setHeaderState('hidden');
        } else if (hideProgress > 0.001) {
            setHeaderState('hiding');
        } else if (morphProgress >= 0.995) {
            setHeaderState('compact');
        } else if (morphProgress > 0.001) {
            setHeaderState('morphing');
        } else if (collapseProgress > 0.001) {
            setHeaderState('collapsing');
        } else {
            setHeaderState('expanded');
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
    window.addEventListener('load', handleViewportChange);
    bindMediaChange(mobileBreakpoint, handleViewportChange);
    bindMediaChange(reducedMotion, () => scheduleRender(true));

    if (typeof ResizeObserver === 'function') {
        const resizeObserver = new ResizeObserver(() => {
            updateMetrics();
            scheduleRender(true);
        });

        resizeObserver.observe(headerMain);
        resizeObserver.observe(headerAccreditation);
    }
})();

(function () {
    const container = document.querySelector('[data-hero-slideshow]');
    if (!container) {
        return;
    }

    const slides = Array.from(container.querySelectorAll('.hero-slide'));
    const dots = Array.from(container.querySelectorAll('[data-hero-dot]'));
    const nextButton = container.querySelector('[data-hero-next]');
    const prevButton = container.querySelector('[data-hero-prev]');
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

    if (!slides.length) {
        return;
    }

    const state = {
        currentIndex: Math.max(slides.findIndex((slide) => slide.classList.contains('is-active')), 0),
        autoplayId: null,
        cleanupTimerId: null,
    };

    function setSlideAccessibility() {
        slides.forEach((slide, index) => {
            const isCurrent = index === state.currentIndex;
            slide.setAttribute('aria-hidden', String(!isCurrent));
            slide.classList.toggle('is-active', isCurrent);
        });

        dots.forEach((dot, index) => {
            const isCurrent = index === state.currentIndex;
            dot.classList.toggle('is-active', isCurrent);
            dot.setAttribute('aria-current', String(isCurrent));
        });
    }

    function stopAutoplay() {
        if (state.autoplayId) {
            window.clearInterval(state.autoplayId);
            state.autoplayId = null;
        }
    }

    function startAutoplay() {
        stopAutoplay();

        if (slides.length <= 1 || reducedMotion.matches) {
            return;
        }

        state.autoplayId = window.setInterval(() => {
            goToSlide(state.currentIndex + 1);
        }, 5500);
    }

    function goToSlide(nextIndex) {
        const normalizedIndex = (nextIndex + slides.length) % slides.length;
        if (normalizedIndex === state.currentIndex) {
            return;
        }

        const previousSlide = slides[state.currentIndex];

        previousSlide.classList.remove('is-active');
        previousSlide.classList.add('was-active');

        state.currentIndex = normalizedIndex;
        slides[normalizedIndex].classList.add('is-active');
        setSlideAccessibility();

        if (state.cleanupTimerId) {
            window.clearTimeout(state.cleanupTimerId);
        }

        state.cleanupTimerId = window.setTimeout(() => {
            previousSlide.classList.remove('was-active');
        }, reducedMotion.matches ? 0 : 820);
    }

    nextButton?.addEventListener('click', () => {
        goToSlide(state.currentIndex + 1);
        startAutoplay();
    });

    prevButton?.addEventListener('click', () => {
        goToSlide(state.currentIndex - 1);
        startAutoplay();
    });

    dots.forEach((dot, index) => {
        dot.addEventListener('click', () => {
            if (index === state.currentIndex) {
                return;
            }

            goToSlide(index);
            startAutoplay();
        });
    });

    container.addEventListener('mouseenter', stopAutoplay);
    container.addEventListener('mouseleave', startAutoplay);
    container.addEventListener('focusin', stopAutoplay);
    container.addEventListener('focusout', (event) => {
        if (!container.contains(event.relatedTarget)) {
            startAutoplay();
        }
    });

    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            stopAutoplay();
        } else {
            startAutoplay();
        }
    });

    setSlideAccessibility();
    startAutoplay();
})();

// ---- Scroll Reveal Blocks ----
(function () {
    const revealItems = Array.from(document.querySelectorAll('[data-reveal]'));
    if (!revealItems.length) {
        return;
    }

    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    if (reducedMotion.matches || typeof IntersectionObserver !== 'function') {
        revealItems.forEach((item) => item.classList.add('is-visible'));
        return;
    }

    const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (!entry.isIntersecting) {
                return;
            }

            entry.target.classList.add('is-visible');
            observer.unobserve(entry.target);
        });
    }, {
        threshold: 0.14,
        rootMargin: '0px 0px -48px 0px',
    });

    revealItems.forEach((item) => observer.observe(item));
})();

// ---- Initiative Gallery — Thumbnail Swap ----
(function () {
    const galleries = document.querySelectorAll('[data-initiative-gallery]');
    if (!galleries.length) return;

    galleries.forEach(function (gallery) {
        const mainImg = gallery.querySelector('[data-gallery-main]');
        const thumbs = Array.from(gallery.querySelectorAll('[data-gallery-thumb]'));
        if (!mainImg || thumbs.length < 2) return;

        thumbs.forEach(function (thumb) {
            thumb.addEventListener('click', function () {
                var newSrc = thumb.getAttribute('data-src');
                var newAlt = thumb.getAttribute('data-alt') || '';

                // Skip if already active
                if (thumb.classList.contains('is-active')) return;

                // Fade out current image
                mainImg.classList.add('is-fading');

                setTimeout(function () {
                    mainImg.src = newSrc;
                    mainImg.alt = newAlt;

                    // Wait for image load then fade in
                    mainImg.onload = function () {
                        mainImg.classList.remove('is-fading');
                        mainImg.onload = null;
                    };

                    // Fallback: remove fade if image already cached
                    if (mainImg.complete) {
                        mainImg.classList.remove('is-fading');
                        mainImg.onload = null;
                    }
                }, 300);

                // Update active states
                thumbs.forEach(function (t) { t.classList.remove('is-active'); });
                thumb.classList.add('is-active');
            });
        });
    });
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

// ---- Community Members Queue (Home Page) ----
(function () {
    const gridContainer = document.getElementById('communityGrid');
    if (!gridContainer) return;

    let membersData = [];
    try {
        membersData = JSON.parse(gridContainer.getAttribute('data-members') || '[]');
    } catch (e) {
        console.error('Failed to parse community members data', e);
        return;
    }

    if (membersData.length === 0) return;

    const MAX_DISPLAY = Math.min(10, membersData.length);
    let displayQueue = membersData.slice(0, MAX_DISPLAY);
    let waitingQueue = membersData.slice(MAX_DISPLAY);

    // Helper to generate HTML for a member
    const createMemberHTML = (member) => `
        <div class="community-member" data-id="${member.id}">
            <div class="community-member__photo-wrapper">
                <img src="${member.photo_url || '/static/photos/placeholder-user.png'}" alt="${member.name}" class="community-member__photo" loading="lazy">
            </div>
            <h3 class="community-member__name">${member.name}</h3>
            <p class="community-member__qual">${member.qualification}</p>
        </div>
    `;

    // Initialize grid
    gridContainer.innerHTML = displayQueue.map(createMemberHTML).join('');

    // If we have 10 or fewer members, no need to cycle
    if (waitingQueue.length === 0) return;

    let intervalId = null;

    const cycleMember = () => {
        // Pick a random currently displayed member to replace
        const randomIndex = Math.floor(Math.random() * displayQueue.length);
        const slotToReplace = gridContainer.children[randomIndex];
        const oldMember = displayQueue[randomIndex];

        // Pick the first person from the waiting queue
        const newMember = waitingQueue.shift();

        // Animate out
        slotToReplace.classList.add('fade-out');

        setTimeout(() => {
            // Swap in memory
            displayQueue[randomIndex] = newMember;
            waitingQueue.push(oldMember); // put old member back in waiting line

            // Update DOM
            slotToReplace.outerHTML = createMemberHTML(newMember);
            const newSlot = gridContainer.children[randomIndex];
            
            // Force reflow and animate in
            void newSlot.offsetWidth;
            newSlot.classList.add('fade-in');
        }, 600); // Wait for fade-out to finish
    };

    // Intersection Observer to only run animation when visible
    const observer = new IntersectionObserver((entries) => {
        const isVisible = entries[0].isIntersecting;
        if (isVisible && !intervalId) {
            intervalId = setInterval(cycleMember, 4000); // Swap every 4 seconds
        } else if (!isVisible && intervalId) {
            clearInterval(intervalId);
            intervalId = null;
        }
    }, { threshold: 0.1 });

    observer.observe(document.getElementById('community-queue'));
})();
