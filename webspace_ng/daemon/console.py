import json
import logging
import stat
import os
from os import path
import shutil
import threading
import select
import socket

from eventfd import EventFD
from ws4py.client import WebSocketBaseClient
from ws4py.messaging import TextMessage

class ConsoleControl(WebSocketBaseClient):
    def __init__(self, ws_uri, resource, *args, **kwargs):
        WebSocketBaseClient.__init__(self, ws_uri, *args, **kwargs)
        self.resource = resource

    def resize(self, width, height):
        payload = json.dumps({
            'command': 'window-resize',
            'args': {
                'width': width,
                'height': height
            }
        }).encode('utf-8')
        self.send(payload, binary=False)
    def signal(self, signal):
        payload = json.dumps({
            'command': 'signal',
            'signal': signal
        }).encode('utf-8')
        self.send(payload, binary=False)

    def received_message(self, message):
        print('control msg', message.data)

class ConsoleSession(WebSocketBaseClient):
    def __init__(self, user, ws_uri, console_path, control_path, *args, socket_suffix='console', **kwargs):
        self.__shutdown_event = EventFD()

        self.socket_path = path.join('/tmp', '{}-ws-{}.socket'.format(user, socket_suffix))
        try:
            os.unlink(self.socket_path)
        except OSError:
            if os.path.exists(self.socket_path):
                raise

        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.bind(self.socket_path)
        self.socket.listen(1)
        shutil.chown(self.socket_path, user=user)
        os.chmod(self.socket_path, stat.S_IRWXU)

        self.control = ConsoleControl(ws_uri, control_path)
        self.control.connect()

        WebSocketBaseClient.__init__(self, ws_uri, *args, **kwargs)
        self.resource = console_path
        self.socket_conn = None
        self.run_thread = threading.Thread(target=self.run_read)

        self.connect()

    def __accept(self):
        while True:
            r, _, _ = select.select([self.__shutdown_event, self.socket], [], [])
            if self.__shutdown_event in r:
                break
            if self.socket in r:
                self.socket_conn, _ = self.socket.accept()
                break
    def __read_loop(self):
        while True:
            r, _, _ = select.select([self.__shutdown_event, self.sock, self.control.sock, self.socket_conn], [], [])
            if self.__shutdown_event in r:
                break
            if self.sock in r:
                if not self.once():
                    logging.debug('websocket error')
                    break
            if self.control.sock in r:
                if not self.control.once():
                    logging.debug('control websocket error')
                    break
            if self.socket_conn in r:
                try:
                    read = self.socket_conn.recv(4096)
                except:
                    logging.debug('pipe socket error')
                    break
                if not read:
                    # Socket was closed
                    break

                self.send(read, binary=True)
    def run_read(self):
        self.__accept()
        self.socket.close()

        if self.socket_conn is not None:
            self.__read_loop()
            self.socket_conn.close()

        os.unlink(self.socket_path)

        logging.debug('closing websockets')
        try:
            self.control.close()
            self.close()
        except:
            pass
        self.control.terminate()
        self.terminate()

    def start(self):
        self.run_thread.start()
    def join(self):
        self.run_thread.join()
    def stop(self, join=False):
        self.__shutdown_event.set()
        if join:
            self.join()

    def received_message(self, message):
        # Apparently a text message is a "message barrier"
        if isinstance(message, TextMessage):
            logging.debug('received websocket message barrier')
            self.stop()
            return

        if self.socket_conn is not None:
            self.socket_conn.sendall(message.data)
