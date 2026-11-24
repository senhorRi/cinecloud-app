FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DB_PATH=/data/cinecloud.db PORT=8080
WORKDIR /app
RUN groupadd --gid 10001 cinecloud && useradd --uid 10001 --gid 10001 --no-log-init cinecloud && mkdir /data && chown 10001:10001 /data
COPY --chown=10001:10001 app/ /app/
USER 10001:10001
EXPOSE 8080
VOLUME ["/data"]
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=2)"
CMD ["python", "main.py"]
