from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("rag_api.urls")),
    path("", include("rag_api.urls")),
]
