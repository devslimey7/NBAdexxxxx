from __future__ import annotations

from django.contrib import admin

from ..models import CoinTransaction


@admin.register(CoinTransaction)
class CoinTransactionAdmin(admin.ModelAdmin):
    list_display = ("player", "amount", "reason", "timestamp")
    list_filter = ("timestamp", "reason")
    search_fields = ("player__discord_id", "reason")
    search_help_text = "Search by Discord ID or reason"
    readonly_fields = ("timestamp", "player", "amount", "reason")
    
    fieldsets = (
        (
            "Transaction Information",
            {
                "fields": ("player", "amount", "reason", "timestamp"),
            },
        ),
    )
    
    def has_add_permission(self, request):
        """Prevent manual transaction creation"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Prevent transaction deletion"""
        return False
