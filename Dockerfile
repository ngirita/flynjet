# Use Python 3.11 slim image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Hardcode database URL for build (required for Docker builds on free tier)
ENV DATABASE_URL=postgresql://neondb_owner:npg_1UCtjIi9fZDW@ep-falling-term-aktjxj41-pooler.c-3.us-west-2.aws.neon.tech/neondb?sslmode=require

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

# Import airport data
RUN python import_airports.py

# Expose port
EXPOSE 10000

# Run gunicorn
CMD ["gunicorn", "flynjet.wsgi:application", "--bind", "0.0.0.0:10000"]