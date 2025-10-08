from django.urls import path
from .views import GetFeedView, AddKeywordsView

urlpatterns = [
    path('get_feed/', GetFeedView.as_view()),
    path('add_keywords/', AddKeywordsView.as_view(), name='add-keywords'),
]
