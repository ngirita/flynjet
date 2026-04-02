from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.chat.api import ConversationViewSet, MessageViewSet, ChatBotTrainingViewSet

router = DefaultRouter()
router.register(r'conversations', ConversationViewSet, basename='conversation')
router.register(r'messages', MessageViewSet, basename='message')
router.register(r'training', ChatBotTrainingViewSet, basename='training')

urlpatterns = [
    path('', include(router.urls)),
]