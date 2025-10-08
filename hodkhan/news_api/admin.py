from django.contrib import admin
from .models import AgencyKey, SearchKeyWord, KeyWordTable 

admin.site.register(SearchKeyWord)
admin.site.register(KeyWordTable)

@admin.register(AgencyKey)
class AgencyKeyAdmin(admin.ModelAdmin):
    list_display = ['name', 'active', 'created_at', 'key']  # shown in list view
    readonly_fields = ['key', 'created_at']  # shown (but not editable) in form
    fields = ['name', 'active', 'key', 'created_at']  # control field order