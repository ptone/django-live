import time

from django.conf import settings
from django.utils.http import cookie_date

from colorpicks.models import ColorChoice



class SetColorIdMiddleware(object):
    def process_response(self, request, response):
        # print request.session.keys()
        # print '\n\n\n\n -=-=-=- =- =- -= =- =- -= = - - =- =- '
        if request.session.session_key:
            # print request.session.session_key
            colorid = 'unset'
            try:
                obj = ColorChoice.objects.get(
                        identifier=request.session.session_key)
                colorid = obj.id
            except ColorChoice.DoesNotExist:
                print 'no color matching session'
                obj = ColorChoice.objects.create(identifier=request.session.session_key)
                colorid = obj.id
                pass
            # request.session['colorid'] = colorid
            # request.session.save()
            # print request.session
            max_age = request.session.get_expiry_age()
            expires_time = time.time() + max_age
            expires = cookie_date(expires_time)
            print 'setting colorid cookie'
            response.set_cookie('colorid',
                    colorid, max_age=max_age,
                    expires=expires, domain=settings.SESSION_COOKIE_DOMAIN,
                    path=settings.SESSION_COOKIE_PATH,
                    secure=False,
                    httponly=False)
        return response
