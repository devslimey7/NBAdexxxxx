from __future__ import annotations

from django.contrib import admin

from ..models import Pack, CoinReward, CoinTransaction


@admin.register(Pack)
class PackAdmin(admin.ModelAdmin):
    list_display = ("name", "cost", "enabled")
    list_filter = ("enabled",)
    search_fields = ("name",)
    fieldsets = (
        ("Pack Information", {
            "fields": ("name", "cost", "description", "enabled")
        }),
    )


@admin.register(CoinReward)
class CoinRewardAdmin(admin.ModelAdmin):
    list_display = ("name", "base_coins")
    search_fields = ("name",)
    fieldsets = (
        ("Reward Information", {
            "fields": ("name", "base_coins", "description")
        }),
    )


@admin.register(CoinTransaction)
class CoinTransactionAdmin(admin.ModelAdmin):
    list_display = ("player", "amount", "reason", "timestamp")
    list_filter = ("timestamp", "reason")
    search_fields = ("player__discord_id", "reason")
    readonly_fields = ("player", "amount", "reason", "timestamp")
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
