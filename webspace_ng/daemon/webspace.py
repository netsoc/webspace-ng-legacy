from urllib import parse
from functools import wraps
import ipaddress
import logging
import pwd
import grp
import time
import threading

from pylxd import Client
from pylxd.models import Operation
import dns.resolver

from .. import ADMIN_GROUP, WebspaceError
from .console import ConsoleSession

def str2bool(s):
    ls = s.lower()
    if ls == 'true':
        return True
    if ls == 'false':
        return False
    raise ValueError('Invalid boolean value {}'.format(s))

def image_info(image):
    return {
        'fingerprint': image.fingerprint,
        'aliases': image.aliases,
        'properties': image.properties,
        'size': image.size,
    }

def check_user(f):
    @wraps(f)
    def wrapper(self, *args):
        req = self.server.current_request
        if req.client_user in self.admins:
            try:
                pwd.getpwnam(args[0])
            except KeyError:
                raise WebspaceError('User {} does not exist'.format(args[0]))
            return f(self, *args)
        return f(self, req.client_user, *args)
    return wrapper
def check_admin(f):
    @wraps(f)
    def wrapper(self, *args):
        req = self.server.current_request
        if req.client_user not in self.admins:
            raise WebspaceError('You must be an admin to call this function')
        return f(self, *args)
    return wrapper
def check_init(f):
    @wraps(f)
    @check_user
    def wrapper(self, user, *args):
        container_name = self.user_container(user)
        if not self.client.containers.exists(container_name):
            raise WebspaceError('Your container has not been initialized')
        container = self.client.containers.get(container_name)
        return f(self, user, container, *args)
    return wrapper
def check_running(f):
    @wraps(f)
    @check_init
    def wrapper(self, user, container, *args):
        if container.status_code != 103:
            raise WebspaceError('Your container is not running')
        return f(self, user, container, *args)
    return wrapper
def check_console(f):
    @wraps(f)
    @check_running
    def wrapper(self, user, container, *args):
        if not user in self.console_sessions:
            raise WebspaceError("Your container doesn't have an active console session")
        session = self.console_sessions[user]
        return f(self, user, container, session, *args)
    return wrapper

class Manager:
    allowed = {'images', 'init', 'status', 'log', 'console', 'console_close',
               'console_resize', 'shutdown', 'reboot', 'delete', 'boot_and_host',
               'boot_and_ip', 'get_config', 'set_option', 'unset_option',
               'get_domains', 'add_domain', 'remove_domain'}
    private_options = {'_domains'}

    def __init__(self, config, server):
        self.config = config

        endpoint = 'http+unix://{}'.format(parse.quote(config.lxd.socket, safe=''))
        self.client = Client(endpoint=endpoint)
        self.server = server
        self.admins = set(grp.getgrnam(ADMIN_GROUP).gr_mem)
        self.console_sessions = {}
        self.reserved_options = {
            'terminate_ssl': str2bool,
            'startup_delay': self.startup_delay
        }

        self.running_containers = list(map(lambda c: c.name, filter(
            lambda c: c.name.endswith(self.config.lxd.suffix) and c.status_code == 103,
            self.client.containers.all())))
        self.container_lock = threading.RLock()
        logging.debug('containers running at startup: %s', self.running_containers)

        self.ip_cache = {}

        self.custom_domains = {}
        for container in filter(lambda c: c.name.endswith(self.config.lxd.suffix), self.client.containers.all()):
            for domain in self.get_container_domains(container):
                self.custom_domains[domain] = container.name[:-len(self.config.lxd.suffix)]
        logging.debug('existing custom domain configuration: %s', self.custom_domains)

    def _stop(self):
        for session in self.console_sessions.values():
            session.stop(join=True)

        with self.container_lock:
            for c in self.running_containers:
                container = self.client.containers.get(c)
                if container.status_code == 103:
                    container.stop(wait=True)

    def user_container(self, user):
        return '{}{}'.format(user, self.config.lxd.suffix)
    def container_user(self, container):
        return container.name[:-len(self.config.lxd.suffix)]
    def user_domain(self, user):
        return '{}{}'.format(user, self.config.domain_suffix)
    def get_new_config(self, user, image):
        return {
            'name': self.user_container(user),
            'ephemeral': False,
            'profiles': [self.config.lxd.profile],
            'source': {
                'type': 'image',
                'fingerprint': image
            },
            'config': {
                'user.terminate_ssl': self.config.defaults.terminate_ssl,
                'user.startup_delay': self.config.defaults.startup_delay,
                'user._domains': ''
            }
        }
    def startup_delay(self, i):
        i = int(i)
        if i > self.config.max_startup_delay:
            raise ValueError('Startup delay is too large (max {})'.format(self.config.max_startup_delay))
        if i < 0:
            raise ValueError('Startup delay must be positive')
        return i
    def get_user_option(self, container, key):
        value = container.config['user.{}'.format(key)]
        if key in self.reserved_options:
            return self.reserved_options[key](value)
        return value
    def get_container_domains(self, container):
        return list(filter(lambda d: len(d) > 0, container.config['user._domains'].split(',')))
    def set_container_domains(self, container, domains):
        container.config['user._domains'] = ','.join(domains)
        container.save()
    def start_container(self, container):
        with self.container_lock:
            if len(self.running_containers) == self.config.run_limit:
                c = self.running_containers.pop(0)
                to_shutdown = self.client.containers.get(c)
                if to_shutdown.status_code == 103:
                    logging.debug('at run limit, shutting down container %s', to_shutdown.name)
                    self.stop_container(to_shutdown)

            logging.info('booting container %s', container.name)
            container.start(wait=True)
            self.running_containers.append(container.name)
            # Wait for the container to get an IP
            time.sleep(self.get_user_option(container, 'startup_delay'))
    def stop_container(self, container):
        with self.container_lock:
            if container.name in self.ip_cache:
                del self.ip_cache[container.name]
            self.running_containers.remove(container.name)
            container.stop(wait=True)

    @check_user
    def images(self, _):
        return list(map(image_info, self.client.images.all()))

    @check_user
    def init(self, user, image_fingerprint):
        container_name = self.user_container(user)
        if self.client.containers.exists(container_name):
            raise WebspaceError('Your container has already been initialized!')

        self.client.containers.create(self.get_new_config(user, image_fingerprint), wait=True)

    @check_init
    def status(self, _, container):
        return container.state()

    @check_running
    def log(self, _user, container):
        response = container.api['console'].get()
        return response.text

    @check_init
    def console(self, user, container, t_width, t_height):
        if container.status_code != 103:
            self.start_container(container)

        response = container.api['console'].post(json={
            'width': t_width,
            'height': t_height
        }).json()

        # Get the control websocket path
        operation_id = Operation.extract_operation_id(response['operation'])
        ws_uri = self.client.api.operations[operation_id] \
                 .websocket._api_endpoint
        ws_path = parse.urlparse(ws_uri).path

        # Get the secrets for the console fd and control fd
        fds = response['metadata']['metadata']['fds']

        console_path = '{}?secret={}'.format(ws_path, fds['0'])
        control_path = '{}?secret={}'.format(ws_path, fds['control'])

        if user in self.console_sessions:
            logging.info('closing existing console session for %s', user)
            self.console_sessions[user].stop(join=True)
        session = ConsoleSession(user, self.client.websocket_url, console_path, control_path)
        session.start()
        self.console_sessions[user] = session

        return session.socket_path

    @check_console
    def console_resize(self, _user, _container, session, t_width, t_height):
        session.control.resize(t_width, t_height)

    @check_console
    def console_close(self, user, _, session):
        session.stop(join=True)
        del self.console_sessions[user]

    @check_running
    def shutdown(self, _user, container):
        self.stop_container(container)

    @check_running
    def reboot(self, _user, container):
        with self.container_lock:
            if container.name in self.ip_cache:
                del self.ip_cache[container.name]
            container.restart(wait=True)

    @check_init
    def delete(self, _user, container):
        if container.status_code == 103:
            self.stop_container(container)
        container.delete(wait=True)

    @check_init
    def get_config(self, _user, container):
        return {k[len('user.'):]: v for k, v in container.config.items() if k.startswith('user.') and not k[len('user.'):] in Manager.private_options}

    @check_init
    def set_option(self, _user, container, key, value):
        if key in Manager.private_options:
            raise WebspaceError('{} is a private option and may not be set'.format(key))
        if key in self.reserved_options:
            # Validate the input before setting
            self.reserved_options[key](value)

        container.config['user.{}'.format(key)] = value
        container.save()

    @check_init
    def unset_option(self, _user, container, key):
        if key in Manager.private_options or self.reserved_options:
            raise WebspaceError('{} is a reserved/private option and may not be unset'.format(key))

        del container.config['user.{}'.format(key)]
        container.save()

    def get_container_ip(self, container):
        if container.status_code != 103:
            self.start_container(container)

        if container.name in self.ip_cache:
            ip = self.ip_cache[container.name]
            logging.debug('using cached ip %s for container %s', ip, container.name)
        else:
            info = container.state()
            if self.config.lxd.net.container_iface not in info.network:
                raise WebspaceError('iface')
            for ip in map(
                          lambda i: ipaddress.IPv4Address(i['address']),
                          filter(
                                 lambda i: i['family'] == 'inet',
                                 info.network[self.config.lxd.net.container_iface]['addresses'])):
                if ip in self.config.lxd.net.cidr:
                    ip = str(ip)
                    self.ip_cache[container.name] = ip
        return ip
    @check_admin
    def boot_and_host(self, host, https_hint):
        wildcard_host = '*'+host[host.find('.'):]
        if host in self.custom_domains:
            user = self.custom_domains[host]
        elif wildcard_host in self.custom_domains:
            # Wildcard domain
            user = self.custom_domains[wildcard_host]
        elif host.endswith(self.config.domain_suffix):
            user = host[:-len(self.config.domain_suffix)]
            try:
                pwd.getpwnam(user)
            except KeyError:
                return None, 'user'
        else:
            return None, 'not_webspace'

        container_name = self.user_container(user)
        if not self.client.containers.exists(container_name):
            return None, 'init'

        container = self.client.containers.get(container_name)
        try:
            ip = self.get_container_ip(container)
        except WebspaceError as ex:
            return None, str(ex)
        scheme = 'https' if https_hint and not self.get_user_option(container, 'terminate_ssl') else 'http'
        return scheme, str(ip)
    @check_admin
    def boot_and_ip(self, user):
        container_name = self.user_container(user)
        if not self.client.containers.exists(container_name):
            raise WebspaceError('container not initialized')

        container = self.client.containers.get(container_name)
        return self.get_container_ip(container)

    @check_init
    def get_domains(self, user, container):
        return [self.user_domain(user)] + self.get_container_domains(container)

    @check_init
    def add_domain(self, user, container, domain):
        if domain in self.custom_domains:
            raise WebspaceError("'{}' has already been configured as a custom domain")

        answer = dns.resolver.query(domain, 'CNAME')
        verified = False
        for rdata in answer:
            if rdata.target.to_text().rstrip('.') == self.user_domain(user):
                verified = True
                break

        if not verified:
            raise WebspaceError("'{}' has not been verified".format(domain))

        with self.container_lock:
            self.custom_domains[domain] = user
            self.set_container_domains(container, self.get_container_domains(container) + [domain])

    @check_init
    def remove_domain(self, user, container, domain):
        if not domain in self.custom_domains:
            raise WebspaceError("'{}' has not been configured as a custom domain")

        with self.container_lock:
            del self.custom_domains[domain]
            domains = self.get_container_domains(container)
            domains.remove(domain)
            self.set_container_domains(container, domains)

    def _dispatch(self, method, params):
        if not method in Manager.allowed:
            raise Exception('method "{}" is not supported'.format(method))

        try:
            return getattr(self, method)(*params)
        except:
            import traceback
            traceback.print_exc()
            raise
