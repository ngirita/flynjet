#!/bin/bash

# FlynJet Deployment Script
set -e

echo "🚀 Starting FlynJet deployment..."

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
    echo "✅ Environment variables loaded"
else
    echo "❌ .env file not found"
    exit 1
fi

# Pull latest changes
echo "📦 Pulling latest changes..."
git pull origin main

# Build and start containers
echo "🐳 Building Docker containers..."
docker-compose -f docker-compose.yml build

echo "🔄 Stopping existing containers..."
docker-compose -f docker-compose.yml down

echo "▶️ Starting containers..."
docker-compose -f docker-compose.yml up -d

# Wait for database to be ready
echo "⏳ Waiting for database to be ready..."
sleep 10

# Run migrations
echo "🗃️ Running database migrations..."
docker-compose exec -T web python manage.py migrate --noinput

# Collect static files
echo "📁 Collecting static files..."
docker-compose exec -T web python manage.py collectstatic --noinput

# Create cache tables
echo "⚡ Creating cache tables..."
docker-compose exec -T web python manage.py createcachetable

# Clear cache
echo "🧹 Clearing cache..."
docker-compose exec -T redis redis-cli flushall

# Check if superuser exists, create if not
echo "👤 Checking superuser..."
docker-compose exec -T web python manage.py shell -c "
from django.contrib.auth import get_user_model;
User = get_user_model();
if not User.objects.filter(is_superuser=True).exists():
    User.objects.create_superuser('info@flynjet.com', 'Admin123!@#');
    print('✅ Superuser created');
else:
    print('✅ Superuser exists');
"

# Load initial data if needed
echo "📊 Loading initial data..."
docker-compose exec -T web python manage.py loaddata initial_data.json || true

# Restart nginx
echo "🌐 Restarting nginx..."
docker-compose exec -T nginx nginx -s reload

# Check services health
echo "🏥 Checking service health..."
services=("web" "celery" "celery-beat" "nginx" "redis" "db")
for service in "${services[@]}"; do
    if docker-compose ps | grep -q "${service}.*Up"; then
        echo "✅ $service is running"
    else
        echo "❌ $service is not running"
        exit 1
    fi
done

# Run tests
echo "🧪 Running tests..."
docker-compose exec -T web python manage.py test --noinput

# Clear old sessions
echo "🧹 Clearing old sessions..."
docker-compose exec -T web python manage.py clearsessions

# Optimize database
echo "⚡ Optimizing database..."
docker-compose exec -T db psql -U $DB_USER -d $DB_NAME -c "VACUUM ANALYZE;"

# Create backup
echo "💾 Creating backup..."
docker-compose exec -T web python scripts/backup_db.py

echo "✅ Deployment completed successfully!"

# Display service URLs
echo ""
echo "📌 Service URLs:"
echo "   Web: https://flynjet.com"
echo "   Admin: https://flynjet.com/admin"
echo "   API: https://api.flynjet.com"
echo "   API Docs: https://api.flynjet.com/docs"
echo ""
echo "📊 Monitoring:"
echo "   Health Check: https://flynjet.com/health/"
echo "   Metrics: https://flynjet.com/metrics"
echo ""

# Display resource usage
echo "📈 Resource Usage:"
docker-compose stats --no-stream

exit 0