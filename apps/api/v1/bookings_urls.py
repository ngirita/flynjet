from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.bookings.api import BookingViewSet, InvoiceViewSet

router = DefaultRouter()
router.register(r'bookings', BookingViewSet)
router.register(r'invoices', InvoiceViewSet)

urlpatterns = [
    path('', include(router.urls)),
]