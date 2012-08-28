from django.forms import ModelForm

from colorpicks.models import ColorChoice

class ColorChoiceModelForm(ModelForm):
    class Meta:
        model = ColorChoice
        fields = ['color_choice', 'name', 'email']
