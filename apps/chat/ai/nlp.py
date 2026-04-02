import re
import json
import random
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from django.utils import timezone
from django.db.models import Q, Count
from ..models import ChatBotTraining
import logging

logger = logging.getLogger(__name__)

class NLPProcessor:
    """Natural Language Processing for chatbot with real database integration"""
    
    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            lowercase=True,
            stop_words='english',
            ngram_range=(1, 2)
        )
        self.training_data = []
        self.vectors = None
        self._is_initialized = False
        self.conversation_context = {}
    
    def initialize(self):
        """Initialize the processor with database data (must be called in sync context)"""
        if self._is_initialized:
            logger.info("NLP processor already initialized, skipping")
            return
        
        logger.info("Initializing NLP processor with training data")
        
        try:
            trainings = ChatBotTraining.objects.filter(is_active=True)
            logger.info(f"Found {trainings.count()} active training intents")
            
            if trainings.exists():
                for training in trainings:
                    for pattern in training.patterns:
                        self.training_data.append({
                            'intent': training.intent,
                            'pattern': pattern.lower(),
                            'responses': training.responses,
                            'context': training.context,
                            'transfer_to_agent': training.intent == 'agent'
                        })
                logger.info(f"Loaded {len(self.training_data)} training patterns from database")
            else:
                logger.info("No training data found, using default patterns")
                self.training_data = self.get_default_training_data()
                self.save_default_training_data()
            
            if self.training_data:
                self.train()
                logger.info(f"Training complete, vectors shape: {self.vectors.shape if self.vectors is not None else 'None'}")
            
            self._is_initialized = True
            logger.info("NLP processor initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing NLP processor: {e}")
            raise
    
    def get_default_training_data(self):
        """Get default training data with extensive patterns"""
        return [
            # ========== GREETINGS ==========
            {'intent': 'greeting', 'pattern': 'hello', 'responses': ["Hello! Welcome to FlynJet. How can I assist you today?"], 'context': '', 'transfer_to_agent': False},
            {'intent': 'greeting', 'pattern': 'hi', 'responses': ["Hi there. I am your FlynJet virtual assistant. Need help with bookings, fleet info, or anything else?"], 'context': '', 'transfer_to_agent': False},
            {'intent': 'greeting', 'pattern': 'hey', 'responses': ["Hey there. How can I help you with your travel plans today?"], 'context': '', 'transfer_to_agent': False},
            {'intent': 'greeting', 'pattern': 'good morning', 'responses': ["Good morning. Ready to assist with your private jet needs today."], 'context': '', 'transfer_to_agent': False},
            {'intent': 'greeting', 'pattern': 'good afternoon', 'responses': ["Good afternoon. How can I make your travel experience exceptional today?"], 'context': '', 'transfer_to_agent': False},
            {'intent': 'greeting', 'pattern': 'good evening', 'responses': ["Good evening. How can I help you with your luxury travel plans?"], 'context': '', 'transfer_to_agent': False},
            {'intent': 'greeting', 'pattern': 'how are you', 'responses': ["I am doing great, thank you for asking. How can I help you with your travel needs today?"], 'context': '', 'transfer_to_agent': False},
            {'intent': 'greeting', 'pattern': 'what\'s up', 'responses': ["Not much, just here to help you with private jet charters. What can I do for you?"], 'context': '', 'transfer_to_agent': False},
            {'intent': 'greeting', 'pattern': 'howdy', 'responses': ["Howdy. Welcome to FlynJet. Ready to help with your aviation needs."], 'context': '', 'transfer_to_agent': False},
            {'intent': 'greeting', 'pattern': 'greetings', 'responses': ["Greetings. Welcome to FlynJet. How may I assist you today?"], 'context': '', 'transfer_to_agent': False},
            
            # ========== FAREWELLS ==========
            {'intent': 'farewell', 'pattern': 'goodbye', 'responses': ["Thank you for chatting with FlynJet. Have a wonderful day and safe travels."], 'context': '', 'transfer_to_agent': False},
            {'intent': 'farewell', 'pattern': 'bye', 'responses': ["Goodbye. We are here whenever you need us. Safe travels."], 'context': '', 'transfer_to_agent': False},
            {'intent': 'farewell', 'pattern': 'see you', 'responses': ["See you next time. Have a great day."], 'context': '', 'transfer_to_agent': False},
            {'intent': 'farewell', 'pattern': 'take care', 'responses': ["Take care. Feel free to reach out anytime you need assistance."], 'context': '', 'transfer_to_agent': False},
            {'intent': 'farewell', 'pattern': 'later', 'responses': ["Talk soon. Have a wonderful day."], 'context': '', 'transfer_to_agent': False},
            
            # ========== THANKS ==========
            {'intent': 'thanks', 'pattern': 'thank you', 'responses': ["You are very welcome. Is there anything else I can help you with?"], 'context': '', 'transfer_to_agent': False},
            {'intent': 'thanks', 'pattern': 'thanks', 'responses': ["Happy to help. Any other questions about your travel plans?"], 'context': '', 'transfer_to_agent': False},
            {'intent': 'thanks', 'pattern': 'appreciate it', 'responses': ["My pleasure. Let me know if you need anything else."], 'context': '', 'transfer_to_agent': False},
            {'intent': 'thanks', 'pattern': 'thank you so much', 'responses': ["You are very welcome. Anything else I can assist with?"], 'context': '', 'transfer_to_agent': False},
            
            # ========== HELP ==========
            {'intent': 'help', 'pattern': 'help', 'responses': ["I can help you with:\n\n- Booking flights\n- Checking booking status\n- Fleet information\n- Pricing and quotes\n- Connecting you to a human agent\n\nWhat would you like to do?"], 'context': '', 'transfer_to_agent': False},
            {'intent': 'help', 'pattern': 'what can you do', 'responses': ["I am your FlynJet virtual assistant. I can help you with:\n\n- Book a flight\n- Check booking status\n- Learn about our fleet\n- Get pricing quotes\n- Connect you to a human agent\n\nWhat interests you?"], 'context': '', 'transfer_to_agent': False},
            {'intent': 'help', 'pattern': 'how can you help', 'responses': ["I can assist with bookings, status checks, fleet information, pricing, and connecting you to agents. What do you need help with?"], 'context': '', 'transfer_to_agent': False},
            {'intent': 'help', 'pattern': 'i need help', 'responses': ["I am here to help. What can I assist you with today?"], 'context': '', 'transfer_to_agent': False},
            
            # ========== BOOKING ==========
            {'intent': 'booking', 'pattern': 'book a flight', 'responses': ["I would be happy to help you book a flight. Please provide:\n\n- Departure city or airport\n- Destination\n- Travel date\n- Number of passengers\n\nOnce I have these details, I can check availability and provide pricing."], 'context': '', 'transfer_to_agent': False},
            {'intent': 'booking', 'pattern': 'book flight', 'responses': ["Let us get you booked. What is your departure city and destination?"], 'context': '', 'transfer_to_agent': False},
            {'intent': 'booking', 'pattern': 'booking', 'responses': ["I can help with your booking. Are you looking to make a new booking or check an existing one?"], 'context': '', 'transfer_to_agent': False},
            {'intent': 'booking', 'pattern': 'bookings', 'responses': ["I would be happy to help with bookings. Would you like to make a new booking or check an existing one?"], 'context': '', 'transfer_to_agent': False},
            {'intent': 'booking', 'pattern': 'make a reservation', 'responses': ["I would be happy to help you make a reservation. Please share your travel details."], 'context': '', 'transfer_to_agent': False},
            {'intent': 'booking', 'pattern': 'reserve a jet', 'responses': ["I can help you reserve a jet. Please share your travel details."], 'context': '', 'transfer_to_agent': False},
            {'intent': 'booking', 'pattern': 'new booking', 'responses': ["Great. Let us create a new booking. Where would you like to fly?"], 'context': '', 'transfer_to_agent': False},
            {'intent': 'booking', 'pattern': 'need to book', 'responses': ["Let me help you book a flight. What are your travel plans?"], 'context': '', 'transfer_to_agent': False},
            
            # ========== STATUS ==========
            {'intent': 'status', 'pattern': 'check status', 'responses': ["I can help check your booking status. Please provide your booking reference number (e.g., FJABC12345)."], 'context': '', 'transfer_to_agent': False},
            {'intent': 'status', 'pattern': 'booking status', 'responses': ["Please share your booking reference number to check the status."], 'context': '', 'transfer_to_agent': False},
            {'intent': 'status', 'pattern': 'check my booking', 'responses': ["Let me check your booking. What is your reference number?"], 'context': '', 'transfer_to_agent': False},
            {'intent': 'status', 'pattern': 'view booking', 'responses': ["I can show you your booking details. Please share your reference number."], 'context': '', 'transfer_to_agent': False},
            {'intent': 'status', 'pattern': 'flight status', 'responses': ["To check flight status, I will need your booking reference or flight number."], 'context': '', 'transfer_to_agent': False},
            {'intent': 'status', 'pattern': 'track flight', 'responses': ["I can track your flight. Please provide your booking reference."], 'context': '', 'transfer_to_agent': False},
            {'intent': 'status', 'pattern': 'where is my flight', 'responses': ["I will help you track your flight. Please provide your booking reference."], 'context': '', 'transfer_to_agent': False},
            
            # ========== FLEET ==========
            {'intent': 'fleet', 'pattern': 'what jets', 'responses': ["Let me fetch our current fleet information for you."], 'context': '', 'transfer_to_agent': False},
            {'intent': 'fleet', 'pattern': 'fleet', 'responses': ["Let me get you our fleet information."], 'context': '', 'transfer_to_agent': False},
            {'intent': 'fleet', 'pattern': 'aircraft', 'responses': ["I will show you our aircraft fleet."], 'context': '', 'transfer_to_agent': False},
            {'intent': 'fleet', 'pattern': 'planes', 'responses': ["Let me get details about our aircraft."], 'context': '', 'transfer_to_agent': False},
            {'intent': 'fleet', 'pattern': 'aircraft types', 'responses': ["I can show you the different aircraft types we offer."], 'context': '', 'transfer_to_agent': False},
            
            # ========== PRICING ==========
            {'intent': 'pricing', 'pattern': 'how much', 'responses': ["Pricing varies based on aircraft type, distance, and duration. Would you like a custom quote?"], 'context': '', 'transfer_to_agent': False},
            {'intent': 'pricing', 'pattern': 'cost', 'responses': ["Cost depends on several factors. Let me know your travel details for an accurate quote."], 'context': '', 'transfer_to_agent': False},
            {'intent': 'pricing', 'pattern': 'quote', 'responses': ["I can help you get a quote. Please share your travel details."], 'context': '', 'transfer_to_agent': False},
            {'intent': 'pricing', 'pattern': 'price estimate', 'responses': ["I can help you get a price estimate. What are your travel plans?"], 'context': '', 'transfer_to_agent': False},
            {'intent': 'pricing', 'pattern': 'get a quote', 'responses': ["I would be happy to provide a quote. Please share your travel details."], 'context': '', 'transfer_to_agent': False},
            
            # ========== AGENT ==========
            {'intent': 'agent', 'pattern': 'talk to agent', 'responses': ["I will connect you with a human agent. One moment please."], 'context': '', 'transfer_to_agent': True},
            {'intent': 'agent', 'pattern': 'speak to human', 'responses': ["Sure. Let me transfer you to a support agent."], 'context': '', 'transfer_to_agent': True},
            {'intent': 'agent', 'pattern': 'human agent', 'responses': ["I will connect you with a human agent right away."], 'context': '', 'transfer_to_agent': True},
            {'intent': 'agent', 'pattern': 'live agent', 'responses': ["Connecting you to a live agent. Please wait."], 'context': '', 'transfer_to_agent': True},
            {'intent': 'agent', 'pattern': 'customer service', 'responses': ["I will connect you with customer service."], 'context': '', 'transfer_to_agent': True},
            
            # ========== CANCELLATION ==========
            {'intent': 'cancellation', 'pattern': 'cancel booking', 'responses': ["I can help you cancel your booking. Please provide your booking reference number."], 'context': '', 'transfer_to_agent': False},
            {'intent': 'cancellation', 'pattern': 'cancel flight', 'responses': ["I will help you cancel your flight. What is your booking reference?"], 'context': '', 'transfer_to_agent': False},
            {'intent': 'cancellation', 'pattern': 'refund', 'responses': ["I can help with refunds. Please share your booking details."], 'context': '', 'transfer_to_agent': False},
            
            # ========== PAYMENT ==========
            {'intent': 'payment', 'pattern': 'payment', 'responses': ["We accept credit cards, bank transfers, and cryptocurrencies. How would you like to pay?"], 'context': '', 'transfer_to_agent': False},
            {'intent': 'payment', 'pattern': 'pay', 'responses': ["You can pay via credit card, bank transfer, or crypto. Would you like to make a payment?"], 'context': '', 'transfer_to_agent': False},
            {'intent': 'payment', 'pattern': 'payment methods', 'responses': ["We accept Visa, Mastercard, Amex, bank transfers, USDT, Bitcoin, and Ethereum."], 'context': '', 'transfer_to_agent': False},
        ]
    
    def save_default_training_data(self):
        """Save default training data to database"""
        for item in self.get_default_training_data():
            ChatBotTraining.objects.get_or_create(
                intent=item['intent'],
                patterns=[item['pattern']],
                defaults={
                    'responses': item['responses'],
                    'context': item.get('context', ''),
                    'is_active': True
                }
            )
        logger.info("Saved default training data")
    
    def train(self):
        """Train the model on loaded data"""
        patterns = [item['pattern'].lower() for item in self.training_data]
        self.vectors = self.vectorizer.fit_transform(patterns)
        logger.info(f"Trained NLP model on {len(patterns)} patterns")
    
    def extract_booking_reference(self, message):
        """Extract booking reference from message"""
        fj_pattern = r'\b(FJ[A-Z0-9]{8})\b'
        fj_match = re.search(fj_pattern, message.upper())
        if fj_match:
            return fj_match.group(1)
        
        fj_hyphen_pattern = r'\bFJ[-]([A-Z0-9]{8})\b'
        fj_hyphen_match = re.search(fj_hyphen_pattern, message.upper())
        if fj_hyphen_match:
            return f"FJ{fj_hyphen_match.group(1)}"
        
        ref_pattern = r'\b([A-Z0-9]{8,12})\b'
        ref_match = re.search(ref_pattern, message.upper())
        if ref_match:
            return ref_match.group(1)
        
        return None
    
    def find_booking(self, reference, user=None):
        """Find booking in database by reference"""
        try:
            from apps.bookings.models import Booking
            
            clean_ref = reference.upper().strip()
            booking = Booking.objects.filter(
                Q(booking_reference__iexact=clean_ref) |
                Q(booking_reference__icontains=clean_ref)
            ).first()
            
            if booking and user and booking.user != user:
                return None
            
            return booking
        except Exception as e:
            logger.error(f"Error finding booking: {e}")
            return None
    
    def get_booking_details_response(self, booking, reference, user=None):
        """Generate detailed response with real booking information"""
        if user and booking.user != user:
            return {
                'intent': 'booking_not_authorized',
                'confidence': 0.95,
                'response': f"I found a booking with reference {reference}, but it does not belong to your account. Please contact support if this is your booking.",
                'suggestions': ['Contact support', 'Try another reference', 'Talk to agent'],
                'context': 'booking_not_authorized',
                'transfer_to_agent': True
            }
        
        departure_date = booking.departure_datetime.strftime('%B %d, %Y at %I:%M %p')
        arrival_date = booking.arrival_datetime.strftime('%B %d, %Y at %I:%M %p')
        total_amount = f"${float(booking.total_amount_usd):,.2f}"
        amount_paid = f"${float(booking.amount_paid):,.2f}"
        amount_due = f"${float(booking.amount_due):,.2f}"
        aircraft_name = f"{booking.aircraft.manufacturer.name} {booking.aircraft.model}" if booking.aircraft else "Aircraft"
        
        response = f"""**Booking Details for {booking.booking_reference}**

Flight Information:
Aircraft: {aircraft_name}
From: {booking.departure_airport}
To: {booking.arrival_airport}
Departure: {departure_date}
Arrival: {arrival_date}
Passengers: {booking.passenger_count}

Financial Summary:
Total: {total_amount}
Paid: {amount_paid}
Due: {amount_due}

Status: {booking.get_status_display()}
Payment Status: {booking.get_payment_status_display()}

Would you like to:
- View full booking details
- Make a payment
- Modify this booking
- Cancel this booking
- Speak with an agent
"""
        
        return {
            'intent': 'booking_found',
            'confidence': 0.99,
            'response': response,
            'suggestions': ['View full details', 'Make a payment', 'Modify booking', 'Cancel booking', 'Talk to agent'],
            'context': 'booking_details',
            'transfer_to_agent': False,
            'booking_data': {
                'reference': booking.booking_reference,
                'status': booking.status,
                'payment_status': booking.payment_status,
                'total_amount': float(booking.total_amount_usd),
                'amount_paid': float(booking.amount_paid),
                'amount_due': float(booking.amount_due),
                'departure_airport': booking.departure_airport,
                'arrival_airport': booking.arrival_airport,
                'departure_datetime': booking.departure_datetime.isoformat(),
                'arrival_datetime': booking.arrival_datetime.isoformat(),
                'passenger_count': booking.passenger_count
            }
        }
    
    def get_fleet_info_response(self, user=None):
        """Get real fleet information from database"""
        try:
            from apps.fleet.models import Aircraft, AircraftCategory
            
            total_aircraft = Aircraft.objects.filter(is_active=True).count()
            categories = AircraftCategory.objects.filter(is_active=True)
            category_lines = []
            
            for category in categories:
                count = Aircraft.objects.filter(category=category, is_active=True).count()
                if count > 0:
                    category_lines.append(f"{category.name}: {count} aircraft")
            
            category_text = "\n  - ".join(category_lines) if category_lines else "No aircraft found"
            
            featured_aircraft = Aircraft.objects.filter(is_active=True, is_featured=True)[:3]
            featured_text = ""
            if featured_aircraft:
                featured_list = []
                for a in featured_aircraft:
                    featured_list.append(f"  - {a.manufacturer.name} {a.model} (Capacity: {a.passenger_capacity} passengers)")
                featured_text = "\n\nFeatured Aircraft:\n" + "\n".join(featured_list)
            
            response = f"""**FlynJet Fleet Overview**

We currently have {total_aircraft} aircraft in our active fleet.

Fleet Breakdown:
  - {category_text}
{featured_text}

Our aircraft are available for:
  - Private charters
  - Corporate travel
  - Group charters
  - Cargo services

Would you like more details about specific aircraft types or get a quote?
"""
            
            return {
                'intent': 'fleet_info',
                'confidence': 0.95,
                'response': response,
                'suggestions': ['Light Jets', 'Midsize Jets', 'Heavy Jets', 'VIP Airliners', 'Get a quote', 'Talk to agent'],
                'context': 'fleet_info',
                'transfer_to_agent': False
            }
        except Exception as e:
            logger.error(f"Error getting fleet info: {e}")
            return None
    
    def get_user_bookings_response(self, user):
        """Get all bookings for a user"""
        try:
            from apps.bookings.models import Booking
            
            bookings = Booking.objects.filter(user=user).order_by('-created_at')[:5]
            
            if not bookings.exists():
                return {
                    'intent': 'no_bookings',
                    'confidence': 0.9,
                    'response': "You do not have any bookings yet. Would you like to book a flight?",
                    'suggestions': ['Book a flight', 'View fleet', 'Talk to agent'],
                    'context': 'no_bookings',
                    'transfer_to_agent': False
                }
            
            response_lines = ["Your Recent Bookings:", ""]
            for booking in bookings:
                response_lines.append(f"- {booking.booking_reference}")
                response_lines.append(f"  From: {booking.departure_airport} to {booking.arrival_airport}")
                response_lines.append(f"  Date: {booking.departure_datetime.strftime('%b %d, %Y')}")
                response_lines.append(f"  Status: {booking.get_status_display()}")
                response_lines.append("")
            
            response_lines.append("To view details of a specific booking, please provide the booking reference number.")
            response = "\n".join(response_lines)
            
            return {
                'intent': 'user_bookings',
                'confidence': 0.95,
                'response': response,
                'suggestions': ['Check specific booking', 'Make a payment', 'Book new flight', 'Talk to agent'],
                'context': 'user_bookings',
                'transfer_to_agent': False
            }
        except Exception as e:
            logger.error(f"Error getting user bookings: {e}")
            return None
    
    def get_aircraft_details_response(self):
        """Get detailed aircraft information"""
        try:
            response = """**Aircraft Types We Offer**

Light Jets (4-6 passengers)
  - Perfect for short trips (up to 3 hours)
  - Popular models: Citation CJ3, Phenom 300
  - Hourly rate: $3,000 - $5,000

Midsize Jets (6-8 passengers)
  - Ideal for business travel
  - Range: 2-4 hours
  - Popular models: Hawker 800, Citation XLS
  - Hourly rate: $4,500 - $7,000

Heavy Jets (10-16 passengers)
  - Luxury long-haul flights
  - Range: 4-8 hours
  - Popular models: Gulfstream G450, Falcon 2000
  - Hourly rate: $7,000 - $12,000

VIP Airliners (16-50 passengers)
  - Group charters
  - Popular models: Boeing Business Jet, Airbus ACJ
  - Custom pricing available

Would you like a quote for any of these categories?
"""
            
            return {
                'intent': 'aircraft_details',
                'confidence': 0.95,
                'response': response,
                'suggestions': ['Light Jets pricing', 'Heavy Jets pricing', 'Get a quote', 'Talk to agent'],
                'context': 'aircraft_types',
                'transfer_to_agent': False
            }
        except Exception as e:
            logger.error(f"Error getting aircraft details: {e}")
            return None
    
    def get_quote_prompt_response(self):
        """Get quote prompt response"""
        return {
            'intent': 'get_quote',
            'confidence': 0.95,
            'response': "I would be happy to provide a quote. Please share your travel details:\n\nPlease provide:\n  - Departure city or airport (e.g., JFK, Miami, Los Angeles)\n  - Destination\n  - Travel date\n  - Number of passengers\n\nOnce I have these details, I will give you an accurate estimate.",
            'suggestions': ['JFK to LAX on Dec 15', 'Miami to New York', 'Los Angeles to Chicago', '3 passengers'],
            'context': 'awaiting_quote_details',
            'transfer_to_agent': False
        }
    
    def process_message(self, message, conversation_id=None, user=None):
        """Process a message and return response"""
        # Check if initialized
        if not self._is_initialized:
            logger.error("NLP processor not initialized. This should not happen at runtime.")
            return self.get_fallback_response()
        
        logger.info(f"process_message called with: message={message}")
        
        if not self.training_data or self.vectors is None:
            logger.warning("No training data or vectors")
            return self.get_fallback_response()
        
        message_lower = message.lower().strip()
        logger.info(f"Message lower: {message_lower}")
        
        # Check for booking reference
        booking_ref = self.extract_booking_reference(message_lower)
        if booking_ref:
            booking = self.find_booking(booking_ref, user)
            if booking:
                return self.get_booking_details_response(booking, booking_ref, user)
            else:
                return {
                    'intent': 'booking_not_found',
                    'confidence': 0.95,
                    'response': f"I could not find a booking with reference {booking_ref}. Please double-check and try again.",
                    'suggestions': ['Try again', 'Contact support', 'Talk to agent'],
                    'context': 'booking_not_found',
                    'transfer_to_agent': False
                }
        
        # Check for greetings
        greeting_patterns = ['hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening', 'how are you', 'what\'s up', 'howdy', 'greetings']
        if any(word in message_lower for word in greeting_patterns):
            # Return a random greeting response
            greetings = [
                "Hello. Welcome to FlynJet. How can I assist you today?",
                "Hi there. I am your FlynJet virtual assistant. Need help with bookings, fleet info, or anything else?",
                "Good to see you. How can I help with your travel plans today?",
                "Welcome to FlynJet. I am here to help with your private jet needs."
            ]
            return {
                'intent': 'greeting',
                'confidence': 0.95,
                'response': random.choice(greetings),
                'suggestions': ['Book a flight', 'Check status', 'View fleet', 'Get a quote', 'Talk to agent'],
                'context': 'greeting',
                'transfer_to_agent': False
            }
        
        # Check for affirmative responses (yes, sure, please, etc.)
        affirmative_patterns = ['yes', 'sure', 'ok', 'okay', 'yeah', 'yep', 'please', 'yes please', 'sure thing', 'i would', 'i would like', 'i\'d like']
        get_quote_patterns = ['quote', 'pricing', 'cost', 'price', 'estimate', 'how much', 'get a quote']
        aircraft_details_patterns = ['details', 'aircraft', 'jet', 'plane', 'types', 'specifications', 'light jet', 'midsize jet', 'heavy jet']
        
        # Check if this is a follow-up
        if any(word in message_lower for word in affirmative_patterns):
            if any(word in message_lower for word in get_quote_patterns):
                return self.get_quote_prompt_response()
            elif any(word in message_lower for word in aircraft_details_patterns):
                aircraft_response = self.get_aircraft_details_response()
                if aircraft_response:
                    return aircraft_response
            else:
                return {
                    'intent': 'affirmative',
                    'confidence': 0.85,
                    'response': "Great. How can I help you further? You can:\n  - Get a quote - Tell me your travel details\n  - Learn about aircraft - See our fleet details\n  - Book a flight - Start the booking process\n  - Talk to an agent - Connect with a human agent\n\nWhat would you like to do?",
                    'suggestions': ['Get a quote', 'Show me aircraft', 'Book a flight', 'Talk to agent'],
                    'context': 'main_menu',
                    'transfer_to_agent': False
                }
        
        # Check for get quote directly
        if any(word in message_lower for word in get_quote_patterns):
            return self.get_quote_prompt_response()
        
        # Check for aircraft details directly
        if any(word in message_lower for word in aircraft_details_patterns):
            aircraft_response = self.get_aircraft_details_response()
            if aircraft_response:
                return aircraft_response
        
        # Check for my bookings
        booking_keywords = ['my bookings', 'my flights', 'my reservations', 'show my bookings', 'my trips']
        if any(word in message_lower for word in booking_keywords):
            if user and user.is_authenticated:
                return self.get_user_bookings_response(user)
            else:
                return {
                    'intent': 'login_required',
                    'confidence': 0.9,
                    'response': "I would love to show you your bookings, but I need you to log in first.",
                    'suggestions': ['Login', 'Continue as guest', 'Talk to agent'],
                    'context': 'login_required',
                    'transfer_to_agent': False
                }
        
        # Check for fleet-related queries
        fleet_keywords = ['fleet', 'aircraft', 'jets', 'planes', 'what jets', 'aircraft types', 'fleet info']
        if any(word in message_lower for word in fleet_keywords):
            fleet_response = self.get_fleet_info_response(user)
            if fleet_response:
                return fleet_response
        
        # Vectorize input message for intent classification
        message_vector = self.vectorizer.transform([message_lower])
        similarities = cosine_similarity(message_vector, self.vectors).flatten()
        
        best_idx = np.argmax(similarities)
        best_score = similarities[best_idx]
        
        threshold = 0.12
        if best_score < threshold:
            return self.get_fallback_response()
        
        matched_item = self.training_data[best_idx]
        intent = matched_item['intent']
        response = random.choice(matched_item['responses'])
        
        self.update_training_stats(intent, True)
        suggestions = self.get_suggestions(intent)
        
        return {
            'intent': intent,
            'confidence': float(best_score),
            'response': response,
            'suggestions': suggestions,
            'context': matched_item['context'],
            'transfer_to_agent': matched_item.get('transfer_to_agent', False)
        }
    
    def get_fallback_response(self):
        return {
            'intent': 'fallback',
            'confidence': 0.0,
            'response': "I am not sure I understand. Would you like to speak with a human agent?",
            'suggestions': ['Talk to agent', 'Book a flight', 'Check status'],
            'context': '',
            'transfer_to_agent': False
        }
    
    def get_suggestions(self, intent):
        suggestions_map = {
            'booking': ['Book a flight', 'Check availability', 'View my bookings', 'Get a quote'],
            'status': ['Check booking status', 'Track flight', 'Enter reference', 'Flight details'],
            'fleet': ['Light Jets', 'Midsize Jets', 'Heavy Jets', 'VIP Airliners', 'Compare aircraft'],
            'pricing': ['Get a quote', 'Payment methods', 'Special offers', 'Price estimate'],
            'agent': ['Yes, connect me', 'No, I am fine', 'I will wait'],
            'greeting': ['Book a flight', 'Check status', 'Talk to agent', 'Fleet info', 'Get quote'],
            'farewell': ['Rate chat', 'Email transcript', 'Start over', 'Book another flight'],
            'thanks': ['You are welcome', 'Anything else', 'Book another flight'],
            'help': ['Book a flight', 'Check status', 'Talk to agent', 'Pricing', 'Fleet info'],
            'fallback': ['Talk to agent', 'Book a flight', 'Check status', 'Fleet info', 'Get quote']
        }
        return suggestions_map.get(intent, ['Talk to agent', 'Book a flight', 'Check status', 'Get quote'])
    
    def update_training_stats(self, intent, successful):
        try:
            training = ChatBotTraining.objects.filter(intent=intent, is_active=True).first()
            if training:
                training.times_used += 1
                if successful:
                    training.success_rate = ((training.success_rate * (training.times_used - 1)) + 1) / training.times_used
                training.last_used = timezone.now()
                training.save()
        except Exception as e:
            logger.error(f"Error updating training stats: {e}")
    
    def extract_entities(self, message):
        entities = {}
        ref_match = re.search(r'\b(FJ[A-Z0-9]{8})\b', message.upper())
        if ref_match:
            entities['booking_reference'] = ref_match.group(1)
        
        date_pattern = r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}'
        date_match = re.search(date_pattern, message)
        if date_match:
            entities['date'] = date_match.group()
        
        airport_pattern = r'\b[A-Z]{3}\b'
        airports = re.findall(airport_pattern, message.upper())
        if len(airports) >= 2:
            entities['from_airport'] = airports[0]
            entities['to_airport'] = airports[1]
        elif len(airports) == 1:
            entities['airport'] = airports[0]
        
        number_pattern = r'\b\d+\b'
        numbers = re.findall(number_pattern, message)
        if numbers:
            entities['numbers'] = [int(n) for n in numbers]
        
        return entities