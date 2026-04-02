import numpy as np
from .training import ModelTrainer

class IntentClassifier:
    """Classify user intent using trained model"""
    
    def __init__(self):
        self.trainer = ModelTrainer()
        self.model = self.trainer.load_intent_model()
        self.response_map = self.trainer.load_response_map()
    
    def classify(self, message):
        """Classify message intent"""
        if not self.model:
            return {
                'intent': 'fallback',
                'confidence': 0.0,
                'response': "I'm still learning. Let me connect you with a human agent."
            }
        
        # Predict
        intent = self.model.predict([message])[0]
        probabilities = self.model.predict_proba([message])[0]
        confidence = float(max(probabilities))
        
        # Get confidence threshold from training data
        from ..models import ChatBotTraining
        try:
            training = ChatBotTraining.objects.get(intent=intent, is_active=True)
            threshold = training.confidence_threshold
        except ChatBotTraining.DoesNotExist:
            threshold = 0.7
        
        if confidence < threshold:
            return {
                'intent': 'fallback',
                'confidence': confidence,
                'response': "I'm not entirely sure I understood. Could you rephrase that?"
            }
        
        # Get response
        from .responses import ResponseGenerator
        response = ResponseGenerator.get_response(intent)
        
        return {
            'intent': intent,
            'confidence': confidence,
            'response': response
        }
    
    def batch_classify(self, messages):
        """Classify multiple messages"""
        if not self.model:
            return [self.classify(m) for m in messages]
        
        predictions = self.model.predict(messages)
        probabilities = self.model.predict_proba(messages)
        
        results = []
        for i, (intent, probs) in enumerate(zip(predictions, probabilities)):
            confidence = float(max(probs))
            results.append({
                'intent': intent,
                'confidence': confidence,
                'message': messages[i]
            })
        
        return results
    
    def get_possible_intents(self, message, top_n=3):
        """Get top N possible intents"""
        if not self.model:
            return []
        
        probabilities = self.model.predict_proba([message])[0]
        classes = self.model.classes_
        
        # Get top N indices
        top_indices = np.argsort(probabilities)[-top_n:][::-1]
        
        results = []
        for idx in top_indices:
            results.append({
                'intent': classes[idx],
                'confidence': float(probabilities[idx])
            })
        
        return results
    
    def update_model(self):
        """Retrain and update model"""
        self.trainer.train_all()
        self.model = self.trainer.load_intent_model()
        self.response_map = self.trainer.load_response_map()