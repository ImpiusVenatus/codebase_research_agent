"""WSGI config for coderesearch project."""
import os

from django.core.wsgi import get_wsgi_application


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "coderesearch.settings")

application = get_wsgi_application()
