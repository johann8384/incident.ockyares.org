#!/bin/bash

echo "Setting up Emergency Incident Management System with SSL..."

# 1. Create necessary directories
mkdir -p database/init database/backups static/qr_codes logs geoserver/workspaces geoserver/styles ssl/letsencrypt ssl/challenges ssl/certs

# 2. Set permissions
chmod 755 ssl/letsencrypt ssl/challenges ssl/certs

# 3. Check DNS resolution
echo "Checking DNS resolution..."
if ! dig incident.ockyeoc.org +short | grep -q "75.34.212.4"; then
    echo "WARNING: DNS not yet propagated. Please wait and try again."
    echo "Expected: 75.34.212.4"
    echo "Actual: $(dig incident.ockyeoc.org +short)"
    read -p "Continue anyway? (y/N): " confirm
    if [[ $confirm != [yY] ]]; then
        exit 1
    fi
fi

# 4. Start services without SSL
echo "Starting services..."
docker-compose up -d postgis postgrest geoserver incident_app

# 5. Wait for services to be ready
echo "Waiting for services to start..."
sleep 30

# 6. Start nginx without SSL first (for Let's Encrypt challenge)
docker-compose up -d nginx

# 7. Get SSL certificate
echo "Obtaining SSL certificate..."
docker-compose run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email your-email@ockyeoc.org \
    --agree-tos \
    --no-eff-email \
    -d incident.ockyeoc.org \
    -d www.incident.ockyeoc.org

# 8. Restart nginx with SSL
echo "Restarting nginx with SSL..."
docker-compose restart nginx

# 9. Test the setup
echo "Testing SSL setup..."
sleep 10
if curl -s -k https://incident.ockyeoc.org/health | grep -q "healthy"; then
    echo "✅ SSL setup successful!"
    echo "🌐 Application: https://incident.ockyeoc.org"
    echo "🗺️ GeoServer: https://incident.ockyeoc.org/geoserver"
    echo "🔌 API: https://incident.ockyeoc.org/api"
else
    echo "❌ SSL setup may have issues. Check logs:"
    echo "docker-compose logs nginx"
    echo "docker-compose logs incident_app"
fi

echo "Setup complete!"
