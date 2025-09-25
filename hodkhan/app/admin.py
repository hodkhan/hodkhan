from .models import Article, Keyword, Feed, Interaction, UserFeed
from django.contrib import admin

admin.site.register(Feed)
admin.site.register(Keyword)
admin.site.register(Article)
admin.site.register(Interaction)
admin.site.register(UserFeed)
