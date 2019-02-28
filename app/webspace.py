#!/usr/bin/env python
from werkzeug.contrib.fixers import ProxyFix
from flask import Flask

import lxd

app = Flask(__name__)
# Make sure request.remote_addr represents the real client IP
app.wsgi_app = ProxyFix(app.wsgi_app)

lxd.init_app(app)

@app.route('/')
def test():
    return str(lxd.container_names())

if __name__ == "__main__":
    # If we are started directly, run the Flask development server
    app.run(host='0.0.0.0', port=8080)
