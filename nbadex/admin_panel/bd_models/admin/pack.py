from __future__ import annotations

from django.contrib import admin

from ..models import Pack


@admin.register(Pack)
class PackAdmin(admin.ModelAdmin):
    list_display = ("name", "cost", "enabled")
    list_filter = ("enabled",)
    search_fields = ("name",)
    search_help_text = "Search for pack name"
    
    fieldsets = (
        (
            "Pack Information",
            {
                "fields": ("name", "cost", "description", "enabled"),
            },
        ),
    )
