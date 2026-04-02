from flask import Flask, request, jsonify
from flask_cors import CORS
import numpy as np
import joblib
import nltk
import redis
import json
import logging

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)

# Connect to Redis
redis_client = redis.Redis(host='redis', port=6379, db=2)

# Load models
try:
    intent_model = joblib.load('/app/models/intent_model.pkl')
    vectorizer = joblib.load('/app/models/vectorizer.pkl')
    app.logger.info("Models loaded successfully")
except Exception as e:
    app.logger.error(f"Failed to load models: {e}")
    intent_model = None
    vectorizer = None

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'})

@app.route('/predict/intent', methods=['POST'])
def predict_intent():
    data = request.json
    message = data.get('message', '')
    
    if not intent_model or not vectorizer:
        return jsonify({'error': 'Model not loaded'}), 503
    
    # Vectorize message
    X = vectorizer.transform([message])
    
    # Predict intent
    intent = intent_model.predict(X)[0]
    probabilities = intent_model.predict_proba(X)[0]
    confidence = float(max(probabilities))
    
    # Get top 3 intents
    top_indices = np.argsort(probabilities)[-3:][::-1]
    alternatives = [
        {
            'intent': intent_model.classes_[i],
            'confidence': float(probabilities[i])
        }
        for i in top_indices
    ]
    
    return jsonify({
        'intent': intent,
        'confidence': confidence,
        'alternatives': alternatives
    })

@app.route('/train', methods=['POST'])
def train():
    data = request.json
    training_data = data.get('training_data', [])
    
    # Training logic here
    # This would retrain the model
    
    return jsonify({'status': 'training_started'})

@app.route('/cache/<key>', methods=['GET'])
def get_cache(key):
    value = redis_client.get(key)
    if value:
        return jsonify({'key': key, 'value': json.loads(value)})
    return jsonify({'error': 'Key not found'}), 404

@app.route('/cache', methods=['POST'])
def set_cache():
    data = request.json
    key = data.get('key')
    value = data.get('value')
    ttl = data.get('ttl', 3600)
    
    redis_client.setex(key, ttl, json.dumps(value))
    return jsonify({'status': 'cached'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)