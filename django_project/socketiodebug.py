from gevent import monkey

monkey.patch_all()

from socketio import socketio_manage
from socketio.server import SocketIOServer
from socketio.namespace import BaseNamespace
from socketio.mixins import RoomsMixin, BroadcastMixin

from colorpicks.socket import ColorsNamespace

dummy_api_response = [{"email": "mary@mary.com", "identifier": "as34klj34lk43", "id": 1, "name": "Mary", "color_choice": "#333333"}, {"email": "", "identifier": "1e2a8e172adbefb11540883c69532f30", "id": 2, "name": "", "color_choice": "#0e37ed"}, {"email": "bob@bob.com", "identifier": "5949b3b2692d7", "id": 3, "name": "bob", "color_choice": "#E80E91"}, {"email": "", "identifier": "4ab2956f6c03e978dcb94b1a0412d10b", "id": 4, "name": "", "color_choice": "#9D0DD6"}, {"email": "", "identifier": "fd045a6582bafc586963cbc1fbe4a2f5", "id": 5, "name": "", "color_choice": "#E8D01C"}, {"email": "", "identifier": "d358ea7904f61ddb180871d28ed8d36e", "id": 6, "name": "", "color_choice": "#7F7FE3"}, {"email": "", "identifier": "0697a284c1c8d2f28ec2a7000f415e80", "id": 7, "name": "", "color_choice": "#D60000"}, {"email": "", "identifier": "7ee16df18ce3776bec45b76c5a0ed069", "id": 8, "name": "", "color_choice": "#b9e8b2"}]

def not_found(start_response):
    start_response('404 Not Found', [])
    return ['<h1>Not Found</h1>']

class ChatNamespace(BaseNamespace, RoomsMixin, BroadcastMixin):
    def on_nickname(self, nickname):
        self.request['nicknames'].append(nickname)
        self.socket.session['nickname'] = nickname
        self.broadcast_event('announcement', '%s has connected' % nickname)
        self.broadcast_event('nicknames', self.request['nicknames'])
        # Just have them join a default-named room
        self.join('main_room')

    def recv_disconnect(self):
        # Remove nickname from the list.
        print 'socket disconnecting'
        # nickname = self.socket.session['nickname']
        # self.request['nicknames'].remove(nickname)
        # self.broadcast_event('announcement', '%s has disconnected' % nickname)
        # self.broadcast_event('nicknames', self.request['nicknames'])

        self.disconnect(silent=True)

    def on_testemit(self, msg):
        print 'testemit:'
        print msg

    def on_api_read(self, msg):
        print 'api:read'
        print msg
        self.emit('/api/colors/:create', dummy_api_response)

    def on_user_message(self, msg):
        self.emit_to_room('main_room', 'msg_to_room',
            self.socket.session['nickname'], msg)

    def recv_message(self, message):
        print "PING!!!", message

class Application(object):

    def __init__(self):
        self.buffer = []
        # Dummy request object to maintain state between Namespace
        # initialization.
        self.request = {
            'nicknames': [],
        }

    def __call__(self, environ, start_response):
        path = environ['PATH_INFO'].strip('/')
        print path
        if not path:
            start_response('200 OK', [('Content-Type', 'text/html')])
            return ['<h1>Welcome. '
                'Try the <a href="/chat.html">chat</a> example.</h1>']

        if path.startswith('static/') or path == 'chat.html':
            try:
                data = open(path).read()
            except Exception:
                return not_found(start_response)

            if path.endswith(".js"):
                content_type = "text/javascript"
            elif path.endswith(".css"):
                content_type = "text/css"
            elif path.endswith(".swf"):
                content_type = "application/x-shockwave-flash"
            else:
                content_type = "text/html"

            start_response('200 OK', [('Content-Type', content_type)])
            return [data]

        if path.startswith("socket.io"):
            socketio_manage(environ, {'': ColorsNamespace}, self.request)
        else:
            return not_found(start_response)

# socket = SocketIOServer(('', 8008), receive, resource='socket.io').serve_forever()


if __name__ == '__main__':
    print 'Listening on port 8080 and on port 843 (flash policy server)'
    SocketIOServer(('0.0.0.0', 8008), Application(),
        resource="socket.io", policy_server=True,
        policy_listener=('0.0.0.0', 10843)).serve_forever()
