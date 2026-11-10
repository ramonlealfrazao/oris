# ORIS - imagem da aplicacao (Flask + gunicorn). O banco MySQL 8 sobe em outro
# contêiner (ver docker-compose.yml).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Usuario sem privilegios: o processo web nao roda como root.
RUN useradd --system --create-home --uid 10001 oris \
    && mkdir -p /app/uploads && chown -R oris:oris /app
USER oris

EXPOSE 5000

HEALTHCHECK --interval=15s --timeout=5s --start-period=40s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5000/login', timeout=4).status==200 else 1)"

# Entrypoint em Python (funciona mesmo se o Git no Windows trocar o fim de linha).
CMD ["python", "docker/entrypoint.py"]
