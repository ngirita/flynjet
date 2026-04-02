from rest_framework import serializers
from .models import Review, Testimonial, ReviewSummary, ReviewPhoto

class ReviewPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewPhoto
        fields = ['id', 'image', 'caption', 'uploaded_at']


class ReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    photos = ReviewPhotoSerializer(many=True, read_only=True)
    
    class Meta:
        model = Review
        fields = [
            'id', 'review_number', 'user', 'user_name', 'display_name',
            'review_type', 'title', 'content', 'overall_rating',
            'punctuality_rating', 'comfort_rating', 'service_rating',
            'value_rating', 'cleanliness_rating', 'photos',
            'created_at', 'helpful_votes', 'not_helpful_votes'
        ]


class ReviewDetailSerializer(serializers.ModelSerializer):
    aircraft_name = serializers.CharField(source='aircraft.model', read_only=True)
    booking_reference = serializers.CharField(source='booking.booking_reference', read_only=True)
    
    class Meta:
        model = Review
        fields = '__all__'


class TestimonialSerializer(serializers.ModelSerializer):
    class Meta:
        model = Testimonial
        fields = [
            'id', 'customer_name', 'customer_title', 'customer_company',
            'customer_image', 'content', 'rating', 'is_featured'
        ]


class ReviewSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewSummary
        fields = '__all__'