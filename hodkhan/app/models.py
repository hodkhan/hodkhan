from django.conf import settings
from django.db import models
from uuid import uuid4


class Keyword(models.Model):
    id = models.CharField(max_length=15, primary_key=True, default=uuid4, editable=False)
    name = models.CharField(max_length=100)
    vector = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.name


class Feed(models.Model):
    id = models.CharField(max_length=15, primary_key=True, default=uuid4, editable=False)
    name = models.CharField(max_length=300)
    address = models.CharField(max_length=500)
    favicon = models.CharField(max_length=500)
    type = models.CharField(max_length=500)
    vector = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.name


class Article(models.Model):
    id = models.CharField(max_length=15, primary_key=True, default=uuid4, editable=False)
    title = models.CharField(max_length=500)
    abstract = models.TextField(null=True)
    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)
    keyword = models.ManyToManyField(Keyword, default=dict)
    link = models.CharField(max_length=1000, null=True)
    published = models.IntegerField(null=True)
    cover = models.CharField(max_length=1000, null=True)
    vector = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.title


class UserFeed(models.Model):
    id = models.CharField(max_length=15, primary_key=True, default=uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'feed')

    def __str__(self):
        return f"{self.user.username} follows {self.feed.name}"


class Interaction(models.Model):
    INTERACTION_TYPES = [
        ("view", "View"),
        ("read", "Read"),
        ("like", "Like"),
        ("comment", "Comment"),
        ("archive", "Archive"),
        ("follow", "Follow"),
    ]

    id = models.CharField(max_length=15, primary_key=True, default=uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='interaction_article', null=True,
                                blank=True)
    feed = models.ForeignKey(Feed, on_delete=models.CASCADE, related_name="interactions_feed", null=True, blank=True)
    keyword = models.ForeignKey(Keyword, on_delete=models.CASCADE, related_name='interaction_keyword', null=True,
                                blank=True)
    type = models.CharField(max_length=20, choices=INTERACTION_TYPES, default="view")
    value = models.TextField(null=True, blank=True)
    # star = models.IntegerField(null=True, blank=True, default=0)
    is_trained = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["user", "type"]), models.Index(fields=["article"])]

    def __str__(self):
        user = self.user.username if self.user else "anonymous"
        return f"{user}: {self.type} {self.article_id if self.article_id else ''}"

