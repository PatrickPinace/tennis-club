from django.apps import AppConfig


class MyConfig(AppConfig):
    name = 'apps.home'
    label = 'apps_home'

    def ready(self):
        import apps.home.signals

