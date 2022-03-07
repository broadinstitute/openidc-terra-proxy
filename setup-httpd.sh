#!/bin/bash

set -e

echo "Setting up http environment"

ln -s /etc/pki/tls/private /etc/ssl/private

# Generate a snakeoil certificate in case it's needed
openssl req -newkey rsa:4096 -days 365 -nodes -x509 \
    -subj "/C=US/ST=Massachusetts/L=Cambridge/O=Random Bits/OU=Widgets/CN=localhost/emailAddress=webmaster@example.org" \
    -keyout /etc/ssl/private/server.key \
    -out /etc/ssl/certs/server.crt

# Use the snakeoil cert as the ca-bundle.crt as well
cat /etc/ssl/certs/server.crt >> /etc/ssl/certs/ca-bundle.crt

# Remove default ssl.conf
rm /etc/httpd/conf.d/ssl.conf