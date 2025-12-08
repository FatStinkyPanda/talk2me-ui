#!/bin/bash

# Initialize SSL certificates for Let's Encrypt
# This script should be run once to obtain initial certificates

set -e

DOMAIN=${DOMAIN:-localhost}

if [ ! -d "/etc/letsencrypt/live/$DOMAIN" ]; then
    echo "Obtaining SSL certificate for $DOMAIN..."
    certbot certonly --webroot -w /var/www/html -d $DOMAIN --email admin@$DOMAIN --agree-tos --non-interactive
else
    echo "SSL certificate already exists for $DOMAIN"
fi

# Start renewal loop
while true; do
    echo "Checking for certificate renewal..."
    certbot renew
    sleep 12h
done
