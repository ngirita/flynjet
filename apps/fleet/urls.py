from django.urls import path
from .views import SubmitEnquiryView
from . import views

app_name = 'fleet'

urlpatterns = [
    path('', views.AircraftListView.as_view(), name='list'),
    path('category/', views.CategoryListView.as_view(), name='categories'),
    path('category/<slug:slug>/', views.CategoryDetailView.as_view(), name='category_detail'),
    path('aircraft/<uuid:pk>/', views.AircraftDetailView.as_view(), name='detail'),
    path('check-availability/', views.check_availability, name='check_availability'),
    path('enquiry/submit/', SubmitEnquiryView.as_view(), name='submit_enquiry'),
    path('thank-you/', views.thank_you, name='thank_you'),
    path('cargo-thank-you/', views.cargo_thank_you, name='cargo_thank_you'),
]