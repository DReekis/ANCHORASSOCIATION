console.log('Anchor Association - Site loaded');

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

    navToggle?.addEventListener('click', () => {
        const expanded = navToggle.getAttribute('aria-expanded') === 'true';
        navToggle.setAttribute('aria-expanded', String(!expanded));
        navLinks?.classList.toggle('active');

        if (expanded) {
            closeDropdowns();
        }
    });

    dropdownTriggers.forEach((trigger) => {
        trigger.addEventListener('click', (event) => {
            if (window.innerWidth > 1080) {
                event.preventDefault();
            }

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
            closeDropdowns();
            navLinks?.classList.remove('active');
            navToggle?.setAttribute('aria-expanded', 'false');
        });
    });

    document.addEventListener('click', (event) => {
        if (!nav.contains(event.target)) {
            closeDropdowns();
        }
    });

    window.addEventListener('resize', () => {
        closeDropdowns();
        if (window.innerWidth > 1080) {
            navLinks?.classList.remove('active');
            navToggle?.setAttribute('aria-expanded', 'false');
        }
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

    setInterval(() => {
        slides[current].classList.remove('active');
        current = (current + 1) % slides.length;
        slides[current].classList.add('active');
    }, 3000);
})();
