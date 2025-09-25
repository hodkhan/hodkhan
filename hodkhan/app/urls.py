from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("feed/", views.index, name="feed"),
    path("privacy/", views.privacy, name="privacy"),
    path("account/", views.account, name="account"),
    path("article/<id>", views.article, name="article"),
    path("topic/<topic>", views.topic, name="topic"),
    path("dbToDjango/", views.dbToDjango, name="dbToDjango"),
    path('search/', views.search, name='search'),
    path('api/feed/<username>/<count>', views.stream_articles, name='feed'),
    path('api/get/article/content/<id>', views.getArticleContentView, name='article_content'),
    path('api/search-suggestions', views.search_suggestions, name='search_suggestions'),
    path("api/interaction/", views.interaction, name='interaction'),
    path('api/follow_feed/', views.follow_feed, name='follow_feed'),
]
