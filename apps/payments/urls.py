# apps/payments/urls.py

from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    # Payment listing and details
    path('', views.PaymentListView.as_view(), name='list'),
    path('<uuid:pk>/', views.PaymentDetailView.as_view(), name='detail'),
    path('<uuid:pk>/instructions/', views.PaymentInstructionsView.as_view(), name='payment_instructions'),
    path('contract/<str:token>/', views.ContractPaymentView.as_view(), name='contract_payment'),
    
    # Payment creation and verification
    path('booking/<uuid:booking_id>/', views.PaymentCreateView.as_view(), name='create'),
    path('verify/', views.PaymentVerifyView.as_view(), name='verify'),
    path('success/<uuid:payment_id>/', views.PaymentSuccessView.as_view(), name='success'),
    
    # Refund
    path('refund/booking/<uuid:booking_id>/', views.RefundRequestView.as_view(), name='refund_request'),
    
    # Webhook (Paystack - no login required)
    path('webhook/paystack/', views.PaystackWebhookView.as_view(), name='paystack_webhook'),
]