#!/bin/bash
# Traefik setup script voor remote server
# Run this as root on your remote server

set -e

echo "🚀 Traefik setup voor eventaflow.eu"

# 1. Create traefik_network
docker network create traefik_network 2>/dev/null || echo "Network traefik_network bestaat al"

# 2. Create directories
mkdir -p /opt/traefik
cd /opt/traefik

# 3. Create acme.json for Let's Encrypt certificates
touch acme.json
chmod 600 acme.json

# 4. Create Traefik config file
cat > traefik.yml << 'EOF'
global:
  checkNewVersion: true
  sendAnonymousUsage: false

entryPoints:
  web:
    address: ":80"
    http:
      redirections:
        entrypoint:
          regex: '^http://(.*)'
          replacement: 'https://$1'
          permanent: true
  websecure:
    address: ":443"

providers:
  docker:
    endpoint: "unix:///var/run/docker.sock"
    exposedByDefault: false
    network: traefik_network

certificatesResolvers:
  letsencrypt:
    acme:
      email: info@eventaflow.be
      storage: acme.json
      httpChallenge:
        entryPoint: web

api:
  insecure: false
  dashboard: true

log:
  level: INFO
EOF

# 5. Create docker-compose for Traefik
cat > docker-compose.yml << 'EOF'
version: '3.9'

services:
  traefik:
    image: traefik:v3.0
    container_name: traefik
    restart: always
    command:
      - "--configFile=/traefik.yml"
    ports:
      - "80:80"
      - "443:443"
      - "8080:8080"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ./traefik.yml:/traefik.yml
      - ./acme.json:/acme.json
    networks:
      - traefik_network

networks:
  traefik_network:
    external: true
EOF

# 6. Start Traefik
docker compose up -d

echo "✅ Traefik is gestart!"
echo ""
echo "📝 Volgende stappen:"
echo "1. Deploy je Django app met: docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d"
echo "2. Check Traefik dashboard: https://traefik.eventaflow.eu:8080"
echo "3. Je app is beschikbaar op: https://eventaflow.eu"
