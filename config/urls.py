"""Routes principales du projet Dreamcatcher."""

# from django.conf import settings
# from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.decorators import login_not_required
from django.urls import include, path
from django.views.generic import TemplateView

from . import views

urlpatterns = [
    # pages publiques
    path(
        "",
        login_not_required(TemplateView.as_view(template_name="accueil.html")),
        name="accueil",
    ),
    path(
        "confidentialite/",
        login_not_required(TemplateView.as_view(template_name="confidentialite.html")),
        name="confidentialite",
    ),
    # applications
    path("comptes/", include("accounts.urls")),
    path("reves/", include("dreams.urls")),
    # pages admin
    path("admin/", admin.site.urls),
    path("health", views.health, name="health"),
]

# dev
# if settings.DEBUG:
#     urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
