FROM python:3.11-slim

WORKDIR /app

# Version argument
ARG VERSION=unknown
ENV BOT_VERSION=$VERSION

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends     curl     && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY *.py ./
COPY *.json ./
COPY templates/ ./templates/
COPY static/ ./static/

# Create logs directory
RUN mkdir -p /app/logs

# Set environment variables
ENV PYTHONUNBUFFERED=1

CMD ["python", "mm_bot.py"]
