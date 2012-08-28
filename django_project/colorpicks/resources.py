from djangorestframework.resources import ModelResource

from .models import ColorChoice


class ColorResource(ModelResource):
    model = ColorChoice
    fields = ('id', 'color_choice', 'name', 'identifier', 'email')


