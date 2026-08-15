# Dockerfile de SUBMISSAO a plataforma lugobots.ai (padrao .lugo/Dockerfile,
# contexto = raiz do repo). Genoma FORTE embutido via BOT_PARAMS_FILE
# (Fase A + pass_status_mode + cover_mode). params.py le esse arquivo quando
# BOT_PARAMS nao esta setado (a plataforma nao seta).
FROM python:3.9-slim-bookworm

WORKDIR /usr/src/app
ENV PYTHONUNBUFFERED=1

COPY bot/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY bot/src ./src
COPY bot/genome_submit.json ./genome_submit.json
ENV BOT_PARAMS_FILE=/usr/src/app/genome_submit.json

CMD [ "python", "./src/main.py" ]
