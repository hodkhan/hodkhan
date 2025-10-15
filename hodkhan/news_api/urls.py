from django.urls import path
from .views import GetFeedView, AddKeywordsView, Search, SearchAndAppendArticles, AddBanwordsView

urlpatterns = [
    path('get_feed/', GetFeedView.as_view()),
    path('add_keyword/', AddKeywordsView.as_view(), name='add-keywords'),
    path('add_banword/', AddBanwordsView.as_view(), name='add-banwords'),
    path('search/', Search.as_view()),
    path('update_articles/', SearchAndAppendArticles.as_view(), name='update_articles'),
]
