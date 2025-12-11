FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    build-essential \
    libxml2 \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
ENV PYTHONUNBUFFERED=1
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "main.py"]
