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

from django.core.handlers.wsgi import WSGIHandler

from colorpicks.socket import ColorsNamespace

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
            # here we hand off this request to a blocking socketio manager
            # the Namespace subclass handles all the socketio messages
            socketio_manage(environ, {'': ColorsNamespace}, self.request)
        else:
            return self.django(environ, start_response)

if __name__ == '__main__':
    print 'starting gevent server'
    print "port", os.environ['PORT']
    SocketIOServer(
            ('0.0.0.0',  int(os.environ['PORT'])),
            Application(),
            resource="socket.io",
            transports=['websocket'],
            policy_server=False
            ).serve_forever()
