from django.urls import path
from rest_framework.routers import DefaultRouter

# Import mobile API views directly from their modules
from .mobile.auth import mobile_login, mobile_register, mobile_logout, mobile_refresh
from .mobile.bookings import mobile_bookings, mobile_booking_detail, mobile_create_booking, mobile_cancel_booking
from .mobile.tracking import mobile_track_flight, mobile_track_history, mobile_share_tracking
from .mobile.notifications import (
    mobile_notifications, mobile_mark_read, mobile_mark_all_read,
    mobile_delete_notification, mobile_register_push
)

app_name = 'api_v2'

urlpatterns = [
    # Mobile API endpoints
    path('auth/login/', mobile_login, name='mobile_login'),
    path('auth/register/', mobile_register, name='mobile_register'),
    path('auth/logout/', mobile_logout, name='mobile_logout'),
    path('auth/refresh/', mobile_refresh, name='mobile_refresh'),
    
    path('bookings/', mobile_bookings, name='mobile_bookings'),
    path('bookings/<uuid:booking_id>/', mobile_booking_detail, name='mobile_booking_detail'),
    path('bookings/create/', mobile_create_booking, name='mobile_create_booking'),
    path('bookings/<uuid:booking_id>/cancel/', mobile_cancel_booking, name='mobile_cancel_booking'),
    
    path('tracking/<uuid:booking_id>/', mobile_track_flight, name='mobile_track_flight'),
    path('tracking/<uuid:booking_id>/history/', mobile_track_history, name='mobile_track_history'),
    path('tracking/<uuid:booking_id>/share/', mobile_share_tracking, name='mobile_share_tracking'),
    
    path('notifications/', mobile_notifications, name='mobile_notifications'),
    path('notifications/<uuid:notification_id>/read/', mobile_mark_read, name='mobile_mark_read'),
    path('notifications/read-all/', mobile_mark_all_read, name='mobile_mark_all_read'),
    path('notifications/<uuid:notification_id>/', mobile_delete_notification, name='mobile_delete_notification'),
    path('notifications/push/register/', mobile_register_push, name='mobile_register_push'),
]