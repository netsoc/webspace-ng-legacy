from urllib.parse import quote
from pylxd import Client

SOCKET_PATH = '/var/lib/lxd.socket'

def init_app(app):
    @app.before_first_request
    def connect_lxd():
        global client
        # We have to escape the /'s in the socket path
        endpoint = 'http+unix://{}'.format(quote(SOCKET_PATH, safe=''))
        client = Client(endpoint=endpoint)

def container_names():
    names = []
    for container in client.containers.all():
        names.append(container.name)

    return names
