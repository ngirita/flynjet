from django.contrib import admin
from .models import Review, Testimonial, ReviewVote, ReviewPhoto, ReviewSummary

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['review_number', 'user', 'aircraft', 'overall_rating', 'status', 'created_at']
    list_filter = ['status', 'review_type', 'overall_rating', 'created_at']
    search_fields = ['review_number', 'user__email', 'title', 'content']
    readonly_fields = ['review_number', 'created_at', 'updated_at', 'helpful_votes', 'not_helpful_votes', 'report_count']
    
    fieldsets = (
        ('Review Info', {
            'fields': ('review_number', 'user', 'booking', 'aircraft', 'agent')
        }),
        ('Content', {
            'fields': ('review_type', 'title', 'content', 'display_name', 'is_verified')
        }),
        ('Ratings', {
            'fields': ('overall_rating', 'punctuality_rating', 'comfort_rating', 
                      'service_rating', 'value_rating', 'cleanliness_rating')
        }),
        ('Media', {
            'fields': ('photos', 'videos'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('status', 'moderation_note', 'moderated_by', 'moderated_at')
        }),
        ('Response', {
            'fields': ('response', 'responded_by', 'responded_at')
        }),
        ('Votes', {
            'fields': ('helpful_votes', 'not_helpful_votes', 'report_count')
        }),
        ('Metadata', {
            'fields': ('ip_address', 'user_agent', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['approve_reviews', 'reject_reviews', 'feature_reviews']
    
    def approve_reviews(self, request, queryset):
        for review in queryset:
            review.approve(request.user)
        self.message_user(request, f"{queryset.count()} reviews approved.")
    approve_reviews.short_description = "Approve selected reviews"
    
    def reject_reviews(self, request, queryset):
        for review in queryset:
            review.reject(request.user, "Rejected by admin")
        self.message_user(request, f"{queryset.count()} reviews rejected.")
    reject_reviews.short_description = "Reject selected reviews"
    
    def feature_reviews(self, request, queryset):
        queryset.update(status='featured')
        self.message_user(request, f"{queryset.count()} reviews featured.")
    feature_reviews.short_description = "Feature selected reviews"

@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ['customer_name', 'rating', 'is_featured', 'is_verified', 'created_at']
    list_filter = ['is_featured', 'is_verified', 'rating']
    search_fields = ['customer_name', 'content']
    readonly_fields = ['testimonial_number', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Testimonial Info', {
            'fields': ('testimonial_number', 'review', 'user', 'is_featured', 'display_order')
        }),
        ('Content', {
            'fields': ('customer_name', 'customer_title', 'customer_company', 'content', 'rating')
        }),
        ('Media', {
            'fields': ('customer_image',)
        }),
        ('Verification', {
            'fields': ('is_verified', 'verified_at', 'verified_by')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['verify_testimonials', 'feature_testimonials']
    
    def verify_testimonials(self, request, queryset):
        for testimonial in queryset:
            testimonial.verify(request.user)
        self.message_user(request, f"{queryset.count()} testimonials verified.")
    verify_testimonials.short_description = "Verify selected testimonials"
    
    def feature_testimonials(self, request, queryset):
        queryset.update(is_featured=True)
        self.message_user(request, f"{queryset.count()} testimonials featured.")
    feature_testimonials.short_description = "Feature selected testimonials"

@admin.register(ReviewVote)
class ReviewVoteAdmin(admin.ModelAdmin):
    list_display = ['review', 'user', 'vote_type', 'created_at']
    list_filter = ['vote_type', 'created_at']
    search_fields = ['review__review_number', 'user__email']
    readonly_fields = ['created_at']

@admin.register(ReviewPhoto)
class ReviewPhotoAdmin(admin.ModelAdmin):
    list_display = ['review', 'caption', 'uploaded_at']
    list_filter = ['uploaded_at']
    search_fields = ['review__review_number', 'caption']
    readonly_fields = ['uploaded_at']

@admin.register(ReviewSummary)
class ReviewSummaryAdmin(admin.ModelAdmin):
    list_display = ['aircraft', 'total_reviews', 'average_rating', 'period_start', 'period_end']
    list_filter = ['period_start', 'period_end']
    search_fields = ['aircraft__registration_number', 'aircraft__model']
    readonly_fields = ['calculated_at']
    
    fieldsets = (
        ('Target', {
            'fields': ('aircraft', 'agent')
        }),
        ('Statistics', {
            'fields': ('total_reviews', 'average_rating')
        }),
        ('Distribution', {
            'fields': ('rating_5_count', 'rating_4_count', 'rating_3_count', 
                      'rating_2_count', 'rating_1_count')
        }),
        ('Period', {
            'fields': ('period_start', 'period_end', 'calculated_at')
        }),
    )