import json

from django.conf import settings
from django.db.models.signals import post_save, post_delete
from django.db.utils import DatabaseError

from redis import Redis

from predicate import P

from colorpicks.models import ColorChoice

redis_client = Redis(connection_pool=settings.REDIS_POOL)

# reset current users at server startup
connected_users= tuple(redis_client.smembers('connected_users'))
print "connected_usersusers at server startup ", connected_users
# this method not working ERR wrong number of arguments for 'srem' command
if connected_users:
    redis_client.srem('connected_users', *connected_users)
# for cu in connected_users:
    # redis_client.srem('connected_users', cu)
connected_users = redis_client.smembers('connected_users')
print "connected_usersusers at server startup end",connected_users

class Collection(object):

    def __init__(self, name, predicate):
        self.name = name
        self.predicate = predicate
        self.reset()

    def reset(self):
        print 'collection reset for ', self.name
        current_members = ColorChoice.objects.filter(self.predicate)
        print current_members.count(), " current members"
        for member in current_members:
            self.update(member)
        current_ids = set([str(m.id) for m in current_members])
        print 'current ids ', current_ids
        redis_members = redis_client.smembers(self.name)
        print 'redis members', redis_members
        removed_ids = redis_members - current_ids
        print 'removing ids ', removed_ids
        if len(removed_ids):
            removed_objects = ColorChoice.objects.filter(
                    id__in=[int(i) for i in removed_ids])
            print removed_objects
            for obj in removed_objects:
                self.remove(obj)
            # remove any stale IDs of items no in the DB
            redis_client.srem(self.name, *tuple(removed_ids))

    def add(self, instance):
         if not redis_client.sismember(self.name, instance.id):
                # Not a member, add an publish
                redis_client.sadd(self.name, instance.id)
                data = instance.data()
                data['id'] = instance.id
                print 'publishing to collection'
                redis_client.publish(self.name, json.dumps(
                    {'action':'create', 'data':data}))


    def update(self, instance):
        print "updating for ", self.name, instance
        # new versions of django-predicate allow for an __in__ test
        if self.predicate.eval(instance):
            print 'adding'
            self.add(instance)
        else:
            print 'removing'
            self.remove(instance)

    def remove(self, instance):
        print 'removing', instance
        if redis_client.sismember(self.name, instance.id):
            # should no longer be a member, remove
            redis_client.srem(self.name, instance.id)
            data = instance.data()
            data['id'] = instance.id
            redis_client.publish(self.name, json.dumps(
                {'action':'delete', 'data':data}))

    def fetch(self):
        data = list(
                ColorChoice.objects.filter(self.predicate).values(
                    'id',
                    'name',
                    'color_choice'
                    ))
        return data

collections = {}

try:
    blue = Collection('blue', P(
        hue__range=(171, 264),
        saturation__range=(30,100),
        brightness__range=(30, 100)))

    collections['blue'] = blue
except DatabaseError as exc:
    # we will get this if syncdb has not run yet
    from django.db import connection
    connection._rollback()


def publish_color(sender, instance, **kwargs):
    """
    This function is responsible for relaying save events from Django's
    post_save signal, into redis pubsub channels. The managed socketio sessions
    are sub'd to these channels for each model being displayed - and will
    update the client as soon as the model is saved
    """
    for collection in collections.values():
        print "update ", collection.name, instance
        collection.update(instance)

    channel = 'color/{}'.format(instance.pk)
    data = instance.data()
    data['id'] = instance.id
    print 'publishing post_save for model to redis channel for model'
    redis_client.publish(channel, json.dumps({'action':'update', 'data':data}))

def delete_color(sender, instance, **kwargs):
    for collection in collections.values():
        collection.remove(instance)

post_save.connect(publish_color, ColorChoice)
post_delete.connect(delete_color, ColorChoice)


