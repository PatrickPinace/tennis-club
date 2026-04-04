"""
URL configuration for tracker project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView, RedirectView
from django.contrib.staticfiles.storage import staticfiles_storage
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls import handler404, handler500
from django.http import HttpResponse

handler404 = 'apps.home.views.custom_404'
handler500 = 'apps.home.views.custom_500'

from django.contrib.sitemaps.views import sitemap
from .sitemaps import StaticViewSitemap, NewsSitemap

sitemaps = {
    'static': StaticViewSitemap,
    'news': NewsSitemap,
}

def health_check(request):
    return HttpResponse("OK", content_type="text/plain")

urlpatterns = [
    path('health/', health_check, name='health_check'),
    path('', include('apps.home.urls')),
    path('friends/', include('apps.friends.urls')),
    path('courts/', include('apps.courts.urls')),
    path('users/', include('apps.users.urls')),
    path('accounts/3rdparty/login/cancelled/', RedirectView.as_view(url='/users/login/', permanent=False), name='socialaccount_login_cancelled'),
    path('accounts/', include('allauth.urls')),
    path('matches/', include('apps.matches.urls')),
    # path('rankings/', include('apps.rankings.urls')),
    path('tournaments/', include('apps.tournaments.urls')),
    path('activities/', include(('apps.activities.urls', 'activities'), namespace='activities')),
    path('news/', include('apps.news.urls', namespace='news')),
    path('manage/', admin.site.urls),
    path('feedback/', include('apps.feedback.urls', namespace='feedback')),
    path('manifest.json', TemplateView.as_view(template_name='manifest.json', content_type='application/json')),
    path('notifications/', include('notifications.urls')),
    # path('api/', include('apps.api.urls')),
    path('chat/', include('chats.urls', namespace='chats')),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('robots.txt', TemplateView.as_view(template_name='robots.txt', content_type='text/plain')),
    path('favicon.ico', RedirectView.as_view(url=staticfiles_storage.url('img/favicon.ico'))),
]

# Dodaj to do obsługi plików mediów w trybie deweloperskim
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) + [
        path('__debug__/', include('debug_toolbar.urls')),
    ]
