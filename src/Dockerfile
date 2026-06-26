# Build from the project root:
# docker build -f src/Dockerfile .
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LOTTERY_MODEL_DIR=/app/src/models \
    LOTTERY_OUTPUT_DIR=/app/resultados_Loterias \
    LOTTERY_HISTORY_DB=/app/data/loterias_history.sqlite3

WORKDIR /app/src

COPY src/requirements.txt /app/src/
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ /app/src/
COPY *.csv /app/
RUN mkdir -p /app/resultados_Loterias /app/data

EXPOSE 5000

CMD sh -c "gunicorn --bind 0.0.0.0:${PORT:-5000} app:app"
