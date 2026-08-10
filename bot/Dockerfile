FROM python:3.9-slim-bookworm

WORKDIR /usr/src/app

# sem isto o stdout do Python fica em buffer e os erros não aparecem no log
ENV PYTHONUNBUFFERED=1

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src

CMD [ "python", "./src/main.py" ]
