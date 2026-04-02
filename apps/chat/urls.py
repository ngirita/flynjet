from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .api import ConversationViewSet, MessageViewSet, ChatBotTrainingViewSet

router = DefaultRouter()
router.register(r'conversations', ConversationViewSet, basename='conversation')
router.register(r'messages', MessageViewSet, basename='message')
router.register(r'training', ChatBotTrainingViewSet, basename='training')

app_name = 'chat'

urlpatterns = [
    # Web URLs
    path('', views.ChatWidgetView.as_view(), name='widget'),
    path('agent/', views.AgentDashboardView.as_view(), name='agent_dashboard'),
    path('conversation/<uuid:conversation_id>/', views.ConversationView.as_view(), name='conversation'),
    path('history/', views.ChatHistoryView.as_view(), name='history'),
    
    # API URLs
    path('api/', include(router.urls)),
    path('api/init/', views.init_chat, name='api_init_chat'),
    path('api/agent/queue/', views.agent_queue, name='api_agent_queue'),
    path('api/agent/accept/<uuid:conversation_id>/', views.accept_conversation, name='api_accept'),
    path('api/switch-to-ai/<str:conversation_id>/', views.switch_to_ai_api, name='api_switch_to_ai'),
    path('api/end-chat/<str:conversation_id>/', views.end_chat_api, name='api_end_chat'),
    path('api/test-ai/', views.test_ai, name='test_ai'),
    
    # NEW: Agent Dashboard API Endpoints
    path('api/agent/conversations/', views.agent_conversations, name='api_agent_conversations'),
    path('api/mark-viewing/<str:conversation_id>/', views.mark_agent_viewing, name='api_mark_viewing'),
    path('api/mark-active/<str:conversation_id>/', views.mark_conversation_active, name='api_mark_active'),
    path('api/unmark-viewing/<str:conversation_id>/', views.unmark_agent_viewing, name='api_unmark_viewing'),
    path('api/messages/<str:conversation_id>/', views.conversation_messages, name='api_conversation_messages'),
    path('api/conversation/<str:conversation_id>/', views.conversation_detail, name='api_conversation_detail'),
    path('api/accept/<str:conversation_id>/', views.accept_conversation_api, name='api_accept_conversation'),
    path('api/resolve/<str:conversation_id>/', views.resolve_conversation_api, name='api_resolve_conversation'),
    path('api/close/<str:conversation_id>/', views.close_conversation_api, name='api_close_conversation'),
]