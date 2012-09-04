
from gevent import monkey; monkey.patch_all()
from gevent import Greenlet
import json
from socketio.namespace import BaseNamespace
from socketio.mixins import BroadcastMixin

from redis import Redis
from socketio.namespace import allowed_event_name_regex

from django.conf import settings

from predicate import P

from colorpicks.models import ColorChoice
from colorpicks.publisher import collections, Collection

debug = 1

def dlog(*args, **kwargs):
    """
    the world's lightest weight logging framework
    """
    level = kwargs.get('level', 1)
    if level >= debug:
        print ' '.join([str(x) for x in list(args)])

class ColorsNamespace(BaseNamespace, BroadcastMixin):
    """
    This is where all of the socketio management happens

    gevent-socketio handles this through a namespace client
    this demo only uses the default namespace of ''

    and instance of this class is created in the serve.py file
    whenever a client connects to /socketio - at which point
    the gevent server will go into a blocking loop managing the
    websocket

    Normally each named <event> is routed to a matching on_<event>
    method in the class. We deviate from that slightly to factor
    any collection 'read' events with one method
    """
    def __init__(self, *args, **kwargs):
        dlog( "********************************  Namespace init")
        super(ColorsNamespace, self).__init__(*args, **kwargs)

        # our redis tools
        # the redis pubsub can only be used for subscribe, not publish
        self.redis = Redis(connection_pool=settings.REDIS_POOL)
        self.pubsub = self.redis.pubsub()

        # a dicitonary where we keep track of subscriber greenlets
        self.subscribers = {}
        self.show_only_connected_users = True
        self.collection = 'all'

        # subscribe to the default collection, and new user connections
        self.on_subscribe({'url':self.collection})
        self.on_subscribe({'url':'connected_users'})

    def process_event(self, packet):
        """
        This is the namespace event -> method dispatcher

        This method is overridden here because backbone.iobind uses ':' in the
        event names, and gevent-socketio only allows valid python names, so we
        convert to _

        we also take any collection fetch - and route it to a single method
        on self.
        """

        # log all events for debugging
        dlog( "socketio ", id(self), packet['name'], packet['args'])

        if ':' in packet['name']:
            # iobind uses a : to denote a target:action
            target, action = packet['name'].split(':')

            if target == 'similar' and self.collection.startswith('similar'):
                # 'similar' is generic on the browser client, but on
                # the python side they are unique, in the form similar<id>
                target = self.collection

            if target in collections:
                target = self.collection
                # TODO perhaps call through the namespace ACL machinery
                return self.on_fetch_collection(collections[target])

        # we have something other than a collection
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
        """
        This hook is called by event-socketio when the client closes the websocket
        """

        # TODO - currently this does not handle multiple tabs from same browser
        # close one tab - and your removed - because sessionid is shared between
        # windows/tabs, need either a reference counter, or a window specific
        # token
        dlog( id(self), ' disconnecting')
        color_obj = ColorChoice.objects.get(identifier=self.identifier)
        self.colorid = color_obj.id
        data = color_obj.data()
        # we add the ID back here - normally part of the URL/topic
        data['id'] = self.colorid

        # remove from the current users list
        if self.redis.sismember('connected_users', self.colorid):
            self.redis.publish('connected_users', json.dumps({'action':'delete',
                'data':data}))
            self.redis.srem('connected_users', self.colorid)
        self.clear_subscribers()
        # continue with the gevent-socketio disconnect
        self.disconnect(silent=True)

    def on_identify(self, msg):
        """
        sent when the socket is first connected

        This is an app specific handshake convention, and not a default
        part of socketio. There is a handshake in socketio, but that happens
        in gevent-socketio outside the namespace management
        """

        self.identifier = msg['identifier']
        color_obj = ColorChoice.objects.get(identifier=self.identifier)
        self.colorid = color_obj.id
        data = color_obj.data()
        # we add the ID back here - normally part of the URL/topic
        data['id'] = self.colorid
        if not self.redis.sismember('connected_users', self.colorid):
            # don't add me again for multiple tabs
            self.redis.publish('connected_users', json.dumps(
                {'action':'create','data':data}))
            self.redis.sadd('connected_users', self.colorid)
        self.on_subscribe({'url':'connected_users'})

    def on_fetch_collection(self, collection):

        collection_data = collection.fetch()

        if self.show_only_connected_users:
            # if needed, filter down to only connected_users
            connected_users= self.redis.smembers('connected_users')
            collection_data = [d for d in collection_data if str(d['id']) in connected_users]

        current_ids = [d['id'] for d in collection_data]

        if self.colorid not in current_ids:
            # TODO currently we don't send the data for our own color independently
            # which would be a bit more clean - so we need to make sure we include
            # into any collection that is fetched
            self_data = ColorChoice.objects.get(id=self.colorid).data()
            self_data['id'] = self.colorid
            collection_data.append(self_data)

        # dlog( 'end of fetch collection ', collection.name, collection_data)

        dlog( id(self), " emitting collection:create data ", collection_data)

        # TODO This is currently perhaps a hack - I handle collection
        # swapping here, because I can't get seem to swap a
        # collection out on a backbone view. So all self.collection changes
        # on self, but all collection IO events are sent as if they are the
        # collection 'all'

        # self.emit('{}:create'.format(collection.name), collection_data)
        self.emit('{}:create'.format('all'), collection_data)

    def on_subscribe(self, msg):
        """
        subscribe to a channel

        The channels for this app are one of:

            connected users
            the current collection of interest
            any model currently displayed
        """

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
                        # We are only interested in 'message' events on the channel
                        # dlog( 'rejecting ', message)
                        continue
                    dlog( id(self), ' pubsub ', message)

                    # redis pubsub data is always a string
                    data = json.loads(message['data'])

                    if data['action'] == 'unsub':
                        redis_sub.unsubscribe(topic)
                        # ends the greenlet
                        return

                    colorid = str(data['data']['id'])

                    chan = message['channel']

                    if (data['action'] == 'delete' and
                            colorid == self.colorid):
                        # don't delete yourself, this can happen when you
                        # are watching the 'similar' channel, and you change
                        # your color
                        continue

                    if (data['action'] in ['update', 'create'] and
                            self.show_only_connected_users and not
                            self.redis.sismember('connected_users', colorid)):
                        # a color of a non-connected user has been updated
                        # (perhaps through admin) and we are only watching for
                        # connected users - so do nothing
                        return

                    if chan == 'connected_users':
                        # we want to see if a connecting user is part of
                        # the current collection
                        if (self.redis.sismember(self.collection, colorid) and
                            self.show_only_connected_users):
                            # emit as if this were just added to the collection
                            chan = self.collection
                        else:
                            # don't emit a create event
                            continue

                    if not chan.startswith('color/'):
                        # again - hack to manage collection state on self here
                        chan = 'all'

                    dlog( id(self), 'emitting: ', chan, data['action'], data['data'])

                    io.emit(chan + ":" +
                            data['action'],
                            data['data']
                            )

                    if data['action'] == 'delete':
                        # send an extra delete event for the model also
                        # as the backbone collection seems buggy
                        io.emit('color/{}:delete'.format(data['data']['id']),
                                data['data'])
                        io.emit(chan + ":" +
                                data['action'],
                                list(data['data'])
                                )

        # we could filter our own ID out, so we don't subscribe to
        # ourselves. It would depend on whether you want to allow changes
        # made through other avenues to be reflected
        # if you don't filter, that means there is no way to avoid
        # getting your own round tripped updates - which defeates some of the
        # point of the client side MVC

        url = msg['url']
        if url not in self.subscribers:
            greenlet = Greenlet.spawn(subscriber, self, url)
            # stash this greenlet in a dictionary in order
            # to kill/unsub later on
            self.subscribers[url] = greenlet
        else:
            pass
            # dlog( 'already subscribed do ', url)

    def on_color_update(self, msg):
        """
        This is sent by backbone when a model is saved

        this probably would not scale great as is
        one step to mitigate used here in the demo is to throttle
        the save calls in JS on the client - something similar
        could probably done in python, so that the model save was
        only called at a certain frequency and/or only on the last
        of a string of events within a time period
        """
        choice_obj = ColorChoice.objects.get(pk=msg['id'])
        choice_obj.color_choice = msg['color_choice']
        choice_obj.name = msg['name']
        choice_obj.save()
        if self.collection.startswith('similar'):
            dlog("reset similar")
            self.set_similar(my_obj=choice_obj)
            # self.reset_collection()
        # broadcasting this save is handled through post_save signal
        # which publishes to redis pubsub

    def on_currentuser(self, msg):
        """
        This event handles the toggling of the "show only connected users"
        pref/checkbox
        """
        original_value = self.show_only_connected_users
        self.show_only_connected_users = msg['showonly']
        # TODO remove individual color model subscriptions as appropriate

    def reset_collection(self, collection=None):
        # TODO I believe this is now obsoleted
        if collection is None:
            collection = self.collection
        dlog( "?refreshing ", collection)
        if collection in collections.keys():
            dlog( 'yes - refreshing')
            # munge because all collections on client under the name "all"
            # tmp_emit_debug = "{}:refresh".format(collection)
            tmp_emit_debug = "all:refresh"
            # dlog(tmp_emit_debug)
            refresh_data = collections[collection].fetch()
            self.emit(tmp_emit_debug, refresh_data)

    def set_similar(self, my_obj=None):
        dlog( "settings similar")
        if my_obj is None:
            my_obj = ColorChoice.objects.get(id=self.colorid)
        my_name = 'similar{}'.format(self.colorid)
        similar_color = P(
            hue__range = (max(0, my_obj.hue - 25), min(365, my_obj.hue + 25)),
            saturation__range = (max(0, my_obj.saturation-20), min(100, my_obj.saturation+20)),
            brightness__range = (max(0, my_obj.brightness-20), min(100, my_obj.brightness+20))
            )
        dlog(similar_color.children)
        collections[my_name] = Collection(my_name, similar_color)
        return my_name

    def on_setcollection(self, msg):
        """
        this handles the radio button group selection
        of the current collection to view
        """

        dlog("setting collection", msg)
        if self.collection.startswith(msg['url']):
            # no change to current collection
            return
        else:
            # collection has changed
            # unsubscribe to the current collection
            self.unsubscribe(self.collection)

        if msg['url'].startswith('similar'):
            if not self.collection.startswith('similar'):
                # create a new collection on the fly - to look
                # for similar colors
                msg['url'] = self.set_similar()
                # self.reset_collection(my_name)
        else:
            if self.collection.startswith('similar'):
                # if the current collection was 'similar to me'
                # make sure we remove it from the global collections
                del(collections[self.collection])

        self.collection = msg['url']
        self.on_subscribe(msg)
        # the fetching of the newly switched-to collection
        # is handled in the backbone app

    def unsubscribe(self, chan):
        # publishing 'unsub' will cause ANY subscribed listener to return
        # not just self, so we kill our greenlet only, directly
        self.subscribers[chan].kill(block=False)
        del(self.subscribers[chan])

    def clear_subscribers(self):
        for sub in self.subscribers:
            # self.subscribers[sub].kill(block=False)
            self.unsubscribe(sub)
        self.subscribers = {}

# Some Debug methods
    def on_testemit(self, msg):
        dlog( 'testemit')


    def recv_message(self, message):
        dlog( "PING!!!", message)

    def on_log(self, message):
        # currently printed at on_process_event
        # print "log: ", message
        pass
