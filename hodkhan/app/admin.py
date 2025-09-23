from .models import Article, Keyword, Feed, Interaction
from django.contrib import admin

admin.site.register(Feed)
admin.site.register(Keyword)
admin.site.register(Article)
admin.site.register(Interaction)
