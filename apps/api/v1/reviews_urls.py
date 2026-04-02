from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.reviews.api import ReviewViewSet, TestimonialViewSet, ReviewSummaryViewSet

router = DefaultRouter()
router.register(r'reviews', ReviewViewSet, basename='review')
router.register(r'testimonials', TestimonialViewSet, basename='testimonial')
router.register(r'summaries', ReviewSummaryViewSet, basename='summary')

urlpatterns = [
    path('', include(router.urls)),
]