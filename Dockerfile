FROM python:3.12-slim


ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1


WORKDIR /app


# ... bovenaan bij de apt-get install ...
RUN apt-get update \
    && apt-get install -y gcc libpq-dev ca-certificates \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt


COPY . /app/


WORKDIR /app/djangoproject


CMD ["gunicorn", "djangoproject.wsgi:application", "--bind", "0.0.0.0:8000", "--timeout", "120", "--workers", "3"]