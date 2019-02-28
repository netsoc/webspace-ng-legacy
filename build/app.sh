#!/bin/sh
# main application entrypoint

# python output buffering breaks stdout in docker
export PYTHONUNBUFFERED=1

if [ "$FLASK_ENV" == "development" ]; then
	# use flask debug server in development
	exec python /opt/app/webspace.py
else
	# use gunicorn in production
	exec gunicorn --workers $GUNICORN_WORKERS --bind :8080 --chdir /opt/app webspace:app
fi
