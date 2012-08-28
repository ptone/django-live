#!/usr/bin/env python

# from gevent import monkey; monkey.patch_all()

import gevent
import gevent.monkey
gevent.monkey.patch_all()

import psycogreen.gevent.psyco_gevent
psycogreen.gevent.psyco_gevent.make_psycopg_green()

from socketio import socketio_manage
from socketio.server import SocketIOServer

import os

os.environ['DJANGO_SETTINGS_MODULE'] = 'django_project.settings'

from gevent.wsgi import WSGIServer
from django.core.handlers.wsgi import WSGIHandler

from colorpicks.socket import ColorsNamespace


# WSGIServer(('', 8088), WSGIHandler()).serve_forever()

class Application(object):

    def __init__(self):
        self.buffer = []
        # Dummy request object to maintain state between Namespace
        # initialization.
        self.request = {}
        self.django = WSGIHandler()

    def __call__(self, environ, start_response):
        path = environ['PATH_INFO'].strip('/')
        if path.startswith("socket.io"):
            socketio_manage(environ, {'': ColorsNamespace}, self.request)
        else:
            return self.django(environ, start_response)

# socket = SocketIOServer(('', 8008), receive, resource='socket.io').serve_forever()


if __name__ == '__main__':
    print 'Listening on port 8080 and on port 843 (flash policy server)'
    SocketIOServer(('0.0.0.0', 8000), Application(),
        resource="socket.io", policy_server=True,
        policy_listener=('0.0.0.0', 10843)).serve_forever()
