from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.payments.api import PaymentViewSet, RefundRequestViewSet

router = DefaultRouter()
router.register(r'payments', PaymentViewSet)
router.register(r'refunds', RefundRequestViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('webhook/stripe/', include('apps.payments.urls')),
]