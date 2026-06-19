




# Eventaflow.eu - Multi-Tenant Time & Project Management

[cite_start]Eventaflow.eu is een moderne, multi-tenant webapplicatie gebouwd met Django, specifiek ontworpen voor zelfstandigen en kleine teams[cite: 9, 11, 132]. [cite_start]Het platform combineert live start/stop-tijdsregistratie met uitgebreid projectbeheer via taken (todo's), divisies en milestones[cite: 10, 45, 207]. [cite_start]Dankzij de multi-tenant architectuur blijft de data van elk bedrijf strikt en veilig van elkaar gescheiden[cite: 132, 133].

---

## 🚀 Belangrijkste Functionaliteiten

- [cite_start]**Multi-Tenant Architectuur:** Volledige dataseparatie op database- en view-niveau middels custom Django Mixins[cite: 132].
- [cite_start]**Tijdsregistratie:** Live start/stop-tijdschrijfsysteem op de hoofdpagina met automatische urenberekening en Excel-export[cite: 15].
- [cite_start]**Project- & Takenbeheer (Todo's):** Uitgebreid takenbeheer met prioriteiten, deadlines en toewijzing aan specifieke collega's[cite: 24, 26].
- [cite_start]**Milestones & Divisies:** Projecten opsplitsen in duidelijke fasen (milestones) en organisatorische eenheden (divisies)[cite: 42, 207, 208].
- [cite_start]**Beveiligde API & Externe Toegang:** Token-based, read-only REST API waarmee externe klanten zonder inlog de projectstatus kunnen raadplegen[cite: 58, 113, 114].
- [cite_start]**Google Drive & Docs Integratie:** Gecentraliseerd documentbeheer per divisie via OAuth2 met transparante database-encryptie voor API-credentials[cite: 47, 51].

---

## 🛠️ Technische Architectuur & Tech Stack

- [cite_start]**Backend Framework:** Django 5.x & Django REST Framework (DRF) [cite: 9, 64]
- [cite_start]**Pakketbeheer:** `uv` (Astromesh) voor deterministische en snelle dependency-resolving (`uv.lock`) [cite: 215]
- [cite_start]**Database:** PostgreSQL 15 (met unieke oplopende ID's per tenant) [cite: 9, 132, 159]
- [cite_start]**Containerisatie:** Docker & Docker Compose [cite: 215]
- **Reverse Proxy / Ingress:** Traefik Proxy met automatische Let's Encrypt TLS/SSL-certificering
- [cite_start]**Continuous Deployment:** Watchtower voor automatische container-updates bij nieuwe image pushes 

---

## 💻 Lokale Ontwikkelomgeving (Development)

### Vereisten
- Docker Desktop & Docker Compose
- [cite_start]Python 3.12+ & `uv` (optioneel, voor lokale linting buiten Docker) [cite: 215]

### Quick Start
1. **Kloon de repository:**
   ```bash
   git clone [https://github.com/Geertvb1977/Time_registry_webversion.git](https://github.com/Geertvb1977/Time_registry_webversion.git)
   cd Time_registry_webversion