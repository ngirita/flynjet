// Reviews Carousel

class ReviewsCarousel {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        this.options = {
            autoplay: options.autoplay || true,
            interval: options.interval || 5000,
            pauseOnHover: options.pauseOnHover || true,
            showDots: options.showDots !== false,
            showArrows: options.showArrows !== false,
            itemsPerView: options.itemsPerView || 1,
            ...options
        };
        
        this.currentIndex = 0;
        this.totalItems = 0;
        this.autoplayTimer = null;
        this.isPaused = false;
        
        this.init();
    }
    
    init() {
        if (!this.container) return;
        
        this.track = this.container.querySelector('.carousel-track');
        this.items = this.container.querySelectorAll('.carousel-item');
        this.totalItems = this.items.length;
        
        if (this.totalItems === 0) return;
        
        this.createControls();
        this.setupEventListeners();
        this.update();
        
        if (this.options.autoplay) {
            this.startAutoplay();
        }
    }
    
    createControls() {
        // Create navigation dots
        if (this.options.showDots) {
            const dotsContainer = document.createElement('div');
            dotsContainer.className = 'carousel-dots';
            
            for (let i = 0; i < this.totalItems; i++) {
                const dot = document.createElement('button');
                dot.className = 'carousel-dot';
                dot.setAttribute('data-index', i);
                dot.addEventListener('click', () => this.goTo(i));
                dotsContainer.appendChild(dot);
            }
            
            this.container.appendChild(dotsContainer);
            this.dots = dotsContainer.querySelectorAll('.carousel-dot');
        }
        
        // Create navigation arrows
        if (this.options.showArrows && this.totalItems > 1) {
            const prevBtn = document.createElement('button');
            prevBtn.className = 'carousel-arrow prev';
            prevBtn.innerHTML = '&lsaquo;';
            prevBtn.addEventListener('click', () => this.prev());
            
            const nextBtn = document.createElement('button');
            nextBtn.className = 'carousel-arrow next';
            nextBtn.innerHTML = '&rsaquo;';
            nextBtn.addEventListener('click', () => this.next());
            
            this.container.appendChild(prevBtn);
            this.container.appendChild(nextBtn);
        }
    }
    
    setupEventListeners() {
        if (this.options.pauseOnHover) {
            this.container.addEventListener('mouseenter', () => this.pause());
            this.container.addEventListener('mouseleave', () => this.resume());
        }
        
        // Touch events for mobile
        let touchStartX = 0;
        let touchEndX = 0;
        
        this.container.addEventListener('touchstart', (e) => {
            touchStartX = e.touches[0].clientX;
        }, { passive: true });
        
        this.container.addEventListener('touchend', (e) => {
            touchEndX = e.changedTouches[0].clientX;
            const diff = touchStartX - touchEndX;
            
            if (Math.abs(diff) > 50) {
                if (diff > 0) {
                    this.next();
                } else {
                    this.prev();
                }
            }
        });
    }
    
    goTo(index) {
        if (index < 0) index = this.totalItems - 1;
        if (index >= this.totalItems) index = 0;
        
        this.currentIndex = index;
        this.update();
    }
    
    next() {
        this.goTo(this.currentIndex + 1);
    }
    
    prev() {
        this.goTo(this.currentIndex - 1);
    }
    
    update() {
        // Update track position
        const offset = -this.currentIndex * 100;
        this.track.style.transform = `translateX(${offset}%)`;
        
        // Update dots
        if (this.dots) {
            this.dots.forEach((dot, i) => {
                dot.classList.toggle('active', i === this.currentIndex);
            });
        }
        
        // Update active states
        this.items.forEach((item, i) => {
            item.classList.toggle('active', i === this.currentIndex);
        });
    }
    
    startAutoplay() {
        if (this.autoplayTimer) return;
        
        this.autoplayTimer = setInterval(() => {
            if (!this.isPaused) {
                this.next();
            }
        }, this.options.interval);
    }
    
    stopAutoplay() {
        if (this.autoplayTimer) {
            clearInterval(this.autoplayTimer);
            this.autoplayTimer = null;
        }
    }
    
    pause() {
        this.isPaused = true;
    }
    
    resume() {
        this.isPaused = false;
    }
    
    destroy() {
        this.stopAutoplay();
        // Remove event listeners
        // Remove controls
    }
}

// Initialize carousels on page load
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.reviews-carousel').forEach((carousel, index) => {
        new ReviewsCarousel(carousel.id || `carousel-${index}`, {
            autoplay: true,
            interval: 5000,
            itemsPerView: 1
        });
    });
});

// Export for use
window.ReviewsCarousel = ReviewsCarousel;