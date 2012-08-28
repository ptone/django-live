from django.http import HttpRequest

from djangorestframework.views import ListOrCreateModelView
from djangorestframework.response import Response
from djangorestframework import status
from djangorestframework.renderers import JSONRenderer

from colorpicks.resources import ColorResource

def get_colors_json():
    """
    This is a surprising kludge to get the json from a
    DRF resource, outside of a true request/response context
    """
    resource_view = ListOrCreateModelView(resource=ColorResource)
    dummy_request = HttpRequest()
    response_obj = resource_view.get(dummy_request)
    response = Response(status.HTTP_200_OK, response_obj)
    jsonr =  JSONRenderer(resource_view)
    filtered_content = resource_view.filter_response(response_obj)
    # json_string = jsonr.render(filtered_content)
    return filtered_content

