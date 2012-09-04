import json

from django.conf import settings
from django.db.models.signals import post_save, post_delete
from django.db.utils import DatabaseError

from redis import Redis

from predicate import P

from colorpicks.models import ColorChoice

"""
This module has three parts and should probably eventually be split up

defines a "Collection" class

defines a global 'collections' dictionary to hold collection instances

connects to ORM signals for model save/delete

creates a few app-wide common collections
"""

redis_client = Redis(connection_pool=settings.REDIS_POOL)

# reset current users at server startup
redis_client.delete('connected_users')

class Collection(object):
    """
    An in memory representation of a group of objects

    This class manages relaying ORM signal events to any connected socket
    clients by managing a couple redis structures.

    A collection consists of:

        name/label
        predicate
        redis set
        redis channel

    A predicate is essentially like a Django Q object, be can be used to evaluate
    whether an object meets a condition, without running a query against the DB

    After initially setting up the Collection - any save/delete model signal
    will relay to all collections .update method - which checks whether the model
    matches the predicate, if is already a member, and adds or removes it to the
    collection as appropriate. Any add/remove is broadcast to anyone subscribed
    to the collection's channel.

    Currently there are aspects of this class that are highly coupled to this
    demo - but it could be refactored and made a bit more abstract without much
    effort.
    """

    def __init__(self, name, predicate):
        self.name = name
        self.predicate = predicate
        self.reset()

    def reset(self):
        """
        Clear/Set up our redis set
        Query the db for any current members
        Update collection with current db members
        """

        redis_client.delete(self.name)
        current_members = ColorChoice.objects.filter(self.predicate)
        for member in current_members:
            self.update(member)

    def add(self, instance):
        print 'evaluating for add ', instance, self.name
        if not redis_client.sismember(self.name, instance.id):
            # Not a member, add and publish
            redis_client.sadd(self.name, instance.id)
            data = instance.data()
            data['id'] = instance.id
            redis_client.publish(self.name, json.dumps(
                {'action':'create', 'data':data}))
            print 'added'
        else:
            print 'not added'


    def update(self, instance):
        print "updating for ", self.name, instance
        if instance in self.predicate:
            self.add(instance)
        else:
            self.remove(instance)

    def remove(self, instance):
        print 'evaluating for removal ', instance, self.name
        if redis_client.sismember(self.name, instance.id):
            # should no longer be a member, remove
            redis_client.srem(self.name, instance.id)
            data = instance.data()
            data['id'] = instance.id
            redis_client.publish(self.name, json.dumps(
                {'action':'delete', 'data':data}))
            print 'removed'
        else:
            print 'not removed'

    def fetch(self, limit=70):
        """
        When a collection is first requested from the client
        we fetch with a sane limit here
        """
        data = list(
                ColorChoice.objects.filter(self.predicate).values(
                    'id',
                    'name',
                    'color_choice'
                    ))[:limit]
        return data

def publish_color(sender, instance, **kwargs):
    """
    This function is responsible for relaying save events from Django's
    post_save signal, into redis pubsub channels. The managed socketio sessions
    are sub'd to these channels for each model being displayed - and will
    update the client as soon as the model is saved
    """
    for collection in collections.values():
        # print "update ", collection.name, instance
        collection.update(instance)

    channel = 'color/{}'.format(instance.pk)
    data = instance.data()
    data['id'] = instance.id
    # print 'publishing post_save for model to redis channel for model'
    redis_client.publish(channel, json.dumps({'action':'update', 'data':data}))

def delete_color(sender, instance, **kwargs):
    for collection in collections.values():
        collection.remove(instance)
    # send an unsub message to this colors channel
    # any listening greenlets will unsub and return
    redis_client.publish('color/{}'.format(instance.id),
            json.dumps({'action':'unsub', 'data':{}}))

post_save.connect(publish_color, ColorChoice)
post_delete.connect(delete_color, ColorChoice)

# This is a global collections data structure accessed by all connected sockets
# it intially holds any commonly defined collections, but clients can add their
# own collections to wire into the signal-collection dispatching. If there were
# to be many user registered collections, the signal should be converted to a
# queued task instead of in the req/res cycle.
collections = {}

try:
    # We do this here in the try because we can't
    # access these models on startup if we are running in the syncdb
    # code. Could import this file in other-than-models.py to avoid that
    blue_colors = P(
        hue__range=(171, 264),
        saturation__range=(30,100),
        brightness__range=(30, 100)
        )

    django1 = P(
        hue__range=(154, 160),
        saturation__range=(35, 82),
        brightness__range=(10, 38)
        )

    django2 = P(
        hue__range=(82, 95),
        saturation__range=(70,90),
        brightness__range=(29,90)
        )

    django3 = P(
        hue__range=(131, 148),
        saturation__range=(20,50),
        brightness__range=(15,60)
        )

    django_colors = django1 | django2 | django3

    # create the common collections
    collections['blue'] = Collection('blue', blue_colors)
    collections['all'] = Collection('all', P())
    collections['django'] = Collection('django', django_colors)
except DatabaseError as exc:
    # we will get this if syncdb has not run yet
    from django.db import connection
    connection._rollback()

