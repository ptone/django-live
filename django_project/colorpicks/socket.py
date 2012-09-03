
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
    each event is routed to a method matching that name.

    so an 'update' event is routed to an on_update method

    """
    def __init__(self, *args, **kwargs):
        dlog( "--= --******** ********* *******  --   Namespace init")
        super(ColorsNamespace, self).__init__(*args, **kwargs)
        self.redis = Redis(connection_pool=settings.REDIS_POOL)
        self.pubsub = self.redis.pubsub()
        self.subscribers = {}
        self.show_only_connected_users = True
        self.collection = 'all' #'all'
        self.on_subscribe({'url':self.collection})
        self.on_subscribe({'url':'connected_users'})

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
        name = packet['name'].replace(":","_")
        if not allowed_event_name_regex.match(name):
            self.error("unallowed_event_name",
                       "name must only contains alpha numerical characters")
            return

        method_name = 'on_' + name.replace(' ', '_')
        return self.call_method_with_acl(method_name, packet, *args)

    def recv_disconnect(self):
        # cleanup here
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
        # remove it from the current users list
        if self.redis.sismember('connected_users', self.colorid):
            self.redis.publish('connected_users', json.dumps({'action':'delete',
                'data':data}))
            self.redis.srem('connected_users', self.colorid)
        self.clear_subscribers()
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
            # dlog( "publishing that user has joined ", self.colorid)
            self.redis.publish('connected_users', json.dumps(
                {'action':'create','data':data}))
            self.redis.sadd('connected_users', self.colorid)
        # dlog( 'currently connected users after this join ', self.redis.smembers('connected_users'))
        self.on_subscribe({'url':'connected_users'})

    def on_fetch_collection(self, collection):
        # TODO currently we don't fetch the data for our own color in the best
        # way - so we need to make sure we add it into any collection that is fetched
        #
        collection_data = collection.fetch()
        if self.show_only_connected_users:
            # dlog( 'filtering to connected_users')
            # dlog( [d['id'] for d in collection_data])
            connected_users= self.redis.smembers('connected_users')
            # dlog( 'connected_usersredis members',connected_users)
            collection_data = [d for d in collection_data if str(d['id']) in connected_users]
            # dlog( 'new collection data', collection_data)
        current_ids = [d['id'] for d in collection_data]
        if self.colorid not in current_ids:
            self_data = ColorChoice.objects.get(id=self.colorid).data()
            self_data['id'] = self.colorid
            collection_data.append(self_data)
        # dlog( 'end of fetch collection ', collection.name, collection_data)
        # This is currently a hack - I handle collection
        # swapping here, because I can't get seem to swap a 
        # collection out on a backbone view

        # self.emit('{}:create'.format(collection.name), collection_data)
        dlog( id(self), " emitting collection:create data ", collection_data)
        self.emit('{}:create'.format('all'), collection_data)

    def on_subscribe(self, msg):
        """
        subscribe to a channel, sent by backbone for each model instantiated
        """
        # dlog( 'subscriber', msg, self.identifier, self.colorid)
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
                        # dlog( 'rejecting ', message)
                        continue
                    dlog( id(self), ' pubsub ', message)

                    data = json.loads(message['data'])
                    if data['action'] == 'unsub':
                        redis_sub.unsubscribe(topic)
                        # ends the greenlet
                        return

                    # dlog( 'message data: ', data)
                    colorid = str(data['data']['id'])

                    chan = message['channel']
                    if chan == 'connected_users':
                        # dlog( 'subscriber hearing of join ', message)
                        pass
                    if (data['action'] == 'update' and
                            self.show_only_connected_users and not
                            self.redis.sismember('connected_users', colorid)):
                        return
                    if chan == 'connected_users':
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

        # dlog( msg)
        url = msg['url']
        # dlog( 'subscribe request for ', url)
        if url not in self.subscribers:
            # dlog( 'subscribigng to ', url)
            greenlet = Greenlet.spawn(subscriber, self, url)
            self.subscribers[url] = greenlet
            # dlog( 'subscriber greenlets so far: ', len(self.subscribers))
        else:
            pass
            # dlog( 'already subscribed do ', url)
        # TODO not yet worried about unsubscribing
        # should stash the greenlet in a dict of channels to disconnect from

    def on_connected_users_read(self, msg):
        """
        backbone collection fetch,
        socket.io event name '<collection url>:read'
        used to do the initial population of the backbone collection
        """
        dlog( "- -8 -8 -8 -8 - 8- 8- 8 -8 - 8 Don't think this is being called")
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
        # dlog( 'saving', choice_obj)
        choice_obj.save()
        # broadcast is handled through post_save signal
        # which publishes to redis pubsub

    def on_currentuser(self, msg):
        # dlog( 'currentuser', msg)
        original_value = self.show_only_connected_users
        self.show_only_connected_users = msg['showonly']
        # TODO remove individual color model subscriptions as appropriate
        # if self.show_only_connected_users != original_value:
            # self.on_fetch_collection(collections[self.collection])

    def unsubscribe(self, url):
        # publishing 'unsub' will cause ANY subscribed listener to return
        # not just self
        # self.redis.publish(url, json.dumps({'action':'unsub','data':{}}))
        self.subscribers[url].kill(block=False)
        del(self.subscribers[url])

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

    def on_setcollection(self, msg):
        dlog( "setting collection", msg)
        self.unsubscribe(self.collection)
        if (msg['url'].startswith('similar') and not
                self.collection.startswith('similar')):
            dlog( "settings similar")
            my_obj = ColorChoice.objects.get(id=self.colorid)
            my_name = 'similar{}'.format(self.colorid)
            self.redis.delete(my_name)
            similar_color = P(
                hue__range = (max(0, my_obj.hue - 15), min(365, my_obj.hue + 15)),
                saturation__range = (max(0, my_obj.saturation-15), min(100, my_obj.saturation+15)),
                brightness__range = (max(0, my_obj.brightness-15), min(100, my_obj.brightness+15))
                )
            dlog(similar_color.children)
            collections[my_name] = Collection(my_name, similar_color)
            msg['url'] = my_name
            # self.reset_collection(my_name)
        else:
            if self.collection.startswith('similar'):
                del(collections[self.collection])

        self.collection = msg['url']
        self.on_subscribe(msg)
        dlog( "collections:\n", collections)
        # fetch of new collection handled by client

    def clear_subscribers(self):
        for sub in self.subscribers:
            self.subscribers[sub].kill(block=False)
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
