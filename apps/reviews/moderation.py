import re
from django.utils import timezone
from .models import Review

class ReviewModerator:
    """Automated review moderation"""
    
    INAPPROPRIATE_WORDS = [
        'spam', 'scam', 'fraud', 'illegal', 'drugs', 'weapon',
        'porn', 'sex', 'nude', 'explicit', 'offensive', 'hate',
        'racist', 'discrimination', 'violence', 'terrorist'
    ]
    
    SUSPICIOUS_PATTERNS = [
        r'\b(viagra|cialis|casino|poker|lottery|winner)\b',
        r'https?://\S+',  # URLs
        r'\b\d{10,}\b',  # Long numbers (phone numbers)
        r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',  # Emails
    ]
    
    @classmethod
    def moderate(cls, review):
        """Run moderation checks on review"""
        issues = []
        
        # Check for inappropriate words
        content_lower = review.content.lower()
        for word in cls.INAPPROPRIATE_WORDS:
            if word in content_lower:
                issues.append(f"Contains inappropriate word: {word}")
        
        # Check for suspicious patterns
        for pattern in cls.SUSPICIOUS_PATTERNS:
            if re.search(pattern, review.content, re.IGNORECASE):
                issues.append("Contains suspicious content (links, emails, etc.)")
        
        # Check for excessive caps
        caps_ratio = sum(1 for c in review.content if c.isupper()) / max(len(review.content), 1)
        if caps_ratio > 0.5 and len(review.content) > 20:
            issues.append("Excessive use of capital letters")
        
        # Check for repetitive content
        words = review.content.lower().split()
        if len(words) > 10:
            unique_words = len(set(words))
            if unique_words / len(words) < 0.3:
                issues.append("Repetitive content detected")
        
        # Check for extreme ratings with short content
        if review.overall_rating in [1, 5] and len(review.content) < 50:
            issues.append("Extreme rating with very short review")
        
        # Check for multiple reviews from same IP
        if review.ip_address:
            recent_from_ip = Review.objects.filter(
                ip_address=review.ip_address,
                created_at__gte=timezone.now() - timezone.timedelta(hours=24)
            ).count()
            if recent_from_ip > 3:
                issues.append("Multiple reviews from same IP in 24 hours")
        
        return {
            'is_clean': len(issues) == 0,
            'issues': issues,
            'should_flag': len(issues) >= 2,
            'should_reject': len(issues) >= 3
        }
    
    @classmethod
    def auto_approve(cls, review):
        """Check if review can be auto-approved"""
        # Verified booker
        if not review.booking:
            return False
        
        # Not too short
        if len(review.content) < 30:
            return False
        
        # Not too extreme without justification
        if review.overall_rating in [1, 5] and len(review.content) < 100:
            return False
        
        # Pass moderation
        result = cls.moderate(review)
        return result['is_clean']
    
    @classmethod
    def calculate_helpfulness_score(cls, review):
        """Calculate helpfulness score based on votes and content"""
        base_score = 0
        
        # Content quality
        if len(review.content) > 200:
            base_score += 10
        elif len(review.content) > 100:
            base_score += 5
        
        # Specific ratings
        if all([
            review.punctuality_rating,
            review.comfort_rating,
            review.service_rating,
            review.value_rating,
            review.cleanliness_rating
        ]):
            base_score += 10
        
        # Has photos
        if review.photos:
            base_score += 20
        
        # Vote ratio
        total_votes = review.helpful_votes + review.not_helpful_votes
        if total_votes > 0:
            helpful_ratio = review.helpful_votes / total_votes
            base_score += int(helpful_ratio * 20)
        
        return min(base_score, 100)

class ReviewScorer:
    """Calculate review scores and rankings"""
    
    @classmethod
    def calculate_aircraft_score(cls, aircraft):
        """Calculate overall aircraft score based on reviews"""
        reviews = Review.objects.filter(
            aircraft=aircraft,
            status='approved'
        )
        
        if not reviews.exists():
            return 0
        
        # Weighted average based on recency
        total_weight = 0
        weighted_sum = 0
        now = timezone.now()
        
        for review in reviews:
            days_ago = (now - review.created_at).days
            weight = max(1, 30 - days_ago) / 30  # Recent reviews weigh more
            weighted_sum += review.overall_rating * weight
            total_weight += weight
        
        return weighted_sum / total_weight
    
    @classmethod
    def get_top_reviews(cls, aircraft, limit=5):
        """Get top reviews for aircraft"""
        reviews = Review.objects.filter(
            aircraft=aircraft,
            status='approved'
        )
        
        # Score each review
        scored = []
        for review in reviews:
            score = ReviewModerator.calculate_helpfulness_score(review)
            scored.append((score, review))
        
        # Sort by score and return top
        scored.sort(reverse=True, key=lambda x: x[0])
        return [r for s, r in scored[:limit]]

class ReviewAnalytics:
    """Analyze review trends"""
    
    @classmethod
    def get_trends(cls, aircraft, months=6):
        """Get rating trends over time"""
        end_date = timezone.now().date()
        start_date = end_date - timezone.timedelta(days=30 * months)
        
        reviews = Review.objects.filter(
            aircraft=aircraft,
            status='approved',
            created_at__date__gte=start_date
        ).order_by('created_at')
        
        # Group by month
        monthly = {}
        for review in reviews:
            month_key = review.created_at.strftime('%Y-%m')
            if month_key not in monthly:
                monthly[month_key] = []
            monthly[month_key].append(review.overall_rating)
        
        # Calculate averages
        trends = []
        for month, ratings in sorted(monthly.items()):
            trends.append({
                'month': month,
                'average': sum(ratings) / len(ratings),
                'count': len(ratings)
            })
        
        return trends
    
    @classmethod
    def get_common_keywords(cls, aircraft, limit=10):
        """Extract common keywords from reviews"""
        from collections import Counter
        import nltk
        from nltk.corpus import stopwords
        
        reviews = Review.objects.filter(
            aircraft=aircraft,
            status='approved'
        ).values_list('content', flat=True)
        
        # Tokenize and count
        words = []
        stop_words = set(stopwords.words('english'))
        
        for content in reviews:
            tokens = nltk.word_tokenize(content.lower())
            words.extend([w for w in tokens if w.isalnum() and w not in stop_words and len(w) > 3])
        
        counter = Counter(words)
        return counter.most_common(limit)