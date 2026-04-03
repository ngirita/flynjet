import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'flynjet.settings')
django.setup()

from django.contrib.auth import get_user_model
User = get_user_model()

# Hardcoded credentials (only for build time)
username = 'admin'
email = 'flynjetair@gmail.com'
password = 'MyAdminFlynjetCompanyBusiness1$'

if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username, email, password)
    print(f"✅ Superuser '{username}' created successfully!")
else:
    print(f"ℹ️ Superuser '{username}' already exists.")