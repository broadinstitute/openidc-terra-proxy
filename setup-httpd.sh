#!/bin/bash

set -e

echo "Setting up http environment"

sed -i 's/Listen 80/Listen 0.0.0.0:\$\{HTTPD_PORT\}\nListen 0.0.0.0:\$\{SSL_HTTPD_PORT\}/' /etc/httpd/conf/httpd.conf
sed -i 's/ServerAdmin root@localhost/ServerAdmin \$\{SERVER_ADMIN\}/' /etc/httpd/conf/httpd.conf
sed -i 's/\#ServerName www.example.com:80/ServerName \$\{SERVER_NAME\}/' /etc/httpd/conf/httpd.conf

ln -s /etc/pki/tls/private /etc/ssl/private

# Generate a snakeoil certificate in case it's needed
openssl req -newkey rsa:4096 -days 365 -nodes -x509 \
    -subj "/C=US/ST=Massachusetts/L=Cambridge/O=Random Bits/OU=Widgets/CN=localhost/emailAddress=webmaster@example.org" \
    -keyout /etc/ssl/private/server.key \
    -out /etc/ssl/certs/server.crt

# Use the snakeoil cert as the ca-bundle.crt as well
cp /etc/ssl/certs/server.crt /etc/ssl/certs/server-ca-bundle.crt

# Remove default ssl.conf
rm /etc/httpd/conf.d/ssl.conf