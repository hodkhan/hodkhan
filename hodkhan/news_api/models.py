from django.conf import settings
from django.db import models
from uuid import uuid4
import secrets
class SearchKeyWord(models.Model):
    text = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.text}"


# Agency authentication
class AgencyKey(models.Model):
    name = models.CharField(max_length=255, unique=True)
    key = models.CharField(max_length=64, unique=True, editable=False)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = secrets.token_hex(32)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({'Active' if self.active else 'Inactive'})"


class KeyWordTable(models.Model):
    id = models.CharField(max_length=15, primary_key=True, default=uuid4, editable=False)
    agency = models.OneToOneField(AgencyKey, on_delete=models.CASCADE, related_name='keyword_table')
    words = models.ManyToManyField(SearchKeyWord)

    
    def __str__(self):
        return f"Keywords for {self.agency.name}"
