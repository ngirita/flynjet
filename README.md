# FlynJet - Private Jet Charter Platform

## Overview
FlynJet is a comprehensive private jet charter and logistics platform that enables users to book private jets, cargo planes, and helicopters with real-time tracking, secure payments, and 24/7 support.

## Features
- ✈️ User Authentication (Email + Social Login)
- 💳 Secure Payments (Credit Cards, Crypto, Bank Transfer)
- 🛩️ Fleet Management with 360° Views
- 📍 Real-Time Flight Tracking
- 💬 AI Chatbot with Human Handoff
- 📄 Printable Invoices
- 👥 Admin Dashboard
- 🔧 Maintenance Management

## Tech Stack
- **Backend**: Django 4.2, Django REST Framework
- **Database**: PostgreSQL
- **Cache/Queue**: Redis, Celery
- **Frontend**: Django Templates, Bootstrap 5, JavaScript
- **Real-time**: Django Channels, WebSockets
- **Payments**: Stripe, Coinbase, Web3
- **Container**: Docker, Nginx

## Installation

### Local Development
```bash
# Clone repository
git clone https://github.com/yourusername/flynjet.git
cd flynjet

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment variables
cp .env.example .env
# Edit .env with your settings

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Run development server
python manage.py runserver