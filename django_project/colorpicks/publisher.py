import json

from django.db.models.signals import post_save, post_delete
from django.db.utils import DatabaseError

from redis import Redis

from predicate import P

from colorpicks.models import ColorChoice

redis_client = Redis()

class Collection(object):

    def __init__(self, name, predicate):
        self.name = name
        self.predicate = predicate
        self.reset()

    def reset(self):
        current_members = ColorChoice.objects.filter(self.predicate)
        for member in current_members:
            self.update(member)
        current_ids = set([m.id for m in current_members])
        redis_members = redis_client.smembers(self.name)
        removed_ids = redis_members - current_ids
        if len(removed_ids):
            removed_objects = ColorChoice.objects.filter(id__in=removed_ids)
            for obj in removed_objects:
                self.remove(obj)


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
        if instance in self.predicate:
            self.add(instance)
        else:
            self.remove(instance)

    def remove(self, instance):
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
    blue = Collection('blue', P(hue__range=(171, 264)))
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
        collection.update(instance)

    channel = 'color/{}'.format(instance.pk)
    data = instance.data()
    print 'publishing post_save for model to redis channel for model'
    redis_client.publish(channel, json.dumps({'action':'update', 'data':data}))

def delete_color(sender, instance, **kwargs):
    for collection in collections.values():
        collection.remove(instance)

post_save.connect(publish_color, ColorChoice)
post_delete.connect(delete_color, ColorChoice)


