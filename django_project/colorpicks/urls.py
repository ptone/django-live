from django.conf.urls.defaults import patterns, url
from django.views.generic import ListView, DetailView

from colorpicks.models import ColorChoice
from colorpicks.views import ColorListView

urlpatterns = patterns('',
        url(r'^$', ColorListView.as_view(model=ColorChoice)),
        url(r'(?P<pk>[0-9]+)$', DetailView.as_view(
            model=ColorChoice), name='colorchoice_detail'),
        )
