SECRET_KEY = "test-secret"
DEBUG = True
ALLOWED_HOSTS = ["*"]

# Minimal installed apps to satisfy DRF imports in smoke scripts
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
]

# Minimal REST_FRAMEWORK settings used by DRF internals
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}
