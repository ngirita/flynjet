from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from .models import Conversation, Message, ChatBotTraining, ChatFeedback
from .serializers import (
    ConversationSerializer, ConversationDetailSerializer,
    MessageSerializer, MessageCreateSerializer,
    ChatBotTrainingSerializer, ChatFeedbackSerializer
)
from .ai.nlp import NLPProcessor

class ConversationViewSet(viewsets.ModelViewSet):
    """API for conversations"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.user_type in ['admin', 'agent']:
            return Conversation.objects.all()
        return Conversation.objects.filter(user=user)
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ConversationDetailSerializer
        return ConversationSerializer
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Resolve conversation"""
        conversation = self.get_object()
        conversation.resolve()
        return Response({'status': 'resolved'})
    
    @action(detail=True, methods=['post'])
    def feedback(self, request, pk=None):
        """Submit feedback"""
        conversation = self.get_object()
        
        serializer = ChatFeedbackSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(conversation=conversation)
            
            conversation.satisfaction_rating = serializer.validated_data['rating']
            conversation.save(update_fields=['satisfaction_rating'])
            
            return Response(serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MessageViewSet(viewsets.ModelViewSet):
    """API for messages"""
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Message.objects.filter(conversation__user=self.request.user)
    
    def get_serializer_class(self):
        if self.action == 'create':
            return MessageCreateSerializer
        return MessageSerializer
    
    def perform_create(self, serializer):
        message = serializer.save(sender=self.request.user)
        
        # Process with AI if no agent assigned
        if not message.conversation.agent:
            processor = NLPProcessor()
            response = processor.process_message(
                message.message,
                message.conversation.conversation_id
            )
            
            if response and response.get('response'):
                Message.objects.create(
                    conversation=message.conversation,
                    message=response['response'],
                    is_ai=True,
                    sender_name='FlynJet Assistant',
                    intent=response.get('intent', ''),
                    confidence=response.get('confidence', 0.0)
                )


class ChatBotTrainingViewSet(viewsets.ModelViewSet):
    """API for chatbot training data"""
    serializer_class = ChatBotTrainingSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = ChatBotTraining.objects.all()