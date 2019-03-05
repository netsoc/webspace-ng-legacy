from functools import wraps

from humanfriendly import format_size

from .. import WebspaceError
from .client import Client

def find_image(client, id_):
    images = client.images()
    # First try to find it by an alias
    for i in images:
        for a in i['aliases']:
            if a['name'] == id_:
                return i

    # Otherwise by fingerprint
    for i in images:
        if i['fingerprint'] == id_:
            return i

    return None

def cmd(f):
    @wraps(f)
    def wrapper(args):
        user = args.user if 'user' in args else None
        with Client(args.socket_path, user=user) as client:
            return f(client, args)
    return wrapper

@cmd
def images(client, _args):
    image_list = client.images()
    print('Available images: ')
    for image in image_list:
        print(' - Fingerprint: {}'.format(image['fingerprint']))
        if image['aliases']:
            aliases = map(lambda a: a['name'], image['aliases'])
            print('   Aliases: {}'.format(', '.join(aliases)))
        if 'description' in image['properties']:
            print('   Description: {}'.format(image['properties']['description']))
        print('   Size: {}'.format(format_size(image['size'], binary=True)))

@cmd
def init(client, args):
    print('Creating your container...')
    image = find_image(client, args.image)
    if image is None:
        raise WebspaceError('"{}" is not a valid image alias / fingerprint'.format(args.image))

    client.init(image['fingerprint'])
    print('Success!')

@cmd
def status(client, args):
    info = client.status()
    print('Container status: {}'.format(info))
