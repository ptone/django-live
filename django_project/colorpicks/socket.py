from gevent import monkey; monkey.patch_all()
from gevent import Greenlet
import json
from socketio.namespace import BaseNamespace
from socketio.mixins import BroadcastMixin

from redis import Redis, ConnectionPool
from socketio.namespace import allowed_event_name_regex
from django.core import serializers
from colorpicks.resources import ColorResource
from colorpicks.models import ColorChoice
from colorpicks.utils import get_colors_json

dummy_api_response = [{"email": "mary@mary.com", "identifier": "as34klj34lk43", "id": 1, "name": "Mary", "color_choice": "#333333"}, {"email": "", "identifier": "1e2a8e172adbefb11540883c69532f30", "id": 2, "name": "", "color_choice": "#0e37ed"}, {"email": "bob@bob.com", "identifier": "5949b3b2692d7", "id": 3, "name": "bob", "color_choice": "#E80E91"}, {"email": "", "identifier": "4ab2956f6c03e978dcb94b1a0412d10b", "id": 4, "name": "", "color_choice": "#9D0DD6"}, {"email": "", "identifier": "fd045a6582bafc586963cbc1fbe4a2f5", "id": 5, "name": "", "color_choice": "#E8D01C"}, {"email": "", "identifier": "d358ea7904f61ddb180871d28ed8d36e", "id": 6, "name": "", "color_choice": "#7F7FE3"}, {"email": "", "identifier": "0697a284c1c8d2f28ec2a7000f415e80", "id": 7, "name": "", "color_choice": "#D60000"}, {"email": "", "identifier": "7ee16df18ce3776bec45b76c5a0ed069", "id": 8, "name": "", "color_choice": "#b9e8b2"}]


class ColorsNamespace(BaseNamespace, BroadcastMixin):

    def __init__(self, *args, **kwargs):
        super(ColorsNamespace, self).__init__(*args, **kwargs)
        # TODO need util function to get redis client with configured settings
        self.redis = Redis()
        self.pubsub = self.redis.pubsub()

    def process_event(self, packet):
        # print packet
        args = packet['args']
        # Special case here, where we want to allow ":" as sent by
        # backbone.iobine
        name = packet['name'].replace(":","_")
        if not allowed_event_name_regex.match(name):
            self.error("unallowed_event_name",
                       "name must only contains alpha numerical characters")
            return

        method_name = 'on_' + name.replace(' ', '_')
        return self.call_method_with_acl(method_name, packet, *args)

    def recv_disconnect(self):
        # cleanup here
        print 'socket disconnecting'
        # TODO redis disconnect

        color_obj = ColorChoice.objects.get(identifier=self.identifier)
        self.colorid = color_obj.id
        data = color_obj.data()
        # we add the ID back here - normally part of the URL/topic
        data['id'] = self.colorid


        self.broadcast_event_not_me('color/{}:delete'.format(self.colorid), data)
        self.redis.srem('connected_users', self.identifier)
        self.disconnect(silent=True)

    def on_identify(self, msg):
        print msg['identifier']
        self.identifier = msg['identifier']
        color_obj = ColorChoice.objects.get(identifier=self.identifier)
        self.colorid = color_obj.id
        data = color_obj.data()
        # we add the ID back here - normally part of the URL/topic
        data['id'] = self.colorid
        self.broadcast_event_not_me('colors:create', data)
        self.redis.sadd('connected_users', self.identifier)

    def on_subscribe(self, msg):
        """
        subscribe to a channel
        """
        print 'subscriber', msg, self.identifier, self.colorid
        # Subscribe to incoming pubsub messages from redis.
        def subscriber(io, topic):
            # TODO not sure I can reuse the same redis client for multiple
            # pubsub classes? Also is there a good way to avoide duplicate
            # subscriptions?
            redis_sub = self.redis.pubsub()
            redis_sub.subscribe(topic)
            while io.socket.connected:
                for message in redis_sub.listen():
                    if message['type'] == 'message':
                        # print message
                        io.emit(message['channel'] + ":update", json.loads(message['data']))
        greenlet = Greenlet.spawn(subscriber, self, msg['url'])
        # TODO not yet worried about unsubscribing
        # assume that redis unsubscribes once disconnected
        # self.pubsub.subscribe(msg['channel'])

    def on_colors_read(self, msg):
        """
        backbone collection fetch,
        socket.io event name 'api:read'
        """
        # TODO does this shortcut the subscribe here
        # or does it let the backbone subscribe at the level of the model
        # being created?
        data = get_colors_json()
        connected_users = self.redis.smembers('connected_users')
        colors = ColorChoice.objects.filter(identifier__in=connected_users).values(
                'id',
                'name',
                'color_choice')
        data = list(colors)
        print 'api:read'
        print data
        self.emit('colors:create', data)

    def on_color_update(self, msg):
        print 'color:update'
        # print msg
        choice_obj = ColorChoice.objects.get(pk=msg['id'])
        choice_obj.color_choice = msg['color_choice']
        # this will not scale - need a way to save the model
        # only on last edit in a drag, or on blur
        choice_obj.save()
        # broadcast is handled through post_save signal
        # which publishes to redis pubsub


    def on_testemit(self, msg):
        print 'testemit'

    def recv_message(self, message):
        print "PING!!!", message
