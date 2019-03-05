from urllib.parse import quote
from functools import wraps
import logging
import grp

from pylxd import Client

from .. import *

def user_container(user):
    return '{}-ws'.format(user)
def get_new_config(user, image):
    return {
        'name': user_container(user),
        'ephemeral': False,
        'profiles': ['webspace'],
        'source': {
            'type': 'image',
            'fingerprint': image
        }
    }
def image_info(image):
    return {
        'fingerprint': image.fingerprint,
        'aliases': image.aliases,
        'properties': image.properties,
        'size': image.size,
    }

class Manager:
    allowed = set(['images', 'init'])

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
    def images(self, user):
        return list(map(image_info, self.client.images.all()))

    @check_user
    def init(self, user, image_fingerprint):
        container_name = user_container(user)
        if self.client.containers.exists(container_name):
            raise WebspaceError('Your container has already been initialized!')

        container = self.client.containers.create(get_new_config(user, image_fingerprint), wait=True)

    def _dispatch(self, method, params):
        if not method in Manager.allowed:
            raise Exception('method "{}" is not supported'.format(method))

        return getattr(self, method)(*params)
