"""
Tennis Club v2 - URL Configuration (Minimal for MVP)
"""
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static
from v2_core.views import health_check

urlpatterns = [
    # Health check
    path('health/', health_check, name='health_check'),

    # Admin
    path('admin/', admin.site.urls),

    # API (for mobile apps)
    # path('api/', include('v2_core.api_urls')),

    # Home redirect
    path('', RedirectView.as_view(url='/admin/', permanent=False)),
]

# Media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += [path('__debug__/', include('debug_toolbar.urls'))]
