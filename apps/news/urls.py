from django.urls import path
from . import views
from .views import ArticleListView

app_name = 'news'

urlpatterns = [
    path('upload-image/', views.upload_image, name='upload_image'),
    path('', ArticleListView.as_view(), name='article_list'),
    path('create/', views.ArticleCreateView.as_view(), name='article_create'),
    path('<slug:slug>/', views.ArticleDetailView.as_view(), name='article_detail'),
    path('<slug:slug>/edit/', views.ArticleUpdateView.as_view(), name='article_edit'),
    path('<slug:slug>/comment/', views.add_comment, name='add_comment'),
    path('comment/<int:pk>/react/', views.react_to_comment, name='react_to_comment'),
    path('<slug:slug>/like/', views.like_article, name='like_article'),
]
