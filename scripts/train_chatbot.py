#!/usr/bin/env python
import os
import sys
import django
from pathlib import Path

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'flynjet.settings')
django.setup()

from apps.chat.ai.training import ModelTrainer
from apps.chat.ai.nlp import NLPProcessor
from apps.chat.models import ChatBotTraining
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_default_training_data():
    """Create default training data if none exists"""
    if ChatBotTraining.objects.exists():
        return
    
    logger.info("Creating default training data...")
    
    training_data = [
        {
            'intent': 'greeting',
            'patterns': [
                'hello', 'hi', 'hey', 'good morning', 'good afternoon',
                'good evening', 'howdy', 'greetings', 'what\'s up'
            ],
            'responses': [
                'Hello! How can I help you today?',
                'Hi there! Welcome to FlynJet support.',
                'Greetings! How may I assist you?'
            ]
        },
        {
            'intent': 'farewell',
            'patterns': [
                'bye', 'goodbye', 'see you', 'take care', 'have a good day',
                'talk to you later', 'thanks bye'
            ],
            'responses': [
                'Goodbye! Have a great day!',
                'Thank you for chatting with us. Farewell!',
                'Take care! Feel free to reach out anytime.'
            ]
        },
        {
            'intent': 'booking',
            'patterns': [
                'book a flight', 'make a reservation', 'charter a jet',
                'how to book', 'i want to book', 'schedule a flight',
                'rent a plane', 'hire a private jet'
            ],
            'responses': [
                'I can help you book a flight. What are your travel details?',
                'To book a flight, please provide your departure and arrival airports, date, and number of passengers.',
                'You can book a flight through our website or I can assist you here. What are your requirements?'
            ]
        },
        {
            'intent': 'payment',
            'patterns': [
                'how to pay', 'payment methods', 'what payment methods',
                'can i pay with crypto', 'do you accept bitcoin',
                'credit card payment', 'bank transfer'
            ],
            'responses': [
                'We accept all major credit cards, bank transfers, and cryptocurrencies including USDT, Bitcoin, and Ethereum.',
                'You can pay via credit card, bank transfer, or cryptocurrency. Which method would you prefer?',
                'Our payment options include Visa, Mastercard, Amex, bank transfer, and major cryptocurrencies.'
            ]
        },
        {
            'intent': 'tracking',
            'patterns': [
                'track my flight', 'where is my flight', 'flight status',
                'is my flight on time', 'flight tracking', 'track my booking'
            ],
            'responses': [
                'You can track your flight using your booking reference on our tracking page.',
                'Please provide your booking reference and I can help you track your flight.',
                'Flight tracking is available on our website. Would you like me to help you find it?'
            ]
        },
        {
            'intent': 'cancellation',
            'patterns': [
                'cancel booking', 'cancel flight', 'how to cancel',
                'i want to cancel', 'refund policy', 'cancellation policy'
            ],
            'responses': [
                'To cancel a booking, please visit your account or contact our support team.',
                'Our cancellation policy varies based on timing. Cancellations made 48 hours or more before departure receive a full refund.',
                'I can help you with the cancellation process. May I have your booking reference?'
            ]
        },
        {
            'intent': 'baggage',
            'patterns': [
                'baggage allowance', 'luggage', 'how much baggage',
                'baggage policy', 'what can i bring', 'weight limit'
            ],
            'responses': [
                'Baggage allowance depends on the aircraft type. Typically, each passenger can bring up to 23kg of checked baggage.',
                'Our standard baggage policy allows 23kg per passenger. Would you like specific information for your flight?',
                'Baggage information is provided in your booking confirmation. Would you like me to check for your flight?'
            ]
        },
        {
            'intent': 'help',
            'patterns': [
                'help', 'support', 'need assistance', 'can you help',
                'i need help', 'what can you do'
            ],
            'responses': [
                'I can help with bookings, payments, flight tracking, cancellations, and general inquiries. What do you need?',
                'I\'m here to assist! You can ask me about bookings, flights, payments, or any other questions.',
                'How can I help you today? Feel free to ask about our services.'
            ]
        }
    ]
    
    for data in training_data:
        ChatBotTraining.objects.create(
            intent=data['intent'],
            patterns=data['patterns'],
            responses=data['responses'],
            is_active=True
        )
    
    logger.info(f"Created {len(training_data)} training intents")

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Train chatbot models')
    parser.add_argument('--create-data', action='store_true', help='Create default training data')
    parser.add_argument('--train', action='store_true', help='Train models')
    
    args = parser.parse_args()
    
    if args.create_data:
        create_default_training_data()
    
    if args.train:
        logger.info("Training chatbot models...")
        trainer = ModelTrainer()
        result = trainer.train_all()
        
        if result['intent_model']:
            logger.info("✓ Intent model trained successfully")
        else:
            logger.error("✗ Intent model training failed")
        
        if result['response_map']:
            logger.info("✓ Response map created successfully")
        else:
            logger.error("✗ Response map creation failed")
        
        logger.info(f"Training completed at: {result['timestamp']}")
    
    if not args.create_data and not args.train:
        parser.print_help()

if __name__ == '__main__':
    main()