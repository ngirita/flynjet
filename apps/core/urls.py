from django.urls import path
from . import views_admin
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('about/', views.AboutView.as_view(), name='about'),
    path('services/', views.ServicesView.as_view(), name='services'),
    path('contact/', views.ContactView.as_view(), name='contact'),
    path('faq/', views.FAQView.as_view(), name='faq'),
    path('terms/', views.TermsView.as_view(), name='terms'),
    path('privacy/', views.PrivacyView.as_view(), name='privacy'),
    
    # Newsletter
    path('newsletter-signup/', views.newsletter_signup, name='newsletter_signup'),  # Add this line
    
    # Support tickets
    path('support/new/', views.SupportTicketCreateView.as_view(), name='support_ticket_create'),
    path('support/', views.SupportTicketListView.as_view(), name='support_tickets'),
    path('support/<uuid:pk>/', views.SupportTicketDetailView.as_view(), name='support_ticket_detail'),

    # Admin notification endpoints
    path('admin/api/notifications/', views_admin.admin_notifications_api, name='admin_notifications_api'),
    path('admin/api/notifications/mark-all-read/', views_admin.mark_all_notifications_read, name='mark_all_notifications_read'),
    path('admin/api/notifications/<uuid:notification_id>/mark-read/', views_admin.mark_notification_read, name='mark_notification_read'),
    path('admin/api/enquiry/<uuid:enquiry_id>/', views_admin.get_enquiry_data, name='admin_enquiry_data'),
]