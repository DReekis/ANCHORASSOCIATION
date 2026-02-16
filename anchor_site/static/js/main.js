
console.log('Anchor Association - Site loaded');

// ---- Gallery Slideshow (Home Page) ----
(function () {
    const slideshow = document.getElementById('gallerySlideshow');
    if (!slideshow) return;

    const slides = slideshow.querySelectorAll('.gallery-slide');
    if (slides.length <= 1) return;

    let current = 0;

    setInterval(() => {
        slides[current].classList.remove('active');
        current = (current + 1) % slides.length;
        slides[current].classList.add('active');
    }, 3000);
})();
