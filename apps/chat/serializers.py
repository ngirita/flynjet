from rest_framework import serializers
from .models import Conversation, Message, ChatBotTraining, ChatFeedback
from apps.accounts.serializers import UserSerializer

class MessageSerializer(serializers.ModelSerializer):
    sender_details = UserSerializer(source='sender', read_only=True)
    
    class Meta:
        model = Message
        fields = [
            'id', 'sender', 'sender_details', 'sender_name',
            'message', 'message_type', 'is_agent', 'is_ai',
            'created_at', 'is_read', 'intent', 'confidence'
        ]


class MessageCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ['conversation', 'message', 'message_type']


class ConversationSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    message_count = serializers.IntegerField(source='messages.count', read_only=True)
    
    class Meta:
        model = Conversation
        fields = [
            'id', 'conversation_id', 'user', 'user_email',
            'agent', 'status', 'priority', 'subject',
            'started_at', 'message_count', 'satisfaction_rating'
        ]


class ConversationDetailSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)
    user_details = UserSerializer(source='user', read_only=True)
    agent_details = UserSerializer(source='agent', read_only=True)
    
    class Meta:
        model = Conversation
        fields = '__all__'


class ChatBotTrainingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatBotTraining
        fields = '__all__'


class ChatFeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatFeedback
        fields = ['rating', 'comment', 'resolved_issue', 'agent_helpful', 'response_time_satisfied']