import json

from django.db.models.signals import post_save

from redis import Redis

from colorpicks.models import ColorChoice

redis_client = Redis()


def publish_color(sender, instance, **kwargs):
    channel = 'color/{}'.format(instance.pk)
    data = instance.data()
    redis_client.publish(channel, json.dumps(data))

post_save.connect(publish_color, ColorChoice)


