📜 Makefile (Django + uv + Docker)
makefile
Kopiëren

# Variabelen
PYTHON = python3
UV = uv
MANAGE = $(PYTHON) manage.py
DOCKER_COMPOSE = docker compose
PROJECT_NAME = myproject  # Vervang door je Django-projectnaam
SRC_DIR = src            # Pas aan als je broncode elders staat

# Standaarddoel
all: help

# Toon beschikbare commando's
help:
	@echo "📌 Django + uv + Docker commando's:"
	@echo "---------------------------------"
	@echo "🛠️  Project setup:"
	@echo "  make install          - Installeer Python afhankelijkheden (uv sync)"
	@echo "  make docker-build     - Bouw Docker containers"
	@echo "  make docker-up         - Start Docker containers"
	@echo "  make docker-down       - Stop Docker containers"
	@echo "  make docker-restart    - Herstart Docker containers"
	@echo "  make docker-shell      - Open shell in Django container"
	@echo ""
	@echo "🚀 Django:"
	@echo "  make migrate          - Voer database migraties uit"
	@echo "  make makemigrations   - Maak nieuwe migraties"
	@echo "  make run              - Start Django server (binnen container)"
	@echo "  make superuser        - Maak een Django superuser aan"
	@echo "  make shell            - Open Django shell"
	@echo "  make collectstatic    - Verzamel statische bestanden"
	@echo ""
	@echo "🔍 Linting & Formatteren:"
	@echo "  make lint             - Voer isort, black, pylint, flake8 uit"
	@echo "  make format           - Formatteer code met isort + black"
	@echo "  make lint-isort       - Alleen isort"
	@echo "  make lint-black       - Alleen black"
	@echo "  make lint-pylint      - Alleen pylint"
	@echo "  make lint-flake8      - Alleen flake8"
	@echo ""
	@echo "🧹 Opschonen:"
	@echo "  make clean            - Verwijder __pycache__, .pyc, etc."
	@echo "  make docker-clean     - Verwijder Docker volumes, containers, netwerken"

# --- Docker commando's ---
docker-build:
	$(DOCKER_COMPOSE) build

docker-up:
	$(DOCKER_COMPOSE) up -d

docker-down:
	$(DOCKER_COMPOSE) down

docker-restart:
	$(DOCKER_COMPOSE) restart

docker-shell:
	$(DOCKER_COMPOSE) exec django bash

docker-clean:
	$(DOCKER_COMPOSE) down -v --rmi local
	docker system prune -f

# --- Django commando's (binnen container) ---
migrate:
	$(DOCKER_COMPOSE) exec django $(MANAGE) migrate

makemigrations:
	$(DOCKER_COMPOSE) exec django $(MANAGE) makemigrations

run:
	$(DOCKER_COMPOSE) exec django $(MANAGE) runserver 0.0.0.0:8000

superuser:
	$(DOCKER_COMPOSE) exec django $(MANAGE) createsuperuser

shell:
	$(DOCKER_COMPOSE) exec django $(MANAGE) shell

collectstatic:
	$(DOCKER_COMPOSE) exec django $(MANAGE) collectstatic --noinput

# --- Afhankelijkheden ---
install:
	$(UV) sync

# --- Linting & Formatteren ---
lint: lint-isort lint-black lint-pylint lint-flake8

lint-isort:
	$(UV) run isort --profile black $(SRC_DIR)

lint-black:
	$(UV) run black $(SRC_DIR) --line-length=99

lint-pylint:
	$(UV) run pylint $(SRC_DIR) --max-line-length=99

lint-flake8:
	$(UV) run flake8 $(SRC_DIR) --max-line-length=99

format: lint-isort lint-black

# --- Opschonen ---
clean:
	find . -type d -name "__pycache__" -exec rm -r {} +
	find . -type f -name "*.py[cod]" -delete
	find . -type f -name ".Python" -delete
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/

.PHONY: all help install docker-build docker-up docker-down docker-restart docker-shell docker-clean \
        migrate makemigrations run superuser shell collectstatic \
        lint lint-isort lint-black lint-pylint lint-flake8 format clean




🚀 Hoe gebruik je deze Makefile?
1️⃣ Docker opzetten

Zorg dat je een docker-compose.yml hebt voor je Django-project.
Voorbeeld (minimaal):
yaml
Kopiëren

services:
  django:
    build: .
    volumes:
      - .:/app
    ports:
      - "8000:8000"
    working_dir: /app
    command: tail -f /dev/null  # Houdt container draaiend




Bouw en start de containers:
bash
Kopiëren

make docker-build
make docker-up




2️⃣ Afhankelijkheden installeren (binnen container)
bash
Kopiëren

make docker-shell  # Open een shell in de container
uv sync             # Installeer afhankelijkheden
exit                # Verlaat de container



Of direct via Makefile (als uv lokaal geïnstalleerd is):
bash
Kopiëren

make install



3️⃣ Django commando's


  
    
      Commando
      Actie
    
  
  
    
      make migrate
      Voer migraties uit (in container)
    
    
      make run
      Start Django server (poort 8000)
    
    
      make superuser
      Maak een superuser aan
    
    
      make shell
      Open Django shell
    
  



4️⃣ Linting & Formatteren


  
    
      Commando
      Actie
    
  
  
    
      make lint
      Voer alle linters uit
    
    
      make format
      Formatteer code met isort + black
    
    
      make lint-isort
      Alleen isort uitvoeren
    
    
      make lint-black
      Alleen black uitvoeren
    
  



5️⃣ Docker beheer


  
    
      Commando
      Actie
    
  
  
    
      make docker-down
      Stop alle containers
    
    
      make docker-clean
      Verwijder containers, volumes, images
    
    
      make docker-shell
      Open shell in Django container
    
  




📦 Benodigde Python pakketten
Zorg dat deze pakketten in je pyproject.toml of requirements.txt staan:
toml
Kopiëren

# pyproject.toml (voor uv)
[project]
[dependencies-groups]
dev = [
    "django",
    "isort",
    "black",
    "pylint",
    "flake8",
]



Installeer ze met:
bash
Kopiëren

uv add --dev isort black pylint flake8



