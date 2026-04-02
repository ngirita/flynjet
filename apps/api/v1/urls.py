from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.accounts.api import UserViewSet, LoginHistoryViewSet
from apps.bookings.api import BookingViewSet, InvoiceViewSet
from apps.payments.api import PaymentViewSet, RefundRequestViewSet
from apps.fleet.api import AircraftViewSet, AircraftCategoryViewSet as CategoryViewSet

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'login-history', LoginHistoryViewSet, basename='loginhistory')
router.register(r'bookings', BookingViewSet, basename='booking')
router.register(r'invoices', InvoiceViewSet, basename='invoice')
router.register(r'payments', PaymentViewSet, basename='payment')
router.register(r'refunds', RefundRequestViewSet, basename='refund')
router.register(r'aircraft', AircraftViewSet, basename='aircraft')
router.register(r'categories', CategoryViewSet, basename='category')

urlpatterns = [
    path('', include(router.urls)),
    path('auth/', include('apps.accounts.api.auth_urls')),
]