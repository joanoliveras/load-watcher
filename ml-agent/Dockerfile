FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy application code and packaged model
COPY app /app/app

ENV ML_AGENT_HOST=0.0.0.0
ENV ML_AGENT_PORT=8080

EXPOSE 8080

CMD ["python", "-m", "app.main"]


