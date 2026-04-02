from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from .models import Conversation, Message, ChatBotTraining
from .ai.nlp import NLPProcessor

User = get_user_model()

class ChatModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
    
    def test_create_conversation(self):
        conversation = Conversation.objects.create(
            user=self.user,
            subject='Test Conversation',
            status='active'
        )
        
        self.assertEqual(conversation.conversation_id[:4], 'CHAT')
        self.assertEqual(conversation.user, self.user)
        self.assertEqual(conversation.status, 'active')
    
    def test_create_message(self):
        conversation = Conversation.objects.create(
            user=self.user,
            subject='Test Conversation'
        )
        
        message = Message.objects.create(
            conversation=conversation,
            sender=self.user,
            message='Hello, this is a test message'
        )
        
        self.assertEqual(message.message, 'Hello, this is a test message')
        self.assertFalse(message.is_read)
    
    def test_assign_agent(self):
        conversation = Conversation.objects.create(
            user=self.user,
            subject='Test Conversation'
        )
        
        agent = User.objects.create_user(
            email='agent@example.com',
            password='agentpass123',
            user_type='agent'
        )
        
        conversation.assign_agent(agent)
        
        self.assertEqual(conversation.agent, agent)
        self.assertEqual(conversation.status, 'active')
        self.assertIsNotNone(conversation.first_response_at)

class ChatAITest(TestCase):
    def setUp(self):
        # Create training data
        ChatBotTraining.objects.create(
            intent='greeting',
            patterns=['hello', 'hi', 'hey', 'good morning'],
            responses=['Hello! How can I help you today?', 'Hi there! What can I do for you?'],
            is_active=True
        )
        
        ChatBotTraining.objects.create(
            intent='booking',
            patterns=['book a flight', 'make a reservation', 'charter a jet'],
            responses=['I can help you book a flight. What are your travel details?'],
            is_active=True
        )
    
    def test_nlp_processor(self):
        processor = NLPProcessor()
        
        # Test greeting
        result = processor.process_message('Hello there')
        self.assertEqual(result['intent'], 'greeting')
        self.assertGreater(result['confidence'], 0.5)
        
        # Test booking
        result = processor.process_message('I want to book a flight')
        self.assertEqual(result['intent'], 'booking')
        self.assertGreater(result['confidence'], 0.5)
        
        # Test unknown
        result = processor.process_message('asdfghjkl')
        self.assertEqual(result['intent'], 'fallback')