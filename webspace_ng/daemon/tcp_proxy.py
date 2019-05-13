import subprocess

from .. import WebspaceError

class TcpProxyError(WebspaceError):
    pass

class TcpProxy:
    def __init__(self, proxy_bin, sock_path):
        self.proc = subprocess.Popen([proxy_bin, sock_path], stdin=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf8')

    def add_forwarding(self, eport, user, iport):
        self.proc.stdin.write('add {} {} {}\n'.format(eport, user, iport))
        self.proc.stdin.flush()

        result = self.proc.stderr.readline().strip()
        if result != 'ok':
            raise TcpProxyError('failed to add port forwarding {} -> {}:{}: {}'.format(eport, user, iport, result))
    def remove_forwarding(self, eport):
        self.proc.stdin.write('remove {}\n'.format(eport))
        self.proc.stdin.flush()

        result = self.proc.stderr.readline().strip()
        if result != 'ok':
            raise TcpProxyError('failed to remove port {}: {}'.format(eport, result))

    def stop(self):
        self.proc.terminate()
        self.proc.wait(timeout=3)
