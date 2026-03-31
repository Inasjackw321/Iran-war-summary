FROM python:3.11-slim

WORKDIR /app

# Install deps as a separate layer so Docker can cache it
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# /data is mounted as a Fly.io persistent volume (session + database)
RUN mkdir -p /data
ENV DATA_DIR=/data

EXPOSE 5000

CMD ["python", "app.py"]
