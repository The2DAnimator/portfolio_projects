from django.contrib import admin
from .models import UserStorageSettings


@admin.register(UserStorageSettings)
class UserStorageSettingsAdmin(admin.ModelAdmin):
    list_display = ("user", "quota_mb")
    search_fields = ("user__username", "user__email")
    autocomplete_fields = ("user",)


