import colorsys

from django.core.urlresolvers import reverse
from django.db import models

def split_count(s, count):
     return [''.join(x) for x in zip(*[list(s[z::count]) for z in range(count)])]

# Create your models here.
class ColorChoice(models.Model):
    color_choice = models.CharField(max_length=7, default='#000000')
    name = models.CharField(max_length=100, blank=True)
    identifier = models.CharField(max_length=100)
    email = models.CharField(max_length=100, default='', blank=True)
    hue = models.IntegerField(default=0)
    saturation = models.IntegerField(default=0)
    brightness = models.IntegerField(default=0)

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
        r, g, b = [int(s, 16) for s in split_count(self.color_choice.lstrip('#'), 2)]
        return colorsys.rgb_to_hsv(r, g, b)

    def save(self,  *args, **kwargs):
        self.hue, self.saturation, self.brightness = self.to_hsv()
        super(ColorChoice, self).save(*args, **kwargs)



# dec to hex
# print "%x" % 255
# return "%02X" % d
# dec to hex:
# int(s, 16)



# trigger module level execution of signal connection
from colorpicks import publisher
