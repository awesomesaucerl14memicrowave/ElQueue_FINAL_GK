import os
import sys

# Add your project directory to the sys.path
path = '/home/YOUR_PYTHONANYWHERE_USERNAME/ElQueue_FINAL_GK'
if path not in sys.path:
    sys.path.append(path)

# Set environment variable to tell Django where your settings.py is
os.environ['DJANGO_SETTINGS_MODULE'] = 'lab_queue.settings'

# Set the application
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application() 