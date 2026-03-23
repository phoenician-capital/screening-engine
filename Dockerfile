FROM python:3.11-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY . .

RUN chmod +x scripts/start.sh scripts/start_dashboard.sh scripts/start_mcp.sh

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8000 5000

CMD ["bash", "scripts/start_dashboard.sh"]
