import colorsys

from django.db import models

def split_count(s, count):
     return [''.join(x) for x in zip(*[list(s[z::count]) for z in range(count)])]

def hex_to_rgb(value):
    value = value.lstrip('#')
    lv = len(value)
    return tuple(int(value[i:i+lv/3], 16) for i in range(0, lv, lv/3))

def rgb_to_hex(rgb):
    return '#%02x%02x%02x' % rgb

class ColorChoice(models.Model):
    color_choice = models.CharField(max_length=7, default='#c9d4ca')
    name = models.CharField(max_length=100, blank=True)
    identifier = models.CharField(max_length=100)
    email = models.CharField(max_length=100, default='', blank=True)
    hue = models.IntegerField(default=0, blank=True)
    saturation = models.IntegerField(default=0, blank=True)
    brightness = models.IntegerField(default=0, blank=True)

    def __unicode__(self):
        return '{}: {}'.format(self.name, self.color_choice)

    @models.permalink
    def get_absolute_url(self):
        return ('colorchoice_detail', (), {'pk':self.id})

    def data(self):
        """
        A brain-dead shortcut to get serialized repr of model
        """
        return {'color_choice':self.color_choice, 'name':self.name}

    def to_hsv(self):
        # r, g, b = [int(s, 16)/255.0 for s in split_count(self.color_choice.lstrip('#'), 2)]
        r, g, b = hex_to_rgb(self.color_choice)
        return colorsys.rgb_to_hsv(r/255.0, g/255.0, b/255.0)

    def save(self,  *args, **kwargs):
        hue, saturation, brightness = self.to_hsv()
        self.hue = hue * 365
        self.saturation = saturation * 100
        self.brightness = brightness * 100
        super(ColorChoice, self).save(*args, **kwargs)


# trigger module level execution of signal connection
from colorpicks import publisher
