# Build from the project root:
# docker build -f src/Dockerfile .
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AUTH_DB_PATH=/app/data/loterias_auth.sqlite3 \
    LOTTERY_BACKUP_DIR=/app/data/backups_loterias \
    LOTTERY_DATA_DIR=/app/data/lottery_data \
    LOTTERY_LOG_FILE=/app/data/logs/loterias.log \
    LOTTERY_MODEL_DIR=/app/src/models \
    LOTTERY_OUTPUT_DIR=/app/data/resultados_Loterias \
    LOTTERY_HISTORY_DB=/app/data/loterias_history.sqlite3 \
    LOTTERY_USE_ML=0

WORKDIR /app/src

COPY src/requirements.txt /app/src/
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ /app/src/
COPY *.csv /app/
RUN mkdir -p \
    /app/data/backups_loterias \
    /app/data/logs \
    /app/data/lottery_data \
    /app/data/resultados_Loterias

EXPOSE 5000

CMD sh -c "gunicorn --bind 0.0.0.0:${PORT:-5000} app:app"
