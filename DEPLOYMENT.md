# Remote Server Deployment Guide

## Overview

Dit project uses Docker Compose met twee configuraties:
- **docker-compose.yml** → Development (poort 8000, geen Traefik)
- **docker-compose.prod.yml** → Production (Traefik reverse proxy, SSL/TLS)

Traefik draait apart op de server en routeert automatisch naar je Django container.

## Development Setup (Local Machine)

```bash
docker compose up -d
```

Je app is bereikbaar op: `http://localhost:8000`

## Production Setup (Remote Server)

### 1. Prerequisites

- Linux server met Docker en Docker Compose
- Root access
- DNS records pointing naar je server IP
  - `eventaflow.eu` → server IP
  - (optional) `*.eventaflow.eu` → server IP

### 2. Zet Traefik op (één keer)

```bash
# SSH naar je server
ssh root@eventaflow.eu

# Clone je project
cd /opt
git clone <je-repo> Time_registry_webversion
cd Time_registry_webversion

# Run Traefik setup
chmod +x setup-traefik.sh
./setup-traefik.sh
```

Dit:
- Maakt docker network `traefik_network` aan
- Installeert Traefik v3.0
- Configureert Let's Encrypt automatische certificaten
- Traefik draait in `/opt/traefik`

### 3. Deploy je Django App

```bash
# In je project directory
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

Dit:
- Zet web container op (8000, zonder externe poort)
- Zet database op
- Verbindt alles met `traefik_network`
- Traefik detecteert automatisch via labels

### 4. Verify

```bash
# Check all containers
docker ps

# Check Traefik logs
docker compose -f /opt/traefik/docker-compose.yml logs traefik

# Check Django logs
docker compose logs web
```

## Architecture

```
Internet (80, 443)
    ↓
Traefik (port 80→8080, 443→8000+)
    ↓
Django Web Container (8000, internal)
    ↓
PostgreSQL Container
```

### How it works:

1. User hits `https://eventaflow.eu`
2. Traefik intercepts (port 443)
3. Traefik checks certificate (Let's Encrypt automatic)
4. Traefik routes to Django web container (via docker label rules)
5. Django responds
6. Traefik sends back to user with HTTPS

## SSL/TLS Certificates

Traefik handles automatisch:
- Certificate generation via Let's Encrypt
- Auto-renewal 30 days before expiry
- Certificates stored in `/opt/traefik/acme.json`

Geen manual cert management nodig!

## Updates & Maintenance

### Update Django app:

```bash
cd /path/to/project
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

### Update Traefik:

```bash
cd /opt/traefik
docker compose pull
docker compose up -d
```

## Troubleshooting

### Traefik can't connect to Docker socket

```bash
# Check socket permissions
ls -la /var/run/docker.sock

# Should be root:docker or root:root
sudo chmod 666 /var/run/docker.sock
```

### Let's Encrypt rate limit

If you hit rate limits, Let's Encrypt will backoff. Check logs:

```bash
docker compose -f /opt/traefik/docker-compose.yml logs traefik | grep acme
```

### Django app not responding

```bash
# Check if container is running
docker ps | grep time_registry

# Check logs
docker compose logs web

# Check network
docker network inspect traefik_network
```

## Security Notes

- `.env` file contains secrets → **Never commit to git**
- Django `DEBUG = False` in production (check settings.py)
- Use strong `POSTGRES_PASSWORD`
- Keep server updated: `apt update && apt upgrade`
- Use firewall: only open 80, 443, 22

## Backup & Recovery

### Backup database:

```bash
docker compose exec db pg_dump -U $POSTGRES_USER $POSTGRES_DB > backup.sql
```

### Backup SSL certificates:

```bash
cp /opt/traefik/acme.json /backups/acme.json.backup
```

### Restore database:

```bash
docker compose exec -T db psql -U $POSTGRES_USER $POSTGRES_DB < backup.sql
```
