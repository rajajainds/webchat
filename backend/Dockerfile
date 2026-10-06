# Backend image. Small, runs as a non-root user.
FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
RUN useradd -m appuser
USER appuser
# --proxy-headers: trust Nginx for the real client IP (rate limits need it)
# --ws-max-size: reject WebSocket frames over 64 KB
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*", "--ws-max-size", "65536"]
