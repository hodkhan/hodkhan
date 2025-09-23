from django.apps import AppConfig as Config


class AppConfig(Config):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app'
    label = 'app'
