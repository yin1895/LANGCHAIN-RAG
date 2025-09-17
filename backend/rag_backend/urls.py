from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("backend.rag_api.urls")),
    path("", include("backend.rag_api.urls")),
]
