from gevent import monkey; monkey.patch_all()
from gevent import Greenlet
import json
from socketio.namespace import BaseNamespace
from socketio.mixins import BroadcastMixin

from redis import Redis
from socketio.namespace import allowed_event_name_regex

from colorpicks.models import ColorChoice
from colorpicks.utils import get_colors_json

class ColorsNamespace(BaseNamespace, BroadcastMixin):
    """
    This is where all of the socketio management happens
    each event is routed to a method matching that name.

    so an 'update' event is routed to an on_update method

    """
    def __init__(self, *args, **kwargs):
        super(ColorsNamespace, self).__init__(*args, **kwargs)
        # TODO need util function to get redis client configuration from settings
        self.redis = Redis()
        self.pubsub = self.redis.pubsub()

    def process_event(self, packet):
        """
        This method is overridden here because backbone.iobind uses ':' in the
        event names, and gevent-socketio only allows valid python names, so we
        convert to _
        """
        args = packet['args']
        # Special case here, where we want to allow ":" as sent by
        # backbone.iobind
        name = packet['name'].replace(":","_")
        if not allowed_event_name_regex.match(name):
            self.error("unallowed_event_name",
                       "name must only contains alpha numerical characters")
            return

        method_name = 'on_' + name.replace(' ', '_')
        return self.call_method_with_acl(method_name, packet, *args)

    def recv_disconnect(self):
        # cleanup here
        # TODO redis disconnect?
        # need a dict of pubsub channels to greenlets
        # TODO - currently this does not handle multiple tabs from same browser
        # close one tab - and your removed - because sessionid is shared between
        # windows/tabs, need either a reference counter, or a window specific
        # token
        color_obj = ColorChoice.objects.get(identifier=self.identifier)
        self.colorid = color_obj.id
        data = color_obj.data()
        # we add the ID back here - normally part of the URL/topic
        data['id'] = self.colorid
        # remove my color from everyone elses collection
        self.broadcast_event_not_me('color/{}:delete'.format(self.colorid), data)
        # remove it from the current users list
        self.redis.srem('connected_users', self.identifier)
        self.disconnect(silent=True)

    def on_identify(self, msg):
        """
        sent when the socket is first connected
        """
        self.identifier = msg['identifier']
        color_obj = ColorChoice.objects.get(identifier=self.identifier)
        self.colorid = color_obj.id
        data = color_obj.data()
        # we add the ID back here - normally part of the URL/topic
        data['id'] = self.colorid
        if not self.redis.sismember('connected_users', self.identifier):
            # don't add me again for multiple tabs
            self.broadcast_event_not_me('colors:create', data)
        self.redis.sadd('connected_users', self.identifier)

    def on_subscribe(self, msg):
        """
        subscribe to a channel, sent by backbone for each model instantiated
        """
        # print 'subscriber', msg, self.identifier, self.colorid
        def subscriber(io, topic):
            """
            Subscribe to incoming pubsub messages from redis.

            This will run in a greenlet, and blocks waiting for publish
            messages from other redis clients. One source for the publish
            events is a bridge to Django's signals - see colorpicks.publisher
            """
            redis_sub = self.redis.pubsub()
            redis_sub.subscribe(topic)
            while io.socket.connected:
                for message in redis_sub.listen():
                    if message['type'] == 'message':
                        # print message
                        io.emit(message['channel'] + ":update", json.loads(message['data']))
        greenlet = Greenlet.spawn(subscriber, self, msg['url'])
        # TODO not yet worried about unsubscribing
        # should stash the greenlet in a dict of channels to disconnect from

    def on_colors_read(self, msg):
        """
        backbone collection fetch,
        socket.io event name 'colors:read'
        used to do the initial population of the backbone collection
        """
        # data = get_colors_json()
        connected_users = self.redis.smembers('connected_users')
        colors = ColorChoice.objects.filter(identifier__in=connected_users).values(
                'id',
                'name',
                'color_choice')
        data = list(colors)
        self.emit('colors:create', data)

    def on_color_update(self, msg):
        choice_obj = ColorChoice.objects.get(pk=msg['id'])
        choice_obj.color_choice = msg['color_choice']
        # this will not scale - need a way to save the model
        # only on last edit in a drag, or on blur
        # can also use client side throttling
        # but then need another way to notify other clients
        choice_obj.save()
        # broadcast is handled through post_save signal
        # which publishes to redis pubsub

# Some Debug methods
    def on_testemit(self, msg):
        print 'testemit'

    def recv_message(self, message):
        print "PING!!!", message
