from urllib.parse import quote

from pylxd import Client

class Manager:
    def __init__(self, socket_path):
        endpoint = 'http+unix://{}'.format(quote(socket_path, safe=''))
        self.client = Client(endpoint=endpoint)

    def test(self):
        names = []
        for container in self.client.containers.all():
            names.append(container.name)

        return names
