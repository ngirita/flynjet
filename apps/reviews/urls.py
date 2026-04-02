from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .api import ReviewViewSet, TestimonialViewSet, ReviewSummaryViewSet

router = DefaultRouter()
router.register(r'reviews', ReviewViewSet, basename='review')
router.register(r'testimonials', TestimonialViewSet, basename='testimonial')
router.register(r'summaries', ReviewSummaryViewSet, basename='summary')

app_name = 'reviews'

urlpatterns = [
    # Web URLs
    path('', views.ReviewListView.as_view(), name='list'),
    path('create/<uuid:booking_id>/', views.CreateReviewView.as_view(), name='create'),
    path('<uuid:pk>/', views.ReviewDetailView.as_view(), name='detail'),
    path('<uuid:pk>/vote/', views.vote_review, name='vote'),
    path('<uuid:pk>/report/', views.report_review, name='report'),
    path('testimonials/', views.TestimonialListView.as_view(), name='testimonials'),
    
    # Admin URLs
    path('admin/', views.ReviewModerationView.as_view(), name='admin_list'),
    path('admin/<uuid:pk>/moderate/', views.moderate_review, name='moderate'),
    
    # API URLs
    path('api/', include(router.urls)),
]