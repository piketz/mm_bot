FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends     gcc     build-essential     libxml2     libxml2-dev     libxslt1-dev     ca-certificates fonts-dejavu-core     && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org -r requirements.txt
COPY . .
CMD ["python", "mm_bot.py"]
