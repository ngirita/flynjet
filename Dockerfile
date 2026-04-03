# Use Python 3.11 slim image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    libcairo2 \
    libcairo2-dev \
    libpango-1.0-0 \
    libpango1.0-dev \
    libpangocairo-1.0-0 \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy project files
COPY . .

# Run migrations, create cache table, and collect static files
RUN python manage.py migrate --noinput
RUN python manage.py createcachetable
RUN python manage.py collectstatic --noinput

# Create superuser using Django's shell command
RUN echo "from django.contrib.auth import get_user_model; User = get_user_model(); user, created = User.objects.get_or_create(username='admin', defaults={'email': 'flynjetair@gmail.com', 'is_superuser': True, 'is_staff': True}); user.set_password('MyAdminFlynjetCompanyBusiness1$'); user.save(); print('✅ Superuser created' if created else 'ℹ️ Superuser already exists')" | python manage.py shell

# Expose port
EXPOSE 10000

# Run gunicorn
CMD ["gunicorn", "flynjet.wsgi:application", "--bind", "0.0.0.0:10000"]