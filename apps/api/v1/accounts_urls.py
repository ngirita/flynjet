from django.urls import path
from rest_framework.routers import DefaultRouter
from apps.accounts.api import UserViewSet, LoginHistoryViewSet, RegisterView, LoginView, LogoutView

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'login-history', LoginHistoryViewSet)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('', include(router.urls)),
]