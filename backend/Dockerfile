FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends mosquitto && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.lock.txt /app/requirements.lock.txt
RUN pip install --no-cache-dir -r requirements.lock.txt
RUN useradd --uid 10001 --create-home court && mkdir -p /data /secrets && chown -R court:court /data /secrets
COPY --chown=court:court backend/ /app/
COPY --chown=court:court scripts/ /app/scripts/
USER court
CMD ["python", "-m", "uvicorn", "aiot.app:app", "--host", "0.0.0.0", "--port", "8000"]
