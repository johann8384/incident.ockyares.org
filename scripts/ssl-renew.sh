#!/bin/bash

# Automatic renewal script
docker-compose run --rm certbot renew --quiet

# Reload nginx if certificates were renewed
if [ $? -eq 0 ]; then
    docker-compose exec nginx nginx -s reload
    echo "SSL certificates renewed and nginx reloaded"
else
    echo "No renewal needed"
fi
