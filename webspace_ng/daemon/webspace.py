from urllib.parse import quote
from functools import wraps
import logging
import grp

from pylxd import Client

from .. import ADMIN_GROUP

class Manager:
    allowed = set(['test'])

    def __init__(self, socket_path, server):
        endpoint = 'http+unix://{}'.format(quote(socket_path, safe=''))
        self.client = Client(endpoint=endpoint)
        self.server = server
        self.admins = set(grp.getgrnam(ADMIN_GROUP).gr_mem)

    def check_user(f):
        @wraps(f)
        def wrapper(self, *args):
            req = self.server.current_request
            if req.client_user in self.admins:
                return f(self, *args)
            return f(self, req.client_user, *args)
        return wrapper

    @check_user
    def test(self, user):
        logging.debug('user is %s', user)
        names = []
        for container in self.client.containers.all():
            names.append(container.name)

        return names

    def _dispatch(self, method, params):
        if not method in Manager.allowed:
            raise Exception('method "{}" is not supported'.format(method))

        return getattr(self, method)(*params)
