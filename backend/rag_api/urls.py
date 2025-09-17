from django.urls import path

from . import views

urlpatterns = [
    # root and static-like
    path("", views.root_page, name="root"),
    # core api
    path("health", views.health, name="health"),
    path("ingest", views.ingest, name="ingest"),
    path("ask", views.AskView.as_view(), name="ask"),
    path("ask/stream", views.AskStreamView.as_view(), name="ask_stream"),
    path("upload", views.upload_file, name="upload"),
    path("uploads", views.list_docs, name="list_docs"),
    # auth
    path("register", views.register, name="register"),
    path("login", views.login, name="login"),
    path("admin/users", views.admin_list_users, name="admin_list_users"),
    path("admin/users/<str:username>/promote", views.admin_promote, name="admin_promote"),
    path("admin/users/<str:username>/demote", views.admin_demote, name="admin_demote"),
    path("admin/users/<str:username>/freeze", views.admin_freeze, name="admin_freeze"),
    path("admin/users/<str:username>/unfreeze", views.admin_unfreeze, name="admin_unfreeze"),
    path("admin/tokens/revoke", views.admin_revoke_token, name="admin_revoke"),
    path("admin/tokens", views.admin_list_revoked, name="admin_tokens"),
]
