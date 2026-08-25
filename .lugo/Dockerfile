# Dockerfile de SUBMISSÃO à plataforma lugobots.ai (padrão .lugo/Dockerfile,
# contexto = raiz do repo). Config da Fase A EMBUTIDA (genes ON) via
# BOT_PARAMS_FILE; params.py lê esse arquivo quando BOT_PARAMS não está setado.
FROM python:3.9-slim-bookworm

WORKDIR /usr/src/app
ENV PYTHONUNBUFFERED=1

COPY bot/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY bot/src ./src
COPY bot/genome_submit.json ./genome_submit.json
ENV BOT_PARAMS_FILE=/usr/src/app/genome_submit.json

CMD [ "python", "./src/main.py" ]
