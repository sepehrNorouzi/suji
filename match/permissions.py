import os
import sys

from django.utils.translation import gettext_lazy as _
from rest_framework.permissions import BasePermission


class IsGameServer(BasePermission):
    message = _("Server key is required.")

    def has_permission(self, request, view):
        if 'test' in sys.argv:
            return True

        headers = request.headers
        server_key = headers.get('X-Suji-Server-Key')
        if not server_key:
            return False
        return server_key == os.environ.get('SUJI_SERVER_KEY')