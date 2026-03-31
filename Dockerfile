FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Data volume mount point (session file + SQLite DB)
RUN mkdir -p /data
ENV DATA_DIR=/data

EXPOSE 5000

CMD ["python", "app.py"]
