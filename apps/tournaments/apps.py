from django.apps import AppConfig


class TournamentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.tournaments'
    verbose_name = 'Tournaments'

    def ready(self):
        import apps.tournaments.signals  # noqa: F401
