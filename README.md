# Time Registry Web Version

A web-based time tracking and project management application built with Django.

## Features

- Time tracking with start/stop functionality
- Project and customer management  
- Data export to Excel
- User authentication and company management
- Responsive web interface with Tailwind CSS

## Local Development

### Prerequisites

- Docker & Docker Compose
- Python 3.12+ (for local development)
- PostgreSQL (runs in Docker)

### Setup

1. Clone the repository:
```bash
git clone https://github.com/Geertvb1977/Time_registry_webversion.git
cd Time_registry_webversion
```

2. Create `.env` file from template:
```bash
cp .env.example .env
```

3. Start development environment:
```bash
docker-compose up -d
```

4. Run migrations:
```bash
docker-compose exec web python manage.py migrate
```

5. Access at `http://localhost:8000`

## Production Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for complete production deployment guide with Traefik reverse proxy and Let's Encrypt SSL.

### Quick Start (Production)

1. **Setup .env** - Copy `.env.example` to `.env` and configure:
   - `DEBUG=False`
   - `CSRF_TRUSTED_ORIGINS=https://yourdomain.com`
   - `ALLOWED_HOSTS=yourdomain.com`
   - Strong `DJANGO_SECRET_KEY` and `POSTGRES_PASSWORD`

2. **Deploy** on server:
```bash
cd /opt/Time_registry_webversion
git pull
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
docker-compose exec web python manage.py migrate
```

3. **Traefik** automatically handles:
   - HTTP → HTTPS redirects
   - SSL certificates via Let's Encrypt
   - Reverse proxying to Django

## Architecture

```
Internet (HTTPS)
    ↓
Traefik (Reverse Proxy + SSL)
    ↓
Django (Gunicorn on port 8000)
    ↓
PostgreSQL Database
```

## Configuration

All settings use environment variables from `.env`:

| Variable | Default | Purpose |
|----------|---------|---------|
| `DEBUG` | False | Django debug mode |
| `POSTGRES_DB` | time_registry | Database name |
| `POSTGRES_USER` | time_registry_user | Database user |
| `POSTGRES_PASSWORD` | - | Database password (required) |
| `DJANGO_SECRET_KEY` | - | Django secret key (required) |
| `CSRF_TRUSTED_ORIGINS` | - | Allowed CSRF origins (production) |
| `ALLOWED_HOSTS` | - | Allowed hostnames (production) |

## Security Notes

- `.env` is not committed (contains secrets)
- Use strong passwords and secret keys in production
- DEBUG must be False in production
- SSL certificates are auto-renewed by Let's Encrypt

## License

[Your License]
