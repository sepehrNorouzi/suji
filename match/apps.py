from django.apps import AppConfig


class MatchConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'match'

    def ready(self):
        # PyNoInscpect
        from match.tasks import handle_game_started

        return super().ready()
