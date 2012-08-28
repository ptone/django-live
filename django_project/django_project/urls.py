from django.views.generic.base import TemplateView
from django.conf.urls import patterns, include, url

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    url(r'^$',
        TemplateView.as_view(template_name='colorpicks/app.html'), name='home'),
    url(r'^api/', include('colorpicks.api_urls')),
    url(r'^colors/app$',
        TemplateView.as_view(template_name='colorpicks/colorchoice_app.html'),
        name='app'),

    url(r'^colors/app2$',
        TemplateView.as_view(template_name='colorpicks/colorchoice_app2.html'),
        name='app2'),

    url(r'^colors/', include('colorpicks.urls')),

    # Examples:
    # url(r'^$', 'django_project.views.home', name='home'),
    # url(r'^django_project/', include('django_project.foo.urls')),

    # Uncomment the admin/doc line below to enable admin documentation:
    # url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    url(r'^admin/', include(admin.site.urls)),
)

from django.contrib.staticfiles.urls import staticfiles_urlpatterns
urlpatterns += staticfiles_urlpatterns()

