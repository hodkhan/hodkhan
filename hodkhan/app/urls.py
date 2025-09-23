from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("news/", views.index, name="news"),
    path("article/<id>", views.article, name="article"),
    path("topic/<topic>", views.topic, name="topic"),
    path("dbToDjango/", views.dbToDjango, name="dbToDjango"),
    path('search/', views.search, name='search'),
    path('api/feed/<username>/<count>', views.stream_articles, name='feed'),
    path('api/get/article/content/<id>', views.getArticleContentView, name='article_content'),
    path('api/search-suggestions', views.search_suggestions, name='search_suggestions'),
]
