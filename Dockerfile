FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends     curl     && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py ./
COPY *.json.template ./
COPY templates/ ./templates/
COPY static/ ./static/

RUN mkdir -p /app/logs

ENV PYTHONUNBUFFERED=1

CMD [python, main.py]
