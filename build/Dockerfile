FROM python:3-alpine

COPY requirements.txt /opt/
RUN apk --no-cache add gcc musl-dev libffi libffi-dev openssl openssl-dev && \
	pip install -r /opt/requirements.txt && \
	apk --no-cache del gcc musl-dev libffi-dev openssl-dev && \
	mkdir /opt/app
COPY app.sh /opt/

ENV GUNICORN_WORKERs=4
EXPOSE 8080/tcp
CMD [ "/opt/app.sh" ]
