// Rating System JavaScript

class RatingSystem {
    constructor(options = {}) {
        this.container = options.container || document.body;
        this.inputSelector = options.inputSelector || '.rating-input';
        this.displaySelector = options.displaySelector || '.rating-display';
        this.onRate = options.onRate || null;
        
        this.init();
    }
    
    init() {
        this.initRatingInputs();
        this.initRatingDisplays();
    }
    
    initRatingInputs() {
        const inputs = this.container.querySelectorAll(this.inputSelector);
        
        inputs.forEach(input => {
            const stars = input.querySelectorAll('.rating-star');
            const hiddenInput = input.querySelector('input[type="hidden"]');
            
            stars.forEach(star => {
                star.addEventListener('mouseover', () => {
                    this.highlightStars(input, star.dataset.value);
                });
                
                star.addEventListener('mouseout', () => {
                    this.resetStars(input);
                });
                
                star.addEventListener('click', () => {
                    this.setRating(input, star.dataset.value);
                    if (hiddenInput) {
                        hiddenInput.value = star.dataset.value;
                    }
                    if (this.onRate) {
                        this.onRate(star.dataset.value);
                    }
                });
            });
        });
    }
    
    initRatingDisplays() {
        const displays = this.container.querySelectorAll(this.displaySelector);
        
        displays.forEach(display => {
            const rating = parseFloat(display.dataset.rating) || 0;
            this.renderStars(display, rating);
        });
    }
    
    highlightStars(input, rating) {
        const stars = input.querySelectorAll('.rating-star');
        rating = parseInt(rating);
        
        stars.forEach((star, index) => {
            if (index < rating) {
                star.classList.add('hover');
            } else {
                star.classList.remove('hover');
            }
        });
    }
    
    resetStars(input) {
        const stars = input.querySelectorAll('.rating-star');
        const currentRating = parseInt(input.dataset.currentRating) || 0;
        
        stars.forEach((star, index) => {
            star.classList.remove('hover');
            if (index < currentRating) {
                star.classList.add('active');
            } else {
                star.classList.remove('active');
            }
        });
    }
    
    setRating(input, rating) {
        const stars = input.querySelectorAll('.rating-star');
        rating = parseInt(rating);
        input.dataset.currentRating = rating;
        
        stars.forEach((star, index) => {
            if (index < rating) {
                star.classList.add('active');
            } else {
                star.classList.remove('active');
            }
        });
    }
    
    renderStars(container, rating) {
        const fullStars = Math.floor(rating);
        const hasHalf = rating % 1 >= 0.5;
        const emptyStars = 5 - fullStars - (hasHalf ? 1 : 0);
        
        container.innerHTML = '';
        
        // Full stars
        for (let i = 0; i < fullStars; i++) {
            container.innerHTML += '<i class="fas fa-star"></i>';
        }
        
        // Half star
        if (hasHalf) {
            container.innerHTML += '<i class="fas fa-star-half-alt"></i>';
        }
        
        // Empty stars
        for (let i = 0; i < emptyStars; i++) {
            container.innerHTML += '<i class="far fa-star"></i>';
        }
    }
    
    calculateAverage(ratings) {
        if (!ratings.length) return 0;
        const sum = ratings.reduce((a, b) => a + b, 0);
        return sum / ratings.length;
    }
    
    formatRating(rating) {
        return rating.toFixed(1);
    }
}

class ReviewVoting {
    constructor(options = {}) {
        this.reviewId = options.reviewId;
        this.csrfToken = options.csrfToken;
        this.onVote = options.onVote || null;
        
        this.init();
    }
    
    init() {
        this.bindVoteButtons();
    }
    
    bindVoteButtons() {
        const helpfulBtn = document.getElementById(`helpful-${this.reviewId}`);
        const notHelpfulBtn = document.getElementById(`not-helpful-${this.reviewId}`);
        
        if (helpfulBtn) {
            helpfulBtn.addEventListener('click', () => this.vote('helpful'));
        }
        
        if (notHelpfulBtn) {
            notHelpfulBtn.addEventListener('click', () => this.vote('not_helpful'));
        }
    }
    
    vote(voteType) {
        fetch(`/api/v1/reviews/${this.reviewId}/vote/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.csrfToken
            },
            body: JSON.stringify({ vote_type: voteType })
        })
        .then(response => response.json())
        .then(data => {
            this.updateVoteCounts(data);
            if (this.onVote) {
                this.onVote(voteType, data);
            }
        })
        .catch(error => {
            console.error('Error voting:', error);
        });
    }
    
    updateVoteCounts(data) {
        const helpfulCount = document.getElementById(`helpful-count-${this.reviewId}`);
        const notHelpfulCount = document.getElementById(`not-helpful-count-${this.reviewId}`);
        
        if (helpfulCount) {
            helpfulCount.textContent = data.helpful;
        }
        
        if (notHelpfulCount) {
            notHelpfulCount.textContent = data.not_helpful;
        }
    }
}

class ReviewReporting {
    constructor(options = {}) {
        this.reviewId = options.reviewId;
        this.csrfToken = options.csrfToken;
        this.modal = options.modal;
        
        this.init();
    }
    
    init() {
        const reportBtn = document.getElementById(`report-${this.reviewId}`);
        if (reportBtn) {
            reportBtn.addEventListener('click', () => this.showReportModal());
        }
    }
    
    showReportModal() {
        if (this.modal) {
            this.modal.show();
            
            const submitBtn = this.modal.querySelector('.submit-report');
            if (submitBtn) {
                submitBtn.addEventListener('click', () => this.submitReport());
            }
        }
    }
    
    submitReport() {
        const reason = document.getElementById('report-reason').value;
        const details = document.getElementById('report-details').value;
        
        fetch(`/api/v1/reviews/${this.reviewId}/report/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.csrfToken
            },
            body: JSON.stringify({
                reason: reason,
                details: details
            })
        })
        .then(response => response.json())
        .then(data => {
            alert('Thank you for reporting. Our team will review this content.');
            if (this.modal) {
                this.modal.hide();
            }
        })
        .catch(error => {
            console.error('Error reporting:', error);
        });
    }
}

// Photo Gallery for Reviews
class ReviewPhotoGallery {
    constructor(options = {}) {
        this.photos = options.photos || [];
        this.container = options.container;
        this.currentIndex = 0;
        
        this.init();
    }
    
    init() {
        this.bindThumbnails();
    }
    
    bindThumbnails() {
        const thumbnails = this.container.querySelectorAll('.review-photo');
        
        thumbnails.forEach((thumb, index) => {
            thumb.addEventListener('click', () => this.openLightbox(index));
        });
    }
    
    openLightbox(index) {
        this.currentIndex = index;
        
        // Create lightbox
        const lightbox = document.createElement('div');
        lightbox.className = 'lightbox';
        lightbox.innerHTML = `
            <div class="lightbox-content">
                <button class="lightbox-close">&times;</button>
                <button class="lightbox-prev">&lsaquo;</button>
                <img src="${this.photos[index].url}" class="lightbox-image">
                <button class="lightbox-next">&rsaquo;</button>
                <div class="lightbox-caption">${this.photos[index].caption || ''}</div>
            </div>
        `;
        
        document.body.appendChild(lightbox);
        
        // Bind events
        lightbox.querySelector('.lightbox-close').addEventListener('click', () => {
            lightbox.remove();
        });
        
        lightbox.querySelector('.lightbox-prev').addEventListener('click', () => {
            this.navigate(-1, lightbox);
        });
        
        lightbox.querySelector('.lightbox-next').addEventListener('click', () => {
            this.navigate(1, lightbox);
        });
        
        // Keyboard navigation
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') lightbox.remove();
            if (e.key === 'ArrowLeft') this.navigate(-1, lightbox);
            if (e.key === 'ArrowRight') this.navigate(1, lightbox);
        });
    }
    
    navigate(direction, lightbox) {
        this.currentIndex = (this.currentIndex + direction + this.photos.length) % this.photos.length;
        const img = lightbox.querySelector('.lightbox-image');
        img.src = this.photos[this.currentIndex].url;
        
        const caption = lightbox.querySelector('.lightbox-caption');
        if (caption) {
            caption.textContent = this.photos[this.currentIndex].caption || '';
        }
    }
}

// Export
window.RatingSystem = RatingSystem;
window.ReviewVoting = ReviewVoting;
window.ReviewReporting = ReviewReporting;
window.ReviewPhotoGallery = ReviewPhotoGallery;