from django.contrib import admin
from .models import Conversation, Message, ChatQueue, ChatBotTraining, ChatFeedback

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ['conversation_id', 'user', 'agent', 'status', 'priority', 'started_at']
    list_filter = ['status', 'priority', 'created_at']
    search_fields = ['conversation_id', 'user__email', 'agent__email', 'subject']
    readonly_fields = ['conversation_id', 'started_at', 'first_response_at', 'resolved_at']
    
    fieldsets = (
        ('Conversation Info', {
            'fields': ('conversation_id', 'user', 'agent', 'status', 'priority', 'subject')
        }),
        ('Timing', {
            'fields': ('started_at', 'first_response_at', 'resolved_at', 'closed_at', 'response_time')
        }),
        ('AI/ML Data', {
            'fields': ('intent', 'confidence', 'sentiment')
        }),
        ('Satisfaction', {
            'fields': ('satisfaction_rating', 'satisfaction_feedback')
        }),
        ('Metadata', {
            'fields': ('ip_address', 'user_agent', 'page_url'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['conversation', 'sender', 'message_type', 'created_at', 'is_read']
    list_filter = ['message_type', 'is_read', 'is_agent', 'is_ai', 'created_at']
    search_fields = ['conversation__conversation_id', 'sender__email', 'message']
    readonly_fields = ['created_at', 'read_at', 'delivered_at']
    
    fieldsets = (
        ('Message Info', {
            'fields': ('conversation', 'sender', 'sender_name', 'message_type')
        }),
        ('Content', {
            'fields': ('message', 'html_message')
        }),
        ('Attachments', {
            'fields': ('attachment', 'attachment_name', 'attachment_size', 'attachment_type')
        }),
        ('Status', {
            'fields': ('is_read', 'read_at', 'is_delivered', 'delivered_at')
        }),
        ('AI Data', {
            'fields': ('intent', 'confidence', 'suggested_responses')
        }),
    )

@admin.register(ChatQueue)
class ChatQueueAdmin(admin.ModelAdmin):
    list_display = ['conversation', 'position', 'entered_at', 'exited_at']
    list_filter = ['entered_at']
    search_fields = ['conversation__conversation_id', 'conversation__user__email']
    readonly_fields = ['entered_at']

@admin.register(ChatBotTraining)
class ChatBotTrainingAdmin(admin.ModelAdmin):
    list_display = ['intent', 'language', 'is_active', 'times_used', 'success_rate']
    list_filter = ['is_active', 'language', 'intent']
    search_fields = ['intent', 'patterns']
    readonly_fields = ['times_used', 'success_rate', 'last_used', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Intent', {
            'fields': ('intent', 'language', 'is_active')
        }),
        ('Training Data', {
            'fields': ('patterns', 'responses', 'context')
        }),
        ('Configuration', {
            'fields': ('confidence_threshold',)
        }),
        ('Statistics', {
            'fields': ('times_used', 'success_rate', 'last_used')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(ChatFeedback)
class ChatFeedbackAdmin(admin.ModelAdmin):
    list_display = ['conversation', 'rating', 'resolved_issue', 'created_at']
    list_filter = ['rating', 'resolved_issue', 'agent_helpful']
    search_fields = ['conversation__conversation_id', 'comment']
    readonly_fields = ['created_at']