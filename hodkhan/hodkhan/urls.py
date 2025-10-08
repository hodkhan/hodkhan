from django.views.generic.base import TemplateView
from django.contrib import admin
from django.urls import path, include
from . import views, settings
from django.conf import settings


urlpatterns = [
    path("", include("app.urls")),
    path("admin/", admin.site.urls),
    path('account/', include('account.urls')),
    path('news_api/', include('news_api.urls')),

    path(
        "robots.txt",
        TemplateView.as_view(template_name="robots.txt", content_type="text/plain"),
    ),
]
