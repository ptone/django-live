from django.core.urlresolvers import reverse
# from django.views.generic import ListView
from django.views.generic.edit import *
from django.views.generic.detail import *
from django.views.generic.list import *
from django.db.models import ObjectDoesNotExist

from djangorestframework.compat import View  # Use Django 1.3's django.views.generic.View, or fall back to a clone of that if Django < 1.3
from djangorestframework.mixins import ResponseMixin
from djangorestframework.renderers import DEFAULT_RENDERERS
from djangorestframework.response import Response

from colorpicks.models import ColorChoice
from colorpicks.forms import ColorChoiceModelForm

class ColorDataView(ResponseMixin, View):
    renderers = DEFAULT_RENDERERS

    def get(self, request):
        response = Response(200, {'description': 'Some example content',
                                  'url': reverse('data_view')})
        return self.render(response)


class ColorListView(
        ModelFormMixin,
        TemplateResponseMixin,
        BaseListView,
        MultipleObjectMixin,
        SingleObjectMixin,
        ProcessFormView,
        View,
        ):

    template_name = 'colorpicks/colorchoice_list.html'
    model = ColorChoice
    form_class = ColorChoiceModelForm

    def __init__(self, *args, **kwargs):
        super(ColorListView, self).__init__(*args, **kwargs)
        self._mycolor = None

    @property
    def mycolor(self):
        if self._mycolor is None:
            try:
                self._mycolor = ColorChoice.objects.get(
                    identifier=self.request.session.session_key)
            except ObjectDoesNotExist as e:
                self._mycolor = ColorChoice()
        return self._mycolor

    def get_success_url(self):
        return self.request.get_full_path()

    def get_object(self, *args, **kwargs):
        return self.mycolor

    def form_valid(self, form):
        """
        If the form is valid, save the associated model.
        """
        self.object = form.save(commit=False)
        self.object.identifier = self.request.session.session_key
        self.object.save()
        return super(ModelFormMixin, self).form_valid(form)

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if 'sessionid' in request.COOKIES:
            print request.COOKIES['sessionid']
        else:
            print 'no cookie for you'
        return super(ColorListView, self).get(request, *args, **kwargs)

    # def post(self, request, *args, **kwargs):
        # print "posted"
        # return super(ProcessFormView, self).post(request, *args, **kwargs)
    def post(self, request, *args, **kwargs):
        print 'in post'
        self.object = self.get_object()
        # request.POST['color_choice'] = request.POST['color_choice'].lstrip('#')
        # print request.POST['color_choice']
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        if form.is_valid():
            print 'form valid'
            return self.form_valid(form)
        else:
            print 'form invalid'
            return self.form_invalid(form)

    # def get_form_kwargs(self):
        # kwargs = super(ColorListView, self).get_form_kwargs()
        # kwargs

    def get_context_data(self, *args, **kwargs):
        context = super(ColorListView, self).get_context_data(*args, **kwargs)
        context.update({'request': self.request})
        context['mycolor'] = self.mycolor
        context['mycolorid'] = self.mycolor.id or 0
        context['form'] = self.get_form(self.get_form_class())
        return context
