from django.urls import path
from . import views

app_name = 'bookings'

urlpatterns = [
    path('', views.BookingListView.as_view(), name='list'),
    path('create/', views.BookingCreateView.as_view(), name='create'),
    path('passenger-details/', views.PassengerDetailsView.as_view(), name='passenger_details'),
    path('<uuid:pk>/', views.BookingDetailView.as_view(), name='detail'),
    path('<uuid:pk>/edit/', views.BookingUpdateView.as_view(), name='update'),
    path('<uuid:pk>/cancel/', views.BookingCancelView.as_view(), name='cancel'),
    path('<uuid:pk>/invoice/', views.InvoiceDetailView.as_view(), name='invoice'),
    path('track/', views.BookingTrackView.as_view(), name='track'),
    path('check-availability/', views.check_availability, name='check_availability'),
    path('<uuid:pk>/review/', views.BookingReviewView.as_view(), name='review'),
    path('history/', views.BookingHistoryView.as_view(), name='history'),
]