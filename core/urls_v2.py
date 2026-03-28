"""
Tennis Club v2 - URL Configuration (Minimal for MVP)
"""
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static
from v2_core.views import health_check, signup, home

urlpatterns = [
    # Health check
    path('health/', health_check, name='health_check'),

    # Admin
    path('admin/', admin.site.urls),

    # Authentication
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('signup/', signup, name='signup'),

    # Home
    path('', home, name='home'),

    # API (for mobile apps)
    # path('api/', include('v2_core.api_urls')),
]

# Media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += [path('__debug__/', include('debug_toolbar.urls'))]
