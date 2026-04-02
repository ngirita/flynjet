from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .api import DocumentViewSet, DocumentTemplateViewSet, DocumentSigningViewSet

router = DefaultRouter()
router.register(r'documents', DocumentViewSet, basename='document')
router.register(r'templates', DocumentTemplateViewSet, basename='template')
router.register(r'signatures', DocumentSigningViewSet, basename='signature')

app_name = 'documents'

urlpatterns = [
    # Web URLs
    path('', views.DocumentListView.as_view(), name='list'),
    path('generate/<uuid:booking_id>/<str:doc_type>/', views.GenerateDocumentView.as_view(), name='generate'),
    path('view/<uuid:pk>/', views.DocumentViewerView.as_view(), name='view'),
    path('download/<uuid:pk>/', views.download_document, name='download'),
    path('sign/<uuid:pk>/', views.SignDocumentView.as_view(), name='sign'),
    path('verify/<uuid:token>/', views.VerifyDocumentView.as_view(), name='verify'),
    
    # API URLs
    path('api/', include(router.urls)),
]