from django.views.generic.edit import *
from django.views.generic.detail import *
from django.views.generic.list import *
from django.db.models import ObjectDoesNotExist

from colorpicks.models import ColorChoice
from colorpicks.forms import ColorChoiceModelForm

class ColorListView(
        ModelFormMixin,
        TemplateResponseMixin,
        BaseListView,
        MultipleObjectMixin,
        SingleObjectMixin,
        ProcessFormView,
        View,
        ):

    """
    This is crazy hack view that provides a form at the top of a listview

    This provides the 'standard' request/response way of editing your color
    while also showing you other people's color
    """

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

    def post(self, request, *args, **kwargs):
        print 'in post'
        self.object = self.get_object()
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        if form.is_valid():
            print 'form valid'
            return self.form_valid(form)
        else:
            print 'form invalid'
            return self.form_invalid(form)

    def get_context_data(self, *args, **kwargs):
        context = super(ColorListView, self).get_context_data(*args, **kwargs)
        context.update({'request': self.request})
        context['mycolor'] = self.mycolor
        context['mycolorid'] = self.mycolor.id or 0
        # this has to be added here, as we can't inherit from
        # both listview and processformview
        context['form'] = self.get_form(self.get_form_class())
        return context
