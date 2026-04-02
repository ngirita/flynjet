import json
import pickle
import numpy as np
from django.utils import timezone
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from django.conf import settings
import os

class ModelTrainer:
    """Train and save ML models for chatbot"""
    
    def __init__(self):
        self.model_path = os.path.join(settings.BASE_DIR, 'apps/chat/ai/models/')
        self.ensure_model_directory()
    
    def ensure_model_directory(self):
        """Ensure model directory exists"""
        os.makedirs(self.model_path, exist_ok=True)
    
    def prepare_training_data(self):
        """Prepare training data from database"""
        from ..models import ChatBotTraining
        
        trainings = ChatBotTraining.objects.filter(is_active=True)
        
        X = []  # Patterns
        y = []  # Intents
        
        for training in trainings:
            for pattern in training.patterns:
                X.append(pattern)
                y.append(training.intent)
        
        return X, y
    
    def train_intent_classifier(self):
        """Train intent classification model"""
        from ..models import ChatBotTraining
        
        X, y = self.prepare_training_data()
        
        if not X:
            return None
        
        # Create pipeline
        pipeline = Pipeline([
            ('tfidf', TfidfVectorizer(
                lowercase=True,
                stop_words='english',
                ngram_range=(1, 2)
            )),
            ('clf', MultinomialNB())
        ])
        
        # Train
        pipeline.fit(X, y)
        
        # Save model
        model_file = os.path.join(self.model_path, 'intent_model.pkl')
        with open(model_file, 'wb') as f:
            pickle.dump(pipeline, f)
        
        return pipeline
    
    def train_response_selector(self):
        """Train response selection model"""
        from ..models import ChatBotTraining
        
        # This would be a more complex model for response selection
        # For now, we'll just save the response mappings
        
        response_map = {}
        trainings = ChatBotTraining.objects.filter(is_active=True)
        
        for training in trainings:
            response_map[training.intent] = {
                'responses': training.responses,
                'context': training.context
            }
        
        # Save response map
        response_file = os.path.join(self.model_path, 'response_map.json')
        with open(response_file, 'w') as f:
            json.dump(response_map, f, indent=2)
        
        return response_map
    
    def train_all(self):
        """Train all models"""
        intent_model = self.train_intent_classifier()
        response_map = self.train_response_selector()
        
        return {
            'intent_model': intent_model is not None,
            'response_map': response_map is not None,
            'timestamp': timezone.now().isoformat()
        }
    
    def load_intent_model(self):
        """Load trained intent model"""
        model_file = os.path.join(self.model_path, 'intent_model.pkl')
        
        if os.path.exists(model_file):
            with open(model_file, 'rb') as f:
                return pickle.load(f)
        
        return None
    
    def load_response_map(self):
        """Load response map"""
        response_file = os.path.join(self.model_path, 'response_map.json')
        
        if os.path.exists(response_file):
            with open(response_file, 'r') as f:
                return json.load(f)
        
        return {}