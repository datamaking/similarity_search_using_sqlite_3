"""
WSGI config for similarity_search project.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'similarity_search.settings')

application = get_wsgi_application()