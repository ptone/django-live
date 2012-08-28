import json

from django.db.models.signals import post_save

from redis import Redis

from colorpicks.models import ColorChoice

redis_client = Redis()


def publish_color(sender, instance, **kwargs):
    """
    This function is responsible for relaying save events from Django's
    post_save signal, into redis pubsub channels. The managed socketio sessions
    are sub'd to these channels for each model being displayed - and will
    update the client as soon as the model is saved
    """
    channel = 'color/{}'.format(instance.pk)
    data = instance.data()
    redis_client.publish(channel, json.dumps(data))

post_save.connect(publish_color, ColorChoice)


