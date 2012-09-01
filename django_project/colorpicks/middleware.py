import time

from django.conf import settings
from django.shortcuts import redirect
from django.utils.http import cookie_date

from colorpicks.models import ColorChoice



class SetColorIdMiddleware(object):
    def process_response(self, request, response):
        print request.path
        if request.session.session_key:
            colorid = 'unset'
            try:
                obj = ColorChoice.objects.get(
                        identifier=request.session.session_key)
                colorid = obj.id
            except ColorChoice.DoesNotExist:
                # no color matching session
                # create a new color with the current session as identifier
                obj = ColorChoice.objects.create(identifier=request.session.session_key)
                colorid = obj.id
            response.set_cookie('colorid',
                    colorid,
                    path=settings.SESSION_COOKIE_PATH,
                    secure=False,
                    httponly=False)
        else:
            request.session.flush()
            return redirect(request.path)
            # if request.path == '/colors/app':
                # This is sort of a hack - we only want to do a redirect
                # for the conventional app in this demo - the other apps
                # will use more dynamic methods
                # return redirect('/colors/app')
        return response
