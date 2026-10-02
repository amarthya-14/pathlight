FROM python:3.12-slim

# No .pyc clutter, unbuffered logs (so Render's log stream shows output immediately).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as a non-root user — a compromised process can't touch the rest of the container.
RUN useradd --create-home pathlight && chown -R pathlight /app
USER pathlight

EXPOSE 8000
# Render (and most PaaS hosts) inject $PORT; default to 8000 for local Docker Compose.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
