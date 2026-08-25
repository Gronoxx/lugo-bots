# Clone local do bot "BotAdversario2" (parede vertical) — oponente de sparring.
FROM python:3.9-slim-bookworm
WORKDIR /usr/src/app
ENV PYTHONUNBUFFERED=1
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY src ./src
CMD [ "python", "./src/main.py" ]
