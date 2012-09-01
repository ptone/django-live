
from gevent import monkey; monkey.patch_all()
from gevent import Greenlet
import json
from socketio.namespace import BaseNamespace
from socketio.mixins import BroadcastMixin

from redis import Redis
from socketio.namespace import allowed_event_name_regex

from django.conf import settings

from colorpicks.models import ColorChoice
from colorpicks.publisher import collections

class ColorsNamespace(BaseNamespace, BroadcastMixin):
    """
    This is where all of the socketio management happens
    each event is routed to a method matching that name.

    so an 'update' event is routed to an on_update method

    """
    def __init__(self, *args, **kwargs):
        print "--= --******** ********* *******  --   Namespace init"
        super(ColorsNamespace, self).__init__(*args, **kwargs)
        self.redis = Redis(connection_pool=settings.REDIS_POOL)
        self.pubsub = self.redis.pubsub()
        self.subscribers = {}
        self.show_only_connected_users = True
        self.collection = 'blue' #'all'

    def process_event(self, packet):
        """
        This method is overridden here because backbone.iobind uses ':' in the
        event names, and gevent-socketio only allows valid python names, so we
        convert to _

        we also take any collection fetch - and route it to a single method
        on self.
        """
        args = packet['args']
        # Special case here, where we want to allow ":" as sent by
        # backbone.iobind
        print packet
        if ':' in packet['name']:
            url, action = packet['name'].split(':')
            print collections
            if url in collections:
                # TODO perhaps call through the namespace ACL machinery
                return self.on_fetch_collection(collections[url])
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
        # remove it from the current users list
        if self.redis.sismember('connected_users', self.colorid):
            self.redis.publish('connected_users', json.dumps({'action':'delete',
                'data':data}))
            self.redis.srem('connected_users', self.colorid)
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
        if not self.redis.sismember('connected_users', self.colorid):
            # don't add me again for multiple tabs
            # self.broadcast_event_not_me('colors:create', data)
            print "publishing that user has joined ", self.colorid
            self.redis.publish('connected_users', json.dumps(
                {'action':'create','data':data}))
            self.redis.sadd('connected_users', self.colorid)
        print 'currently connected users after this join ', self.redis.smembers('connected_users')
        self.on_subscribe({'url':'connected_users'})

    def on_fetch_collection(self, collection):
        # TODO currently we don't fetch the data for our own color in the best
        # way - so we need to make sure we add it into any collection that is fetched
        #
        collection_data = collection.fetch()
        if self.show_only_connected_users:
            print 'filtering to connected_users'
            print [d['id'] for d in collection_data]
            connected_users= self.redis.smembers('connected_users')
            print 'connected_usersredis members',connected_users
            collection_data = [d for d in collection_data if str(d['id']) in connected_users]
            print 'new collection data', collection_data
        current_ids = [d['id'] for d in collection_data]
        if self.colorid not in current_ids:
            self_data = ColorChoice.objects.get(id=self.colorid).data()
            self_data['id'] = self.colorid
            collection_data.append(self_data)
        print 'end of fetch collection ', collection.name, collection_data
        self.emit('{}:create'.format(collection.name), collection_data)

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
            events is a bridge to Django's signals - see colorpicks.publisher.

            When a message is received on the redis channel, it emits an event
            to backbone over socketio
            """
            redis_sub = self.redis.pubsub()
            redis_sub.subscribe(topic)

            while io.socket.connected:
                # TODO the nesting dictionaries with the key 'data'
                # is highly problematic now - need to fix
                for message in redis_sub.listen():
                    if message['type'] != 'message':
                        print 'rejecting ', message
                        continue
                    print 'pubsub message for ', id(self), message
                    data = json.loads(message['data'])
                    print 'message data: ', data
                    colorid = str(data['data']['id'])

                    chan = message['channel']
                    if chan == 'connected_users':
                        print 'subscriber hearing of join ', message
                    if (data['action'] == 'update' and
                            self.show_only_connected_users and not
                            self.redis.sismember('connected_users', colorid)):
                        return
                    if (chan == 'connected_users' and
                            self.redis.sismember(self.collection, colorid)):
                        # emit as if this were just added to the collection
                        chan = self.collection
                    io.emit(chan + ":" +
                            data['action'],
                            data['data']
                            )

        # we could filter our own ID out, so we don't subscribe to
        # ourselves. It would depend on whether you want to allow changes
        # made through other avenues to be reflected
        # if you don't filter, that means there is no way to avoid
        # getting your own round tripped updates - which defeates some of the
        # point of the client side MVC

        # print msg
        url = msg['url']
        print 'subscribe request for ', url
        if url not in self.subscribers:
            print 'subscribigng to ', url
            greenlet = Greenlet.spawn(subscriber, self, url)
            self.subscribers[url] = greenlet
            print 'subscriber greenlets so far: ', len(self.subscribers)
        else:
            print 'already subscribed do ', url
        # TODO not yet worried about unsubscribing
        # should stash the greenlet in a dict of channels to disconnect from

    def on_connected_users_read(self, msg):
        """
        backbone collection fetch,
        socket.io event name '<collection url>:read'
        used to do the initial population of the backbone collection
        """
        connected_users = self.redis.smembers('connected_users')
        colors = ColorChoice.objects.filter(id__in=[int(i) for i in connected_users]).values(
                'id',
                'name',
                'color_choice')
        data = list(colors)
        self.emit('connected_users:create', data)

    def on_color_update(self, msg):
        choice_obj = ColorChoice.objects.get(pk=msg['id'])
        choice_obj.color_choice = msg['color_choice']
        choice_obj.name = msg['name']
        # this will not scale - need a way to save the model
        # only on last edit in a drag, or on blur
        # can also use client side throttling
        # but then need another way to notify other clients
        print 'saving', choice_obj
        choice_obj.save()
        # broadcast is handled through post_save signal
        # which publishes to redis pubsub

    def on_currentuser(self, msg):
        print 'currentuser', msg
        original_value = self.show_only_connected_users
        self.show_only_connected_users = msg['showonly']
        # if self.show_only_connected_users != original_value:
            # self.on_fetch_collection(collections[self.collection])

# Some Debug methods
    def on_testemit(self, msg):
        print 'testemit'


    def recv_message(self, message):
        print "PING!!!", message
