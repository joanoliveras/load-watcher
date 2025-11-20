FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

ENV ORCH_METRICS_PORT=9105 \
    ORCH_METRICS_BIND_ADDRESS=0.0.0.0

CMD ["python", "-m", "app.main"]

