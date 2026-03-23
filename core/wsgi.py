"""
WSGI config for tracker project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/wsgi/
"""

import os
from pathlib import Path
from dotenv import load_dotenv

from django.core.wsgi import get_wsgi_application

# Ścieżka do głównego katalogu projektu
BASE_DIR = Path(__file__).resolve().parent.parent

# Wczytaj zmienne środowiskowe z pliku .env.prod dla środowiska produkcyjnego.
# Zakładamy, że na serwerze produkcyjnym istnieje plik .env.prod w głównym katalogu projektu.
load_dotenv(dotenv_path=os.path.join(BASE_DIR, '.env'))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

application = get_wsgi_application()
