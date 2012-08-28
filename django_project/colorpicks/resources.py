from djangorestframework.resources import ModelResource

from .models import ColorChoice

class ColorResource(ModelResource):
    """
    A very simple resource class. 'id' is included explicitly here - as it is
    used by backbone as the primary id on the client side.
    """
    model = ColorChoice
    fields = ('id', 'color_choice', 'name', 'identifier', 'email')


