from django.conf.urls.defaults import patterns, url

from djangorestframework.views import ListOrCreateModelView, InstanceModelView
from .resources import ColorResource

urlpatterns = patterns('',
    url(r'^colors/$',
        ListOrCreateModelView.as_view(resource=ColorResource),
        name='todo-resources'),
    url(r'^colors/(?P<pk>[0-9]+)$',
        InstanceModelView.as_view(resource=ColorResource)),
)

