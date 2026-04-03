import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'flynjet.settings')
django.setup()

from django.contrib.auth import get_user_model
User = get_user_model()

# Get admin credentials from environment variables (set in Render)
username = os.environ.get('ADMIN_USERNAME', 'admin')
email = os.environ.get('ADMIN_EMAIL', 'flynjetair@gmail.com')
password = os.environ.get('ADMIN_PASSWORD')

# Ensure password is set in environment
if not password:
    raise ValueError("ADMIN_PASSWORD environment variable not set! Please add it in Render Dashboard.")

# Create superuser only if it doesn't exist
if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username, email, password)
    print(f"✅ Superuser '{username}' created successfully!")
else:
    print(f"ℹ️ Superuser '{username}' already exists.")