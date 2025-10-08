from django.urls import path
from .views import GetFeedView

urlpatterns = [
    path('get_feed/', GetFeedView.as_view()),
]
