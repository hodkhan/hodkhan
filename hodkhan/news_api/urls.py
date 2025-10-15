from django.urls import path
from .views import GetFeedView, AddKeywordsView, Search, SearchAndAppendArticles

urlpatterns = [
    path('get_feed/', GetFeedView.as_view()),
    path('add_keywords/', AddKeywordsView.as_view(), name='add-keywords'),
    path('search/', Search.as_view()),
    path('update_articles/', SearchAndAppendArticles.as_view(), name='update_articles'),
]
