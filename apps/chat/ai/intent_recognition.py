import re
from .classifier import IntentClassifier

class IntentRecognizer:
    """Advanced intent recognition with rule-based fallback"""
    
    def __init__(self):
        self.classifier = IntentClassifier()
        
        # Rule-based patterns for common intents
        self.patterns = {
            'greeting': [
                r'\b(hi|hello|hey|good\s*(morning|afternoon|evening))\b',
                r'\bhowdy\b',
                r'\bgreetings\b'
            ],
            'farewell': [
                r'\b(bye|goodbye|see\s*you|take\s*care)\b',
                r'\bhave\s*a\s*great\s*day\b'
            ],
            'booking': [
                r'\b(book|reserve|charter)\s*(a|the)?\s*(flight|jet|plane)\b',
                r'\b(make|create)\s*(a|the)?\s*(reservation|booking)\b',
                r'\bhow\s*do\s*i\s*book\b'
            ],
            'payment': [
                r'\b(pay|payment|charge|cost|price)\b',
                r'\bhow\s*much\b',
                r'\bwhat\s*(methods|ways)\s*(can|do)\s*i\s*pay\b'
            ],
            'tracking': [
                r'\b(track|where\s*is|status)\s*(my)?\s*(flight|jet|plane)\b',
                r'\bflight\s*status\b',
                r'\bis\s*my\s*flight\s*on\s*time\b'
            ],
            'cancellation': [
                r'\b(cancel|cancellation)\s*(my)?\s*(booking|flight|reservation)\b',
                r'\bhow\s*do\s*i\s*cancel\b',
                r'\b(refund|money\s*back)\b'
            ],
            'baggage': [
                r'\b(baggage|bag|luggage|suitcase)\b',
                r'\bhow\s*much\s*(baggage|luggage)\b',
                r'\b(weight|size)\s*(limit|restriction)\b'
            ],
            'help': [
                r'\b(help|support|assist|can\s*you\s*help)\b',
                r'\bwhat\s*can\s*you\s*do\b',
                r'\bi\s*need\s*help\b'
            ],
        }
    
    def recognize(self, message):
        """Recognize intent from message"""
        message_lower = message.lower()
        
        # Try rule-based first
        for intent, patterns in self.patterns.items():
            for pattern in patterns:
                if re.search(pattern, message_lower):
                    return {
                        'intent': intent,
                        'confidence': 0.9,
                        'method': 'rule'
                    }
        
        # Fall back to ML classifier
        result = self.classifier.classify(message)
        result['method'] = 'ml'
        return result
    
    def extract_entities(self, message):
        """Extract entities from message"""
        entities = {}
        
        # Extract dates
        date_patterns = [
            r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b',
            r'\b(tomorrow|today|next\s*\w+)\b',
            r'\b(jan(uary)?|feb(ruary)?|mar(ch)?|apr(il)?|may|jun(e)?|jul(y)?|aug(ust)?|sep(tember)?|oct(ober)?|nov(ember)?|dec(ember)?)\s*\d{1,2}\b'
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                entities['date'] = match.group()
                break
        
        # Extract airport codes
        airport_pattern = r'\b([A-Z]{3})\b'
        airports = re.findall(airport_pattern, message.upper())
        if len(airports) >= 2:
            entities['from_airport'] = airports[0]
            entities['to_airport'] = airports[1]
        elif len(airports) == 1:
            entities['airport'] = airports[0]
        
        # Extract numbers (passengers, etc.)
        number_pattern = r'\b(\d+)\b'
        numbers = re.findall(number_pattern, message)
        if numbers:
            entities['numbers'] = [int(n) for n in numbers]
        
        # Extract booking references
        booking_pattern = r'\b([A-Z0-9]{8,12})\b'
        booking_match = re.search(booking_pattern, message.upper())
        if booking_match:
            entities['booking_reference'] = booking_match.group()
        
        return entities
    
    def get_context(self, message):
        """Get context from message"""
        entities = self.extract_entities(message)
        intent = self.recognize(message)
        
        return {
            'intent': intent,
            'entities': entities,
            'original_message': message
        }