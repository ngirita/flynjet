import random
from django.utils import timezone
from ..models import ChatBotTraining

class ResponseGenerator:
    """Generate responses based on intent"""
    
    @classmethod
    def get_response(cls, intent, context=None):
        """Get response for intent"""
        try:
            training = ChatBotTraining.objects.get(
                intent=intent,
                is_active=True
            )
            
            # Randomly select response
            response = random.choice(training.responses)
            
            # Personalize if context available
            if context and context.get('user_name'):
                response = response.replace('{name}', context['user_name'])
            
            if context and context.get('booking_reference'):
                response = response.replace('{booking}', context['booking_reference'])
            
            return response
            
        except ChatBotTraining.DoesNotExist:
            return cls.get_fallback_response()
    
    @classmethod
    def get_fallback_response(cls):
        """Get fallback response"""
        responses = [
            "I'm not sure I understand. Could you rephrase that?",
            "I don't have an answer for that. Would you like to speak with a human agent?",
            "I'm still learning. Let me connect you with a support agent.",
            "I couldn't understand that. Can you please try asking differently?",
        ]
        return random.choice(responses)
    
    @classmethod
    def get_greeting_response(cls, context=None):
        """Get greeting response"""
        hour = timezone.now().hour
        
        if hour < 12:
            greeting = "Good morning"
        elif hour < 17:
            greeting = "Good afternoon"
        else:
            greeting = "Good evening"
        
        if context and context.get('user_name'):
            return f"{greeting}, {context['user_name']}! How can I help you today?"
        else:
            return f"{greeting}! Welcome to FlynJet. How can I assist you?"
    
    @classmethod
    def get_farewell_response(cls):
        """Get farewell response"""
        responses = [
            "Thank you for chatting with us. Have a great day!",
            "Goodbye! Feel free to reach out if you need anything else.",
            "Thanks for contacting FlynJet. We're here if you need us!",
        ]
        return random.choice(responses)
    
    @classmethod
    def get_booking_response(cls, booking_info=None):
        """Get booking-related response"""
        if booking_info:
            return f"I see you have a booking {booking_info}. How can I help with that?"
        else:
            return "I can help you book a flight. What are your travel plans?"
    
    @classmethod
    def get_payment_response(cls):
        """Get payment-related response"""
        responses = [
            "We accept all major credit cards, bank transfers, and cryptocurrencies.",
            "Payments can be made via credit card, bank transfer, or crypto.",
            "You can pay using Visa, Mastercard, Amex, bank transfer, or USDT/Bitcoin.",
        ]
        return random.choice(responses)
    
    @classmethod
    def get_tracking_response(cls, flight_info=None):
        """Get flight tracking response"""
        if flight_info:
            return f"Flight {flight_info} is currently on time. Would you like live tracking?"
        else:
            return "You can track your flight using your booking reference on our tracking page."