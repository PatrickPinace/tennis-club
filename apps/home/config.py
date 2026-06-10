from django.apps import AppConfig


class MyConfig(AppConfig):
    name = 'apps.home'
    label = 'apps_home'
    verbose_name = 'Statystyki i ruch'

    def ready(self):
        import apps.home.signals

