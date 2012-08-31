from django.views.generic.base import TemplateView
from django.conf.urls import patterns, include, url
from django.conf.urls.static import static
from django.conf import settings

from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    url(r'^$',
        TemplateView.as_view(template_name='colorpicks/home.html'), name='home'),
    # The Django Rest Framework APIs
    url(r'^api/', include('colorpicks.api_urls')),
    # This app uses backbone, with ajax sync to api
    url(r'^colors/app$',
        TemplateView.as_view(template_name='colorpicks/colorchoice_app.html'),
        name='app'),

    # this app uses backbone, and backbone.iobind with socket io and websockets
    # instead of ajax
    url(r'^colors/app2$',
        TemplateView.as_view(template_name='colorpicks/colorchoice_app2.html'),
        name='app2'),

    # This is the conventional django version
    url(r'^colors/', include('colorpicks.urls')),

    url(r'^admin/', include(admin.site.urls)),

    url(r'^static/(?P<path>.*)$', 'django.views.static.serve', {
        'document_root': settings.STATIC_ROOT}),
)

