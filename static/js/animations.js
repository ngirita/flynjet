// FlynJet Animations JavaScript

// Intersection Observer for scroll animations
const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add('fade-in-up');
            observer.unobserve(entry.target);
        }
    });
}, observerOptions);

// Observe elements with animation class
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.animate-on-scroll').forEach(el => {
        observer.observe(el);
    });
});

// Parallax scrolling
class Parallax {
    constructor() {
        this.elements = document.querySelectorAll('[data-parallax]');
        this.init();
    }
    
    init() {
        window.addEventListener('scroll', () => {
            const scrolled = window.pageYOffset;
            
            this.elements.forEach(el => {
                const speed = el.dataset.parallaxSpeed || 0.5;
                const yPos = -(scrolled * speed);
                el.style.transform = `translateY(${yPos}px)`;
            });
        });
    }
}

// Initialize parallax if elements exist
if (document.querySelector('[data-parallax]')) {
    new Parallax();
}

// Smooth scroll
class SmoothScroll {
    constructor() {
        this.links = document.querySelectorAll('a[href^="#"]');
        this.init();
    }
    
    init() {
        this.links.forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const target = document.querySelector(link.getAttribute('href'));
                if (target) {
                    target.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }
            });
        });
    }
}

// Initialize smooth scroll
new SmoothScroll();

// Typing animation
class TypingAnimation {
    constructor(element, texts, options = {}) {
        this.element = typeof element === 'string' ? document.querySelector(element) : element;
        this.texts = texts;
        this.options = {
            typeSpeed: options.typeSpeed || 100,
            deleteSpeed: options.deleteSpeed || 50,
            delayBetween: options.delayBetween || 2000,
            loop: options.loop !== false,
            ...options
        };
        
        this.currentIndex = 0;
        this.currentText = '';
        this.isDeleting = false;
        
        this.type();
    }
    
    type() {
        const fullText = this.texts[this.currentIndex];
        
        if (this.isDeleting) {
            this.currentText = fullText.substring(0, this.currentText.length - 1);
        } else {
            this.currentText = fullText.substring(0, this.currentText.length + 1);
        }
        
        this.element.textContent = this.currentText;
        
        let speed = this.options.typeSpeed;
        
        if (this.isDeleting) {
            speed = this.options.deleteSpeed;
        }
        
        if (!this.isDeleting && this.currentText === fullText) {
            speed = this.options.delayBetween;
            this.isDeleting = true;
        } else if (this.isDeleting && this.currentText === '') {
            this.isDeleting = false;
            this.currentIndex = (this.currentIndex + 1) % this.texts.length;
            speed = 500;
        }
        
        setTimeout(() => this.type(), speed);
    }
}

// Initialize typing animation if element exists
const typingElement = document.querySelector('[data-typing]');
if (typingElement) {
    const texts = JSON.parse(typingElement.dataset.typing);
    new TypingAnimation(typingElement, texts);
}

// Counter animation
class Counter {
    constructor(element, target, options = {}) {
        this.element = typeof element === 'string' ? document.querySelector(element) : element;
        this.target = target;
        this.options = {
            duration: options.duration || 2000,
            step: options.step || 1,
            prefix: options.prefix || '',
            suffix: options.suffix || '',
            ...options
        };
        
        this.current = 0;
        this.startTime = null;
        
        this.animate();
    }
    
    animate() {
        if (!this.startTime) {
            this.startTime = performance.now();
        }
        
        const now = performance.now();
        const elapsed = now - this.startTime;
        const progress = Math.min(elapsed / this.options.duration, 1);
        
        this.current = Math.floor(progress * this.target);
        this.element.textContent = this.options.prefix + this.current + this.options.suffix;
        
        if (progress < 1) {
            requestAnimationFrame(() => this.animate());
        } else {
            this.element.textContent = this.options.prefix + this.target + this.options.suffix;
        }
    }
}

// Initialize counters when they come into view
document.querySelectorAll('[data-counter]').forEach(el => {
    const target = parseInt(el.dataset.counter, 10);
    const options = {
        duration: parseInt(el.dataset.counterDuration) || 2000,
        prefix: el.dataset.counterPrefix || '',
        suffix: el.dataset.counterSuffix || ''
    };
    
    const counterObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                new Counter(el, target, options);
                counterObserver.unobserve(el);
            }
        });
    }, { threshold: 0.5 });
    
    counterObserver.observe(el);
});

// Particle animation
class Particles {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) return;
        
        this.ctx = this.canvas.getContext('2d');
        this.particles = [];
        this.particleCount = 50;
        
        this.init();
    }
    
    init() {
        this.resize();
        this.createParticles();
        this.animate();
        
        window.addEventListener('resize', () => this.resize());
    }
    
    resize() {
        this.canvas.width = window.innerWidth;
        this.canvas.height = window.innerHeight;
    }
    
    createParticles() {
        for (let i = 0; i < this.particleCount; i++) {
            this.particles.push({
                x: Math.random() * this.canvas.width,
                y: Math.random() * this.canvas.height,
                radius: Math.random() * 3 + 1,
                speedX: Math.random() * 2 - 1,
                speedY: Math.random() * 2 - 1,
                opacity: Math.random() * 0.5 + 0.2
            });
        }
    }
    
    animate() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        this.particles.forEach(p => {
            p.x += p.speedX;
            p.y += p.speedY;
            
            if (p.x < 0 || p.x > this.canvas.width) p.speedX *= -1;
            if (p.y < 0 || p.y > this.canvas.height) p.speedY *= -1;
            
            this.ctx.beginPath();
            this.ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
            this.ctx.fillStyle = `rgba(102, 126, 234, ${p.opacity})`;
            this.ctx.fill();
        });
        
        requestAnimationFrame(() => this.animate());
    }
}

// Initialize particles if canvas exists
if (document.getElementById('particleCanvas')) {
    new Particles('particleCanvas');
}

// Ripple effect
class Ripple {
    constructor() {
        this.buttons = document.querySelectorAll('.ripple');
        this.init();
    }
    
    init() {
        this.buttons.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const ripple = document.createElement('span');
                ripple.classList.add('ripple-effect');
                
                const rect = btn.getBoundingClientRect();
                const size = Math.max(rect.width, rect.height);
                const x = e.clientX - rect.left - size / 2;
                const y = e.clientY - rect.top - size / 2;
                
                ripple.style.width = ripple.style.height = `${size}px`;
                ripple.style.left = `${x}px`;
                ripple.style.top = `${y}px`;
                
                btn.appendChild(ripple);
                
                setTimeout(() => {
                    ripple.remove();
                }, 600);
            });
        });
    }
}

// Initialize ripple effect
new Ripple();

// Loading animations
class LoadingManager {
    constructor() {
        this.loader = document.querySelector('.global-loader');
        this.progress = 0;
    }
    
    show() {
        if (this.loader) {
            this.loader.style.display = 'flex';
        }
    }
    
    hide() {
        if (this.loader) {
            this.loader.style.display = 'none';
        }
    }
    
    updateProgress(percent) {
        this.progress = percent;
        const progressBar = document.querySelector('.loader-progress');
        if (progressBar) {
            progressBar.style.width = `${percent}%`;
        }
    }
    
    simulateLoading() {
        this.show();
        
        const interval = setInterval(() => {
            this.progress += Math.random() * 10;
            
            if (this.progress >= 100) {
                this.progress = 100;
                this.updateProgress(this.progress);
                
                setTimeout(() => {
                    this.hide();
                }, 500);
                
                clearInterval(interval);
            }
            
            this.updateProgress(this.progress);
        }, 200);
    }
}

// Export for use
window.SmoothScroll = SmoothScroll;
window.TypingAnimation = TypingAnimation;
window.Counter = Counter;
window.Particles = Particles;
window.LoadingManager = LoadingManager;