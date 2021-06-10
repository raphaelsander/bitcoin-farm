FROM python:3-alpine

WORKDIR /usr/src/app

COPY . .
RUN pip install --no-cache-dir -r requirements.txt && \
    chmod 755 docker-entrypoint.sh

CMD [ "./docker-entrypoint.sh" ]